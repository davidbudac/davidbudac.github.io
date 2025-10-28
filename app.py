"""Streamlit application for analyzing Elon Musk's tweets from the past six months."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import List, Tuple

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer
from snscrape.modules import twitter


def _six_months_ago(today: dt.date | None = None) -> dt.date:
    """Return the date six months before *today* (approximate 182 days)."""
    today = today or dt.date.today()
    return today - dt.timedelta(days=182)


@dataclass
class TweetRecord:
    """Simplified representation of a tweet for analysis."""

    tweet_id: int
    date: dt.datetime
    content: str
    like_count: int
    retweet_count: int
    reply_count: int

    @property
    def length(self) -> int:
        return len(self.content or "")


def fetch_tweets(max_results: int = 2000) -> pd.DataFrame:
    """Fetch Elon Musk tweets from the last six months using snscrape."""
    since = _six_months_ago()
    query = f"from:elonmusk since:{since.isoformat()}"
    scraper = twitter.TwitterSearchScraper(query)

    records: List[TweetRecord] = []
    for index, tweet in enumerate(scraper.get_items()):
        if index >= max_results:
            break
        if tweet.date.date() < since:
            break
        record = TweetRecord(
            tweet_id=tweet.id,
            date=tweet.date,
            content=tweet.content,
            like_count=tweet.likeCount,
            retweet_count=tweet.retweetCount,
            reply_count=tweet.replyCount,
        )
        records.append(record)

    if not records:
        return pd.DataFrame(columns=[
            "tweet_id",
            "date",
            "content",
            "like_count",
            "retweet_count",
            "reply_count",
            "length",
        ])

    df = pd.DataFrame([
        {
            "tweet_id": r.tweet_id,
            "date": pd.to_datetime(r.date),
            "content": r.content,
            "like_count": r.like_count,
            "retweet_count": r.retweet_count,
            "reply_count": r.reply_count,
            "length": r.length,
        }
        for r in records
    ])

    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def compute_topics(texts: pd.Series, n_topics: int = 5, top_n_words: int = 10) -> Tuple[List[str], np.ndarray | None]:
    """Generate a lightweight topic summary using TF-IDF and NMF."""
    cleaned = texts.dropna()
    if cleaned.empty:
        return [], None

    n_topics = min(n_topics, max(1, cleaned.shape[0]))

    vectorizer = TfidfVectorizer(stop_words="english", min_df=2)
    try:
        tfidf = vectorizer.fit_transform(cleaned)
    except ValueError:
        # Not enough unique tokens for vectorizer
        return [], None

    try:
        nmf = NMF(n_components=n_topics, random_state=42)
        topic_matrix = nmf.fit_transform(tfidf)
    except ValueError:
        # Fallback to a single topic if decomposition fails
        nmf = NMF(n_components=1, random_state=42)
        topic_matrix = nmf.fit_transform(tfidf)
        n_topics = 1

    feature_names = vectorizer.get_feature_names_out()
    topics: List[str] = []
    for idx, topic in enumerate(nmf.components_):
        top_indices = topic.argsort()[-top_n_words:][::-1]
        words = [feature_names[i] for i in top_indices]
        topics.append(", ".join(words))

    assignments = None
    if topic_matrix.size:
        assignments = np.argmax(topic_matrix, axis=1)

    return topics, assignments


@st.cache_data(ttl=3600)
def load_data(max_results: int = 2000) -> pd.DataFrame:
    return fetch_tweets(max_results=max_results)


def render_overview(df: pd.DataFrame) -> None:
    st.subheader("Dataset overview")
    st.write(
        "Showing tweets published by Elon Musk over the last six months "
        "(limited to the most recent results)."
    )
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Tweets", f"{len(df):,}")
    if not df.empty:
        col_b.metric("Date range", f"{df['date'].min().date()} → {df['date'].max().date()}")
        col_c.metric("Median length", f"{int(df['length'].median())} characters")
    else:
        col_b.metric("Date range", "–")
        col_c.metric("Median length", "–")

    st.dataframe(
        df[["date", "content", "length", "like_count", "retweet_count", "reply_count"]]
        .rename(columns={
            "date": "Timestamp",
            "content": "Tweet",
            "length": "Length",
            "like_count": "Likes",
            "retweet_count": "Retweets",
            "reply_count": "Replies",
        })
        .tail(25),
        use_container_width=True,
    )


def render_time_vs_length(df: pd.DataFrame) -> None:
    st.subheader("Tweet timing vs. length")
    if df.empty:
        st.info("No tweets available to visualise.")
        return

    scatter_chart = (
        alt.Chart(df)
        .mark_circle(size=60, opacity=0.6)
        .encode(
            x=alt.X("date:T", title="Tweet time"),
            y=alt.Y("length:Q", title="Tweet length (characters)"),
            tooltip=["date:T", "length:Q", "like_count:Q", "retweet_count:Q"],
            color=alt.Color("like_count:Q", scale=alt.Scale(scheme="blues"), title="Likes"),
        )
        .interactive()
    )
    st.altair_chart(scatter_chart, use_container_width=True)


def render_time_of_day(df: pd.DataFrame) -> None:
    st.subheader("Time-of-day patterns")
    if df.empty:
        st.info("No data to display.")
        return

    df_hours = df.copy()
    df_hours["hour"] = df_hours["date"].dt.hour

    heatmap = (
        alt.Chart(df_hours)
        .mark_bar()
        .encode(
            x=alt.X("hour:O", title="Hour of day"),
            y=alt.Y("count():Q", title="Number of tweets"),
            tooltip=["hour:O", "count():Q"],
        )
    )
    st.altair_chart(heatmap, use_container_width=True)


def render_daily_stats(df: pd.DataFrame) -> None:
    st.subheader("Daily activity summary")
    if df.empty:
        st.info("No data to display.")
        return

    daily = (
        df.assign(date_only=df["date"].dt.date)
        .groupby("date_only")
        .agg(
            tweets=("tweet_id", "count"),
            avg_length=("length", "mean"),
            likes=("like_count", "sum"),
            retweets=("retweet_count", "sum"),
        )
        .reset_index()
    )

    chart = (
        alt.Chart(daily)
        .mark_line(point=True)
        .encode(
            x=alt.X("date_only:T", title="Date"),
            y=alt.Y("tweets:Q", title="Tweets"),
            tooltip=["date_only:T", "tweets:Q", "avg_length:Q", "likes:Q", "retweets:Q"],
        )
    )
    st.altair_chart(chart, use_container_width=True)

    st.dataframe(daily, use_container_width=True)


def render_topics(df: pd.DataFrame) -> None:
    st.subheader("Topical overview")
    if df.empty:
        st.info("No tweets to analyse.")
        return

    topics, assignments = compute_topics(df["content"], n_topics=5)
    if not topics:
        st.info("Not enough textual variety to compute topics.")
        return

    st.write("Identified themes based on TF-IDF keywords:")
    for idx, topic in enumerate(topics, start=1):
        st.markdown(f"**Topic {idx}:** {topic}")

    if assignments is not None and assignments.size == len(df):
        df_topics = df.copy()
        df_topics["topic"] = assignments
        topic_counts = (
            df_topics.groupby("topic").agg(
                tweets=("tweet_id", "count"),
                avg_length=("length", "mean"),
                likes=("like_count", "mean"),
            )
        )
        st.dataframe(topic_counts, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Elon Musk Twitter Insights", layout="wide")
    st.title("Elon Musk Twitter Insights")
    st.caption("Interactive exploration of recent tweet activity.")

    st.sidebar.header("Controls")
    max_results = st.sidebar.slider("Max tweets to load", min_value=200, max_value=3000, value=1500, step=100)

    if st.sidebar.button("Refresh data", help="Fetch the latest tweets and recompute analysis"):
        load_data.clear()

    with st.spinner("Fetching tweets..."):
        df = load_data(max_results=max_results)

    if df.empty:
        st.warning(
            "No tweets were retrieved. Try increasing the tweet limit or refreshing the data."
        )
        return

    render_overview(df)
    st.markdown("---")
    render_time_vs_length(df)
    st.markdown("---")
    render_time_of_day(df)
    st.markdown("---")
    render_daily_stats(df)
    st.markdown("---")
    render_topics(df)


if __name__ == "__main__":
    main()
