import json
from datetime import datetime, timezone

from briefing.collect import build_input, write_input

NOW = datetime(2026, 9, 26, 4, 15, tzinfo=timezone.utc)


def fakes():
    return dict(
        news=lambda cfg, now: ([{"id": "h001", "title": "T", "summary": "", "published": None,
                                 "region": "world", "sources": [{"name": "A", "url": "u"}]}],
                               {"feeds_ok": 1, "feeds_total": 2, "errors": ["feed B: down"]}),
        markets=lambda cfg: {"groups": {"us": []}, "errors": ["market X: no data"]},
        movers=lambda cfg: {"as_of": None, "gainers": [], "losers": []},
        calendar=lambda cfg, day: ([], ["calendar: down"]),
        earnings=lambda symbols, day: (["NKE"], []),
    )


def test_build_input_combines_stages_and_errors():
    cfg = {"timezone": "Europe/Berlin", "earnings_watch": ["NKE"]}
    data = build_input(cfg, NOW, "2026-09-26", **fakes())
    assert data["date"] == "2026-09-26"
    assert data["generated_at"] == "2026-09-26T04:15:00+00:00"
    assert data["earnings"] == ["NKE"]
    assert data["meta"] == {"feeds_ok": 1, "feeds_total": 2,
                            "errors": ["feed B: down", "market X: no data", "calendar: down"]}


def test_write_input_writes_files_and_clears_stale_briefing(tmp_path):
    cfg = {"timezone": "Europe/Berlin", "earnings_watch": []}
    data = build_input(cfg, NOW, "2026-09-26", **fakes())
    out = tmp_path / "2026-09-26"
    out.mkdir()
    (out / "briefing.json").write_text("{}", encoding="utf-8")  # left over from an earlier run
    write_input(data, out)
    assert json.loads((out / "input.json").read_text(encoding="utf-8"))["date"] == "2026-09-26"
    assert "h001 | A | unknown | T" in (out / "writer_input.md").read_text(encoding="utf-8")
    assert not (out / "briefing.json").exists()
