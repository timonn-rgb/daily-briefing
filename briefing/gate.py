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
