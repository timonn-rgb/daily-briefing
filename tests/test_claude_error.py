import json

from briefing.claude_error import annotation, result_message


def test_reads_result_from_json_array(tmp_path):
    f = tmp_path / "exec.json"
    f.write_text(json.dumps([{"type": "system", "subtype": "init"},
                             {"type": "result", "is_error": True, "result": "Invalid API key · Please run /login"}]),
                 encoding="utf-8")
    assert result_message(f) == "Invalid API key · Please run /login"


def test_reads_result_from_json_lines(tmp_path):
    f = tmp_path / "exec.json"
    f.write_text('{"type": "system"}\n{"type": "result", "result": "OAuth token has expired"}\n', encoding="utf-8")
    assert result_message(f) == "OAuth token has expired"


def test_missing_or_unreadable_log(tmp_path):
    assert result_message(tmp_path / "missing.json") == "(execution log missing)"
    garbage = tmp_path / "garbage.json"
    garbage.write_text("not json", encoding="utf-8")
    assert result_message(garbage) == "(execution log unreadable)"
    no_result = tmp_path / "no_result.json"
    no_result.write_text('[{"type": "system"}]', encoding="utf-8")
    assert result_message(no_result) == "(no result message)"


def test_annotation_is_one_line_and_capped():
    line = annotation("first line\nsecond line " + "x" * 1000)
    assert line.startswith("::error title=Claude error::first line second line ")
    assert "\n" not in line
    assert len(line) <= len("::error title=Claude error::") + 500
