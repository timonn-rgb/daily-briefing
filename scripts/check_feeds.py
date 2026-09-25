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
