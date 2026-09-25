"""Checks Claude's briefing.json against the day's input so nothing unsupported gets published."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

SECTIONS = ("Geopolitics", "Economy & Policy", "Business & Tech", "Other")
MIN_STORIES = 3


def load_briefing(path: Path) -> dict | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text_list(value, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()][:limit]


def _clean_story(i: int, story, by_id: dict) -> tuple[dict | None, str | None]:
    if not isinstance(story, dict):
        return None, f"story {i}: not an object"
    title, summary, why = _text(story.get("title")), _text(story.get("summary")), _text(story.get("why_it_matters"))
    if not (title and summary and why):
        return None, f"story {i} '{title}': missing title, summary or why_it_matters"
    raw_ids = story.get("headline_ids")
    ids = [x for x in raw_ids if isinstance(x, str)] if isinstance(raw_ids, list) else []
    unknown = [x for x in ids if x not in by_id]
    if not ids or unknown or len(ids) != len(raw_ids):
        return None, f"story {i} '{title}': unknown or missing headline ids {unknown or raw_ids}"
    sources, seen = [], set()
    for hid in ids:
        for src in by_id[hid]["sources"]:
            if src["url"] not in seen:
                seen.add(src["url"])
                sources.append(src)
    return {
        "section": story.get("section") if story.get("section") in SECTIONS else "Other",
        "title": title,
        "summary": summary,
        "why_it_matters": why,
        "headline_ids": ids,
        "single_source": bool(story.get("single_source")),
        "sources": sources,
    }, None


def validate_briefing(raw, input_data: dict, max_stories: int = 10) -> tuple[dict | None, list[str]]:
    if not isinstance(raw, dict):
        return None, ["briefing is not a JSON object"]
    # Collapse internal whitespace too: the headline goes straight into the email Subject
    # header, and a stray newline there makes EmailMessage raise.
    headline = " ".join(_text(raw.get("headline")).split())
    if not headline:
        return None, ["missing headline"]
    by_id = {h["id"]: h for h in input_data["news"]}
    stories, problems = [], []
    for i, story in enumerate(raw.get("stories") if isinstance(raw.get("stories"), list) else []):
        clean, problem = _clean_story(i, story, by_id)
        if problem:
            problems.append(problem)
        else:
            stories.append(clean)
    stories = stories[:max_stories]
    if len(stories) < MIN_STORIES:
        return None, problems + [f"only {len(stories)} valid stories (need {MIN_STORIES})"]
    mover_symbols = {m["symbol"] for key in ("gainers", "losers") for m in input_data["movers"].get(key, [])}
    notes = raw.get("mover_notes") if isinstance(raw.get("mover_notes"), dict) else {}
    return {
        "date": input_data["date"],
        "headline": headline,
        "at_a_glance": _text_list(raw.get("at_a_glance"), 5),
        "market_analysis": _text(raw.get("market_analysis")),
        "mover_notes": {k: _text(v) for k, v in notes.items() if k in mover_symbols and _text(v)},
        "stories": stories,
        "watch_today": _text_list(raw.get("watch_today"), 3),
    }, problems


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="data/<date> directory")
    args = parser.parse_args(argv)
    folder = Path(args.dir)
    input_data = json.loads((folder / "input.json").read_text(encoding="utf-8"))
    clean, problems = validate_briefing(load_briefing(folder / "briefing.json"), input_data)
    for problem in problems:
        print("validate:", problem)
    valid = clean is not None
    print("valid" if valid else "invalid")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"valid={'true' if valid else 'false'}\n")


if __name__ == "__main__":
    main()
