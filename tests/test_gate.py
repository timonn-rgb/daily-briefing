from datetime import datetime, timezone

from briefing.gate import main, should_run

TZ = "Europe/Berlin"


def utc(y, m, d, h, mi):
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc)


def run(now, tmp_path, enabled=True, force=False):
    return should_run(now, TZ, 6, tmp_path, enabled, force)


def test_summer_first_cron_runs_second_skips_after_send(tmp_path):
    ok, day, _ = run(utc(2026, 9, 26, 4, 15), tmp_path)  # 06:15 CEST
    assert ok and day == "2026-09-26"
    (tmp_path / day).mkdir()
    (tmp_path / day / "sent").write_text("x")
    ok, _, reason = run(utc(2026, 9, 26, 5, 15), tmp_path)  # 07:15 CEST
    assert not ok and reason == "already sent today"


def test_second_run_skips_after_send(tmp_path):
    (tmp_path / "2026-01-15").mkdir()
    (tmp_path / "2026-01-15" / "sent").write_text("x")
    assert run(utc(2026, 1, 15, 5, 40), tmp_path)[0] is False


def test_winter_first_cron_too_early_second_runs(tmp_path):
    assert run(utc(2026, 1, 15, 4, 15), tmp_path)[0] is False  # 05:15 CET
    assert run(utc(2026, 1, 15, 5, 15), tmp_path)[0] is True   # 06:15 CET


def test_dst_switch_days(tmp_path):
    # 29 Mar 2026: clocks jump to CEST at 01:00 UTC -> 04:15 UTC is 06:15 local
    assert run(utc(2026, 3, 29, 4, 15), tmp_path)[0] is True
    # 25 Oct 2026: back to CET at 01:00 UTC -> 04:15 UTC is 05:15, 05:15 UTC is 06:15
    assert run(utc(2026, 10, 25, 4, 15), tmp_path)[0] is False
    assert run(utc(2026, 10, 25, 5, 15), tmp_path)[0] is True


def test_late_run_still_sends(tmp_path):
    ok, _, _ = run(utc(2026, 9, 26, 5, 50), tmp_path)  # 07:50 CEST, GitHub ran very late
    assert ok
    assert run(utc(2026, 9, 26, 6, 5), tmp_path)[0] is False  # 08:05 is too late


def test_disabled_schedule_and_force(tmp_path):
    ok, _, reason = run(utc(2026, 9, 26, 4, 15), tmp_path, enabled=False)
    assert not ok and "disabled" in reason
    (tmp_path / "2026-09-26").mkdir()
    (tmp_path / "2026-09-26" / "sent").write_text("x")
    ok, day, reason = run(utc(2026, 9, 26, 13, 0), tmp_path, enabled=False, force=True)
    assert ok and day == "2026-09-26" and reason == "forced"


def test_cli_writes_outputs(tmp_path, monkeypatch):
    out = tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    main(["--force", "--data-dir", str(tmp_path)])
    lines = out.read_text().splitlines()
    assert lines[0] == "run=true" and lines[1].startswith("date=20")
