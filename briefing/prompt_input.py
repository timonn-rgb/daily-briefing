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
