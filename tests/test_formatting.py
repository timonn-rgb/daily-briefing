from briefing.formatting import direction, fmt_change, fmt_date_short, fmt_value


def test_fmt_value_by_unit():
    assert fmt_value(5712.3, "index") == "5,712.30"
    assert fmt_value(1.11234, "fx") == "1.1123"
    assert fmt_value(149.456, "fx") == "149.46"
    assert fmt_value(4.213, "yield") == "4.21%"


def test_fmt_change():
    assert fmt_change({"unit": "index", "missing": False, "change": 25.6, "change_pct": 0.4502}) == "+0.45%"
    assert fmt_change({"unit": "index", "missing": False, "change": -3, "change_pct": -1.0}) == "-1.00%"
    assert fmt_change({"unit": "yield", "missing": False, "change": 0.031, "change_pct": 0.7}) == "+3 bp"
    assert fmt_change({"unit": "index", "missing": True}) == "–"


def test_direction():
    assert direction({"missing": False, "change": 1.0}) == "up"
    assert direction({"missing": False, "change": -0.1}) == "down"
    assert direction({"missing": False, "change": 0.0}) == "flat"
    assert direction({"missing": True}) == "flat"


def test_fmt_date_short():
    assert fmt_date_short("2026-09-25") == "Fri 25 Sep"
    assert fmt_date_short(None) == ""
