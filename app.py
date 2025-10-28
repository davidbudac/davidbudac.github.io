from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import snscrape.modules.twitter as sntwitter
from flask import Flask, jsonify, render_template
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

app = Flask(__name__)
logger = logging.getLogger(__name__)

MAX_TWEETS = 500
REFRESH_WINDOW_MINUTES = 30

# In-memory cache to avoid repeated scrapes when the data is still fresh.
_data_cache: Dict[str, Any] = {"data": None, "timestamp": None}


def _clean_text(text: str) -> str:
    """Remove URLs, mentions, hashtags (symbol only) and collapse whitespace."""
    text_no_urls = re.sub(r"https?://\S+", "", text)
    text_no_handles = re.sub(r"@[A-Za-z0-9_]+", "", text_no_urls)
    text_no_hash = text_no_handles.replace("#", "")
    return re.sub(r"\s+", " ", text_no_hash).strip()


def fetch_tweets(limit: int = MAX_TWEETS) -> pd.DataFrame:
    """Fetch tweets from Elon Musk for the last six months using snscrape."""
    six_months_ago = datetime.now(timezone.utc) - timedelta(days=182)
    query = f"from:elonmusk since:{six_months_ago.date()}"
    tweets: List[Dict[str, Any]] = []

    scraper = sntwitter.TwitterSearchScraper(query)
    for i, tweet in enumerate(scraper.get_items()):
        if limit and i >= limit:
            break
        if tweet.date < six_months_ago:
            break
        tweets.append(
            {
                "id": tweet.id,
                "date": tweet.date,
                "content": tweet.rawContent,
                "like_count": tweet.likeCount,
                "reply_count": tweet.replyCount,
                "retweet_count": tweet.retweetCount,
                "quote_count": tweet.quoteCount,
                "url": tweet.url,
            }
        )

    if not tweets:
        raise RuntimeError("No tweets were fetched. The scraper may be rate limited.")

    df = pd.DataFrame(tweets)
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def build_topics(texts: List[str], n_topics: int = 5, n_words: int = 8) -> List[Dict[str, Any]]:
    cleaned = [_clean_text(t) for t in texts if t.strip()]
    if len(cleaned) < 5:
        return []

    vectorizer = CountVectorizer(
        stop_words="english",
        min_df=2,
        max_df=0.9,
    )
    doc_term = vectorizer.fit_transform(cleaned)
    if doc_term.shape[1] == 0:
        return []

    n_topics = min(n_topics, doc_term.shape[0])
    lda = LatentDirichletAllocation(
        n_components=n_topics,
        learning_method="online",
        random_state=42,
        max_iter=10,
    )
    lda.fit(doc_term)

    topics: List[Dict[str, Any]] = []
    feature_names = vectorizer.get_feature_names_out()
    for idx, topic in enumerate(lda.components_):
        top_indices = topic.argsort()[::-1][:n_words]
        top_words = [feature_names[i] for i in top_indices]
        topics.append({"topic": idx + 1, "keywords": top_words})

    return topics


def summarize_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    df = df.copy()
    df["length"] = df["content"].str.len()
    df["clean_content"] = df["content"].apply(_clean_text)
    df["created_at"] = pd.to_datetime(df["date"], utc=True)
    df["hour"] = df["created_at"].dt.hour
    df["date_only"] = df["created_at"].dt.date

    bins = [0, 6, 12, 18, 24]
    labels = ["Late Night", "Morning", "Afternoon", "Evening"]
    df["time_of_day"] = pd.cut(df["hour"], bins=bins, labels=labels, right=False, include_lowest=True)

    summary = {
        "tweet_count": int(df.shape[0]),
        "avg_length": float(df["length"].mean()),
        "median_length": float(df["length"].median()),
        "max_length": int(df["length"].max()),
        "min_length": int(df["length"].min()),
        "avg_likes": float(df["like_count"].mean()),
        "avg_retweets": float(df["retweet_count"].mean()),
    }

    scatter = {
        "timestamps": df["created_at"].dt.tz_convert("UTC").astype(str).tolist(),
        "lengths": df["length"].tolist(),
        "hover_text": [
            f"{row.created_at:%Y-%m-%d %H:%M} UTC | {row.length} chars" for row in df.itertuples()
        ],
    }

    daily = (
        df.groupby("date_only")
        .agg(
            tweet_count=("id", "count"),
            avg_length=("length", "mean"),
            total_likes=("like_count", "sum"),
        )
        .reset_index()
    )
    daily["date_only"] = daily["date_only"].astype(str)

    hourly = (
        df.groupby("hour")
        .agg(tweet_count=("id", "count"), avg_length=("length", "mean"))
        .reset_index()
        .sort_values("hour")
    )

    hourly["hour"] = hourly["hour"].astype(int)

    time_of_day = (
        df.groupby("time_of_day")
        .agg(tweet_count=("id", "count"), avg_length=("length", "mean"))
        .reset_index()
    )

    time_of_day["time_of_day"] = time_of_day["time_of_day"].astype(str)

    hist_counts, hist_edges = np.histogram(df["length"], bins=15)
    hist_centers = ((hist_edges[:-1] + hist_edges[1:]) / 2).tolist()

    topics = build_topics(df["clean_content"].tolist())

    top_examples = (
        df.sort_values("like_count", ascending=False)
        .head(5)[["created_at", "content", "like_count", "retweet_count", "reply_count", "url"]]
    )
    top_examples["created_at"] = top_examples["created_at"].dt.strftime("%Y-%m-%d %H:%M UTC")

    dataset = {
        "summary": summary,
        "scatter": scatter,
        "daily": daily.to_dict(orient="list"),
        "hourly": hourly.to_dict(orient="list"),
        "time_of_day": time_of_day.to_dict(orient="list"),
        "length_hist": {
            "counts": hist_counts.tolist(),
            "bins": hist_centers,
        },
        "topics": topics,
        "top_examples": top_examples.to_dict(orient="records"),
    }
    return dataset


def load_data(force_refresh: bool = False) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    if not force_refresh and _data_cache["data"] is not None:
        ts = _data_cache["timestamp"]
        if ts and now - ts < timedelta(minutes=REFRESH_WINDOW_MINUTES):
            return _data_cache["data"]

    try:
        df = fetch_tweets()
        dataset = summarize_dataframe(df)
    except Exception as exc:  # pragma: no cover - network dependent
        logger.exception("Failed to fetch tweets: %s", exc)
        if _data_cache["data"] is not None and not force_refresh:
            return _data_cache["data"]
        raise RuntimeError(
            "Unable to retrieve tweets at the moment. Try again later or use cached data if available."
        ) from exc

    _data_cache["data"] = dataset
    _data_cache["timestamp"] = now
    return dataset


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/data")
def get_data():
    try:
        dataset = load_data()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    timestamp = _data_cache["timestamp"]
    iso_ts = timestamp.isoformat() if timestamp else None
    return jsonify({"data": dataset, "last_updated": iso_ts})


@app.route("/refresh", methods=["POST"])
def refresh_data():
    try:
        dataset = load_data(force_refresh=True)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    timestamp = _data_cache["timestamp"]
    iso_ts = timestamp.isoformat() if timestamp else None
    return jsonify({"status": "ok", "data": dataset, "last_updated": iso_ts})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
