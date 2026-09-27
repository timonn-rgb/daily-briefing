"""Prints Claude's final result message as a GitHub error annotation.

The Claude Code Action hides Claude's output, so without this a failed Claude step
(e.g. a rejected login token) only shows up as a quiet raw edition.
Usage: python -m briefing.claude_error <execution_file>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_CHARS = 500


def _messages(text: str) -> list:
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]


def result_message(path: Path) -> str:
    if not path.is_file():
        return "(execution log missing)"
    try:
        messages = _messages(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "(execution log unreadable)"
    results = [m for m in messages if isinstance(m, dict) and m.get("type") == "result"]
    return str(results[-1].get("result") or "(no result message)") if results else "(no result message)"


def annotation(message: str) -> str:
    return "::error title=Claude error::" + " ".join(message.split())[:MAX_CHARS]


if __name__ == "__main__":
    print(annotation(result_message(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(""))))
