from scripts.update_sp500 import convert


def test_convert_maps_columns_and_yahoo_symbols():
    text = "Symbol,Security,GICS Sector\nAAPL,Apple Inc.,IT\nBRK.B,Berkshire Hathaway,Financials\n"
    assert convert(text) == [
        {"symbol": "AAPL", "name": "Apple Inc."},
        {"symbol": "BRK-B", "name": "Berkshire Hathaway"},
    ]
