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
