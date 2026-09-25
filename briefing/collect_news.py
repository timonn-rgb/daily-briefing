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
