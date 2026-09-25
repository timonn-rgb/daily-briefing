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
