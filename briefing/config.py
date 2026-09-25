"""Loads config.yaml, the single place for feeds, tickers and settings."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEYS = ("timezone", "send_hour", "schedule_enabled", "model", "site_base_url", "feeds", "markets")


def load_config(path: Path | None = None) -> dict:
    path = path or ROOT / "config.yaml"
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise ValueError(f"config.yaml is missing '{key}'")
    return cfg
