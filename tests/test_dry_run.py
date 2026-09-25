import io

from scripts.dry_run import ensure_utf8_stdout


def test_ensure_utf8_stdout_lets_non_ascii_print_on_a_cp1252_stream(monkeypatch):
    # Windows consoles default stdout to cp1252, which raises UnicodeEncodeError on "->" arrows
    # and other non-ASCII output (see the RAW/FULL edition print in scripts/dry_run.py).
    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    monkeypatch.setattr("sys.stdout", stream)
    ensure_utf8_stdout()
    stream.write("edition → page.html")
    stream.flush()
    assert stream.buffer.getvalue().decode("utf-8") == "edition → page.html"
