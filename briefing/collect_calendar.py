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
