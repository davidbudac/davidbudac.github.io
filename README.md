# Elon Musk Tweet Insights

A lightweight Flask application that scrapes Elon Musk's public tweets from the last six months using [snscrape](https://github.com/JustAnotherArchivist/snscrape) and surfaces interactive analytics powered by Plotly.

## Features

- Pulls tweet metadata (timestamps, engagement counts, text) without requiring the Twitter API.
- Generates visualisations for tweet length over time, hourly activity, time-of-day patterns, and distribution of tweet lengths.
- Calculates daily rollups (tweet count, average length, total likes) and highlights top-performing tweets.
- Performs simple topic modelling on recent tweets to expose dominant discussion themes.
- Provides a **Refresh data** button to trigger a fresh scrape and recompute all analyses on demand.

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The application will start on `http://localhost:5000/`. Initial data is fetched automatically when the page loads.

## Notes

- Scraping is cached for 30 minutes to avoid unnecessary repeated requests; use the refresh button or call `POST /refresh` to force a re-fetch.
- Topic modelling uses scikit-learn's Latent Dirichlet Allocation and may need a slightly larger sample of tweets to produce meaningful topics.
- `snscrape` relies on public Twitter pages. If Twitter introduces blocking or requires authentication, scraping may fail.
