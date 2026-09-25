"""Refresh resources/sp500.csv from the public datasets/s-and-p-500-companies list.

Run by hand every few months: python -m scripts.update_sp500
"""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import requests

SOURCE = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
OUT = Path(__file__).resolve().parent.parent / "resources" / "sp500.csv"


def convert(text: str) -> list[dict]:
    rows = []
    for row in csv.DictReader(io.StringIO(text)):
        rows.append({"symbol": row["Symbol"].strip().replace(".", "-"), "name": row["Security"].strip()})
    return rows


def main() -> None:
    resp = requests.get(SOURCE, timeout=30)
    resp.raise_for_status()
    rows = convert(resp.text)
    if len(rows) < 490:
        sys.exit(f"Only {len(rows)} rows downloaded; refusing to overwrite {OUT}")
    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["symbol", "name"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} companies to {OUT}")


if __name__ == "__main__":
    main()
