import pytest

from briefing.config import ROOT, load_config


def test_loads_project_config():
    cfg = load_config()
    assert cfg["timezone"] == "Europe/Berlin"
    assert cfg["model"] == "claude-sonnet-5"
    assert len(cfg["feeds"]) >= 10
    assert {"us", "europe", "asia", "other"} <= set(cfg["markets"])
    assert (ROOT / "config.yaml").exists()


def test_missing_key_is_reported(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("timezone: Europe/Berlin\n", encoding="utf-8")
    with pytest.raises(ValueError, match="send_hour"):
        load_config(bad)
