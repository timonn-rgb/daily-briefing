from briefing.collect_calendar import collect_calendar, collect_earnings, parse_ff_calendar

EVENTS = [
    {"title": "Core PCE Price Index m/m", "country": "USD", "date": "2026-09-25T08:30:00-04:00",
     "impact": "High", "forecast": "0.2%", "previous": "0.1%"},
    {"title": "ECB President Speaks", "country": "EUR", "date": "2026-09-25T03:00:00-04:00",
     "impact": "High", "forecast": "", "previous": ""},
    {"title": "Pending Home Sales", "country": "USD", "date": "2026-09-25T10:00:00-04:00",
     "impact": "Medium", "forecast": "1.0%", "previous": "-0.5%"},
    {"title": "AUD thing", "country": "AUD", "date": "2026-09-25T02:00:00-04:00", "impact": "High"},
    {"title": "Tomorrow", "country": "USD", "date": "2026-09-26T08:30:00-04:00", "impact": "High"},
    {"title": "Broken", "country": "USD", "date": "not a date", "impact": "High"},
]
CFG = {"calendar_url": "https://cal", "calendar_countries": ["USD", "EUR"],
       "calendar_min_impact": "High", "timezone": "Europe/Berlin"}


def test_filters_by_day_country_impact_and_converts_to_berlin_time():
    out = parse_ff_calendar(EVENTS, "2026-09-25", "Europe/Berlin", ["USD", "EUR"], "High")
    assert out == [
        {"time": "09:00", "country": "EUR", "title": "ECB President Speaks", "impact": "High",
         "forecast": "", "previous": ""},
        {"time": "14:30", "country": "USD", "title": "Core PCE Price Index m/m", "impact": "High",
         "forecast": "0.2%", "previous": "0.1%"},
    ]


def test_medium_threshold_includes_medium():
    out = parse_ff_calendar(EVENTS, "2026-09-25", "Europe/Berlin", ["USD"], "Medium")
    assert [e["title"] for e in out] == ["Core PCE Price Index m/m", "Pending Home Sales"]


def test_calendar_fetch_failure_is_an_error_not_a_crash():
    def fetch(url):
        raise ConnectionError("down")

    events, errors = collect_calendar(CFG, "2026-09-25", fetch=fetch)
    assert events == [] and errors == ["calendar: down"]


def test_calendar_unexpected_payload():
    events, errors = collect_calendar(CFG, "2026-09-25", fetch=lambda url: {"error": "rate limit"})
    assert events == [] and errors == ["calendar: unexpected response"]


def test_earnings_today_only_and_errors_collected():
    dates = {"NKE": "2026-09-25", "AAPL": "2026-10-30"}

    def lookup(symbol):
        if symbol == "BAD":
            raise ValueError("no data")
        return dates.get(symbol)

    today, errors = collect_earnings(["NKE", "AAPL", "BAD", "MSFT"], "2026-09-25", lookup=lookup)
    assert today == ["NKE"]
    assert errors == ["earnings BAD: no data"]
