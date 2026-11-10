# Daily Topic Aggregator

A Streamlit dashboard for searching a daily topic across public news feeds.
News searches work without signing up or configuring source API keys. Optional
OpenAI summaries require an API key. Preview mode is clearly marked as fictional.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run topic_dashboard.py
```

Open the local URL printed by Streamlit (normally `http://localhost:8501`).
The existing crypto app remains available separately with
`python -m streamlit run dashboard.py`.

## Public news sources

The dashboard searches Google News RSS and matches recent stories from BBC
News, ABC News Australia, and NPR RSS feeds. These sources do not need API
credentials. Publisher RSS results are matched against the topic in the latest
feed entries, so a publisher may have no matches for a particular topic. The
app links to original articles and does not scrape article pages.

Source access and availability can change; temporary outages or rate limits
are reported in the dashboard. The source endpoints were checked for public
HTTP access during implementation. GDELT was excluded after its public endpoint
began rate-limiting repeated searches.

## Optional AI summaries

To enable summaries, set `OPENAI_API_KEY` in the environment or in
`.streamlit/secrets.toml`. A template is provided at
`.streamlit/secrets.toml.example`. The optional AI step sends a bounded selection
of public result text to OpenAI and may use your API quota. Without a key, the
news feed still works.

After fetching live results, **Generate AI summary** analyzes the current feed.
Use **Refresh AI summary** to run it again without repeating source searches.

Search results are cached locally in `topic_aggregator.db` by normalized topic
and local calendar date. Use the refresh option in the app to bypass that
cache. Cached results are refreshed when the selected sources or source set
changes.

Use **Search this feed** to filter the displayed results by a case-insensitive
phrase in titles, text, sources, or categories. Clearing the search restores the
full feed; filtering does not repeat provider requests or change the saved
results and summary.

Reviews and comments are not included. Common platforms restrict topic-wide
search to authenticated, approved, or otherwise limited APIs. The dashboard
does not scrape those platforms or claim that inaccessible sources are live.

## Deploy

The app can be deployed to Streamlit Community Cloud or another Python host.
Configure API keys in the host's secret manager, install `requirements.txt`,
and run `streamlit run topic_dashboard.py`. Do not expose provider keys to
browser-side code.
