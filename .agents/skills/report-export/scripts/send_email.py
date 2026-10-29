#!/usr/bin/env python3
"""Email a report (PDF attachment) via SMTP.

One config (``config/email.json``) holds ``from_email``, ``to_emails``,
``body_signature``, a default ``subject``, and a ``subjects`` map (per-skill
subjects). SMTP credentials come from ``~/.config/report-export/email.json``
(smtp_host, smtp_port, username, password).

Subject precedence: ``--subject`` > ``subjects[--skill]`` > default ``subject``.

Usage:
    python3 send_email.py --attachment report.pdf [--skill seo-audit] [--subject "..."] [--to a@b,c@d] [--dry-run]
Exit codes: 0 = sent, 1 = error.
"""
from __future__ import annotations

import argparse
import json
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
CONFIG = SKILL / "config" / "email.json"
CREDS = Path.home() / ".config" / "report-export" / "email.json"


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def resolve_subject(cfg: dict, skill: str | None, explicit: str | None) -> str:
    """Subject precedence: explicit ``--subject`` > ``subjects[skill]`` > ``subject``."""
    if explicit:
        return explicit
    if skill:
        subjects = cfg.get("subjects") or {}
        if skill in subjects:
            return subjects[skill]
    return cfg.get("subject", "Report")


def build_message(cfg: dict, creds: dict, attachment: Path,
                  subject: str | None, to: list[str] | None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = cfg.get("from_email") or creds.get("username", "")
    msg["To"] = ", ".join(to or cfg.get("to_emails", []))
    msg["Subject"] = subject or cfg.get("subject", "Report")
    body = cfg.get("body_signature", "")
    msg.set_content(body or "Please find the report attached.")
    if attachment.exists():
        msg.add_attachment(
            attachment.read_bytes(),
            maintype="application", subtype="pdf", filename=attachment.name,
        )
    return msg


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--attachment", required=True)
    ap.add_argument("--subject", default=None, help="explicit subject (overrides the config)")
    ap.add_argument("--to", default=None, help="comma-separated override")
    ap.add_argument("--skill", default=None,
                    help="skill name; selects its subject from config `subjects`")
    ap.add_argument("--dry-run", action="store_true",
                    help="verify SMTP login and build the message, but do not send")
    args = ap.parse_args(argv)

    cfg = _load(CONFIG)
    creds = _load(CREDS)
    if not creds:
        print(f"ERROR no SMTP credentials at {CREDS} "
              f"(copy config/email.json.example and fill it)", file=sys.stderr)
        return 1
    to = [x.strip() for x in args.to.split(",")] if args.to else None
    attachment = Path(args.attachment)
    if not attachment.exists():
        print(f"ERROR attachment not found: {attachment}", file=sys.stderr)
        return 1

    subject = resolve_subject(cfg, args.skill, args.subject)
    msg = build_message(cfg, creds, attachment, subject, to)
    host = creds.get("smtp_host", "smtp.gmail.com")
    port = int(creds.get("smtp_port", 587))
    try:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(creds["username"], creds["password"])
            if args.dry_run:
                print(f"[dry-run] SMTP login OK; would email {attachment.name} "
                      f"to {msg['To']} (subject: {msg['Subject']})")
                return 0
            s.send_message(msg)
    except Exception as e:  # noqa: BLE001
        label = "dry-run login" if args.dry_run else "send"
        print(f"ERROR {label} failed: {e}", file=sys.stderr)
        return 1
    print(f"emailed {attachment.name} to {msg['To']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
