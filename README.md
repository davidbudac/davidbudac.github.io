# Elon Musk Tweet Insights

This project is an end-to-end analytics dashboard that continuously pulls, analyses, and visualises the last six months of Elon Musk's tweets. It is intended as a lightweight alternative to the official Twitter API, relying solely on publicly accessible data gathered with [snscrape](https://github.com/JustAnotherArchivist/snscrape).

## How it works

### 1. Backend data pipeline (Flask)

1. On startup the Flask app initialises a small cache that stores the most recent scrape for 30 minutes.
2. When the `/data` endpoint is hit (triggered automatically by the front-end on load), the app uses `snscrape.modules.twitter.TwitterUserScraper` to pull the latest six months of Elon Musk tweets, collecting metadata such as timestamp, tweet text, like/reply/retweet counts, and URLs.
3. The raw tweets are converted into a Pandas DataFrame and enriched with derived fields:
   - **Length analytics** – character count, word count, and bucketed length ranges.
   - **Temporal features** – localised time, hour-of-day, day-of-week, and daily aggregates.
   - **Top tweets** – ranking by likes, replies, and retweets to surface standouts.
4. Topic analysis is performed by tokenising the tweet text, building TF-IDF features, and running a lightweight Latent Dirichlet Allocation (LDA) model to produce headline topics with representative terms.
5. The derived analytics and raw tweet metadata are serialised to JSON and returned to the client. If scraping fails, the API responds with an informative error payload that the UI can display.

### 2. Interactive dashboard (Plotly + Vanilla JS)

The `templates/index.html` template renders a Bootstrap-based layout that loads `static/js/main.js`. That script:

1. Calls the `/data` endpoint to populate the dashboard on initial load.
2. Builds Plotly charts for:
   - Tweet length over time.
   - Hourly volume heatmap.
   - Time-of-day distributions.
   - Histogram of tweet lengths.
3. Renders summary tables for daily statistics and top-performing tweets.
4. Lists the extracted LDA topics alongside the tweets that best match each theme.
5. Provides user feedback via Bootstrap alerts when the API returns an error.

### 3. Manual refresh cycle

The UI includes a **Refresh data** button that triggers a `POST /refresh` call. This endpoint invalidates the cached dataset, performs a fresh scrape, recomputes all analytics, and re-renders the dashboard with the updated numbers. A loading spinner indicates progress while the refresh is underway.

## Features at a glance

- **Zero Twitter API usage** – everything is sourced from public pages via snscrape.
- **Comprehensive analytics** – daily rollups, temporal patterns, top tweets, and topic modelling from a single scrape.
- **Cache-aware refresh** – automatic caching prevents unnecessary network calls while a manual refresh lets you force new data when needed.
- **Graceful error handling** – both the Flask API and the client surface actionable messages when scraping is rate-limited or blocked.

## Running the project locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Navigate to `http://localhost:5000/` in your browser. The dashboard fetches data automatically on first load and whenever you press **Refresh data**.

## Troubleshooting tips

- **Scrape cache** – by default the cache TTL is 30 minutes. Use the refresh button or call `POST /refresh` directly to bust the cache sooner.
- **Topic quality** – LDA performs best with a moderate volume of tweets. If Musk has tweeted infrequently, topics may appear noisy or generic.
- **Network limitations** – snscrape relies on unauthenticated access to Twitter. If the service rate-limits requests or requires login, the API will return an error banner in the UI explaining the issue.
- **Python 3.12+ support** – the app ships with a compatibility shim that restores deprecated importlib behaviour so snscrape can be imported successfully on Python 3.12 and newer.
