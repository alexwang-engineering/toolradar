# ToolRadar

> 🚧 **Work in progress** — under active development, not feature-complete. Feedback and review welcome via the open draft PR.

A local tool/resource discovery app. Scrapes GitHub Trending, GitHub Topics, HackerNews (Show HN/Ask HN), and Dev.to weekly, then ranks and categorizes what it finds.

## Highlights

- Collects from four source families, then normalises, deduplicates and ranks
  the results by engagement.
- Groups tools into eight practical categories for faster discovery.
- Serves cached results immediately while a refresh runs in the background.
- Packages the local server and frontend into a standalone macOS window with
  `pywebview` and PyInstaller.
- Uses an original, code-generated radar icon; `make_icon.py` reproducibly
  builds every macOS icon size without external artwork or machine-specific
  paths.

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

This installs Python dependencies (`requests`, `bs4`, `webview`) if missing,
then launches `app.py`. The server listens only on `127.0.0.1:8742`, so it is
not exposed to other machines on the network.

## Build a standalone app

```bash
pyinstaller ToolRadar.spec
```

## Verify

```bash
python -m compileall -q app.py scraper.py server.py make_icon.py
python -m json.tool data/tools.json > /dev/null
```

GitHub Actions runs these offline checks on every push and pull request. Live
source scraping is deliberately excluded from CI because upstream sites and
network conditions are not deterministic.
