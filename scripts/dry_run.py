"""Run the whole pipeline locally into build/ without publishing or emailing.

python -m scripts.dry_run             # uses your local `claude` login
python -m scripts.dry_run --no-claude # skip the AI step and preview the raw edition
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone

from briefing.collect import build_input, write_input
from briefing.config import ROOT, load_config
from briefing.dates import edition_date
from briefing.render import render_edition
from briefing.validate import load_briefing, validate_briefing

BUILD = ROOT / "build"


def ensure_utf8_stdout() -> None:
    """Windows consoles default stdout to cp1252, which can't encode the arrow below."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def task_prompt(input_rel: str, output_rel: str) -> str:
    return (f"Follow the instructions in prompts/writer.md.\n"
            f"Input file: {input_rel}\nOutput file: {output_rel}")


def run_claude(cfg: dict, day: str) -> None:
    exe = shutil.which("claude")
    if not exe:
        print("claude CLI not found, skipping the AI step (raw edition)")
        return
    prompt = task_prompt(f"build/data/{day}/writer_input.md", f"build/data/{day}/briefing.json")
    print(f"Running Claude ({cfg['model']})...")
    subprocess.run([exe, "-p", prompt, "--model", cfg["model"], "--max-turns", "6",
                    "--allowedTools", "Read,Write"], cwd=ROOT, check=False, timeout=600)


def main() -> None:
    ensure_utf8_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-claude", action="store_true")
    args = parser.parse_args()
    cfg = load_config()
    now = datetime.now(timezone.utc)
    day = edition_date(now, cfg["timezone"])
    data_dir = BUILD / "data" / day

    print(f"Collecting for {day}...")
    data = build_input(cfg, now, day)
    write_input(data, data_dir)
    meta = data["meta"]
    print(f"{len(data['news'])} headlines from {meta['feeds_ok']}/{meta['feeds_total']} feeds")
    for err in meta["errors"]:
        print("  -", err)

    if not args.no_claude:
        run_claude(cfg, day)
        _, problems = validate_briefing(load_briefing(data_dir / "briefing.json"), data)
        for p in problems:
            print("  validation:", p)

    result = render_edition(data_dir, BUILD / "site", cfg)
    page = BUILD / "site" / day / "index.html"
    print(f"{'RAW' if result['is_raw'] else 'FULL'} edition → {page}")
    print("Email subject:", (data_dir / "subject.txt").read_text(encoding="utf-8"))
    webbrowser.open(page.as_uri())
    webbrowser.open((data_dir / "email.html").as_uri())


if __name__ == "__main__":
    main()
