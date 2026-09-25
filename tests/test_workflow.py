import yaml

from briefing.config import ROOT, load_config

WORKFLOW = ROOT / ".github" / "workflows" / "daily.yml"


def load():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return wf, wf.get("on", wf.get(True))  # PyYAML reads the bare key `on` as True


def claude_steps(wf):
    return [s for s in wf["jobs"]["briefing"]["steps"] if s.get("uses", "").startswith("anthropics/claude-code-action")]


def test_schedule_covers_cet_and_cest():
    _, on = load()
    assert {c["cron"] for c in on["schedule"]} == {"15 4 * * *", "15 5 * * *"}
    assert "workflow_dispatch" in on


def test_claude_steps_use_subscription_and_config_model():
    wf, _ = load()
    steps = claude_steps(wf)
    assert len(steps) == 2  # first attempt + retry
    model = load_config()["model"]
    for s in steps:
        assert s["with"]["claude_code_oauth_token"] == "${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}"
        assert "anthropic_api_key" not in s["with"]
        assert f"--model {model}" in s["with"]["claude_args"]
        assert '--allowedTools "Read,Write"' in s["with"]["claude_args"]
        assert "--max-turns 6" in s["with"]["claude_args"]
        assert s["timeout-minutes"] == 10 and s["continue-on-error"] is True


def test_only_site_is_published_and_secrets_are_referenced():
    wf, _ = load()
    steps = wf["jobs"]["briefing"]["steps"]
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-pages-artifact"))
    assert upload["with"]["path"] == "site"
    email = next(s for s in steps if "briefing.send_email" in s.get("run", ""))
    assert set(email["env"]) == {"GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "BRIEFING_TO"}
    assert wf["concurrency"]["cancel-in-progress"] is False
