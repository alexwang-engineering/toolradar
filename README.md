# ToolRadar

> 🚧 **Work in progress** — under active development, not feature-complete. Feedback and review welcome via the open draft PR.

A local tool/resource discovery app. Scrapes GitHub Trending, GitHub Topics, HackerNews (Show HN/Ask HN), and Dev.to weekly, then ranks and categorizes what it finds.

## How it works

- `scraper.py` — multi-source scraper. Pulls GitHub Trending (by language/timeframe), GitHub Topics, HN Algolia search, and Dev.to, then deduplicates and ranks results by an engagement score.
- `server.py` — serves the frontend from `web/` and exposes a small JSON API:
  - `GET /api/tools` — returns `data/tools.json` (the current scrape/ranking output)
  - `GET /api/refresh` — triggers a background rescrape
  - `GET /api/status` — scraper status
- `app.py` — wraps the server in a native macOS window via `pywebview`, so it runs as a standalone desktop app instead of "open a browser tab." External tool links open in an in-app child window.
- `web/` — frontend (`index.html`, `styles.css`, `app.js`) that renders the categorized/ranked tool list and a daily "Suggestion for Today."
- `data/tools.json` — the scraped + ranked output; auto-refreshes if older than 7 days.

Results are grouped into categories (Dev Tools & Libraries, AI & Productivity, Learning Resources, Design & Media, DevOps & Infrastructure, Data & Analytics, Security & Privacy, Mobile & Desktop Apps), ranked by total engagement within each category.

## Run locally

```bash
./run.sh
```

This installs Python dependencies (`requests`, `bs4`, `webview`) if missing, then launches `app.py`. The server listens on port `8742`.

## Build a standalone app

```bash
pyinstaller ToolRadar.spec
```
