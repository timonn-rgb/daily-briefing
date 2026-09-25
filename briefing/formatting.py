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
