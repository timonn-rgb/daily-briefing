import json

from briefing.validate import load_briefing, main, validate_briefing


def test_valid_briefing_is_cleaned(sample_input, sample_briefing):
    clean, problems = validate_briefing(sample_briefing, sample_input)
    assert problems == []
    assert clean["date"] == "2026-09-26"
    assert [s["section"] for s in clean["stories"]] == ["Economy & Policy", "Geopolitics", "Business & Tech", "Other"]
    assert clean["stories"][0]["sources"] == [
        {"name": "BBC World", "url": "https://bbcworld.example/h001"},
        {"name": "Guardian World", "url": "https://guardianworld.example/h001"},
    ]
    assert clean["stories"][1]["single_source"] is True
    assert clean["mover_notes"] == {"NVDA": "Rose after upbeat guidance."}


def test_story_with_unknown_or_bad_ids_is_dropped(sample_input, sample_briefing):
    sample_briefing["stories"][0]["headline_ids"] = ["h999"]
    sample_briefing["stories"][1]["headline_ids"] = [["h002"]]
    clean, problems = validate_briefing(sample_briefing, sample_input)
    assert clean is None  # only 2 valid stories left, below MIN_STORIES
    assert any("h999" in p for p in problems)


def test_one_bad_story_does_not_sink_the_rest(sample_input, sample_briefing):
    sample_briefing["stories"][3]["headline_ids"] = ["h999"]
    clean, problems = validate_briefing(sample_briefing, sample_input)
    assert [s["title"] for s in clean["stories"]] == ["Central bank holds", "Talks resume", "Chipmaker beats"]
    assert len(problems) == 1


def test_lists_are_trimmed_and_stories_capped(sample_input, sample_briefing):
    sample_briefing["at_a_glance"] = [f"b{i}" for i in range(8)]
    sample_briefing["watch_today"] = ["a", "b", "c", "d", 5]
    clean, _ = validate_briefing(sample_briefing, sample_input, max_stories=3)
    assert len(clean["at_a_glance"]) == 5
    assert clean["watch_today"] == ["a", "b", "c"]
    assert len(clean["stories"]) == 3


def test_missing_headline_or_non_object_is_invalid(sample_input, sample_briefing):
    sample_briefing["headline"] = "  "
    assert validate_briefing(sample_briefing, sample_input)[0] is None
    assert validate_briefing(None, sample_input) == (None, ["briefing is not a JSON object"])
    assert validate_briefing(["x"], sample_input)[0] is None


def test_load_briefing_strips_fences_and_chatter(tmp_path):
    f = tmp_path / "briefing.json"
    f.write_text('```json\n{"headline": "Hi"}\n```\nDone! Let me know if you need changes.', encoding="utf-8")
    assert load_briefing(f) == {"headline": "Hi"}


def test_load_briefing_rejects_garbage(tmp_path):
    f = tmp_path / "briefing.json"
    f.write_text('{"headline": "cut off mid', encoding="utf-8")
    assert load_briefing(f) is None
    f.write_text("I could not complete the task.", encoding="utf-8")
    assert load_briefing(f) is None
    assert load_briefing(tmp_path / "missing.json") is None


def test_cli_writes_github_output(tmp_path, monkeypatch, sample_input, sample_briefing):
    (tmp_path / "input.json").write_text(json.dumps(sample_input), encoding="utf-8")
    (tmp_path / "briefing.json").write_text(json.dumps(sample_briefing), encoding="utf-8")
    out = tmp_path / "gh_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    main(["--dir", str(tmp_path)])
    assert out.read_text() == "valid=true\n"
    (tmp_path / "briefing.json").unlink()
    main(["--dir", str(tmp_path)])
    assert out.read_text() == "valid=true\nvalid=false\n"
