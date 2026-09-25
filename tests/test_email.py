import json
from email import message_from_bytes, policy

import pytest

from briefing import send_email
from briefing.config import load_config
from briefing.render import render_edition, subject_for


def test_subject_format():
    assert subject_for("2026-09-26", "Rates on hold") == "☀ Sep 26 · Rates on hold"


@pytest.fixture
def rendered(tmp_path, sample_input, sample_briefing):
    data_dir = tmp_path / "data" / "2026-09-26"
    data_dir.mkdir(parents=True)
    (data_dir / "input.json").write_text(json.dumps(sample_input), encoding="utf-8")
    (data_dir / "briefing.json").write_text(json.dumps(sample_briefing), encoding="utf-8")
    cfg = load_config()
    cfg["site_base_url"] = "https://me.github.io/daily-briefing/"
    render_edition(data_dir, tmp_path / "site", cfg)
    return data_dir


def test_email_files_written(rendered):
    html = (rendered / "email.html").read_text(encoding="utf-8")
    text = (rendered / "email.txt").read_text(encoding="utf-8")
    subject = (rendered / "subject.txt").read_text(encoding="utf-8")
    assert subject == "☀ Sep 26 · Rates on hold as ceasefire talks resume"
    assert 'href="https://me.github.io/daily-briefing/2026-09-26/"' in html
    assert "Read the full briefing" in html and "Central bank holds matters." in html
    assert "<svg" not in html  # no charts in email
    assert "S&P 500: 5,712.30 (+0.45%)" in text
    assert "Read the full briefing: https://me.github.io/daily-briefing/2026-09-26/" in text


def test_email_market_rows_show_as_of_date(rendered):
    # sample edition is Saturday 26 Sep, markets as of Friday - the email must show that,
    # since it hides the phone-only sparkline column and has no separate "as of" column.
    html = (rendered / "email.html").read_text(encoding="utf-8")
    text = (rendered / "email.txt").read_text(encoding="utf-8")
    assert "Fri 25 Sep" in html
    assert "Fri 25 Sep" in text


def test_build_message_handles_non_ascii():
    msg = send_email.build_message("me@gmail.com", "me@gmail.com", "☀ Sep 26 · Zölle & Märkte",
                                   "<p>Hallo</p>", "Hallo")
    parsed = message_from_bytes(msg.as_bytes(), policy=policy.default)
    assert parsed["Subject"] == "☀ Sep 26 · Zölle & Märkte"
    assert parsed.is_multipart()
    assert {p.get_content_type() for p in parsed.iter_parts()} == {"text/plain", "text/html"}


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout):
        self.calls = [("connect", host, port)]
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, msg):
        self.calls.append(("send", msg["To"]))


def test_send_message_uses_starttls_and_login():
    msg = send_email.build_message("me@gmail.com", "you@example.com", "s", "<p>h</p>", "t")
    send_email.send_message(msg, "me@gmail.com", "app-pass", smtp_factory=FakeSMTP)
    assert FakeSMTP.instances[-1].calls == [
        ("connect", "smtp.gmail.com", 587), ("starttls",), ("login", "me@gmail.com", "app-pass"),
        ("send", "you@example.com"),
    ]


def test_cli_sends_and_writes_marker(rendered, monkeypatch):
    sent = []
    monkeypatch.setattr(send_email, "send_message", lambda msg, user, password: sent.append(msg["Subject"]))
    monkeypatch.setenv("GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "app-pass")
    monkeypatch.setenv("BRIEFING_TO", "me@gmail.com")
    send_email.main(["--dir", str(rendered)])
    assert sent == ["☀ Sep 26 · Rates on hold as ceasefire talks resume"]
    assert (rendered / "sent").exists()


def test_cli_fails_without_secrets(rendered, monkeypatch):
    for key in ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "BRIEFING_TO"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SystemExit, match="GMAIL_ADDRESS"):
        send_email.main(["--dir", str(rendered)])
    assert not (rendered / "sent").exists()
