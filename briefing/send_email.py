"""Sends the rendered email through Gmail SMTP and records a 'sent' marker for the day."""
from __future__ import annotations

import argparse
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

REQUIRED_ENV = ("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "BRIEFING_TO")


def build_message(sender: str, to: str, subject: str, html: str, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = f"Daily Briefing <{sender}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    return msg


def send_message(msg: EmailMessage, user: str, password: str, host: str = "smtp.gmail.com",
                 port: int = 587, smtp_factory=smtplib.SMTP) -> None:
    with smtp_factory(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, help="data/<date> directory")
    args = parser.parse_args(argv)
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")
    folder = Path(args.dir)
    msg = build_message(
        os.environ["GMAIL_ADDRESS"],
        os.environ["BRIEFING_TO"],
        (folder / "subject.txt").read_text(encoding="utf-8").strip(),
        (folder / "email.html").read_text(encoding="utf-8"),
        (folder / "email.txt").read_text(encoding="utf-8"),
    )
    send_message(msg, os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])
    (folder / "sent").write_text(datetime.now(timezone.utc).isoformat(), encoding="utf-8")
    print(f"Sent: {msg['Subject']}")


if __name__ == "__main__":
    main()
