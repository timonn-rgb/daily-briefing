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
