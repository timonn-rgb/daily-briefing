from datetime import datetime, timezone

from briefing.dates import edition_date, local_now


def test_edition_date_rolls_over_at_berlin_midnight():
    late_utc = datetime(2026, 9, 25, 22, 30, tzinfo=timezone.utc)  # 00:30 CEST on the 26th
    assert edition_date(late_utc, "Europe/Berlin") == "2026-09-26"


def test_local_now_winter_offset():
    now = datetime(2026, 1, 15, 5, 15, tzinfo=timezone.utc)
    assert local_now(now, "Europe/Berlin").hour == 6
