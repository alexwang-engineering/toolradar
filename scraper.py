#!/usr/bin/env python3
"""
ToolRadar Scraper — quality-first edition.
Sources: GitHub Trending, HackerNews Show HN, GitHub Topics (authenticated).
Quality filters: 200+ stars for topic results, 40+ points for HN.
"""

import json
import re
import shutil
import subprocess
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR  = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "tools.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

# ── Quality thresholds ────────────────────────────────────────────────────────
MIN_GH_TOPIC_STARS = 200   # GitHub Topics results below this are filtered out
MIN_HN_POINTS      = 40    # HN stories below this are ignored
MAX_PER_CAT        = 30    # hard cap on tools shown per category
MIN_CAT_TOOLS      = 10    # categories with fewer tools are hidden

# ── Categories ────────────────────────────────────────────────────────────────
CATEGORIES = {
    "AI & Productivity":       {"icon": "🤖", "color": "#A371F7", "id": "ai"},
    "Dev Tools & Libraries":   {"icon": "🛠",  "color": "#388BFD", "id": "dev"},
    "DevOps & Infrastructure": {"icon": "🚀", "color": "#58A6FF", "id": "devops"},
    "Security & Privacy":      {"icon": "🔐", "color": "#FF7B72", "id": "security"},
    "Data & Analytics":        {"icon": "📊", "color": "#FFA657", "id": "data"},
    "Design & Media":          {"icon": "🎨", "color": "#F78166", "id": "design"},
    "Mobile & Desktop Apps":   {"icon": "📱", "color": "#7EE787", "id": "mobile"},
    "Learning Resources":      {"icon": "📚", "color": "#3FB950", "id": "learn"},
}

# ── Category keyword sets ─────────────────────────────────────────────────────
# Only genuinely specific terms — no generic words that bleed across categories.

_AI = {
    "ai", "gpt", "llm", "machine learning", "neural network", "chatbot", "openai",
    "claude", "gemini", "copilot", "assistant", "generative ai", "language model",
    "diffusion", "rag", "embedding", "vector store", "langchain", "huggingface",
    "transformer", "nlp", "deep learning", "stable diffusion", "prompt engineering",
    "mistral", "ollama", "anthropic", "midjourney", "whisper", "text generation",
    "image generation", "fine-tuning", "finetuning", "ai inference", "groq",
    "local llm", "multimodal", "vision model", "speech recognition", "ai agent",
    "large language", "text-to-image", "text-to-speech",
}
_DEVOPS = {
    "docker", "kubernetes", "k8s", "ci/cd", "cicd", "ansible", "terraform",
    "helm", "prometheus", "grafana", "jenkins", "github actions", "gitlab ci",
    "aws", "gcp", "azure", "cloud", "infrastructure as code", "container",
    "serverless", "devops", "deployment", "orchestration", "nginx", "traefik",
    "caddy", "sre", "observability", "opentelemetry", "argocd", "flux", "gitops",
    "pulumi", "vagrant", "podman", "compose", "swarm", "service mesh", "istio",
    "envoy", "load balancer", "reverse proxy", "homelab", "self-hosted",
}
_SECURITY = {
    "security", "pentest", "penetration testing", "vulnerability", "exploit",
    "malware", "encryption", "cryptography", "authentication", "oauth", "jwt",
    "firewall", "vpn", "privacy", "hacking", "ssh", "tls", "ssl", "certificate",
    "password manager", "2fa", "mfa", "zero trust", "siem", "ids", "ips",
    "ctf", "reverse engineering", "nmap", "osint", "forensics", "threat",
    "phishing", "devsecops", "secret scanning", "waf", "network security",
}
_DATA = {
    "database", "sql", "mysql", "postgres", "postgresql", "sqlite", "mongodb",
    "redis", "elasticsearch", "kafka", "spark", "pandas", "numpy", "analytics",
    "data visualization", "dashboard", "business intelligence", "data warehouse",
    "etl", "data pipeline", "data science", "data engineering", "dbt",
    "snowflake", "bigquery", "clickhouse", "dask", "polars", "apache arrow",
    "parquet", "lakehouse", "delta lake", "time series", "metabase", "superset",
    "airflow", "prefect", "dagster",
}
_DESIGN = {
    "ui", "ux", "design system", "css", "svg", "icon", "figma", "tailwind",
    "animation", "font", "color palette", "theme", "visual design", "graphic",
    "component library", "storybook", "shadcn", "radix", "material ui",
    "chakra", "framer motion", "three.js", "webgl", "shader", "dark mode",
    "pixel art", "generative art", "creative coding",
}
_MOBILE = {
    "android", "ios", "swift", "swiftui", "kotlin", "flutter", "react native",
    "expo", "mobile app", "app store", "play store", "capacitor", "ionic",
    "xamarin", "maui", "tauri", "electron", "nativescript", "pwa",
    "progressive web app", "watchos", "tvos", "jetpack compose",
}
_LEARN = {
    "tutorial", "course", "learn", "guide", "book", "documentation",
    "cheatsheet", "roadmap", "awesome list", "resource", "article",
    "reference", "interview prep", "coding practice", "exercises", "algorithm",
    "data structure", "system design", "reading list", "curriculum",
    "beginner guide", "open textbook",
}

# First match (highest score) wins; order = priority when tied
_PRIORITY = [
    ("Security & Privacy",      _SECURITY),
    ("DevOps & Infrastructure", _DEVOPS),
    ("AI & Productivity",       _AI),
    ("Data & Analytics",        _DATA),
    ("Mobile & Desktop Apps",   _MOBILE),
    ("Design & Media",          _DESIGN),
    ("Learning Resources",      _LEARN),
]


def _categorize(name: str, desc: str, lang: str = "") -> str:
    text = f"{name} {desc} {lang}".lower()
    scores = {cat: sum(1 for k in kws if k in text) for cat, kws in _PRIORITY}
    best = max(scores.values())
    if best == 0:
        return "Dev Tools & Libraries"
    for cat, _ in _PRIORITY:
        if scores[cat] == best:
            return cat
    return "Dev Tools & Libraries"


def _score_label(score: int, source: str) -> str:
    if source in ("GitHub Trending", "GitHub"):
        if score >= 1_000_000: return f"⭐ {score/1_000_000:.1f}M"
        if score >= 1000:      return f"⭐ {score/1000:.1f}k"
        return f"⭐ {score}"
    if source == "HackerNews":
        return f"▲ {score}"
    return f"⭐ {score}"


# ── GitHub Trending ───────────────────────────────────────────────────────────

def fetch_github_trending() -> list:
    tools, seen = [], set()
    print("  → GitHub Trending...")

    periods = ["weekly", "monthly"]
    langs   = [
        "", "python", "javascript", "typescript", "go", "rust",
        "java", "kotlin", "swift", "c++", "shell", "c#",
    ]

    for period in periods:
        for lang in langs:
            path = f"/{lang}" if lang else ""
            url  = f"https://github.com/trending{path}?since={period}"
            try:
                r    = requests.get(url, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(r.text, "html.parser")
                for art in soup.select("article.Box-row"):
                    a = art.select_one("h2 a")
                    if not a:
                        continue
                    repo = a["href"].strip("/")
                    if repo in seen:
                        continue
                    seen.add(repo)

                    desc_el  = art.select_one("p")
                    stars_el = art.select_one('a[href$="stargazers"]')
                    lang_el  = art.select_one('[itemprop="programmingLanguage"]')

                    desc      = (desc_el.text.strip()  if desc_el  else "")
                    repo_lang = (lang_el.text.strip()  if lang_el  else "")
                    stars_raw = (stars_el.text.strip() if stars_el else "0")
                    stars     = int(re.sub(r"[^\d]", "", stars_raw) or "0")

                    tools.append({
                        "id":          f"gh_{repo.replace('/', '_')}",
                        "name":        repo,
                        "description": desc or f"Trending {repo_lang} project",
                        "url":         f"https://github.com/{repo}",
                        "source":      "GitHub Trending",
                        "category":    _categorize(repo, desc, repo_lang),
                        "score":       stars,
                        "score_label": _score_label(stars, "GitHub Trending"),
                        "tags":        [repo_lang] if repo_lang else [],
                        "added":       datetime.now().isoformat(),
                    })
            except Exception as e:
                print(f"    [!] Trending ({period},{lang or 'all'}): {e}")
            time.sleep(0.4)

    print(f"     {len(tools)} repos")
    return tools


# ── HackerNews Show HN ────────────────────────────────────────────────────────

def fetch_hackernews() -> list:
    tools, seen = [], set()
    print("  → HackerNews Show HN...")

    cutoff = int((datetime.now() - timedelta(days=90)).timestamp())

    # Only Show HN and Launch HN — these are actual project posts, not articles
    for tag in ("show_hn", "ask_hn"):
        try:
            r = requests.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={
                    "tags":           f"story,{tag}",
                    "hitsPerPage":    "100",
                    "numericFilters": f"created_at_i>{cutoff},points>{MIN_HN_POINTS}",
                },
                timeout=12,
            )
            for h in r.json().get("hits", []):
                oid = h.get("objectID", "")
                if oid in seen:
                    continue
                seen.add(oid)
                title = h.get("title", "").strip()
                if not title:
                    continue
                pts  = h.get("points", 0)
                link = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                clean = re.sub(r"^(Show|Launch|Ask) HN:\s*", "", title, flags=re.I).strip()
                tools.append({
                    "id":          f"hn_{oid}",
                    "name":        clean or title,
                    "description": f"HackerNews · {pts} points",
                    "url":         link,
                    "source":      "HackerNews",
                    "category":    _categorize(title, title),
                    "score":       pts,
                    "score_label": _score_label(pts, "HackerNews"),
                    "tags":        [],
                    "added":       datetime.now().isoformat(),
                })
        except Exception as e:
            print(f"    [!] HN ({tag}): {e}")
        time.sleep(0.3)

    print(f"     {len(tools)} posts")
    return tools


# ── GitHub Topics (authenticated via gh CLI) ──────────────────────────────────

def _gh_bin() -> str | None:
    gh = shutil.which("gh")
    if gh:
        return gh
    for p in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh"):
        if Path(p).exists():
            return p
    return None


def fetch_github_topics() -> list:
    tools, seen = [], set()
    print("  → GitHub Topics (authenticated)...")

    gh = _gh_bin()
    if not gh:
        print("    [!] gh CLI not found — skipping")
        return []

    topics = [
        # Dev Tools
        ("command-line-interface",   "Dev Tools & Libraries"),
        ("developer-tools",          "Dev Tools & Libraries"),
        ("vscode-extension",         "Dev Tools & Libraries"),
        ("terminal",                 "Dev Tools & Libraries"),
        ("neovim",                   "Dev Tools & Libraries"),
        ("vim-plugin",               "Dev Tools & Libraries"),
        ("package-manager",          "Dev Tools & Libraries"),
        ("linter",                   "Dev Tools & Libraries"),
        ("testing",                  "Dev Tools & Libraries"),
        ("rest-api",                 "Dev Tools & Libraries"),
        ("cli",                      "Dev Tools & Libraries"),
        # AI
        ("llm",                      "AI & Productivity"),
        ("large-language-model",     "AI & Productivity"),
        ("openai",                   "AI & Productivity"),
        ("langchain",                "AI & Productivity"),
        ("stable-diffusion",         "AI & Productivity"),
        ("rag",                      "AI & Productivity"),
        ("prompt-engineering",       "AI & Productivity"),
        ("ollama",                   "AI & Productivity"),
        ("ai-agent",                 "AI & Productivity"),
        # DevOps
        ("docker",                   "DevOps & Infrastructure"),
        ("kubernetes",               "DevOps & Infrastructure"),
        ("terraform",                "DevOps & Infrastructure"),
        ("ansible",                  "DevOps & Infrastructure"),
        ("self-hosted",              "DevOps & Infrastructure"),
        ("monitoring",               "DevOps & Infrastructure"),
        ("ci-cd",                    "DevOps & Infrastructure"),
        ("observability",            "DevOps & Infrastructure"),
        ("homelab",                  "DevOps & Infrastructure"),
        # Security
        ("security",                 "Security & Privacy"),
        ("penetration-testing",      "Security & Privacy"),
        ("cybersecurity",            "Security & Privacy"),
        ("cryptography",             "Security & Privacy"),
        ("privacy",                  "Security & Privacy"),
        ("osint",                    "Security & Privacy"),
        ("vulnerability-scanner",    "Security & Privacy"),
        ("hacking",                  "Security & Privacy"),
        # Data
        ("database",                 "Data & Analytics"),
        ("data-visualization",       "Data & Analytics"),
        ("data-science",             "Data & Analytics"),
        ("data-engineering",         "Data & Analytics"),
        ("sql",                      "Data & Analytics"),
        ("time-series",              "Data & Analytics"),
        ("apache-kafka",             "Data & Analytics"),
        ("clickhouse",               "Data & Analytics"),
        # Design
        ("design-system",            "Design & Media"),
        ("css-framework",            "Design & Media"),
        ("tailwindcss",              "Design & Media"),
        ("animation",                "Design & Media"),
        ("icons",                    "Design & Media"),
        ("ui-components",            "Design & Media"),
        # Mobile
        ("android",                  "Mobile & Desktop Apps"),
        ("ios",                      "Mobile & Desktop Apps"),
        ("flutter",                  "Mobile & Desktop Apps"),
        ("react-native",             "Mobile & Desktop Apps"),
        ("electron",                 "Mobile & Desktop Apps"),
        ("swiftui",                  "Mobile & Desktop Apps"),
        ("jetpack-compose",          "Mobile & Desktop Apps"),
        # Learning
        ("awesome",                  "Learning Resources"),
        ("roadmap",                  "Learning Resources"),
        ("interview",                "Learning Resources"),
        ("algorithms",               "Learning Resources"),
        ("system-design",            "Learning Resources"),
        ("computer-science",         "Learning Resources"),
    ]

    for topic, cat in topics:
        try:
            r = subprocess.run(
                [gh, "api",
                 f"search/repositories"
                 f"?q=topic:{topic}+pushed:>2024-01-01+stars:>{MIN_GH_TOPIC_STARS}"
                 f"&sort=stars&order=desc&per_page=12"],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                time.sleep(0.5)
                continue
            for repo in json.loads(r.stdout).get("items", []):
                rid = str(repo.get("id", ""))
                if rid in seen:
                    continue
                seen.add(rid)
                stars = repo.get("stargazers_count", 0)
                lang  = repo.get("language", "") or ""
                tools.append({
                    "id":          f"ghapi_{rid}",
                    "name":        repo.get("full_name", ""),
                    "description": repo.get("description", "") or "",
                    "url":         repo.get("html_url", ""),
                    "source":      "GitHub",
                    "category":    cat,
                    "score":       stars,
                    "score_label": _score_label(stars, "GitHub"),
                    "tags":        [lang] if lang else [],
                    "added":       datetime.now().isoformat(),
                })
        except Exception as e:
            print(f"    [!] Topics ({topic}): {e}")
        time.sleep(0.2)

    print(f"     {len(tools)} repos")
    return tools


# ── Rank history ──────────────────────────────────────────────────────────────

def _load_prev_ranks() -> tuple[dict, dict]:
    if not DATA_FILE.exists():
        return {}, {}
    try:
        prev = json.loads(DATA_FILE.read_text())
        tool_ranks, cat_ranks = {}, {}
        for cat in prev.get("categories", []):
            cat_ranks[cat["name"]] = cat["rank"]
            for t in cat.get("tools", []):
                tool_ranks[t["url"]] = t["rank"]
        return tool_ranks, cat_ranks
    except Exception:
        return {}, {}


def _rank_change(prev_rank, current_rank) -> int | None:
    if prev_rank is None:
        return None
    return prev_rank - current_rank


# ── Data assembly ─────────────────────────────────────────────────────────────

def build_data(raw: list) -> dict:
    prev_tool_ranks, prev_cat_ranks = _load_prev_ranks()

    # Deduplicate by URL (first occurrence wins — trending before topics)
    by_url: dict = {}
    for t in raw:
        url = t.get("url", "")
        if url and url not in by_url:
            by_url[url] = t
    tools = list(by_url.values())

    # Group by category
    grouped: dict = {c: [] for c in CATEGORIES}
    for t in tools:
        cat = t.get("category", "Dev Tools & Libraries")
        grouped.setdefault(cat, []).append(t)

    # Sort, cap, rank, add rank_change
    for lst in grouped.values():
        lst.sort(key=lambda x: x["score"], reverse=True)
        del lst[MAX_PER_CAT:]   # hard cap

    for lst in grouped.values():
        for i, t in enumerate(lst):
            t["rank"]        = i + 1
            t["rank_change"] = _rank_change(prev_tool_ranks.get(t["url"]), i + 1)

    # Rank categories by total engagement; skip thin categories
    cat_totals   = {c: sum(t["score"] for t in lst) for c, lst in grouped.items()}
    ranked_cats  = sorted(
        [c for c, lst in grouped.items() if len(lst) >= MIN_CAT_TOOLS],
        key=cat_totals.get, reverse=True,
    )

    # Daily suggestion — stable per calendar day
    today     = datetime.now().strftime("%Y-%m-%d")
    seed      = int(hashlib.md5(today.encode()).hexdigest(), 16)
    top_tools = [t for lst in grouped.values() for t in lst if t["rank"] <= 3 and t["score"] > 0]
    suggestion = top_tools[seed % len(top_tools)] if top_tools else None

    categories = []
    for pos, cat in enumerate(ranked_cats, 1):
        info = CATEGORIES.get(cat, {"icon": "📦", "color": "#58A6FF", "id": "other"})
        categories.append({
            "id":          info["id"],
            "name":        cat,
            "icon":        info["icon"],
            "color":       info["color"],
            "rank":        pos,
            "rank_change": _rank_change(prev_cat_ranks.get(cat), pos),
            "total_score": cat_totals[cat],
            "tool_count":  len(grouped[cat]),
            "tools":       grouped[cat],
        })

    return {
        "last_updated":          datetime.now().isoformat(),
        "next_update":           (datetime.now() + timedelta(days=7)).isoformat(),
        "total_tools":           sum(len(c["tools"]) for c in categories),
        "suggestion_of_the_day": suggestion,
        "categories":            categories,
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def run_scraper() -> dict:
    print("🔍 ToolRadar — quality scrape...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    raw  = []
    raw += fetch_github_trending()
    raw += fetch_hackernews()
    raw += fetch_github_topics()

    print(f"\n  {len(raw)} items before dedup → filtering and ranking...")
    data = build_data(raw)

    DATA_FILE.write_text(json.dumps(data, indent=2))

    print(f"\n  ✓ {data['total_tools']} tools saved")
    for cat in data["categories"]:
        print(f"    #{cat['rank']} {cat['icon']} {cat['name']}: {cat['tool_count']} tools")
    print()
    return data


if __name__ == "__main__":
    run_scraper()
