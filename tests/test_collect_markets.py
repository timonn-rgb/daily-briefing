from briefing.collect_markets import (
    collect_markets, compute_movers, load_sp500, load_with_retries, summarize_series,
)


def pts(*closes, start_day=21):
    return [(f"2026-09-{start_day + i:02d}", c) for i, c in enumerate(closes)]


def test_summary_computes_change():
    s = summarize_series(pts(100.0, 102.0))
    assert s["last"] == 102.0 and s["prev"] == 100.0
    assert s["change"] == 2.0 and round(s["change_pct"], 2) == 2.0
    assert s["history"] == [["2026-09-21", 100.0], ["2026-09-22", 102.0]]


def test_summary_uses_last_trading_day():
    friday_close = [("2026-09-24", 5686.7), ("2026-09-25", 5712.3)]  # run on Saturday
    assert summarize_series(friday_close)["as_of"] == "2026-09-25"


def test_summary_needs_two_points():
    assert summarize_series(pts(100.0)) is None
    assert summarize_series([]) is None


def test_summary_keeps_last_30_points():
    s = summarize_series([(f"d{i}", float(i)) for i in range(45)])
    assert len(s["history"]) == 30 and s["history"][-1] == ["d44", 44.0]


def test_retries_until_data_arrives():
    calls, sleeps = [], []

    def loader(symbols, period):
        calls.append(list(symbols))
        if len(calls) == 1:
            raise RuntimeError("rate limited")
        return {s: pts(1.0, 2.0) for s in symbols}

    got = load_with_retries(loader, ["A", "B"], "45d", sleep=sleeps.append)
    assert set(got) == {"A", "B"}
    assert len(calls) == 2 and sleeps == [2]


def test_retries_only_missing_symbols_and_gives_up():
    calls = []

    def loader(symbols, period):
        calls.append(list(symbols))
        return {"A": pts(1.0, 2.0)} if "A" in symbols else {}

    got = load_with_retries(loader, ["A", "B"], "45d", sleep=lambda s: None)
    assert set(got) == {"A"}
    assert calls == [["A", "B"], ["B"], ["B"]]


def test_collect_markets_marks_missing_symbols():
    cfg = {"markets": {"us": [{"symbol": "^GSPC", "name": "S&P 500"},
                              {"symbol": "^TNX", "name": "US 10-year yield", "unit": "yield"}]}}

    def loader(symbols, period):
        return {"^GSPC": pts(100.0, 101.0)}

    result = collect_markets(cfg, loader=loader, sleep=lambda s: None)
    spx, tnx = result["groups"]["us"]
    assert spx["missing"] is False and spx["unit"] == "index" and spx["last"] == 101.0
    assert tnx == {"symbol": "^TNX", "name": "US 10-year yield", "unit": "yield", "missing": True}
    assert result["errors"] == ["market ^TNX: no data"]


def test_movers_rank_and_skip_stale_tickers():
    hist = {
        "UP": [("2026-09-24", 100.0), ("2026-09-25", 110.0)],
        "DOWN": [("2026-09-24", 100.0), ("2026-09-25", 95.0)],
        "FLATISH": [("2026-09-24", 100.0), ("2026-09-25", 100.5)],
        "STALE": [("2026-09-20", 100.0), ("2026-09-21", 200.0)],  # delisted/halted
    }
    names = {"UP": "Up Corp", "DOWN": "Down Inc", "FLATISH": "Flat Co", "STALE": "Stale Ltd"}
    movers = compute_movers(hist, names, n=2)
    assert movers["as_of"] == "2026-09-25"
    assert [m["symbol"] for m in movers["gainers"]] == ["UP", "FLATISH"]
    assert [m["symbol"] for m in movers["losers"]] == ["DOWN"]
    assert movers["gainers"][0]["name"] == "Up Corp"


def test_movers_empty_history():
    assert compute_movers({}, {}) == {"as_of": None, "gainers": [], "losers": []}


def test_load_sp500(tmp_path):
    f = tmp_path / "sp500.csv"
    f.write_text("symbol,name\nAAPL,Apple Inc.\nBRK-B,Berkshire Hathaway\n", encoding="utf-8")
    assert load_sp500(f) == {"AAPL": "Apple Inc.", "BRK-B": "Berkshire Hathaway"}
