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
        # Write itself can't be path-scoped (Claude Code accepts a Write(path) rule but never
        # consults it); Edit(path) is the documented, enforced way to scope the Write tool too.
        assert '--allowedTools "Read,Edit(data/**)"' in s["with"]["claude_args"]
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


def test_checkout_uses_branch_tip():
    wf, _ = load()
    steps = wf["jobs"]["briefing"]["steps"]
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"]["ref"] == "${{ github.ref_name }}"


def test_pulls_branch_tip_right_before_the_gate():
    wf, _ = load()
    steps = wf["jobs"]["briefing"]["steps"]
    gate_index = next(i for i, s in enumerate(steps) if s.get("id") == "gate")
    checkout_index = next(i for i, s in enumerate(steps) if s.get("uses", "").startswith("actions/checkout"))
    pull_steps = [s for s in steps[checkout_index:gate_index] if "git pull --ff-only" in s.get("run", "")]
    assert len(pull_steps) == 1


def test_commit_steps_rebase_before_pushing():
    wf, _ = load()
    steps = wf["jobs"]["briefing"]["steps"]
    commit_steps = [s for s in steps if "git commit" in s.get("run", "") and "git push" in s.get("run", "")]
    assert len(commit_steps) == 2  # commit edition, record sent marker
    for s in commit_steps:
        run = s["run"]
        assert run.index("git pull --rebase") < run.index("git push")


def test_checkout_does_not_persist_credentials():
    wf, _ = load()
    steps = wf["jobs"]["briefing"]["steps"]
    checkout = next(s for s in steps if s.get("uses", "").startswith("actions/checkout"))
    assert checkout["with"]["persist-credentials"] is False


def test_commit_edition_step_grants_push_credentials_after_claude_ran():
    wf, _ = load()
    steps = wf["jobs"]["briefing"]["steps"]
    commit = next(s for s in steps if s.get("name") == "Commit edition")
    assert "git remote set-url origin" in commit["run"]
    assert "x-access-token" in commit["run"]
    assert commit["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"


def test_guard_step_after_each_claude_step_and_before_render():
    wf, _ = load()
    steps = wf["jobs"]["briefing"]["steps"]
    claude_indices = [i for i, s in enumerate(steps) if s.get("uses", "").startswith("anthropics/claude-code-action")]
    assert len(claude_indices) == 2
    render_index = next(i for i, s in enumerate(steps) if "briefing.render" in s.get("run", ""))
    for i in claude_indices:
        guard = steps[i + 1]
        assert guard["if"] == "steps.gate.outputs.run == 'true'"
        assert "git diff --exit-code -- . ':!data'" in guard["run"]
        assert "git ls-files --others --exclude-standard -- . ':!data'" in guard["run"]
        assert i + 1 < render_index
