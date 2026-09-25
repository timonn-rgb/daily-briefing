from briefing.prompt_input import build_writer_input


def test_writer_input_lists_markets_movers_calendar_and_headlines():
    data = {
        "date": "2026-09-26", "timezone": "Europe/Berlin",
        "markets": {"us": [
            {"symbol": "^GSPC", "name": "S&P 500", "unit": "index", "missing": False, "last": 5712.3,
             "change": 25.6, "change_pct": 0.45, "as_of": "2026-09-25"},
            {"symbol": "^VIX", "name": "VIX volatility", "unit": "index", "missing": True},
        ]},
        "movers": {"as_of": "2026-09-25",
                   "gainers": [{"symbol": "NVDA", "name": "NVIDIA", "last": 120.5, "change_pct": 6.2}],
                   "losers": []},
        "calendar": [{"time": "14:30", "country": "USD", "title": "Core PCE", "impact": "High",
                      "forecast": "0.2%", "previous": ""}],
        "earnings": ["NKE"],
        "news": [{"id": "h001", "title": "Fed holds", "summary": "Rates unchanged.",
                  "published": "2026-09-25T18:00:00+00:00",
                  "sources": [{"name": "BBC World", "url": "u"}, {"name": "Reuters", "url": "v"}]},
                 {"id": "h002", "title": "Undated", "summary": "", "published": None,
                  "sources": [{"name": "DW", "url": "w"}]}],
    }
    text = build_writer_input(data)
    assert "- S&P 500: 5,712.30 (+0.45%) as of 2026-09-25" in text
    assert "- VIX volatility: no data" in text
    assert "- Gainers: NVDA (NVIDIA) +6.2%" in text
    assert "- Losers: none" in text
    assert "- 14:30 USD Core PCE (impact High; forecast 0.2%; previous n/a)" in text
    assert "## Earnings today: NKE" in text
    assert "h001 | BBC World, Reuters | 2026-09-25 18:00 | Fed holds — Rates unchanged." in text
    assert "h002 | DW | unknown | Undated" in text
