# Daily World & Markets Briefing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GitHub Actions pipeline that collects world news and market data every morning, has Claude Sonnet 5 write a 10–15 minute briefing, publishes it on GitHub Pages and emails a digest by 07:00 Europe/Berlin.

**Architecture:** Four stages that pass files in `data/<date>/` to each other: Python collects (`input.json`, `writer_input.md`), the Claude Code GitHub Action writes `briefing.json`, Python validates and renders (`site/<date>/index.html`, email files), and the workflow commits, deploys Pages and sends the email over Gmail SMTP. Python owns every number. Claude only selects and explains, and it cites headline IDs that the validator checks.

**Tech Stack:** Python 3.12 (CI) / 3.12+ (local), feedparser, requests, yfinance, Jinja2, PyYAML, tzdata, pytest; GitHub Actions, `anthropics/claude-code-action@v1`, GitHub Pages, Gmail SMTP.

**Spec:** `docs/superpowers/specs/2026-09-25-daily-briefing-design.md`

## Global Constraints

- Python: code must run on 3.12 (CI) and the owner's local 3.14. Use `zoneinfo` + the `tzdata` package (Windows has no system tz database).
- Model: `claude-sonnet-5`, authenticated with `CLAUDE_CODE_OAUTH_TOKEN` (the owner's subscription), never an API key.
- Claude step: `--max-turns 6`, `--allowedTools "Read,Write"`, step timeout 10 minutes, one retry.
- Claude never produces a number that's shown. Tables, charts and movers are rendered from collected data only.
- Every story must cite `headline_ids` that exist in the day's input. Anything else is dropped.
- 8–10 stories. Sections: `Geopolitics`, `Economy & Policy`, `Business & Tech`, `Other`.
- Timezone `Europe/Berlin`. Send window starts 06:00 local. Target arrival before 07:00.
- Secrets live only in GitHub secrets: `CLAUDE_CODE_OAUTH_TOKEN`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `BRIEFING_TO`. Never in files or commits.
- Only `site/` is published. `docs/` is never served.
- Page: self-contained HTML (inline CSS + inline SVG, no JS), `noindex`, light/dark, usable at phone width.
- Footer says "Not investment advice". The prompt forbids buy/sell/hold advice.
- Email subject format: `☀ <Mon> <D> · <headline>`.

## Review Focus

1. **Weekend and holiday editions:** on Saturday–Monday the markets show Friday's (or the last trading day's) close. Each market row must show its "as of" trading day, never implying the numbers are from today. (Tests: Task 3 `test_summary_uses_last_trading_day`, Task 8 `test_weekend_edition_shows_last_trading_day`.)
2. **Hostile or messy headline text:** RSS titles with HTML tags, `&amp;` entities, `<script>`, or `javascript:` links must render as plain escaped text, and those links must never be clickable. (Tests: Task 2 `test_parse_feed_strips_html_and_skips_non_http_links`, Task 8 `test_page_escapes_headline_html`.)
3. **Claude output wrapped in extras:** a ```` ```json ```` fence or a trailing sentence around the JSON must still parse. Truncated or garbage output must produce the raw edition, not a crash. (Tests: Task 6 `test_load_briefing_strips_fences_and_chatter`, `test_load_briefing_rejects_garbage`.)
4. **DST switch days and late GitHub runs:** on 29 Mar and 25 Oct 2026, and when GitHub starts a run up to ~100 minutes late, exactly one briefing is sent. (Tests: Task 10 `test_dst_switch_days`, `test_late_run_still_sends`, `test_second_run_skips_after_send`.)
5. **Broken feeds:** a feed that returns garbage, an error page, or entries without title or link is skipped and counted as failed, and the run continues. (Tests: Task 2 `test_garbage_feed_counts_as_failed`, `test_parse_feed_skips_entries_without_title_or_link`.)

---

## File map

| File | Responsibility |
|---|---|
| `config.yaml` | Feeds, tickers, calendar filters, model, timezone, site URL, schedule switch |
| `briefing/config.py` | Load and check `config.yaml`; `ROOT` path |
| `briefing/dates.py` | Berlin-local time and edition date |
| `briefing/collect_news.py` | Fetch RSS → clean → dedupe → rank → IDs |
| `briefing/collect_markets.py` | Yahoo Finance snapshots + S&P 500 movers |
| `briefing/collect_calendar.py` | Economic calendar (ForexFactory JSON) + earnings (yfinance) |
| `briefing/formatting.py` | Number/date/direction formatting shared by prompt input and render |
| `briefing/prompt_input.py` | `input.json` → compact `writer_input.md` for Claude |
| `briefing/collect.py` | Stage 1 CLI |
| `prompts/writer.md` | Claude's editorial instructions + output schema |
| `briefing/validate.py` | Parse and check `briefing.json` against the input; CLI for the workflow |
| `briefing/charts.py` | Inline SVG sparkline + line chart |
| `briefing/render.py` | Stage 3: page, archive, index redirect, email files |
| `templates/*.j2`, `templates/style.css` | HTML/text templates |
| `briefing/send_email.py` | Gmail SMTP sender + `sent` marker |
| `briefing/gate.py` | Decides whether this run should produce today's edition |
| `scripts/update_sp500.py` | Refresh `resources/sp500.csv` |
| `scripts/check_feeds.py` | Report which feeds work |
| `scripts/dry_run.py` | Full local run into `build/`, no publish/email |
| `.github/workflows/daily.yml` | The scheduled pipeline |

---

### Task 1: Project scaffolding, config and dates

**Files:**
- Create: `requirements.txt`, `.gitignore`, `pytest.ini`, `config.yaml`, `briefing/__init__.py`, `scripts/__init__.py`, `briefing/config.py`, `briefing/dates.py`
- Test: `tests/test_config.py`, `tests/test_dates.py`

**Interfaces:**
- Produces: `briefing.config.ROOT: Path`, `load_config(path: Path | None = None) -> dict`; `briefing.dates.local_now(now_utc: datetime, tz: str) -> datetime`, `edition_date(now_utc: datetime, tz: str) -> str` (ISO `YYYY-MM-DD`).

- [ ] **Step 1: Set the repo's Git identity**

Git has no global identity on this PC. Ask the owner for the name and email to use in commits (suggest their GitHub noreply address, because the repo will be public), then run in `C:\Users\nitsc\Projects\daily-briefing`:

```bash
git config user.name "<owner's name>"
git config user.email "<owner's email>"
```

- [ ] **Step 2: Create a virtual environment and the base files**

`requirements.txt`:
```
feedparser>=6.0.11
requests>=2.32
yfinance>=0.2.54
jinja2>=3.1
pyyaml>=6.0
tzdata>=2024.1
pytest>=8.0
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
build/
.pytest_cache/
```

`pytest.ini`:
```
[pytest]
testpaths = tests
pythonpath = .
```

`briefing/__init__.py` and `scripts/__init__.py`: empty files.

Run:
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```
Expected: installs without errors. (Use `.venv/Scripts/python` for every command in this plan when running on Windows. On CI it's plain `python`.)

- [ ] **Step 3: Write `config.yaml`**

```yaml
# Daily Briefing settings. Change feeds, tickers or the model here, not in code.
timezone: Europe/Berlin
send_hour: 6                 # the briefing is produced in the 06:00–07:59 local window
schedule_enabled: false      # set to true after the first manual runs look good (Task 13)
model: claude-sonnet-5       # must match claude_args in .github/workflows/daily.yml
site_base_url: https://YOUR-GITHUB-USERNAME.github.io/daily-briefing   # set in Task 13
lookback_hours: 24
max_headlines: 300
stories_max: 10

# Order matters: when two feeds carry the same story, the earlier feed is listed first.
feeds:
  - {name: Reuters, url: "https://news.google.com/rss/search?q=site:reuters.com+when:1d&hl=en-US&gl=US&ceid=US:en", region: world}
  - {name: AP News, url: "https://news.google.com/rss/search?q=site:apnews.com+when:1d&hl=en-US&gl=US&ceid=US:en", region: world}
  - {name: BBC World, url: "https://feeds.bbci.co.uk/news/world/rss.xml", region: world}
  - {name: BBC Business, url: "https://feeds.bbci.co.uk/news/business/rss.xml", region: business}
  - {name: Guardian World, url: "https://www.theguardian.com/world/rss", region: world}
  - {name: Guardian Business, url: "https://www.theguardian.com/uk/business/rss", region: business}
  - {name: NYT World, url: "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", region: world}
  - {name: NYT Business, url: "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", region: business}
  - {name: Al Jazeera, url: "https://www.aljazeera.com/xml/rss/all.xml", region: world}
  - {name: DW, url: "https://rss.dw.com/rdf/rss-en-all", region: world}
  - {name: France 24, url: "https://www.france24.com/en/rss", region: world}
  - {name: NPR World, url: "https://feeds.npr.org/1004/rss.xml", region: world}
  - {name: Nikkei Asia, url: "https://asia.nikkei.com/rss/feed/nar", region: asia}
  - {name: FT World, url: "https://www.ft.com/world?format=rss", region: world}
  - {name: FT Markets, url: "https://www.ft.com/markets?format=rss", region: markets}
  - {name: Bloomberg Markets, url: "https://feeds.bloomberg.com/markets/news.rss", region: markets}
  - {name: Bloomberg Politics, url: "https://feeds.bloomberg.com/politics/news.rss", region: world}
  - {name: CNBC Top News, url: "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", region: markets}
  - {name: CNBC World, url: "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362", region: world}
  - {name: MarketWatch, url: "https://feeds.content.dowjones.io/public/rss/mw_topstories", region: markets}
  - {name: WSJ Markets, url: "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", region: markets}
  - {name: Yahoo Finance, url: "https://finance.yahoo.com/news/rssindex", region: markets}

# unit: index (default) | yield (change shown in basis points) | fx
markets:
  us:
    - {symbol: "^GSPC", name: "S&P 500"}
    - {symbol: "^IXIC", name: "Nasdaq Composite"}
    - {symbol: "^DJI", name: "Dow Jones"}
    - {symbol: "ES=F", name: "S&P 500 futures"}
    - {symbol: "NQ=F", name: "Nasdaq 100 futures"}
    - {symbol: "^VIX", name: "VIX volatility"}
    - {symbol: "^TNX", name: "US 10-year yield", unit: yield}
  europe:
    - {symbol: "^GDAXI", name: "DAX"}
    - {symbol: "^FTSE", name: "FTSE 100"}
    - {symbol: "^STOXX50E", name: "Euro Stoxx 50"}
  asia:
    - {symbol: "^N225", name: "Nikkei 225"}
    - {symbol: "^HSI", name: "Hang Seng"}
    - {symbol: "000001.SS", name: "Shanghai Composite"}
  other:
    - {symbol: "EURUSD=X", name: "EUR/USD", unit: fx}
    - {symbol: "JPY=X", name: "USD/JPY", unit: fx}
    - {symbol: "DX-Y.NYB", name: "US dollar index"}
    - {symbol: "CL=F", name: "WTI crude oil"}
    - {symbol: "BZ=F", name: "Brent crude oil"}
    - {symbol: "GC=F", name: "Gold"}
    - {symbol: "BTC-USD", name: "Bitcoin"}

sp500_file: resources/sp500.csv
movers_count: 5

calendar_url: https://nfs.faireconomy.media/ff_calendar_thisweek.json
calendar_countries: [USD, EUR, GBP, JPY, CNY]
calendar_min_impact: High     # High | Medium | Low

earnings_watch: [AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, AVGO, BRK-B, JPM, LLY, V, MA, WMT, XOM,
                 UNH, ORCL, COST, NFLX, JNJ, HD, PG, BAC, ABBV, KO, CRM, AMD, ADBE, NKE, MU, FDX]
```

- [ ] **Step 4: Write the failing tests**

`tests/test_config.py`:
```python
import pytest

from briefing.config import ROOT, load_config


def test_loads_project_config():
    cfg = load_config()
    assert cfg["timezone"] == "Europe/Berlin"
    assert cfg["model"] == "claude-sonnet-5"
    assert len(cfg["feeds"]) >= 10
    assert {"us", "europe", "asia", "other"} <= set(cfg["markets"])
    assert (ROOT / "config.yaml").exists()


def test_missing_key_is_reported(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("timezone: Europe/Berlin\n", encoding="utf-8")
    with pytest.raises(ValueError, match="send_hour"):
        load_config(bad)
```

`tests/test_dates.py`:
```python
from datetime import datetime, timezone

from briefing.dates import edition_date, local_now


def test_edition_date_rolls_over_at_berlin_midnight():
    late_utc = datetime(2026, 9, 25, 22, 30, tzinfo=timezone.utc)  # 00:30 CEST on the 26th
    assert edition_date(late_utc, "Europe/Berlin") == "2026-09-26"


def test_local_now_winter_offset():
    now = datetime(2026, 1, 15, 5, 15, tzinfo=timezone.utc)
    assert local_now(now, "Europe/Berlin").hour == 6
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_config.py tests/test_dates.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'briefing.config'`

- [ ] **Step 6: Implement `briefing/config.py` and `briefing/dates.py`**

`briefing/config.py`:
```python
"""Loads config.yaml, the single place for feeds, tickers and settings."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEYS = ("timezone", "send_hour", "schedule_enabled", "model", "site_base_url", "feeds", "markets")


def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise ValueError(f"config.yaml is missing '{key}'")
    return cfg
```

`briefing/dates.py`:
```python
"""Local-time helpers: the edition date is the calendar day in the reader's timezone."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def local_now(now_utc: datetime, tz: str) -> datetime:
    return now_utc.astimezone(ZoneInfo(tz))


def edition_date(now_utc: datetime, tz: str) -> str:
    return local_now(now_utc, tz).date().isoformat()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_config.py tests/test_dates.py -v`
Expected: 4 passed

- [ ] **Step 8: Commit (includes the spec and plan)**

```bash
git add .
git commit -m "Scaffold project: config, dates, spec and plan"
```

---

### Task 2: News collection

**Files:**
- Create: `briefing/collect_news.py`
- Test: `tests/test_collect_news.py`

**Interfaces:**
- Consumes: config dict (`feeds`, `lookback_hours`, `max_headlines`).
- Produces: `collect_news(cfg: dict, now: datetime, fetch: Callable[[str], bytes] = fetch_url) -> tuple[list[dict], dict]`. Headline dict: `{"id": "h001", "title": str, "summary": str, "published": str | None (ISO UTC), "region": str, "sources": [{"name": str, "url": str}]}`. Stats dict: `{"feeds_ok": int, "feeds_total": int, "errors": list[str]}`. Also `parse_feed(feed, raw, now, lookback_hours=24) -> list[dict]` (items without `id`), `dedupe(items, threshold=0.6) -> list[dict]`, `rank_and_cap(items, max_items) -> list[dict]`, `clean_text(value, limit) -> str`, `fetch_url(url, timeout=20) -> bytes`.

- [ ] **Step 1: Write the failing tests**

`tests/test_collect_news.py`:
```python
from datetime import datetime, timezone

from briefing.collect_news import collect_news, dedupe, parse_feed, rank_and_cap

NOW = datetime(2026, 9, 26, 4, 0, tzinfo=timezone.utc)
FEED = {"name": "BBC World", "url": "https://example.com/rss", "region": "world"}


def rss(items: str) -> bytes:
    return f"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{items}</channel></rss>""".encode()


def item(title, link="https://example.com/a", date="Fri, 25 Sep 2026 20:00:00 GMT", desc="Short summary."):
    link_tag = f"<link>{link}</link>" if link else ""
    title_tag = f"<title>{title}</title>" if title else ""
    return f"<item>{title_tag}{link_tag}<pubDate>{date}</pubDate><description>{desc}</description></item>"


def test_parse_feed_keeps_recent_items_only():
    raw = rss(item("Recent story") + item("Old story", date="Tue, 22 Sep 2026 10:00:00 GMT"))
    items = parse_feed(FEED, raw, NOW)
    assert [i["title"] for i in items] == ["Recent story"]
    assert items[0]["sources"] == [{"name": "BBC World", "url": "https://example.com/a"}]
    assert items[0]["published"] == "2026-09-25T20:00:00+00:00"
    assert items[0]["summary"] == "Short summary."


def test_parse_feed_skips_entries_without_title_or_link():
    raw = rss(item("") + item("No link", link=None) + item("Good"))
    assert [i["title"] for i in parse_feed(FEED, raw, NOW)] == ["Good"]


def test_parse_feed_strips_html_and_skips_non_http_links():
    raw = rss(
        item("Markets &amp; &lt;b&gt;bonds&lt;/b&gt;", desc="&lt;p&gt;Rates &amp;amp; yields&lt;/p&gt;")
        + item("Evil", link="javascript:alert(1)")
    )
    items = parse_feed(FEED, raw, NOW)
    assert [i["title"] for i in items] == ["Markets & bonds"]
    assert items[0]["summary"] == "Rates & yields"


def test_undated_items_are_kept():
    raw = rss("<item><title>No date</title><link>https://example.com/x</link></item>")
    items = parse_feed(FEED, raw, NOW)
    assert items[0]["published"] is None


def test_dedupe_merges_same_story_across_feeds():
    a = {"title": "Fed holds interest rates steady amid inflation worries - Reuters", "summary": "",
         "published": None, "region": "world", "sources": [{"name": "Reuters", "url": "https://r/1"}]}
    b = {"title": "Fed holds interest rates steady amid inflation worries", "summary": "More detail.",
         "published": None, "region": "world", "sources": [{"name": "BBC World", "url": "https://b/1"}]}
    c = {"title": "Earthquake strikes northern Japan", "summary": "", "published": None,
         "region": "asia", "sources": [{"name": "NHK", "url": "https://n/1"}]}
    merged = dedupe([a, b, c])
    assert len(merged) == 2
    assert [s["name"] for s in merged[0]["sources"]] == ["Reuters", "BBC World"]
    assert merged[0]["summary"] == "More detail."


def test_rank_and_cap_prefers_multi_source_then_newest_and_assigns_ids():
    items = [
        {"title": "old single", "published": "2026-09-25T01:00:00+00:00", "sources": [{"name": "A", "url": "u"}]},
        {"title": "new single", "published": "2026-09-25T20:00:00+00:00", "sources": [{"name": "A", "url": "u"}]},
        {"title": "double", "published": "2026-09-25T00:00:00+00:00",
         "sources": [{"name": "A", "url": "u"}, {"name": "B", "url": "v"}]},
    ]
    ranked = rank_and_cap(items, 2)
    assert [i["title"] for i in ranked] == ["double", "new single"]
    assert [i["id"] for i in ranked] == ["h001", "h002"]


def test_garbage_feed_counts_as_failed():
    cfg = {"feeds": [FEED, {"name": "Broken", "url": "https://broken", "region": "world"},
                     {"name": "Down", "url": "https://down", "region": "world"}]}

    def fetch(url):
        if url == "https://down":
            raise ConnectionError("timeout")
        if url == "https://broken":
            return b"<html>Service unavailable</html>"
        return rss(item("Working story"))

    headlines, stats = collect_news(cfg, NOW, fetch=fetch)
    assert [h["title"] for h in headlines] == ["Working story"]
    assert stats["feeds_ok"] == 1 and stats["feeds_total"] == 3
    assert len(stats["errors"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_collect_news.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'briefing.collect_news'`

- [ ] **Step 3: Implement `briefing/collect_news.py`**

```python
"""Fetch RSS feeds and turn them into one ranked, deduplicated list of headlines."""
from __future__ import annotations

import calendar
import html
import re
from datetime import datetime, timedelta, timezone
from typing import Callable

import feedparser
import requests

USER_AGENT = "Mozilla/5.0 (compatible; daily-briefing/1.0)"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SUFFIX_RE = re.compile(r"\s+[-–|]\s+[^-–|]{2,40}$")  # " - Reuters" style source suffixes
_WORD_RE = re.compile(r"[a-z0-9]+")


def fetch_url(url: str, timeout: int = 20) -> bytes:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def clean_text(value: str | None, limit: int) -> str:
    text = _TAG_RE.sub(" ", value or "")
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)  # entities like &lt;b&gt; become tags only after unescaping
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _entry_time(entry) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)


def parse_feed(feed: dict, raw: bytes, now: datetime, lookback_hours: int = 24) -> list[dict]:
    parsed = feedparser.parse(raw)
    cutoff = now - timedelta(hours=lookback_hours)
    items = []
    for entry in parsed.entries:
        title = clean_text(entry.get("title"), 300)
        link = (entry.get("link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        published = _entry_time(entry)
        if published is not None and published < cutoff:
            continue
        items.append({
            "title": title,
            "summary": clean_text(entry.get("summary"), 280),
            "published": published.isoformat() if published else None,
            "region": feed.get("region", "world"),
            "sources": [{"name": feed["name"], "url": link}],
        })
    return items


def _tokens(title: str) -> set[str]:
    base = _SUFFIX_RE.sub("", title).lower()
    return {w for w in _WORD_RE.findall(base) if len(w) > 2}


def dedupe(items: list[dict], threshold: float = 0.6) -> list[dict]:
    merged: list[dict] = []
    token_sets: list[set[str]] = []
    for item in items:
        toks = _tokens(item["title"])
        for i, existing in enumerate(merged):
            other = token_sets[i]
            if toks and other and len(toks & other) / len(toks | other) >= threshold:
                known = {s["name"] for s in existing["sources"]}
                existing["sources"].extend(s for s in item["sources"] if s["name"] not in known)
                if not existing["summary"] and item["summary"]:
                    existing["summary"] = item["summary"]
                break
        else:
            merged.append({**item, "sources": list(item["sources"])})
            token_sets.append(toks)
    return merged


def rank_and_cap(items: list[dict], max_items: int) -> list[dict]:
    def key(it: dict):
        ts = datetime.fromisoformat(it["published"]).timestamp() if it.get("published") else 0.0
        return (-len(it["sources"]), -ts)

    ranked = sorted(items, key=key)[:max_items]
    for n, it in enumerate(ranked, 1):
        it["id"] = f"h{n:03d}"
    return ranked


def collect_news(cfg: dict, now: datetime, fetch: Callable[[str], bytes] = fetch_url) -> tuple[list[dict], dict]:
    all_items: list[dict] = []
    errors: list[str] = []
    ok = 0
    for feed in cfg["feeds"]:
        try:
            raw = fetch(feed["url"])
        except Exception as exc:  # any network/HTTP failure just skips this feed
            errors.append(f"feed {feed['name']}: {exc}")
            continue
        items = parse_feed(feed, raw, now, cfg.get("lookback_hours", 24))
        if not items:
            errors.append(f"feed {feed['name']}: no recent items")
            continue
        ok += 1
        all_items.extend(items)
    headlines = rank_and_cap(dedupe(all_items), cfg.get("max_headlines", 300))
    return headlines, {"feeds_ok": ok, "feeds_total": len(cfg["feeds"]), "errors": errors}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_collect_news.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add briefing/collect_news.py tests/test_collect_news.py
git commit -m "Add RSS news collection with dedupe and ranking"
```

---

### Task 3: Market data and S&P 500 movers

**Files:**
- Create: `briefing/collect_markets.py`, `scripts/update_sp500.py`, `resources/sp500.csv` (generated)
- Test: `tests/test_collect_markets.py`, `tests/test_update_sp500.py`

**Interfaces:**
- Consumes: config `markets`, `sp500_file`, `movers_count`; `briefing.config.ROOT`.
- Produces:
  - `collect_markets(cfg, loader=yf_history, sleep=time.sleep) -> {"groups": {group: [row]}, "errors": [str]}`. Row: `{"symbol", "name", "unit", "missing": bool}` plus, when not missing, `"last", "prev", "change", "change_pct", "as_of" (YYYY-MM-DD), "history": [[date, close], ...]` (≤30 points).
  - `collect_movers(cfg, loader=yf_history, sleep=time.sleep) -> {"as_of": str | None, "gainers": [mover], "losers": [mover]}`. Mover: `{"symbol", "name", "last", "change_pct"}`.
  - `summarize_series(points, keep=30) -> dict | None`, `compute_movers(hist, names, n=5)`, `load_with_retries(loader, symbols, period, attempts=3, sleep=time.sleep)`, `load_sp500(path) -> dict[str, str]`.
  - Loader type: `Callable[[list[str], str], dict[str, list[tuple[str, float]]]]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_collect_markets.py`:
```python
from briefing.collect_markets import (
    collect_markets, compute_movers, load_sp500, load_with_retries, summarize_series,
)


def pts(*closes, start_day=21):
    return [(f"2026-09-{start_day + i:02d}", c) for i, c in enumerate(closes)]


def test_summary_computes_change():
    s = summarize_series(pts(100.0, 102.0))
    assert s["last"] == 102.0 and s["prev"] == 100.0
    assert s["change"] == 2.0 and round(s["change_pct"], 2) == 2.0
    assert s["history"] == [["2026-09-21", 100.0], ["2026-09-22", 102.0]]


def test_summary_uses_last_trading_day():
    friday_close = [("2026-09-24", 5686.7), ("2026-09-25", 5712.3)]  # run on Saturday
    assert summarize_series(friday_close)["as_of"] == "2026-09-25"


def test_summary_needs_two_points():
    assert summarize_series(pts(100.0)) is None
    assert summarize_series([]) is None


def test_summary_keeps_last_30_points():
    s = summarize_series([(f"d{i}", float(i)) for i in range(45)])
    assert len(s["history"]) == 30 and s["history"][-1] == ["d44", 44.0]


def test_retries_until_data_arrives():
    calls, sleeps = [], []

    def loader(symbols, period):
        calls.append(list(symbols))
        if len(calls) == 1:
            raise RuntimeError("rate limited")
        return {s: pts(1.0, 2.0) for s in symbols}

    got = load_with_retries(loader, ["A", "B"], "45d", sleep=sleeps.append)
    assert set(got) == {"A", "B"}
    assert len(calls) == 2 and sleeps == [2]


def test_retries_only_missing_symbols_and_gives_up():
    calls = []

    def loader(symbols, period):
        calls.append(list(symbols))
        return {"A": pts(1.0, 2.0)} if "A" in symbols else {}

    got = load_with_retries(loader, ["A", "B"], "45d", sleep=lambda s: None)
    assert set(got) == {"A"}
    assert calls == [["A", "B"], ["B"], ["B"]]


def test_collect_markets_marks_missing_symbols():
    cfg = {"markets": {"us": [{"symbol": "^GSPC", "name": "S&P 500"},
                              {"symbol": "^TNX", "name": "US 10-year yield", "unit": "yield"}]}}

    def loader(symbols, period):
        return {"^GSPC": pts(100.0, 101.0)}

    result = collect_markets(cfg, loader=loader, sleep=lambda s: None)
    spx, tnx = result["groups"]["us"]
    assert spx["missing"] is False and spx["unit"] == "index" and spx["last"] == 101.0
    assert tnx == {"symbol": "^TNX", "name": "US 10-year yield", "unit": "yield", "missing": True}
    assert result["errors"] == ["market ^TNX: no data"]


def test_movers_rank_and_skip_stale_tickers():
    hist = {
        "UP": [("2026-09-24", 100.0), ("2026-09-25", 110.0)],
        "DOWN": [("2026-09-24", 100.0), ("2026-09-25", 95.0)],
        "FLATISH": [("2026-09-24", 100.0), ("2026-09-25", 100.5)],
        "STALE": [("2026-09-20", 100.0), ("2026-09-21", 200.0)],  # delisted/halted
    }
    names = {"UP": "Up Corp", "DOWN": "Down Inc", "FLATISH": "Flat Co", "STALE": "Stale Ltd"}
    movers = compute_movers(hist, names, n=2)
    assert movers["as_of"] == "2026-09-25"
    assert [m["symbol"] for m in movers["gainers"]] == ["UP", "FLATISH"]
    assert [m["symbol"] for m in movers["losers"]] == ["DOWN"]
    assert movers["gainers"][0]["name"] == "Up Corp"


def test_movers_empty_history():
    assert compute_movers({}, {}) == {"as_of": None, "gainers": [], "losers": []}


def test_load_sp500(tmp_path):
    f = tmp_path / "sp500.csv"
    f.write_text("symbol,name\nAAPL,Apple Inc.\nBRK-B,Berkshire Hathaway\n", encoding="utf-8")
    assert load_sp500(f) == {"AAPL": "Apple Inc.", "BRK-B": "Berkshire Hathaway"}
```

`tests/test_update_sp500.py`:
```python
from scripts.update_sp500 import convert


def test_convert_maps_columns_and_yahoo_symbols():
    text = "Symbol,Security,GICS Sector\nAAPL,Apple Inc.,IT\nBRK.B,Berkshire Hathaway,Financials\n"
    assert convert(text) == [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "BRK-B", "name": "Berkshire Hathaway"},
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_collect_markets.py tests/test_update_sp500.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `briefing/collect_markets.py`**

```python
"""Market data from Yahoo Finance: snapshot rows per market group and S&P 500 movers."""
from __future__ import annotations

import csv
import time
from collections import Counter
from pathlib import Path
from typing import Callable

from briefing.config import ROOT

History = dict[str, list[tuple[str, float]]]
Loader = Callable[[list[str], str], History]


def yf_history(symbols: list[str], period: str) -> History:
    """Daily closes per symbol. Thin adapter over yfinance; exercised by the dry run."""
    import pandas as pd
    import yfinance as yf

    df = yf.download(symbols, period=period, interval="1d", progress=False,
                     auto_adjust=False, group_by="ticker", threads=True)
    out: History = {}
    for sym in symbols:
        try:
            series = df[sym]["Close"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
        except KeyError:
            continue
        points = [(idx.strftime("%Y-%m-%d"), float(v)) for idx, v in series.dropna().items()]
        if points:
            out[sym] = points
    return out


def load_with_retries(loader: Loader, symbols: list[str], period: str, attempts: int = 3,
                      sleep: Callable[[float], None] = time.sleep) -> History:
    result: History = {}
    missing = list(symbols)
    for attempt in range(attempts):
        if not missing:
            break
        if attempt:
            sleep(2 ** attempt)
        try:
            got = loader(missing, period)
        except Exception:  # yfinance raises assorted errors on throttling; retry
            got = {}
        result.update({s: p for s, p in got.items() if p})
        missing = [s for s in missing if s not in result]
    return result


def summarize_series(points: list[tuple[str, float]], keep: int = 30) -> dict | None:
    if len(points) < 2:
        return None
    prev_date, prev = points[-2]
    last_date, last = points[-1]
    change = last - prev
    return {
        "last": last,
        "prev": prev,
        "change": change,
        "change_pct": (change / prev * 100) if prev else 0.0,
        "as_of": last_date,
        "history": [[d, v] for d, v in points[-keep:]],
    }


def collect_markets(cfg: dict, loader: Loader = yf_history,
                    sleep: Callable[[float], None] = time.sleep) -> dict:
    symbols = [row["symbol"] for rows in cfg["markets"].values() for row in rows]
    hist = load_with_retries(loader, symbols, "45d", sleep=sleep)
    groups: dict[str, list[dict]] = {}
    errors: list[str] = []
    for group, rows in cfg["markets"].items():
        out = []
        for row in rows:
            entry = {"symbol": row["symbol"], "name": row["name"], "unit": row.get("unit", "index")}
            summary = summarize_series(hist.get(row["symbol"], []))
            if summary is None:
                entry["missing"] = True
                errors.append(f"market {row['symbol']}: no data")
            else:
                entry.update(summary)
                entry["missing"] = False
            out.append(entry)
        groups[group] = out
    return {"groups": groups, "errors": errors}


def load_sp500(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8", newline="") as f:
        return {row["symbol"]: row["name"] for row in csv.DictReader(f)}


def compute_movers(hist: History, names: dict[str, str], n: int = 5) -> dict:
    last_dates = Counter(p[-1][0] for p in hist.values() if len(p) >= 2)
    if not last_dates:
        return {"as_of": None, "gainers": [], "losers": []}
    session = last_dates.most_common(1)[0][0]
    rows = []
    for sym, p in hist.items():
        if len(p) < 2 or p[-1][0] != session or not p[-2][1]:
            continue
        pct = (p[-1][1] - p[-2][1]) / p[-2][1] * 100
        rows.append({"symbol": sym, "name": names.get(sym, sym), "last": p[-1][1], "change_pct": pct})
    rows.sort(key=lambda r: r["change_pct"], reverse=True)
    gainers = [r for r in rows[:n] if r["change_pct"] > 0]
    losers = [r for r in reversed(rows[-n:]) if r["change_pct"] < 0]
    return {"as_of": session, "gainers": gainers, "losers": losers}


def collect_movers(cfg: dict, loader: Loader = yf_history,
                   sleep: Callable[[float], None] = time.sleep) -> dict:
    try:
        names = load_sp500(ROOT / cfg.get("sp500_file", "resources/sp500.csv"))
    except FileNotFoundError:
        return {"as_of": None, "gainers": [], "losers": []}
    hist = load_with_retries(loader, list(names), "5d", sleep=sleep)
    return compute_movers(hist, names, cfg.get("movers_count", 5))
```

- [ ] **Step 4: Implement `scripts/update_sp500.py`**

```python
"""Refresh resources/sp500.csv from the public datasets/s-and-p-500-companies list.

Run by hand every few months: python -m scripts.update_sp500
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import requests

SOURCE = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
OUT = Path(__file__).resolve().parent.parent / "resources" / "sp500.csv"


def convert(text: str) -> list[dict]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        rows.append({"symbol": row["Symbol"].strip().replace(".", "-"), "name": row["Security"].strip()})
    return rows


def main() -> None:
    resp = requests.get(SOURCE, timeout=30)
    resp.raise_for_status()
    rows = convert(resp.text)
    if len(rows) < 490:
        sys.exit(f"Only {len(rows)} rows downloaded; refusing to overwrite {OUT}")
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} companies to {OUT}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_collect_markets.py tests/test_update_sp500.py -v`
Expected: 11 passed

- [ ] **Step 6: Generate the constituents file**

Run: `.venv/Scripts/python -m scripts.update_sp500`
Expected: `Wrote 50x companies to ...\resources\sp500.csv`. Open the file and check that the first lines look like `symbol,name` / `MMM,3M` and that `BRK-B` is present.

- [ ] **Step 7: Commit**

```bash
git add briefing/collect_markets.py scripts/update_sp500.py resources/sp500.csv tests/test_collect_markets.py tests/test_update_sp500.py
git commit -m "Add market snapshots and S&P 500 movers"
```

---

### Task 4: Economic calendar and earnings

**Files:**
- Create: `briefing/collect_calendar.py`
- Test: `tests/test_collect_calendar.py`

**Interfaces:**
- Consumes: config `calendar_url`, `calendar_countries`, `calendar_min_impact`, `timezone`, `earnings_watch`.
- Produces: `collect_calendar(cfg, day: str, fetch=fetch_json) -> tuple[list[dict], list[str]]`. Event: `{"time": "HH:MM" (local), "country", "title", "impact", "forecast", "previous"}`, sorted by time. `collect_earnings(symbols: list[str], day: str, lookup=yf_earnings_date) -> tuple[list[str], list[str]]`. Also `parse_ff_calendar(events, day, tz, countries, min_impact) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_collect_calendar.py`:
```python
from briefing.collect_calendar import collect_calendar, collect_earnings, parse_ff_calendar

EVENTS = [
    {"title": "Core PCE Price Index m/m", "country": "USD", "date": "2026-09-25T08:30:00-04:00",
     "impact": "High", "forecast": "0.2%", "previous": "0.1%"},
    {"title": "ECB President Speaks", "country": "EUR", "date": "2026-09-25T03:00:00-04:00",
     "impact": "High", "forecast": "", "previous": ""},
    {"title": "Pending Home Sales", "country": "USD", "date": "2026-09-25T10:00:00-04:00",
     "impact": "Medium", "forecast": "1.0%", "previous": "-0.5%"},
    {"title": "AUD thing", "country": "AUD", "date": "2026-09-25T02:00:00-04:00", "impact": "High"},
    {"title": "Tomorrow", "country": "USD", "date": "2026-09-26T08:30:00-04:00", "impact": "High"},
    {"title": "Broken", "country": "USD", "date": "not a date", "impact": "High"},
]
CFG = {"calendar_url": "https://cal", "calendar_countries": ["USD", "EUR"],
       "calendar_min_impact": "High", "timezone": "Europe/Berlin"}


def test_filters_by_day_country_impact_and_converts_to_berlin_time():
    out = parse_ff_calendar(EVENTS, "2026-09-25", "Europe/Berlin", ["USD", "EUR"], "High")
    assert out == [
        {"time": "09:00", "country": "EUR", "title": "ECB President Speaks", "impact": "High",
         "forecast": "", "previous": ""},
        {"time": "14:30", "country": "USD", "title": "Core PCE Price Index m/m", "impact": "High",
         "forecast": "0.2%", "previous": "0.1%"},
    ]


def test_medium_threshold_includes_medium():
    out = parse_ff_calendar(EVENTS, "2026-09-25", "Europe/Berlin", ["USD"], "Medium")
    assert [e["title"] for e in out] == ["Core PCE Price Index m/m", "Pending Home Sales"]


def test_calendar_fetch_failure_is_an_error_not_a_crash():
    def fetch(url):
        raise ConnectionError("down")

    events, errors = collect_calendar(CFG, "2026-09-25", fetch=fetch)
    assert events == [] and errors == ["calendar: down"]


def test_calendar_unexpected_payload():
    events, errors = collect_calendar(CFG, "2026-09-25", fetch=lambda url: {"error": "rate limit"})
    assert events == [] and errors == ["calendar: unexpected response"]


def test_earnings_today_only_and_errors_collected():
    dates = {"NKE": "2026-09-25", "AAPL": "2026-10-30"}

    def lookup(symbol):
        if symbol == "BAD":
            raise ValueError("no data")
        return dates.get(symbol)

    today, errors = collect_earnings(["NKE", "AAPL", "BAD", "MSFT"], "2026-09-25", lookup=lookup)
    assert today == ["NKE"]
    assert errors == ["earnings BAD: no data"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_collect_calendar.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `briefing/collect_calendar.py`**

```python
"""Today's economic releases (ForexFactory weekly JSON) and earnings from a watch list (yfinance)."""
from __future__ import annotations

from datetime import datetime
from typing import Callable
from zoneinfo import ZoneInfo

import requests

from briefing.collect_news import USER_AGENT

IMPACT_ORDER = {"Low": 1, "Medium": 2, "High": 3}


def fetch_json(url: str, timeout: int = 20):
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def parse_ff_calendar(events: list[dict], day: str, tz: str, countries: list[str],
                      min_impact: str) -> list[dict]:
    zone = ZoneInfo(tz)
    floor = IMPACT_ORDER.get(min_impact, 3)
    out = []
    for ev in events:
        try:
            when = datetime.fromisoformat(ev["date"]).astimezone(zone)
        except (KeyError, TypeError, ValueError):
            continue
        if when.date().isoformat() != day or ev.get("country") not in countries:
            continue
        if IMPACT_ORDER.get(ev.get("impact"), 0) < floor:
            continue
        out.append({
            "time": when.strftime("%H:%M"),
            "country": ev["country"],
            "title": (ev.get("title") or "").strip(),
            "impact": ev["impact"],
            "forecast": ev.get("forecast") or "",
            "previous": ev.get("previous") or "",
        })
    out.sort(key=lambda e: e["time"])
    return out


def collect_calendar(cfg: dict, day: str, fetch: Callable = fetch_json) -> tuple[list[dict], list[str]]:
    try:
        events = fetch(cfg["calendar_url"])
    except Exception as exc:
        return [], [f"calendar: {exc}"]
    if not isinstance(events, list):
        return [], ["calendar: unexpected response"]
    return parse_ff_calendar(events, day, cfg["timezone"], cfg["calendar_countries"],
                             cfg["calendar_min_impact"]), []


def yf_earnings_date(symbol: str) -> str | None:
    """Next earnings date for a ticker. Thin adapter over yfinance; exercised by the dry run."""
    import yfinance as yf

    cal = yf.Ticker(symbol).calendar or {}
    dates = cal.get("Earnings Date") or []
    return dates[0].isoformat() if dates else None


def collect_earnings(symbols: list[str], day: str,
                     lookup: Callable[[str], str | None] = yf_earnings_date) -> tuple[list[str], list[str]]:
    today, errors = [], []
    for sym in symbols:
        try:
            if lookup(sym) == day:
                today.append(sym)
        except Exception as exc:
            errors.append(f"earnings {sym}: {exc}")
    return today, errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_collect_calendar.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add briefing/collect_calendar.py tests/test_collect_calendar.py
git commit -m "Add economic calendar and earnings collection"
```

---

### Task 5: Collect stage CLI, formatting and Claude's input file

**Files:**
- Create: `briefing/formatting.py`, `briefing/prompt_input.py`, `briefing/collect.py`
- Test: `tests/test_formatting.py`, `tests/test_prompt_input.py`, `tests/test_collect.py`

**Interfaces:**
- Consumes: `collect_news`, `collect_markets`, `collect_movers`, `collect_calendar`, `collect_earnings`, `edition_date`, `load_config`, `ROOT`.
- Produces:
  - `briefing.formatting`: `GROUP_TITLES: dict[str, str]`, `fmt_value(value: float, unit: str) -> str`, `fmt_change(entry: dict) -> str`, `direction(entry: dict) -> str` (`"up" | "down" | "flat"`), `fmt_date_short(iso: str | None) -> str` (e.g. `"Fri 25 Sep"`, `""` for None).
  - `briefing.prompt_input.build_writer_input(data: dict) -> str`.
  - `briefing.collect.build_input(cfg, now, day, *, news, markets, movers, calendar, earnings) -> dict` (the `input.json` shape: `date, generated_at, timezone, news, markets, movers, calendar, earnings, meta{feeds_ok, feeds_total, errors}`), `write_input(data, out_dir: Path) -> None`, `main(argv=None)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_formatting.py`:
```python
from briefing.formatting import direction, fmt_change, fmt_date_short, fmt_value


def test_fmt_value_by_unit():
    assert fmt_value(5712.3, "index") == "5,712.30"
    assert fmt_value(1.11234, "fx") == "1.1123"
    assert fmt_value(149.456, "fx") == "149.46"
    assert fmt_value(4.213, "yield") == "4.21%"


def test_fmt_change():
    assert fmt_change({"unit": "index", "missing": False, "change": 25.6, "change_pct": 0.4502}) == "+0.45%"
    assert fmt_change({"unit": "index", "missing": False, "change": -3, "change_pct": -1.0}) == "-1.00%"
    assert fmt_change({"unit": "yield", "missing": False, "change": 0.031, "change_pct": 0.7}) == "+3 bp"
    assert fmt_change({"unit": "index", "missing": True}) == "–"


def test_direction():
    assert direction({"missing": False, "change": 1.0}) == "up"
    assert direction({"missing": False, "change": -0.1}) == "down"
    assert direction({"missing": False, "change": 0.0}) == "flat"
    assert direction({"missing": True}) == "flat"


def test_fmt_date_short():
    assert fmt_date_short("2026-09-25") == "Fri 25 Sep"
    assert fmt_date_short(None) == ""
```

`tests/test_prompt_input.py`:
```python
from briefing.prompt_input import build_writer_input


def test_writer_input_lists_markets_movers_calendar_and_headlines():
    data = {
        "date": "2026-09-26", "timezone": "Europe/Berlin",
        "markets": {"us": [
            {"symbol": "^GSPC", "name": "S&P 500", "unit": "index", "missing": False, "last": 5712.3,
             "change": 25.6, "change_pct": 0.45, "as_of": "2026-09-25"},
            {"symbol": "^VIX", "name": "VIX volatility", "unit": "index", "missing": True},
        ]},
        "movers": {"as_of": "2026-09-25",
                   "gainers": [{"symbol": "NVDA", "name": "NVIDIA", "last": 120.5, "change_pct": 6.2}],
                   "losers": []},
        "calendar": [{"time": "14:30", "country": "USD", "title": "Core PCE", "impact": "High",
                      "forecast": "0.2%", "previous": ""}],
        "earnings": ["NKE"],
        "news": [{"id": "h001", "title": "Fed holds", "summary": "Rates unchanged.",
                  "published": "2026-09-25T18:00:00+00:00",
                  "sources": [{"name": "BBC World", "url": "u"}, {"name": "Reuters", "url": "v"}]},
                 {"id": "h002", "title": "Undated", "summary": "", "published": None,
                  "sources": [{"name": "DW", "url": "w"}]}],
    }
    text = build_writer_input(data)
    assert "- S&P 500: 5,712.30 (+0.45%) as of 2026-09-25" in text
    assert "- VIX volatility: no data" in text
    assert "- Gainers: NVDA (NVIDIA) +6.2%" in text
    assert "- Losers: none" in text
    assert "- 14:30 USD Core PCE (impact High; forecast 0.2%; previous n/a)" in text
    assert "## Earnings today: NKE" in text
    assert "h001 | BBC World, Reuters | 2026-09-25 18:00 | Fed holds — Rates unchanged." in text
    assert "h002 | DW | unknown | Undated" in text
```

`tests/test_collect.py`:
```python
import json
from datetime import datetime, timezone

from briefing.collect import build_input, write_input

NOW = datetime(2026, 9, 26, 4, 15, tzinfo=timezone.utc)


def fakes():
    return dict(
        news=lambda cfg, now: ([{"id": "h001", "title": "T", "summary": "", "published": None,
                                 "region": "world", "sources": [{"name": "A", "url": "u"}]}],
                               {"feeds_ok": 1, "feeds_total": 2, "errors": ["feed B: down"]}),
        markets=lambda cfg: {"groups": {"us": []}, "errors": ["market X: no data"]},
        movers=lambda cfg: {"as_of": None, "gainers": [], "losers": []},
        calendar=lambda cfg, day: ([], ["calendar: down"]),
        earnings=lambda symbols, day: (["NKE"], []),
    )


def test_build_input_combines_stages_and_errors():
    cfg = {"timezone": "Europe/Berlin", "earnings_watch": ["NKE"]}
    data = build_input(cfg, NOW, "2026-09-26", **fakes())
    assert data["date"] == "2026-09-26"
    assert data["generated_at"] == "2026-09-26T04:15:00+00:00"
    assert data["earnings"] == ["NKE"]
    assert data["meta"] == {"feeds_ok": 1, "feeds_total": 2,
                            "errors": ["feed B: down", "market X: no data", "calendar: down"]}


def test_write_input_writes_files_and_clears_stale_briefing(tmp_path):
    cfg = {"timezone": "Europe/Berlin", "earnings_watch": []}
    data = build_input(cfg, NOW, "2026-09-26", **fakes())
    out = tmp_path / "2026-09-26"
    out.mkdir()
    (out / "briefing.json").write_text("{}", encoding="utf-8")  # left over from an earlier run
    write_input(data, out)
    assert json.loads((out / "input.json").read_text(encoding="utf-8"))["date"] == "2026-09-26"
    assert "h001 | A | unknown | T" in (out / "writer_input.md").read_text(encoding="utf-8")
    assert not (out / "briefing.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_formatting.py tests/test_prompt_input.py tests/test_collect.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `briefing/formatting.py`**

```python
"""Number, change and date formatting shared by Claude's input and the rendered page/email."""
from __future__ import annotations

from datetime import date

GROUP_TITLES = {
    "us": "United States",
    "europe": "Europe",
    "asia": "Asia",
    "other": "FX, commodities & crypto",
}


def fmt_value(value: float, unit: str) -> str:
    if unit == "yield":
        return f"{value:.2f}%"
    if unit == "fx":
        return f"{value:,.4f}" if value < 10 else f"{value:,.2f}"
    return f"{value:,.2f}"


def fmt_change(entry: dict) -> str:
    if entry.get("missing"):
        return "–"
    if entry["unit"] == "yield":
        return f"{entry['change'] * 100:+.0f} bp"
    return f"{entry['change_pct']:+.2f}%"


def direction(entry: dict) -> str:
    if entry.get("missing") or entry["change"] == 0:
        return "flat"
    return "up" if entry["change"] > 0 else "down"


def fmt_date_short(iso: str | None) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d:%a} {d.day} {d:%b}"
```

- [ ] **Step 4: Implement `briefing/prompt_input.py`**

```python
"""Turns input.json into a compact text file Claude can read in one go."""
from __future__ import annotations

from briefing.formatting import GROUP_TITLES, fmt_change, fmt_value


def build_writer_input(data: dict) -> str:
    lines = [f"# Briefing input for {data['date']}", "", "## Markets (latest value, change vs previous close)", ""]
    for group, rows in data["markets"].items():
        lines.append(f"### {GROUP_TITLES.get(group, group)}")
        for r in rows:
            if r["missing"]:
                lines.append(f"- {r['name']}: no data")
            else:
                lines.append(f"- {r['name']}: {fmt_value(r['last'], r['unit'])} ({fmt_change(r)}) as of {r['as_of']}")
        lines.append("")

    movers = data["movers"]
    lines.append(f"## S&P 500 movers (session {movers.get('as_of') or 'n/a'})")
    for label in ("gainers", "losers"):
        listed = ", ".join(f"{m['symbol']} ({m['name']}) {m['change_pct']:+.1f}%" for m in movers.get(label, []))
        lines.append(f"- {label.capitalize()}: {listed or 'none'}")
    lines.append("")

    lines.append(f"## Economic calendar today ({data['timezone']} time)")
    if data["calendar"]:
        for e in data["calendar"]:
            lines.append(f"- {e['time']} {e['country']} {e['title']} (impact {e['impact']}; "
                         f"forecast {e['forecast'] or 'n/a'}; previous {e['previous'] or 'n/a'})")
    else:
        lines.append("- none available")
    lines.append("")
    lines.append("## Earnings today: " + (", ".join(data["earnings"]) or "none from the watch list"))
    lines.append("")

    lines.append("## Headlines")
    lines.append("Format: id | sources | published (UTC) | title — summary")
    for h in data["news"]:
        sources = ", ".join(s["name"] for s in h["sources"])
        published = h["published"][:16].replace("T", " ") if h["published"] else "unknown"
        summary = f" — {h['summary']}" if h["summary"] else ""
        lines.append(f"{h['id']} | {sources} | {published} | {h['title']}{summary}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Implement `briefing/collect.py`**

```python
"""Stage 1: collect news, markets and calendar into data/<date>/input.json and writer_input.md."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from briefing.collect_calendar import collect_calendar, collect_earnings
from briefing.collect_markets import collect_markets, collect_movers
from briefing.collect_news import collect_news
from briefing.config import ROOT, load_config
from briefing.dates import edition_date
from briefing.prompt_input import build_writer_input


def build_input(cfg: dict, now: datetime, day: str, *, news=collect_news, markets=collect_markets,
                movers=collect_movers, calendar=collect_calendar, earnings=collect_earnings) -> dict:
    headlines, news_stats = news(cfg, now)
    market_data = markets(cfg)
    mover_data = movers(cfg)
    cal, cal_errors = calendar(cfg, day)
    earn, earn_errors = earnings(cfg.get("earnings_watch", []), day)
    return {
        "date": day,
        "generated_at": now.isoformat(),
        "timezone": cfg["timezone"],
        "news": headlines,
        "markets": market_data["groups"],
        "movers": mover_data,
        "calendar": cal,
        "earnings": earn,
        "meta": {
            "feeds_ok": news_stats["feeds_ok"],
            "feeds_total": news_stats["feeds_total"],
            "errors": news_stats["errors"] + market_data["errors"] + cal_errors + earn_errors,
        },
    }


def write_input(data: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "input.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "writer_input.md").write_text(build_writer_input(data), encoding="utf-8")
    # Claude's Write tool refuses to overwrite a file it hasn't read, so clear old output.
    (out_dir / "briefing.json").unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="edition date YYYY-MM-DD (default: today in the configured timezone)")
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    args = parser.parse_args(argv)
    cfg = load_config()
    now = datetime.now(timezone.utc)
    day = args.date or edition_date(now, cfg["timezone"])
    data = build_input(cfg, now, day)
    write_input(data, Path(args.data_dir) / day)
    meta = data["meta"]
    print(f"Collected {len(data['news'])} headlines from {meta['feeds_ok']}/{meta['feeds_total']} feeds; "
          f"{len(meta['errors'])} problems")
    for err in meta["errors"]:
        print("  -", err)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_formatting.py tests/test_prompt_input.py tests/test_collect.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add briefing/formatting.py briefing/prompt_input.py briefing/collect.py tests/test_formatting.py tests/test_prompt_input.py tests/test_collect.py
git commit -m "Add collect stage CLI and Claude input file"
```

---

### Task 6: Writer prompt and briefing validation

**Files:**
- Create: `prompts/writer.md`, `briefing/validate.py`, `tests/conftest.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: the `input.json` shape from Task 5.
- Produces:
  - `SECTIONS: tuple[str, ...]`, `MIN_STORIES = 3`.
  - `load_briefing(path: Path) -> dict | None`.
  - `validate_briefing(raw, input_data, max_stories=10) -> tuple[dict | None, list[str]]`. The cleaned briefing has `date, headline, at_a_glance[≤5], market_analysis, mover_notes{symbol: str}, stories[], watch_today[≤3]`. Each story has `section, title, summary, why_it_matters, headline_ids, single_source, sources[{name,url}]`.
  - CLI `python -m briefing.validate --dir data/<date>` prints `valid`/`invalid` and appends `valid=true|false` to `$GITHUB_OUTPUT`.
  - Test fixtures `sample_input`, `sample_briefing` in `tests/conftest.py` (reused by Tasks 8–9).

- [ ] **Step 1: Write `prompts/writer.md`**

````markdown
# Daily Briefing: writer instructions

You are the editor of a private morning briefing for one reader in Germany who wants to stay informed about the most important world news and the stock market. They have 10–15 minutes.

## Input

The task message names an input file. Read it with the Read tool. It contains:
- market data that has already been calculated. Never change or recalculate these numbers.
- the S&P 500's biggest movers in the last session
- today's economic calendar (reader's local time) and earnings from a watch list
- about 300 headlines from the last 24 hours, one per line: `id | sources | published (UTC) | title — summary`

## Your job

1. Choose the 8–10 most important stories for a globally minded reader who follows markets. Rank by global significance and relevance to markets, not by how many outlets repeated a story. Merge headlines about the same event into one story.
2. Write a short market analysis and a "watch today" list.

## Rules

- Use only facts that appear in the input. Don't add facts from memory and don't speculate. If a story's details are thin, keep it short rather than filling gaps.
- Every story lists the ids of the headlines it is based on in `headline_ids`. Use only ids that appear in the input.
- Set `single_source` to true when all of a story's headlines come from one outlet.
- Neutral, factual tone: no hype, no political opinions, no loaded adjectives.
- No investment advice. Never suggest buying, selling or holding anything.
- Quote market numbers only as they appear in the input (e.g. "the S&P 500 rose 0.45%").
- Write in English.

## Output

Use the Write tool to write exactly one JSON object to the output file named in the task message. Don't put markdown fences, comments or any other text in the file. Schema:

```json
{
  "headline": "string",
  "at_a_glance": ["string", "string", "string", "string", "string"],
  "market_analysis": "string",
  "mover_notes": {"TICKER": "string"},
  "stories": [
    {
      "section": "Geopolitics",
      "title": "string",
      "summary": "string",
      "why_it_matters": "string",
      "headline_ids": ["h001"],
      "single_source": false
    }
  ],
  "watch_today": ["string", "string", "string"]
}
```

Field rules:
- `headline`: at most 90 characters, sums up the day.
- `at_a_glance`: exactly 5 bullets, each at most 25 words.
- `market_analysis`: 2–3 paragraphs separated by a blank line, at most 250 words in total. Cover what drove the last US session, how Asia and Europe are trading, and what's in play today (data releases, earnings, central banks).
- `mover_notes`: optional. The key is a ticker from the movers list and the value is a one-line reason, only if a headline explains the move. Leave out tickers you can't explain.
- `stories`: 8–10 items. `section` is one of `Geopolitics`, `Economy & Policy`, `Business & Tech`, `Other`. `summary` is 3–4 sentences. `why_it_matters` is 1–2 sentences on the consequences for the world, the economy or markets.
- `watch_today`: exactly 3 items, one sentence each.

When the file is written, reply with the single word `done`.
````

- [ ] **Step 2: Write `tests/conftest.py`**

```python
import pytest


def make_market(symbol, name, last, prev, unit="index", as_of="2026-09-25"):
    change = last - prev
    return {
        "symbol": symbol, "name": name, "unit": unit, "missing": False,
        "last": last, "prev": prev, "change": change, "change_pct": change / prev * 100,
        "as_of": as_of, "history": [["2026-08-27", prev * 0.97], ["2026-09-24", prev], [as_of, last]],
    }


def headline(hid, title, *sources):
    return {"id": hid, "title": title, "summary": f"Summary of {title}.",
            "published": "2026-09-25T18:00:00+00:00", "region": "world",
            "sources": [{"name": name, "url": f"https://{name.lower().replace(' ', '')}.example/{hid}"}
                        for name in sources]}


@pytest.fixture
def sample_input():
    return {
        "date": "2026-09-26",
        "generated_at": "2026-09-26T04:16:00+00:00",
        "timezone": "Europe/Berlin",
        "news": [
            headline("h001", "Central bank holds rates steady", "BBC World", "Guardian World"),
            headline("h002", "Ceasefire talks resume", "Al Jazeera"),
            headline("h003", "Chipmaker beats earnings forecasts", "CNBC Top News"),
            headline("h004", "Oil rises on supply worries", "Bloomberg Markets"),
        ],
        "markets": {
            "us": [make_market("^GSPC", "S&P 500", 5712.3, 5686.7),
                   make_market("^TNX", "US 10-year yield", 4.21, 4.18, unit="yield")],
            "europe": [make_market("^GDAXI", "DAX", 19012.4, 19100.0)],
            "asia": [{"symbol": "^N225", "name": "Nikkei 225", "unit": "index", "missing": True}],
            "other": [make_market("EURUSD=X", "EUR/USD", 1.1123, 1.1101, unit="fx")],
        },
        "movers": {"as_of": "2026-09-25",
                   "gainers": [{"symbol": "NVDA", "name": "NVIDIA", "last": 120.5, "change_pct": 6.2}],
                   "losers": [{"symbol": "NKE", "name": "Nike", "last": 80.1, "change_pct": -4.8}]},
        "calendar": [{"time": "14:30", "country": "USD", "title": "Core PCE Price Index m/m",
                      "impact": "High", "forecast": "0.2%", "previous": "0.1%"}],
        "earnings": ["NKE"],
        "meta": {"feeds_ok": 18, "feeds_total": 20, "errors": []},
    }


@pytest.fixture
def sample_briefing():
    def story(section, title, ids, single=False):
        return {"section": section, "title": title, "summary": f"{title} summary.",
                "why_it_matters": f"{title} matters.", "headline_ids": ids, "single_source": single}

    return {
        "headline": "Rates on hold as ceasefire talks resume",
        "at_a_glance": ["One.", "Two.", "Three.", "Four.", "Five."],
        "market_analysis": "First paragraph.\n\nSecond paragraph.",
        "mover_notes": {"NVDA": "Rose after upbeat guidance.", "ZZZZ": "Not a mover."},
        "stories": [
            story("Economy & Policy", "Central bank holds", ["h001"]),
            story("Geopolitics", "Talks resume", ["h002"], single=True),
            story("Business & Tech", "Chipmaker beats", ["h003"]),
            story("Energy", "Oil rises", ["h004"]),
        ],
        "watch_today": ["PCE data.", "Nike reaction.", "Oil."],
    }
```

- [ ] **Step 3: Write the failing tests**

`tests/test_validate.py`:
```python
import json

from briefing.validate import load_briefing, main, validate_briefing


def test_valid_briefing_is_cleaned(sample_input, sample_briefing):
    clean, problems = validate_briefing(sample_briefing, sample_input)
    assert problems == []
    assert clean["date"] == "2026-09-26"
    assert [s["section"] for s in clean["stories"]] == ["Economy & Policy", "Geopolitics", "Business & Tech", "Other"]
    assert clean["stories"][0]["sources"] == [
        {"name": "BBC World", "url": "https://bbcworld.example/h001"},
        {"name": "Guardian World", "url": "https://guardianworld.example/h001"},
    ]
    assert clean["stories"][1]["single_source"] is True
    assert clean["mover_notes"] == {"NVDA": "Rose after upbeat guidance."}


def test_story_with_unknown_or_bad_ids_is_dropped(sample_input, sample_briefing):
    sample_briefing["stories"][0]["headline_ids"] = ["h999"]
    sample_briefing["stories"][1]["headline_ids"] = [["h002"]]
    clean, problems = validate_briefing(sample_briefing, sample_input)
    assert clean is None  # only 2 valid stories left, below MIN_STORIES
    assert any("h999" in p for p in problems)


def test_one_bad_story_does_not_sink_the_rest(sample_input, sample_briefing):
    sample_briefing["stories"][3]["headline_ids"] = ["h999"]
    clean, problems = validate_briefing(sample_briefing, sample_input)
    assert [s["title"] for s in clean["stories"]] == ["Central bank holds", "Talks resume", "Chipmaker beats"]
    assert len(problems) == 1


def test_lists_are_trimmed_and_stories_capped(sample_input, sample_briefing):
    sample_briefing["at_a_glance"] = [f"b{i}" for i in range(8)]
    sample_briefing["watch_today"] = ["a", "b", "c", "d", 5]
    clean, _ = validate_briefing(sample_briefing, sample_input, max_stories=3)
    assert len(clean["at_a_glance"]) == 5
    assert clean["watch_today"] == ["a", "b", "c"]
    assert len(clean["stories"]) == 3


def test_missing_headline_or_non_object_is_invalid(sample_input, sample_briefing):
    sample_briefing["headline"] = "  "
    assert validate_briefing(sample_briefing, sample_input)[0] is None
    assert validate_briefing(None, sample_input) == (None, ["briefing is not a JSON object"])
    assert validate_briefing(["x"], sample_input)[0] is None


def test_load_briefing_strips_fences_and_chatter(tmp_path):
    f = tmp_path / "briefing.json"
    f.write_text('```json\n{"headline": "Hi"}\n```\nDone! Let me know if you need changes.', encoding="utf-8")
    assert load_briefing(f) == {"headline": "Hi"}


def test_load_briefing_rejects_garbage(tmp_path):
    f = tmp_path / "briefing.json"
    f.write_text('{"headline": "cut off mid', encoding="utf-8")
    assert load_briefing(f) is None
    f.write_text("I could not complete the task.", encoding="utf-8")
    assert load_briefing(f) is None
    assert load_briefing(tmp_path / "missing.json") is None


def test_cli_writes_github_output(tmp_path, monkeypatch, sample_input, sample_briefing):
    (tmp_path / "input.json").write_text(json.dumps(sample_input), encoding="utf-8")
    (tmp_path / "briefing.json").write_text(json.dumps(sample_briefing), encoding="utf-8")
    out = tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    main(["--dir", str(tmp_path)])
    assert out.read_text() == "valid=true\n"
    (tmp_path / "briefing.json").unlink()
    main(["--dir", str(tmp_path)])
    assert out.read_text() == "valid=true\nvalid=false\n"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_validate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'briefing.validate'`

- [ ] **Step 5: Implement `briefing/validate.py`**

```python
"""Checks Claude's briefing.json against the day's input so nothing unsupported gets published."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

SECTIONS = ("Geopolitics", "Economy & Policy", "Business & Tech", "Other")
MIN_STORIES = 3


def load_briefing(path: Path) -> dict | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text_list(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()][:limit]


def _clean_story(i: int, story, by_id: dict) -> tuple[dict | None, str | None]:
    if not isinstance(story, dict):
        return None, f"story {i}: not an object"
    title, summary, why = _text(story.get("title")), _text(story.get("summary")), _text(story.get("why_it_matters"))
    if not (title and summary and why):
        return None, f"story {i} '{title}': missing title, summary or why_it_matters"
    raw_ids = story.get("headline_ids")
    ids = [x for x in raw_ids if isinstance(x, str)] if isinstance(raw_ids, list) else []
    unknown = [x for x in ids if x not in by_id]
    if not ids or unknown or len(ids) != len(raw_ids):
        return None, f"story {i} '{title}': unknown or missing headline ids {unknown or raw_ids}"
    sources, seen = [], set()
    for hid in ids:
        for src in by_id[hid]["sources"]:
            if src["url"] not in seen:
                seen.add(src["url"])
                sources.append(src)
    return {
        "section": story.get("section") if story.get("section") in SECTIONS else "Other",
        "title": title,
        "summary": summary,
        "why_it_matters": why,
        "headline_ids": ids,
        "single_source": bool(story.get("single_source")),
        "sources": sources,
    }, None


def validate_briefing(raw, input_data: dict, max_stories: int = 10) -> tuple[dict | None, list[str]]:
    if not isinstance(raw, dict):
        return None, ["briefing is not a JSON object"]
    headline = _text(raw.get("headline"))
    if not headline:
        return None, ["missing headline"]
    by_id = {h["id"]: h for h in input_data["news"]}
    stories, problems = [], []
    for i, story in enumerate(raw.get("stories") if isinstance(raw.get("stories"), list) else []):
        clean, problem = _clean_story(i, story, by_id)
        if problem:
            problems.append(problem)
        else:
            stories.append(clean)
    stories = stories[:max_stories]
    if len(stories) < MIN_STORIES:
        return None, problems + [f"only {len(stories)} valid stories (need {MIN_STORIES})"]
    mover_symbols = {m["symbol"] for key in ("gainers", "losers") for m in input_data["movers"].get(key, [])}
    notes = raw.get("mover_notes") if isinstance(raw.get("mover_notes"), dict) else {}
    return {
        "date": input_data["date"],
        "headline": headline,
        "at_a_glance": _text_list(raw.get("at_a_glance"), 5),
        "market_analysis": _text(raw.get("market_analysis")),
        "mover_notes": {k: _text(v) for k, v in notes.items() if k in mover_symbols and _text(v)},
        "stories": stories,
        "watch_today": _text_list(raw.get("watch_today"), 3),
    }, problems


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="data/<date> directory")
    args = parser.parse_args(argv)
    folder = Path(args.dir)
    input_data = json.loads((folder / "input.json").read_text(encoding="utf-8"))
    clean, problems = validate_briefing(load_briefing(folder / "briefing.json"), input_data)
    for problem in problems:
        print("validate:", problem)
    valid = clean is not None
    print("valid" if valid else "invalid")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"valid={'true' if valid else 'false'}\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_validate.py -v`
Expected: 8 passed

- [ ] **Step 7: Commit**

```bash
git add prompts/writer.md briefing/validate.py tests/conftest.py tests/test_validate.py
git commit -m "Add writer prompt and briefing validation"
```

---

### Task 7: SVG charts

**Files:**
- Create: `briefing/charts.py`
- Test: `tests/test_charts.py`

**Interfaces:**
- Produces: `sparkline_svg(values: list[float], width=96, height=28) -> str` and `line_chart_svg(history: list[list], label: str, width=640, height=220) -> str`. Both return `""` for fewer than 2 values. The SVG root class is `spark up|down` / `chart up|down`, and colours come from page CSS.

- [ ] **Step 1: Write the failing tests**

`tests/test_charts.py`:
```python
from briefing.charts import line_chart_svg, sparkline_svg


def test_sparkline_trend_class_and_points():
    svg = sparkline_svg([1.0, 3.0, 2.0])
    assert svg.startswith('<svg class="spark up"')
    assert svg.count(",") == 3  # three x,y pairs
    assert 'class="spark down"' in sparkline_svg([3.0, 1.0])


def test_too_few_points_gives_empty_string():
    assert sparkline_svg([1.0]) == ""
    assert line_chart_svg([["2026-09-25", 1.0]], "x") == ""


def test_flat_series_does_not_divide_by_zero():
    assert "polyline" in sparkline_svg([5.0, 5.0, 5.0])
    assert "polyline" in line_chart_svg([["a", 5.0], ["b", 5.0]], "flat")


def test_line_chart_labels_and_escaping():
    svg = line_chart_svg([["2026-08-14", 5500.0], ["2026-09-25", 5712.3]], "S&P 500 <30d>")
    assert 'aria-label="S&amp;P 500 &lt;30d&gt;"' in svg
    assert ">5,712<" in svg and ">5,500<" in svg
    assert ">2026-08-14<" in svg and ">2026-09-25<" in svg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_charts.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `briefing/charts.py`**

```python
"""Tiny inline-SVG charts so pages need no JavaScript and archived pages keep working."""
from __future__ import annotations

import html


def _scale(values: list[float], x0: float, y0: float, w: float, h: float) -> list[tuple[float, float]]:
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = w / (len(values) - 1)
    return [(x0 + i * step, y0 + h * (1 - (v - lo) / span)) for i, v in enumerate(values)]


def _trend(values: list[float]) -> str:
    return "up" if values[-1] >= values[0] else "down"


def _pts(coords: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)


def sparkline_svg(values: list[float], width: int = 96, height: int = 28) -> str:
    if len(values) < 2:
        return ""
    coords = _scale(values, 2, 2, width - 4, height - 4)
    return (f'<svg class="spark {_trend(values)}" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" aria-hidden="true"><polyline fill="none" stroke-width="1.5" '
            f'points="{_pts(coords)}"/></svg>')


def line_chart_svg(history: list[list], label: str, width: int = 640, height: int = 220) -> str:
    values = [float(v) for _, v in history]
    if len(values) < 2:
        return ""
    left, right, top, bottom = 56, 12, 12, 28
    inner_w, inner_h = width - left - right, height - top - bottom
    coords = _scale(values, left, top, inner_w, inner_h)
    base = top + inner_h
    area = f"{left:.1f},{base:.1f} {_pts(coords)} {coords[-1][0]:.1f},{base:.1f}"
    safe = html.escape(label)
    return (
        f'<svg class="chart {_trend(values)}" viewBox="0 0 {width} {height}" role="img" aria-label="{safe}">'
        f"<title>{safe}</title>"
        f'<line class="grid" x1="{left}" y1="{top}" x2="{width - right}" y2="{top}"/>'
        f'<line class="grid" x1="{left}" y1="{base}" x2="{width - right}" y2="{base}"/>'
        f'<text class="axis" x="{left - 6}" y="{top + 4}" text-anchor="end">{max(values):,.0f}</text>'
        f'<text class="axis" x="{left - 6}" y="{base + 4}" text-anchor="end">{min(values):,.0f}</text>'
        f'<text class="axis" x="{left}" y="{height - 8}">{html.escape(str(history[0][0]))}</text>'
        f'<text class="axis" x="{width - right}" y="{height - 8}" text-anchor="end">'
        f"{html.escape(str(history[-1][0]))}</text>"
        f'<polygon class="area" points="{area}"/>'
        f'<polyline class="line" fill="none" stroke-width="2" points="{_pts(coords)}"/>'
        "</svg>"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_charts.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add briefing/charts.py tests/test_charts.py
git commit -m "Add inline SVG sparkline and line chart"
```

---

### Task 8: Page rendering, raw edition and archive

**Files:**
- Create: `briefing/render.py`, `templates/style.css`, `templates/page.html.j2`, `templates/archive.html.j2`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `load_briefing`, `validate_briefing`, `SECTIONS` (Task 6); `sparkline_svg`, `line_chart_svg` (Task 7); `GROUP_TITLES`, `fmt_value`, `fmt_change`, `direction`, `fmt_date_short` (Task 5); `load_config`, `ROOT`.
- Produces: `render_edition(data_dir: Path, site_dir: Path, cfg: dict) -> dict` with keys `context`, `is_raw`, `editions`. It writes `site/<date>/index.html`, `site/archive.html`, `site/editions.json` and `site/index.html` (redirect to the newest edition). Also `make_env()`, `build_context(input_data, briefing, is_raw, cfg) -> dict`, `build_raw_briefing(input_data, n=15) -> dict`, `banners(input_data, is_raw) -> list[str]`, `market_rows(input_data) -> list[dict]`, `reading_minutes(briefing) -> int`, `update_archive(site_dir, day, headline, env) -> list[dict]`, `write_index(site_dir, latest)`. CLI: `python -m briefing.render --date D [--data-dir] [--site-dir]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:
```python
import json

import pytest

from briefing.config import load_config
from briefing.render import render_edition


@pytest.fixture
def edition(tmp_path, sample_input, sample_briefing):
    def _make(briefing=sample_briefing, input_data=sample_input):
        data_dir = tmp_path / "data" / input_data["date"]
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "input.json").write_text(json.dumps(input_data), encoding="utf-8")
        if briefing is not None:
            (data_dir / "briefing.json").write_text(json.dumps(briefing), encoding="utf-8")
        site = tmp_path / "site"
        result = render_edition(data_dir, site, load_config())
        page = (site / input_data["date"] / "index.html").read_text(encoding="utf-8")
        return result, page, site
    return _make


def test_full_edition_page(edition):
    result, page, site = edition()
    assert result["is_raw"] is False
    assert "Rates on hold as ceasefire talks resume" in page
    assert "Saturday, 26 September 2026" in page
    assert "Why it matters:" in page and "Central bank holds matters." in page
    assert 'href="https://bbcworld.example/h001"' in page
    assert "single-source report" in page
    assert '<svg class="chart' in page            # S&P 500 30-day chart
    assert "+0.45%" in page and "+3 bp" in page   # S&P change, 10y yield change
    assert "Rose after upbeat guidance." in page  # mover note
    assert "<p>Second paragraph.</p>" in page
    assert "Core PCE Price Index m/m" in page and "NKE" in page
    assert "data as of 06:16 CEST" in page
    assert "Not investment advice" in page
    assert 'name="robots" content="noindex"' in page


def test_weekend_edition_shows_last_trading_day(edition):
    _, page, _ = edition()  # sample edition is Saturday 26 Sep, markets as of Friday
    assert "Fri 25 Sep" in page


def test_missing_market_shows_dash(edition):
    _, page, _ = edition()
    assert "Nikkei 225" in page and "–" in page


def test_raw_edition_when_briefing_missing(edition):
    result, page, _ = edition(briefing=None)
    assert result["is_raw"] is True
    assert "AI summary unavailable today" in page
    assert "Central bank holds rates steady" in page  # top headline listed as a link
    assert "Why it matters:" not in page


def test_raw_edition_when_too_few_valid_stories(edition, sample_briefing):
    for s in sample_briefing["stories"]:
        s["headline_ids"] = ["h999"]
    result, _, _ = edition(briefing=sample_briefing)
    assert result["is_raw"] is True


def test_limited_sources_banner(edition, sample_input):
    sample_input["meta"]["feeds_ok"] = 4
    _, page, _ = edition(input_data=sample_input)
    assert "Limited sources today" in page


def test_no_market_data_banner(edition, sample_input):
    for rows in sample_input["markets"].values():
        for r in rows:
            r["missing"] = True
    _, page, _ = edition(input_data=sample_input)
    assert "Market data was unavailable" in page


def test_page_escapes_headline_html(edition, sample_input, sample_briefing):
    sample_briefing["stories"][0]["title"] = "<script>alert(1)</script> & more"
    _, page, _ = edition(briefing=sample_briefing)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in page


def test_archive_and_index_track_editions(edition, sample_input):
    edition()
    later = json.loads(json.dumps(sample_input))
    later["date"] = "2026-09-27"
    _, _, site = edition(input_data=later)
    edition()  # re-render the older day: no duplicate, newest stays first
    editions = json.loads((site / "editions.json").read_text(encoding="utf-8"))
    assert [e["date"] for e in editions] == ["2026-09-27", "2026-09-26"]
    archive = (site / "archive.html").read_text(encoding="utf-8")
    assert 'href="2026-09-27/"' in archive and "Rates on hold as ceasefire talks resume" in archive
    assert 'url=2026-09-27/' in (site / "index.html").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'briefing.render'`

- [ ] **Step 3: Write `templates/style.css`**

```css
:root{--bg:#fbfaf7;--fg:#1d1d1f;--muted:#6b6b70;--line:#e4e2dc;--card:#ffffff;--accent:#1f5eff;--up:#0a7f3f;--down:#c0262d;--warn-bg:#fff4d6;--warn-fg:#7a5200}
@media (prefers-color-scheme: dark){:root{--bg:#121214;--fg:#ececef;--muted:#9a9aa2;--line:#2a2a2f;--card:#1a1a1e;--accent:#7aa2ff;--up:#4cc27f;--down:#ff6b6b;--warn-bg:#3a2f12;--warn-fg:#ffd98a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:760px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.9rem;line-height:1.25;margin:.2em 0}
h2{font-size:1.3rem;margin:2em 0 .6em;padding-bottom:.3em;border-bottom:2px solid var(--fg)}
h3{font-size:1.05rem;margin:1.4em 0 .5em}
h4{font-size:1rem;margin:0 0 .3em}
a{color:var(--accent)}
.kicker,.meta,.muted,small,.asof{color:var(--muted)}
.kicker{text-transform:uppercase;letter-spacing:.06em;font-size:.8rem;margin:0}
.banner{background:var(--warn-bg);color:var(--warn-fg);padding:10px 14px;border-radius:8px}
table{width:100%;border-collapse:collapse;font-size:.92rem}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
th{font-weight:600;color:var(--muted);font-size:.8rem}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.up{color:var(--up)}.down{color:var(--down)}.flat{color:var(--muted)}
svg.spark polyline{stroke:var(--muted)}svg.spark.up polyline{stroke:var(--up)}svg.spark.down polyline{stroke:var(--down)}
svg.chart{width:100%;height:auto}
svg.chart .line{stroke:var(--accent)}svg.chart .area{fill:var(--accent);opacity:.08}
svg.chart .grid{stroke:var(--line)}svg.chart .axis{fill:var(--muted);font-size:11px}
.movers{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.movers ul{list-style:none;padding:0;margin:0}.movers li{padding:4px 0;border-bottom:1px solid var(--line)}
.sym{font-weight:600}
.story{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:12px 0}
.why{border-left:3px solid var(--accent);padding-left:10px}
.sources{font-size:.85rem}
.tag{font-size:.7rem;font-weight:500;background:var(--warn-bg);color:var(--warn-fg);padding:2px 6px;border-radius:4px;vertical-align:middle}
.section-title{text-transform:uppercase;letter-spacing:.05em;font-size:.85rem;color:var(--muted)}
.archive li{padding:6px 0;border-bottom:1px solid var(--line);list-style:none}.archive{padding:0}
footer{margin-top:3em;border-top:1px solid var(--line);font-size:.85rem}
@media (max-width:560px){.movers{grid-template-columns:1fr}.markets th:nth-child(n+4),.markets td:nth-child(n+4){display:none}}
```

- [ ] **Step 4: Write `templates/page.html.j2`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Daily Briefing · {{ date }}</title>
<style>{% include "style.css" %}</style>
</head>
<body>
<main>
<header>
  <p class="kicker">Daily Briefing · {{ date_long }}</p>
  <h1>{{ briefing.headline }}</h1>
  <p class="meta">{{ reading_minutes }} min read · data as of {{ data_as_of }}</p>
</header>

{% for b in banners %}<p class="banner">{{ b }}</p>
{% endfor %}

{% if briefing.at_a_glance %}
<section>
  <h2>At a glance</h2>
  <ul>{% for item in briefing.at_a_glance %}<li>{{ item }}</li>{% endfor %}</ul>
</section>
{% endif %}

<section>
  <h2>Markets</h2>
  {% if spx_chart %}<figure style="margin:0">{{ spx_chart | safe }}</figure>{% endif %}
  {% for g in market_groups %}
  <h3>{{ g.title }}</h3>
  <table class="markets">
    <thead><tr><th>Market</th><th class="num">Value</th><th class="num">Change</th><th>30 days</th><th>As of</th></tr></thead>
    <tbody>
    {% for r in g.rows %}
      <tr><td>{{ r.name }}</td><td class="num">{{ r.value }}</td><td class="num {{ r.dir }}">{{ r.change }}</td><td>{{ r.spark | safe }}</td><td class="asof">{{ r.as_of_label }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
  {% endfor %}

  {% if movers.gainers or movers.losers %}
  <h3>S&amp;P 500 movers{% if movers.as_of %} · {{ movers_as_of }}{% endif %}</h3>
  <div class="movers">
  {% for label, rows in [("Top gainers", movers.gainers), ("Top losers", movers.losers)] %}
    <div>
      <h4>{{ label }}</h4>
      <ul>{% for m in rows %}<li><span class="sym">{{ m.symbol }}</span> {{ m.name }} <span class="{{ 'up' if m.change_pct > 0 else 'down' }}">{{ "%+.1f" | format(m.change_pct) }}%</span>{% if briefing.mover_notes.get(m.symbol) %}<br><small>{{ briefing.mover_notes[m.symbol] }}</small>{% endif %}</li>{% endfor %}</ul>
    </div>
  {% endfor %}
  </div>
  {% endif %}

  {% if analysis_paragraphs %}
  <h3>Analysis</h3>
  {% for para in analysis_paragraphs %}<p>{{ para }}</p>
  {% endfor %}
  {% endif %}
</section>

{% if sections %}
<section>
  <h2>World news</h2>
  {% for s in sections %}
  <h3 class="section-title">{{ s.title }}</h3>
  {% for st in s.stories %}
  <article class="story">
    <h4>{{ st.title }}{% if st.single_source %} <span class="tag">single-source report</span>{% endif %}</h4>
    <p>{{ st.summary }}</p>
    <p class="why"><strong>Why it matters:</strong> {{ st.why_it_matters }}</p>
    <p class="sources">Sources: {% for src in st.sources %}<a href="{{ src.url }}" rel="noopener">{{ src.name }}</a>{% if not loop.last %} · {% endif %}{% endfor %}</p>
  </article>
  {% endfor %}
  {% endfor %}
</section>
{% endif %}

{% if briefing.top_headlines %}
<section>
  <h2>Top headlines</h2>
  <ul>{% for h in briefing.top_headlines %}<li><a href="{{ h.sources[0].url }}" rel="noopener">{{ h.title }}</a> <small>{{ h.sources | map(attribute="name") | join(", ") }}</small></li>{% endfor %}</ul>
</section>
{% endif %}

<section>
  <h2>Today's calendar</h2>
  {% if calendar %}
  <table>
    <thead><tr><th>Time</th><th>Region</th><th>Event</th><th class="num">Forecast</th><th class="num">Previous</th></tr></thead>
    <tbody>
    {% for e in calendar %}<tr><td>{{ e.time }}</td><td>{{ e.country }}</td><td>{{ e.title }}</td><td class="num">{{ e.forecast or "–" }}</td><td class="num">{{ e.previous or "–" }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
  {% else %}<p class="muted">No major economic releases found for today.</p>{% endif %}
  {% if earnings %}<p><strong>Earnings today:</strong> {{ earnings | join(", ") }}</p>{% endif %}
</section>

{% if briefing.watch_today %}
<section>
  <h2>Watch today</h2>
  <ol>{% for w in briefing.watch_today %}<li>{{ w }}</li>{% endfor %}</ol>
</section>
{% endif %}

<footer>
  <p><a href="../archive.html">Archive of past briefings</a></p>
  <p class="muted">Market data from Yahoo Finance, calendar from ForexFactory, data as of {{ data_as_of }}. Story summaries written by Claude from the linked sources. Not investment advice.</p>
</footer>
</main>
</body>
</html>
```

- [ ] **Step 5: Write `templates/archive.html.j2`**

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Daily Briefing · Archive</title>
<style>{% include "style.css" %}</style>
</head>
<body>
<main>
  <p class="kicker">Daily Briefing</p>
  <h1>Archive</h1>
  <ul class="archive">
  {% for e in editions %}<li><a href="{{ e.date }}/">{{ e.date }}</a> · {{ e.headline }}</li>
  {% endfor %}
  </ul>
</main>
</body>
</html>
```

- [ ] **Step 6: Implement `briefing/render.py`**

```python
"""Stage 3: turn input.json + briefing.json into the web page, archive and index redirect."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

from briefing.charts import line_chart_svg, sparkline_svg
from briefing.config import ROOT, load_config
from briefing.formatting import GROUP_TITLES, direction, fmt_change, fmt_date_short, fmt_value
from briefing.validate import SECTIONS, load_briefing, validate_briefing

WORDS_PER_MINUTE = 220


def make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=lambda name: name is not None and ".html" in name,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def build_raw_briefing(input_data: dict, n: int = 15) -> dict:
    return {
        "date": input_data["date"],
        "headline": f"Markets and top headlines for {fmt_date_short(input_data['date'])}",
        "at_a_glance": [],
        "market_analysis": "",
        "mover_notes": {},
        "stories": [],
        "watch_today": [],
        "top_headlines": input_data["news"][:n],
    }


def banners(input_data: dict, is_raw: bool) -> list[str]:
    out = []
    meta = input_data["meta"]
    if meta["feeds_total"] and meta["feeds_ok"] / meta["feeds_total"] < 0.5:
        out.append(f"⚠ Limited sources today: only {meta['feeds_ok']} of {meta['feeds_total']} news feeds responded.")
    rows = [r for group in input_data["markets"].values() for r in group]
    if rows and all(r["missing"] for r in rows):
        out.append("⚠ Market data was unavailable this morning.")
    if is_raw:
        out.append("⚠ AI summary unavailable today. Showing market data and top headlines only.")
    return out


def market_rows(input_data: dict) -> list[dict]:
    groups = []
    for key, rows in input_data["markets"].items():
        items = []
        for r in rows:
            items.append({
                "name": r["name"],
                "value": "–" if r["missing"] else fmt_value(r["last"], r["unit"]),
                "change": fmt_change(r),
                "dir": direction(r),
                "as_of_label": fmt_date_short(r.get("as_of")),
                "spark": "" if r["missing"] else sparkline_svg([v for _, v in r["history"]]),
            })
        groups.append({"key": key, "title": GROUP_TITLES.get(key, key), "rows": items})
    return groups


def reading_minutes(briefing: dict) -> int:
    parts = [briefing["headline"], briefing["market_analysis"], *briefing["at_a_glance"],
             *briefing["watch_today"], *briefing["mover_notes"].values()]
    for s in briefing["stories"]:
        parts += [s["title"], s["summary"], s["why_it_matters"]]
    return max(1, round(sum(len(p.split()) for p in parts) / WORDS_PER_MINUTE))


def build_context(input_data: dict, briefing: dict, is_raw: bool, cfg: dict) -> dict:
    generated = datetime.fromisoformat(input_data["generated_at"]).astimezone(ZoneInfo(cfg["timezone"]))
    spx = next((r for r in input_data["markets"].get("us", []) if r["symbol"] == "^GSPC" and not r["missing"]), None)
    sections = [{"title": name, "stories": [s for s in briefing["stories"] if s["section"] == name]}
                for name in SECTIONS]
    return {
        "date": input_data["date"],
        "date_long": date.fromisoformat(input_data["date"]).strftime("%A, %d %B %Y"),
        "briefing": briefing,
        "is_raw": is_raw,
        "banners": banners(input_data, is_raw),
        "market_groups": market_rows(input_data),
        "spx_chart": line_chart_svg(spx["history"], "S&P 500, last 30 trading days") if spx else "",
        "movers": input_data["movers"],
        "movers_as_of": fmt_date_short(input_data["movers"].get("as_of")),
        "analysis_paragraphs": [p.strip() for p in briefing["market_analysis"].split("\n\n") if p.strip()],
        "sections": [s for s in sections if s["stories"]],
        "calendar": input_data["calendar"],
        "earnings": input_data["earnings"],
        "reading_minutes": reading_minutes(briefing),
        "data_as_of": generated.strftime("%H:%M %Z"),
        "page_url": f"{cfg['site_base_url'].rstrip('/')}/{input_data['date']}/",
    }


def update_archive(site_dir: Path, day: str, headline: str, env: Environment) -> list[dict]:
    path = site_dir / "editions.json"
    editions = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    editions = [e for e in editions if e["date"] != day] + [{"date": day, "headline": headline}]
    editions.sort(key=lambda e: e["date"], reverse=True)
    path.write_text(json.dumps(editions, ensure_ascii=False, indent=1), encoding="utf-8")
    (site_dir / "archive.html").write_text(env.get_template("archive.html.j2").render(editions=editions),
                                           encoding="utf-8")
    return editions


def write_index(site_dir: Path, latest: str) -> None:
    (site_dir / "index.html").write_text(
        f'<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex">'
        f'<title>Daily Briefing</title><meta http-equiv="refresh" content="0; url={latest}/">'
        f'<a href="{latest}/">Latest briefing</a>',
        encoding="utf-8",
    )


def render_edition(data_dir: Path, site_dir: Path, cfg: dict) -> dict:
    input_data = json.loads((data_dir / "input.json").read_text(encoding="utf-8"))
    briefing, problems = validate_briefing(load_briefing(data_dir / "briefing.json"), input_data,
                                           cfg.get("stories_max", 10))
    for problem in problems:
        print("render: dropped", problem)
    is_raw = briefing is None
    if is_raw:
        briefing = build_raw_briefing(input_data)
    env = make_env()
    ctx = build_context(input_data, briefing, is_raw, cfg)
    day = input_data["date"]
    page_dir = site_dir / day
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "index.html").write_text(env.get_template("page.html.j2").render(**ctx), encoding="utf-8")
    editions = update_archive(site_dir, day, briefing["headline"], env)
    write_index(site_dir, editions[0]["date"])
    return {"context": ctx, "is_raw": is_raw, "editions": editions}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--site-dir", default=str(ROOT / "site"))
    args = parser.parse_args(argv)
    result = render_edition(Path(args.data_dir) / args.date, Path(args.site_dir), load_config())
    kind = "RAW edition (no AI summary)" if result["is_raw"] else "full edition"
    print(f"Rendered {kind} for {args.date}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: 9 passed

- [ ] **Step 8: Commit**

```bash
git add briefing/render.py templates/ tests/test_render.py
git commit -m "Render briefing page, raw edition and archive"
```

---

### Task 9: Email rendering and sending

**Files:**
- Create: `templates/email.html.j2`, `templates/email.txt.j2`, `briefing/send_email.py`
- Modify: `briefing/render.py` (add `EMAIL_COLORS`, `subject_for`, `render_email`, and write email files inside `render_edition`)
- Test: `tests/test_email.py`

**Interfaces:**
- Consumes: `build_context` output (Task 8), `make_env`.
- Produces: `render.subject_for(date_iso: str, headline: str) -> str`, `render.render_email(ctx: dict, env) -> tuple[str, str, str]` (subject, html, text). `render_edition` also writes `data/<date>/email.html`, `email.txt`, `subject.txt`. `send_email.build_message(sender, to, subject, html, text) -> EmailMessage`, `send_email.send_message(msg, user, password, host="smtp.gmail.com", port=587, smtp_factory=smtplib.SMTP) -> None`, and CLI `python -m briefing.send_email --dir data/<date>` (env: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `BRIEFING_TO`), which writes the `data/<date>/sent` marker.

- [ ] **Step 1: Write the failing tests**

`tests/test_email.py`:
```python
import json
from email import message_from_bytes, policy

import pytest

from briefing import send_email
from briefing.config import load_config
from briefing.render import render_edition, subject_for


def test_subject_format():
    assert subject_for("2026-09-26", "Rates on hold") == "☀ Sep 26 · Rates on hold"


@pytest.fixture
def rendered(tmp_path, sample_input, sample_briefing):
    data_dir = tmp_path / "data" / "2026-09-26"
    data_dir.mkdir(parents=True)
    (data_dir / "input.json").write_text(json.dumps(sample_input), encoding="utf-8")
    (data_dir / "briefing.json").write_text(json.dumps(sample_briefing), encoding="utf-8")
    cfg = load_config()
    cfg["site_base_url"] = "https://me.github.io/daily-briefing/"
    render_edition(data_dir, tmp_path / "site", cfg)
    return data_dir


def test_email_files_written(rendered):
    html = (rendered / "email.html").read_text(encoding="utf-8")
    text = (rendered / "email.txt").read_text(encoding="utf-8")
    subject = (rendered / "subject.txt").read_text(encoding="utf-8")
    assert subject == "☀ Sep 26 · Rates on hold as ceasefire talks resume"
    assert 'href="https://me.github.io/daily-briefing/2026-09-26/"' in html
    assert "Read the full briefing" in html and "Central bank holds matters." in html
    assert "<svg" not in html  # no charts in email
    assert "S&P 500: 5,712.30 (+0.45%)" in text
    assert "Read the full briefing: https://me.github.io/daily-briefing/2026-09-26/" in text


def test_build_message_handles_non_ascii():
    msg = send_email.build_message("me@gmail.com", "me@gmail.com", "☀ Sep 26 · Zölle & Märkte",
                                   "<p>Hallo</p>", "Hallo")
    parsed = message_from_bytes(msg.as_bytes(), policy=policy.default)
    assert parsed["Subject"] == "☀ Sep 26 · Zölle & Märkte"
    assert parsed.is_multipart()
    assert {p.get_content_type() for p in parsed.iter_parts()} == {"text/plain", "text/html"}


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.calls = [("connect", host, port)]
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, msg):
        self.calls.append(("send", msg["To"]))


def test_send_message_uses_starttls_and_login():
    msg = send_email.build_message("me@gmail.com", "you@example.com", "s", "<p>h</p>", "t")
    send_email.send_message(msg, "me@gmail.com", "app-pass", smtp_factory=FakeSMTP)
    assert FakeSMTP.instances[-1].calls == [
        ("connect", "smtp.gmail.com", 587), ("starttls",), ("login", "me@gmail.com", "app-pass"),
        ("send", "you@example.com"),
    ]


def test_cli_sends_and_writes_marker(rendered, monkeypatch):
    sent = []
    monkeypatch.setattr(send_email, "send_message", lambda msg, user, password: sent.append(msg["Subject"]))
    monkeypatch.setenv("GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-pass")
    monkeypatch.setenv("BRIEFING_TO", "me@gmail.com")
    send_email.main(["--dir", str(rendered)])
    assert sent == ["☀ Sep 26 · Rates on hold as ceasefire talks resume"]
    assert (rendered / "sent").exists()


def test_cli_fails_without_secrets(rendered, monkeypatch):
    for key in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "BRIEFING_TO"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SystemExit, match="GMAIL_ADDRESS"):
        send_email.main(["--dir", str(rendered)])
    assert not (rendered / "sent").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_email.py -v`
Expected: FAIL with `ImportError: cannot import name 'send_email'` (or `subject_for`)

- [ ] **Step 3: Write `templates/email.html.j2`**

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{ subject }}</title></head>
<body style="margin:0;padding:0;background:#f4f3ef;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f3ef;"><tr><td align="center" style="padding:16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:10px;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1d1d1f;">
<tr><td style="padding:24px 24px 8px;">
  <p style="margin:0;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#6b6b70;">Daily Briefing · {{ date_long }}</p>
  <h1 style="margin:6px 0 0;font-size:22px;line-height:1.3;">{{ briefing.headline }}</h1>
</td></tr>
{% for b in banners %}
<tr><td style="padding:8px 24px;"><p style="margin:0;padding:10px 12px;background:#fff4d6;color:#7a5200;border-radius:6px;font-size:14px;">{{ b }}</p></td></tr>
{% endfor %}
{% if briefing.at_a_glance %}
<tr><td style="padding:12px 24px;">
  <h2 style="font-size:16px;margin:0 0 6px;">At a glance</h2>
  <ul style="margin:0;padding-left:20px;font-size:15px;line-height:1.5;">{% for item in briefing.at_a_glance %}<li style="margin-bottom:4px;">{{ item }}</li>{% endfor %}</ul>
</td></tr>
{% endif %}
<tr><td style="padding:12px 24px;">
  <h2 style="font-size:16px;margin:0 0 6px;">Markets</h2>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;border-collapse:collapse;">
  {% for g in market_groups %}{% for r in g.rows %}
    <tr>
      <td style="padding:4px 0;border-bottom:1px solid #eeeeee;">{{ r.name }}</td>
      <td align="right" style="padding:4px 0;border-bottom:1px solid #eeeeee;">{{ r.value }}</td>
      <td align="right" style="padding:4px 0 4px 10px;border-bottom:1px solid #eeeeee;color:{{ colors[r.dir] }};white-space:nowrap;">{{ r.change }}</td>
    </tr>
  {% endfor %}{% endfor %}
  </table>
</td></tr>
{% if briefing.stories %}
<tr><td style="padding:12px 24px;">
  <h2 style="font-size:16px;margin:0 0 6px;">Top stories</h2>
  {% for st in briefing.stories %}<p style="margin:0 0 10px;font-size:15px;line-height:1.45;"><strong>{{ st.title }}</strong><br><span style="color:#444444;">{{ st.why_it_matters }}</span></p>
  {% endfor %}
</td></tr>
{% endif %}
{% if briefing.top_headlines %}
<tr><td style="padding:12px 24px;">
  <h2 style="font-size:16px;margin:0 0 6px;">Top headlines</h2>
  {% for h in briefing.top_headlines %}<p style="margin:0 0 8px;font-size:15px;"><a href="{{ h.sources[0].url }}" style="color:#1f5eff;">{{ h.title }}</a></p>
  {% endfor %}
</td></tr>
{% endif %}
<tr><td align="center" style="padding:16px 24px 28px;">
  <a href="{{ page_url }}" style="display:inline-block;background:#1f5eff;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:600;">Read the full briefing →</a>
</td></tr>
<tr><td style="padding:0 24px 20px;font-size:12px;color:#6b6b70;">Data as of {{ data_as_of }}. Not investment advice.</td></tr>
</table>
</td></tr></table>
</body>
</html>
```

- [ ] **Step 4: Write `templates/email.txt.j2`**

```
{{ briefing.headline }}
Daily Briefing · {{ date_long }}
{% for b in banners %}
{{ b }}
{% endfor %}
{% if briefing.at_a_glance %}

AT A GLANCE
{% for item in briefing.at_a_glance %}
- {{ item }}
{% endfor %}
{% endif %}

MARKETS
{% for g in market_groups %}{% for r in g.rows %}
{{ r.name }}: {{ r.value }} ({{ r.change }})
{% endfor %}{% endfor %}
{% if briefing.stories %}

TOP STORIES
{% for st in briefing.stories %}
- {{ st.title }}: {{ st.why_it_matters }}
{% endfor %}
{% endif %}
{% if briefing.top_headlines %}

TOP HEADLINES
{% for h in briefing.top_headlines %}
- {{ h.title }} ({{ h.sources[0].url }})
{% endfor %}
{% endif %}

Read the full briefing: {{ page_url }}
Data as of {{ data_as_of }}. Not investment advice.
```

- [ ] **Step 5: Add email rendering to `briefing/render.py`**

Add below `WORDS_PER_MINUTE = 220`:
```python
EMAIL_COLORS = {"up": "#0a7f3f", "down": "#c0262d", "flat": "#6b6b70"}
```

Add after `write_index`:
```python
def subject_for(date_iso: str, headline: str) -> str:
    d = date.fromisoformat(date_iso)
    return f"☀ {d:%b} {d.day} · {headline}"


def render_email(ctx: dict, env: Environment) -> tuple[str, str, str]:
    subject = subject_for(ctx["date"], ctx["briefing"]["headline"])
    html = env.get_template("email.html.j2").render(subject=subject, colors=EMAIL_COLORS, **ctx)
    text = env.get_template("email.txt.j2").render(**ctx)
    return subject, html, text
```

In `render_edition`, directly before `return {"context": ctx, ...}`, add:
```python
    subject, email_html, email_text = render_email(ctx, env)
    (data_dir / "subject.txt").write_text(subject, encoding="utf-8")
    (data_dir / "email.html").write_text(email_html, encoding="utf-8")
    (data_dir / "email.txt").write_text(email_text, encoding="utf-8")
```

- [ ] **Step 6: Implement `briefing/send_email.py`**

```python
"""Sends the rendered email through Gmail SMTP and records a 'sent' marker for the day."""
from __future__ import annotations

import argparse
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

REQUIRED_ENV = ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "BRIEFING_TO")


def build_message(sender: str, to: str, subject: str, html: str, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"Daily Briefing <{sender}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def send_message(msg: EmailMessage, user: str, password: str, host: str = "smtp.gmail.com",
                 port: int = 587, smtp_factory=smtplib.SMTP) -> None:
    with smtp_factory(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="data/<date> directory")
    args = parser.parse_args(argv)
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")
    folder = Path(args.dir)
    msg = build_message(
        os.environ["GMAIL_ADDRESS"],
        os.environ["BRIEFING_TO"],
        (folder / "subject.txt").read_text(encoding="utf-8").strip(),
        (folder / "email.html").read_text(encoding="utf-8"),
        (folder / "email.txt").read_text(encoding="utf-8"),
    )
    send_message(msg, os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])
    (folder / "sent").write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    print(f"Sent: {msg['Subject']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run all tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -v`
Expected: all tests pass (Task 8's render tests still pass after the `render_edition` change).

- [ ] **Step 8: Commit**

```bash
git add templates/email.html.j2 templates/email.txt.j2 briefing/render.py briefing/send_email.py tests/test_email.py
git commit -m "Render and send the email digest"
```

---

### Task 10: Send-window gate

**Files:**
- Create: `briefing/gate.py`
- Test: `tests/test_gate.py`

**Interfaces:**
- Consumes: `edition_date`, `local_now` (Task 1), `load_config`, `ROOT`.
- Produces: `should_run(now_utc: datetime, tz: str, send_hour: int, data_dir: Path, enabled: bool, force: bool = False) -> tuple[bool, str, str]` (run?, edition date, reason). CLI `python -m briefing.gate [--force]` appends `run=true|false` and `date=YYYY-MM-DD` to `$GITHUB_OUTPUT`.

- [ ] **Step 1: Write the failing tests**

`tests/test_gate.py`:
```python
from datetime import datetime, timezone

from briefing.gate import main, should_run

TZ = "Europe/Berlin"


def utc(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def run(now, tmp_path, enabled=True, force=False):
    return should_run(now, TZ, 6, tmp_path, enabled, force)


def test_summer_first_cron_runs_second_skips_after_send(tmp_path):
    ok, day, _ = run(utc(2026, 9, 26, 4, 15), tmp_path)  # 06:15 CEST
    assert ok and day == "2026-09-26"
    (tmp_path / day).mkdir()
    (tmp_path / day / "sent").write_text("x")
    ok, _, reason = run(utc(2026, 9, 26, 5, 15), tmp_path)  # 07:15 CEST
    assert not ok and reason == "already sent today"


def test_second_run_skips_after_send(tmp_path):
    (tmp_path / "2026-01-15").mkdir()
    (tmp_path / "2026-01-15" / "sent").write_text("x")
    assert run(utc(2026, 1, 15, 5, 40), tmp_path)[0] is False


def test_winter_first_cron_too_early_second_runs(tmp_path):
    assert run(utc(2026, 1, 15, 4, 15), tmp_path)[0] is False  # 05:15 CET
    assert run(utc(2026, 1, 15, 5, 15), tmp_path)[0] is True   # 06:15 CET


def test_dst_switch_days(tmp_path):
    # 29 Mar 2026: clocks jump to CEST at 01:00 UTC -> 04:15 UTC is 06:15 local
    assert run(utc(2026, 3, 29, 4, 15), tmp_path)[0] is True
    # 25 Oct 2026: back to CET at 01:00 UTC -> 04:15 UTC is 05:15, 05:15 UTC is 06:15
    assert run(utc(2026, 10, 25, 4, 15), tmp_path)[0] is False
    assert run(utc(2026, 10, 25, 5, 15), tmp_path)[0] is True


def test_late_run_still_sends(tmp_path):
    ok, _, _ = run(utc(2026, 9, 26, 5, 50), tmp_path)  # 07:50 CEST, GitHub ran very late
    assert ok
    assert run(utc(2026, 9, 26, 6, 5), tmp_path)[0] is False  # 08:05 is too late


def test_disabled_schedule_and_force(tmp_path):
    ok, _, reason = run(utc(2026, 9, 26, 4, 15), tmp_path, enabled=False)
    assert not ok and "disabled" in reason
    (tmp_path / "2026-09-26").mkdir()
    (tmp_path / "2026-09-26" / "sent").write_text("x")
    ok, day, reason = run(utc(2026, 9, 26, 13, 0), tmp_path, enabled=False, force=True)
    assert ok and day == "2026-09-26" and reason == "forced"


def test_cli_writes_outputs(tmp_path, monkeypatch):
    out = tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    main(["--force", "--data-dir", str(tmp_path)])
    lines = out.read_text().splitlines()
    assert lines[0] == "run=true" and lines[1].startswith("date=20")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest tests/test_gate.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `briefing/gate.py`**

```python
"""Decides whether this workflow run should produce today's edition.

GitHub cron is UTC and often late, so the workflow fires at 04:15 and 05:15 UTC and this gate
accepts any run between send_hour:00 and send_hour+2:00 local time that hasn't been sent yet.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from briefing.config import ROOT, load_config
from briefing.dates import edition_date, local_now


def should_run(now_utc: datetime, tz: str, send_hour: int, data_dir: Path, enabled: bool,
               force: bool = False) -> tuple[bool, str, str]:
    day = edition_date(now_utc, tz)
    if force:
        return True, day, "forced"
    if not enabled:
        return False, day, "schedule disabled in config.yaml (schedule_enabled: false)"
    hour = local_now(now_utc, tz).hour
    if not send_hour <= hour < send_hour + 2:
        return False, day, f"local hour {hour} is outside the send window"
    if (data_dir / day / "sent").exists():
        return False, day, "already sent today"
    return True, day, "in send window"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    args = parser.parse_args(argv)
    cfg = load_config()
    ok, day, reason = should_run(datetime.now(timezone.utc), cfg["timezone"], cfg["send_hour"],
                                 Path(args.data_dir), cfg["schedule_enabled"], args.force)
    print(f"{'RUN' if ok else 'SKIP'} {day}: {reason}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"run={'true' if ok else 'false'}\ndate={day}\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_gate.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add briefing/gate.py tests/test_gate.py
git commit -m "Add send-window gate for DST and late runs"
```

---

### Task 11: Feed check and local dry run

**Files:**
- Create: `scripts/check_feeds.py`, `scripts/dry_run.py`
- Modify: `config.yaml` (remove feeds that fail the check)

**Interfaces:**
- Consumes: `load_config`, `fetch_url`, `parse_feed`, `build_input`, `write_input`, `edition_date`, `render_edition`, `validate_briefing`, `load_briefing`, `ROOT`.
- Produces: `python -m scripts.check_feeds` (a report) and `python -m scripts.dry_run [--no-claude]`, which writes `build/data/<date>/` and `build/site/` and opens the page.

- [ ] **Step 1: Write `scripts/check_feeds.py`**

```python
"""Report which configured RSS feeds work right now: python -m scripts.check_feeds"""
from __future__ import annotations

from datetime import datetime, timezone

from briefing.collect_news import fetch_url, parse_feed
from briefing.config import load_config


def main() -> None:
    cfg = load_config()
    now = datetime.now(timezone.utc)
    bad = 0
    for feed in cfg["feeds"]:
        try:
            items = parse_feed(feed, fetch_url(feed["url"]), now, cfg.get("lookback_hours", 24))
            status = f"OK   {len(items):3d} recent items" if items else "EMPTY no recent items"
            bad += 0 if items else 1
        except Exception as exc:
            status = f"FAIL {exc}"
            bad += 1
        print(f"{feed['name']:<20} {status}")
    print(f"\n{len(cfg['feeds']) - bad}/{len(cfg['feeds'])} feeds working")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the feed check and prune `config.yaml`**

Run: `.venv/Scripts/python -m scripts.check_feeds`
Expected: one line per feed. Remove every `FAIL` or `EMPTY` feed from `config.yaml` (run it twice a few minutes apart first, so a temporary blip doesn't remove a good feed). At least 12 feeds must remain, and they must include some from each of world, business and markets. If fewer remain, tell the owner before continuing.

- [ ] **Step 3: Write `scripts/dry_run.py`**

```python
"""Run the whole pipeline locally into build/ without publishing or emailing.

python -m scripts.dry_run             # uses your local `claude` login
python -m scripts.dry_run --no-claude # skip the AI step and preview the raw edition
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import webbrowser
from datetime import datetime, timezone

from briefing.collect import build_input, write_input
from briefing.config import ROOT, load_config
from briefing.dates import edition_date
from briefing.render import render_edition
from briefing.validate import load_briefing, validate_briefing

BUILD = ROOT / "build"


def task_prompt(input_rel: str, output_rel: str) -> str:
    return (f"Follow the instructions in prompts/writer.md.\n"
            f"Input file: {input_rel}\nOutput file: {output_rel}")


def run_claude(cfg: dict, day: str) -> None:
    exe = shutil.which("claude")
    if not exe:
        print("claude CLI not found, skipping the AI step (raw edition)")
        return
    prompt = task_prompt(f"build/data/{day}/writer_input.md", f"build/data/{day}/briefing.json")
    print(f"Running Claude ({cfg['model']})...")
    subprocess.run([exe, "-p", prompt, "--model", cfg["model"], "--max-turns", "6",
                    "--allowedTools", "Read,Write"], cwd=ROOT, check=False, timeout=600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-claude", action="store_true")
    args = parser.parse_args()
    cfg = load_config()
    now = datetime.now(timezone.utc)
    day = edition_date(now, cfg["timezone"])
    data_dir = BUILD / "data" / day

    print(f"Collecting for {day}...")
    data = build_input(cfg, now, day)
    write_input(data, data_dir)
    meta = data["meta"]
    print(f"{len(data['news'])} headlines from {meta['feeds_ok']}/{meta['feeds_total']} feeds")
    for err in meta["errors"]:
        print("  -", err)

    if not args.no_claude:
        run_claude(cfg, day)
        _, problems = validate_briefing(load_briefing(data_dir / "briefing.json"), data)
        for p in problems:
            print("  validation:", p)

    result = render_edition(data_dir, BUILD / "site", cfg)
    page = BUILD / "site" / day / "index.html"
    print(f"{'RAW' if result['is_raw'] else 'FULL'} edition → {page}")
    print("Email subject:", (data_dir / "subject.txt").read_text(encoding="utf-8"))
    webbrowser.open(page.as_uri())
    webbrowser.open((data_dir / "email.html").as_uri())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Dry run without Claude (checks live data and rendering)**

Run: `.venv/Scripts/python -m scripts.dry_run --no-claude`
Expected: prints a headline count (≥100) and a `RAW edition → ...` path, then opens the page and email preview in the browser. Check that:
- market tables show real values with an "As of" date
- the S&P 500 chart and sparklines are drawn
- the calendar shows today's events or "No major economic releases"
- the page has no horizontal scrolling at phone width (browser dev tools, 375 px)
- dark mode works

Fix any adapter problem (`yf_history`, `yf_earnings_date`) found here, add a test for it, and commit.

- [ ] **Step 5: Dry run with Claude (uses the owner's subscription, about 1 briefing's worth)**

Run: `.venv/Scripts/python -m scripts.dry_run`
Expected: Claude writes `build/data/<date>/briefing.json`, there are no validation errors (or only a few dropped stories), and a `FULL edition` page opens with 8–10 stories, each with source links. Read it with the owner. Check for anything unsupported by the sources, any advice, or any loaded tone, and tune `prompts/writer.md` if needed. Re-run until the owner is happy.

- [ ] **Step 6: Run the full test suite, then commit**

Run: `.venv/Scripts/python -m pytest -v`
Expected: all pass.

```bash
git add scripts/check_feeds.py scripts/dry_run.py config.yaml prompts/writer.md
git commit -m "Add feed check and local dry run; prune dead feeds"
```

---

### Task 12: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/daily.yml`
- Test: `tests/test_workflow.py`

**Interfaces:**
- Consumes: CLIs `briefing.gate`, `briefing.collect`, `briefing.validate`, `briefing.render`, `briefing.send_email`. Secrets: `CLAUDE_CODE_OAUTH_TOKEN`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `BRIEFING_TO`.
- Produces: the scheduled pipeline.

- [ ] **Step 1: Write the failing test**

`tests/test_workflow.py`:
```python
import yaml

from briefing.config import ROOT, load_config

WORKFLOW = ROOT / ".github" / "workflows" / "daily.yml"


def load():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return wf, wf.get("on", wf.get(True))  # PyYAML reads the bare key `on` as True


def claude_steps(wf):
    return [s for s in wf["jobs"]["briefing"]["steps"] if s.get("uses", "").startswith("anthropics/claude-code-action")]


def test_schedule_covers_cet_and_cest():
    _, on = load()
    assert {c["cron"] for c in on["schedule"]} == {"15 4 * * *", "15 5 * * *"}
    assert "workflow_dispatch" in on


def test_claude_steps_use_subscription_and_config_model():
    wf, _ = load()
    steps = claude_steps(wf)
    assert len(steps) == 2  # first attempt + retry
    model = load_config()["model"]
    for s in steps:
        assert s["with"]["claude_code_oauth_token"] == "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"
        assert "anthropic_api_key" not in s["with"]
        assert f"--model {model}" in s["with"]["claude_args"]
        assert '--allowedTools "Read,Write"' in s["with"]["claude_args"]
        assert "--max-turns 6" in s["with"]["claude_args"]
        assert s["timeout-minutes"] == 10 and s["continue-on-error"] is True


def test_only_site_is_published_and_secrets_are_referenced():
    wf, _ = load()
    steps = wf["jobs"]["briefing"]["steps"]
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-pages-artifact"))
    assert upload["with"]["path"] == "site"
    email = next(s for s in steps if "briefing.send_email" in s.get("run", ""))
    assert set(email["env"]) == {"GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "BRIEFING_TO"}
    assert wf["concurrency"]["cancel-in-progress"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_workflow.py -v`
Expected: FAIL with `FileNotFoundError` for `daily.yml`

- [ ] **Step 3: Write `.github/workflows/daily.yml`**

```yaml
name: Daily Briefing

on:
  schedule:
    # 04:15 and 05:15 UTC. One of them is 06:15 in Berlin in both summer (CEST) and winter (CET).
    # briefing.gate lets through only a run in the 06:00–07:59 Berlin window that hasn't been sent yet.
    - cron: "15 4 * * *"
    - cron: "15 5 * * *"
  workflow_dispatch:
    inputs:
      force:
        description: "Run now, even outside the send window, if already sent, or while the schedule is disabled"
        type: boolean
        default: true

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: daily-briefing
  cancel-in-progress: false

jobs:
  briefing:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment:
      name: github-pages
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Check send window
        id: gate
        run: python -m briefing.gate ${{ inputs.force && '--force' || '' }}

      - name: Collect news and market data
        if: steps.gate.outputs.run == 'true'
        run: python -m briefing.collect --date ${{ steps.gate.outputs.date }}

      - name: Write briefing with Claude
        if: steps.gate.outputs.run == 'true'
        continue-on-error: true
        timeout-minutes: 10
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          prompt: |
            Follow the instructions in prompts/writer.md.
            Input file: data/${{ steps.gate.outputs.date }}/writer_input.md
            Output file: data/${{ steps.gate.outputs.date }}/briefing.json
          claude_args: |
            --model claude-sonnet-5
            --max-turns 6
            --allowedTools "Read,Write"

      - name: Check Claude's output
        id: check
        if: steps.gate.outputs.run == 'true'
        run: python -m briefing.validate --dir data/${{ steps.gate.outputs.date }}

      - name: Remove invalid output before retry
        if: steps.gate.outputs.run == 'true' && steps.check.outputs.valid != 'true'
        run: rm -f data/${{ steps.gate.outputs.date }}/briefing.json

      - name: Write briefing with Claude (retry)
        if: steps.gate.outputs.run == 'true' && steps.check.outputs.valid != 'true'
        continue-on-error: true
        timeout-minutes: 10
        uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          prompt: |
            Follow the instructions in prompts/writer.md.
            Input file: data/${{ steps.gate.outputs.date }}/writer_input.md
            Output file: data/${{ steps.gate.outputs.date }}/briefing.json
          claude_args: |
            --model claude-sonnet-5
            --max-turns 6
            --allowedTools "Read,Write"

      - name: Render page and email (raw edition if Claude's output is unusable)
        if: steps.gate.outputs.run == 'true'
        run: python -m briefing.render --date ${{ steps.gate.outputs.date }}

      - name: Commit edition
        if: steps.gate.outputs.run == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data site
          git commit -m "Briefing ${{ steps.gate.outputs.date }}" || echo "Nothing to commit"
          git push

      - name: Upload site
        if: steps.gate.outputs.run == 'true'
        uses: actions/upload-pages-artifact@v3
        with:
          path: site

      - name: Deploy to GitHub Pages
        if: steps.gate.outputs.run == 'true'
        uses: actions/deploy-pages@v4

      - name: Send email
        if: steps.gate.outputs.run == 'true'
        env:
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          BRIEFING_TO: ${{ secrets.BRIEFING_TO }}
        run: python -m briefing.send_email --dir data/${{ steps.gate.outputs.date }}

      - name: Record that the email was sent
        if: steps.gate.outputs.run == 'true'
        run: |
          git add data/${{ steps.gate.outputs.date }}/sent
          git commit -m "Sent briefing ${{ steps.gate.outputs.date }}"
          git push
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -v`
Expected: all pass, including 3 in `tests/test_workflow.py`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/daily.yml tests/test_workflow.py
git commit -m "Add scheduled GitHub Actions workflow"
```

---

### Task 13: Setup and go-live (with the owner)

The owner does every step that involves an account, a password or a token, and Claude guides. Claude never types, sees or stores secrets.

**Files:**
- Modify: `config.yaml` (`site_base_url`, later `schedule_enabled: true`)
- Modify: `C:\Users\nitsc\Desktop\Brain\Brain\Projects\Daily Briefing.md` (tick tasks)

- [ ] **Step 1: GitHub repo (owner)**

The owner signs in or signs up at github.com, then creates a new **public** repository named `daily-briefing` with no README, .gitignore or license, so it's empty. Ask the owner for their GitHub username.

- [ ] **Step 2: Set the site URL and push**

In `config.yaml`, set `site_base_url: https://<username>.github.io/daily-briefing`. Then:
```bash
git add config.yaml
git commit -m "Set site URL"
git remote add origin https://github.com/<username>/daily-briefing.git
git push -u origin main
```
Expected: Git Credential Manager (bundled with Git for Windows) opens a browser window for the owner to sign in to GitHub, then the push succeeds.

- [ ] **Step 3: Claude subscription token (owner)**

The owner runs this in their own terminal:
```bash
claude setup-token
```
Then, in the repo on GitHub: Settings → Secrets and variables → Actions → New repository secret, named `CLAUDE_CODE_OAUTH_TOKEN`, with the token pasted as the value.

- [ ] **Step 4: Gmail app password (owner)**

The owner turns on 2-Step Verification in their Google account (if it isn't already on), creates an app password at myaccount.google.com/apppasswords named "Daily Briefing", and adds three repository secrets:
- `GMAIL_ADDRESS`: the Gmail address that sends
- `GMAIL_APP_PASSWORD`: the 16-character app password
- `BRIEFING_TO`: the address that receives the briefing (can be the same)

- [ ] **Step 5: Turn on GitHub Pages (owner)**

Settings → Pages → Build and deployment → Source: **GitHub Actions**.

- [ ] **Step 6: First live run**

GitHub → Actions → Daily Briefing → Run workflow (force: on). Expected: every step is green within about 5 minutes, the email arrives, and the button opens `https://<username>.github.io/daily-briefing/<date>/`. If a step fails, read its log, fix the cause with a test where it's code, commit, push and re-run. Do one more forced run on another day, or after tuning, and have the owner read both editions.

- [ ] **Step 7: Enable the schedule**

In `config.yaml`, set `schedule_enabled: true`.
```bash
git add config.yaml
git commit -m "Enable daily schedule"
git push
```
Expected: the next morning, the 04:15/05:15 UTC runs produce exactly one email before 07:00 Berlin time. Check the Actions tab the next day: one run says `RUN`, and the other says `SKIP ... already sent today` or `outside the send window`.

- [ ] **Step 8: Update the project note**

In `Brain/Projects/Daily Briefing.md`, tick "Review the written spec", "Write the implementation plan", "Build it", "One-time setup" and "First live runs, then turn on the daily schedule", and add the site URL under **Where**.

- [ ] **Step 9: Tell the owner about maintenance**

- `python -m scripts.update_sp500` every few months (index changes).
- `python -m scripts.check_feeds` if "Limited sources" banners start appearing.
- If GitHub ever emails "scheduled workflow disabled due to inactivity", click **Enable workflow** on the Actions tab.
- `claude setup-token` tokens can expire. If runs start producing raw editions every day, generate a new token and update the secret.
