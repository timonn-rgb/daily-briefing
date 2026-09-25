import json

import pytest

from briefing.config import load_config
from briefing.render import render_edition


@pytest.fixture
def edition(tmp_path, sample_input, sample_briefing):
    def _make(briefing=sample_briefing, input_data=sample_input):
        data_dir = tmp_path / "data" / input_data["date"]
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "input.json").write_text(json.dumps(input_data), encoding="utf-8")
        if briefing is not None:
            (data_dir / "briefing.json").write_text(json.dumps(briefing), encoding="utf-8")
        site = tmp_path / "site"
        result = render_edition(data_dir, site, load_config())
        page = (site / input_data["date"] / "index.html").read_text(encoding="utf-8")
        return result, page, site
    return _make


def test_full_edition_page(edition):
    result, page, site = edition()
    assert result["is_raw"] is False
    assert "Rates on hold as ceasefire talks resume" in page
    assert "Saturday, 26 September 2026" in page
    assert "Why it matters:" in page and "Central bank holds matters." in page
    assert 'href="https://bbcworld.example/h001"' in page
    assert "single-source report" in page
    assert '<svg class="chart' in page            # S&P 500 30-day chart
    assert "+0.45%" in page and "+3 bp" in page   # S&P change, 10y yield change
    assert "Rose after upbeat guidance." in page  # mover note
    assert "<p>Second paragraph.</p>" in page
    assert "Core PCE Price Index m/m" in page and "NKE" in page
    assert "data as of 06:16 CEST" in page
    assert "Not investment advice" in page
    assert 'name="robots" content="noindex"' in page


def test_weekend_edition_shows_last_trading_day(edition):
    _, page, _ = edition()  # sample edition is Saturday 26 Sep, markets as of Friday
    assert "Fri 25 Sep" in page


def test_missing_market_shows_dash(edition):
    _, page, _ = edition()
    assert "Nikkei 225" in page and "–" in page


def test_raw_edition_when_briefing_missing(edition):
    result, page, _ = edition(briefing=None)
    assert result["is_raw"] is True
    assert "AI summary unavailable today" in page
    assert "Central bank holds rates steady" in page  # top headline listed as a link
    assert "Why it matters:" not in page


def test_raw_edition_when_too_few_valid_stories(edition, sample_briefing):
    for s in sample_briefing["stories"]:
        s["headline_ids"] = ["h999"]
    result, _, _ = edition(briefing=sample_briefing)
    assert result["is_raw"] is True


def test_limited_sources_banner(edition, sample_input):
    sample_input["meta"]["feeds_ok"] = 4
    _, page, _ = edition(input_data=sample_input)
    assert "Limited sources today" in page


def test_no_market_data_banner(edition, sample_input):
    for rows in sample_input["markets"].values():
        for r in rows:
            r["missing"] = True
    _, page, _ = edition(input_data=sample_input)
    assert "Market data was unavailable" in page


def test_page_escapes_headline_html(edition, sample_input, sample_briefing):
    sample_briefing["stories"][0]["title"] = "<script>alert(1)</script> & more"
    _, page, _ = edition(briefing=sample_briefing)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in page


def test_archive_and_index_track_editions(edition, sample_input):
    edition()
    later = json.loads(json.dumps(sample_input))
    later["date"] = "2026-09-27"
    _, _, site = edition(input_data=later)
    edition()  # re-render the older day: no duplicate, newest stays first
    editions = json.loads((site / "editions.json").read_text(encoding="utf-8"))
    assert [e["date"] for e in editions] == ["2026-09-27", "2026-09-26"]
    archive = (site / "archive.html").read_text(encoding="utf-8")
    assert 'href="2026-09-27/"' in archive and "Rates on hold as ceasefire talks resume" in archive
    assert 'url=2026-09-27/' in (site / "index.html").read_text(encoding="utf-8")
