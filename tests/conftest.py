import pytest


def make_market(symbol, name, last, prev, unit="index", as_of="2026-09-25"):
    change = last - prev
    return {
        "symbol": symbol, "name": name, "unit": unit, "missing": False,
        "last": last, "prev": prev, "change": change, "change_pct": change / prev * 100,
        "as_of": as_of, "history": [["2026-08-27", prev * 0.97], ["2026-09-24", prev], [as_of, last]],
    }


def headline(hid, title, *sources):
    return {"id": hid, "title": title, "summary": f"Summary of {title}.",
            "published": "2026-09-25T18:00:00+00:00", "region": "world",
            "sources": [{"name": name, "url": f"https://{name.lower().replace(' ', '')}.example/{hid}"}
                        for name in sources]}


@pytest.fixture
def sample_input():
    return {
        "date": "2026-09-26",
        "generated_at": "2026-09-26T04:16:00+00:00",
        "timezone": "Europe/Berlin",
        "news": [
            headline("h001", "Central bank holds rates steady", "BBC World", "Guardian World"),
            headline("h002", "Ceasefire talks resume", "Al Jazeera"),
            headline("h003", "Chipmaker beats earnings forecasts", "CNBC Top News"),
            headline("h004", "Oil rises on supply worries", "Bloomberg Markets"),
        ],
        "markets": {
            "us": [make_market("^GSPC", "S&P 500", 5712.3, 5686.7),
                   make_market("^TNX", "US 10-year yield", 4.21, 4.18, unit="yield")],
            "europe": [make_market("^GDAXI", "DAX", 19012.4, 19100.0)],
            "asia": [{"symbol": "^N225", "name": "Nikkei 225", "unit": "index", "missing": True}],
            "other": [make_market("EURUSD=X", "EUR/USD", 1.1123, 1.1101, unit="fx")],
        },
        "movers": {"as_of": "2026-09-25",
                   "gainers": [{"symbol": "NVDA", "name": "NVIDIA", "last": 120.5, "change_pct": 6.2}],
                   "losers": [{"symbol": "NKE", "name": "Nike", "last": 80.1, "change_pct": -4.8}]},
        "calendar": [{"time": "14:30", "country": "USD", "title": "Core PCE Price Index m/m",
                      "impact": "High", "forecast": "0.2%", "previous": "0.1%"}],
        "earnings": ["NKE"],
        "meta": {"feeds_ok": 18, "feeds_total": 20, "errors": []},
    }


@pytest.fixture
def sample_briefing():
    def story(section, title, ids, single=False):
        return {"section": section, "title": title, "summary": f"{title} summary.",
                "why_it_matters": f"{title} matters.", "headline_ids": ids, "single_source": single}

    return {
        "headline": "Rates on hold as ceasefire talks resume",
        "at_a_glance": ["One.", "Two.", "Three.", "Four.", "Five."],
        "market_analysis": "First paragraph.\n\nSecond paragraph.",
        "mover_notes": {"NVDA": "Rose after upbeat guidance.", "ZZZZ": "Not a mover."},
        "stories": [
            story("Economy & Policy", "Central bank holds", ["h001"]),
            story("Geopolitics", "Talks resume", ["h002"], single=True),
            story("Business & Tech", "Chipmaker beats", ["h003"]),
            story("Energy", "Oil rises", ["h004"]),
        ],
        "watch_today": ["PCE data.", "Nike reaction.", "Oil."],
    }
