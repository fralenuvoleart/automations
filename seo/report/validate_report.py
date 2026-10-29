#!/usr/bin/env python3
"""Mechanical validation of SEO findings/report output against the contract.

Checks the LLM's output against [`seo/references/report-structure.md`](../references/report-structure.md),
[`conciseness-directives.md`](../references/conciseness-directives.md) and (optionally) the source data.
Catches hallucinated URLs and missing labels before the report is delivered.

Usage:
    python3 seo/report/validate_report.py --findings findings.json
    python3 seo/report/validate_report.py --findings findings.json --report report.md --data context.json
Exit codes: 0 = clean, 1 = issues.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # seo/
import window  # noqa: E402

URL_RE = re.compile(r"https?://[^\s)\]\"'<>]+")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED = ("skill", "as_of", "window", "verdict", "sections")


def validate(findings: dict, report_text: str | None = None, data_text: str | None = None) -> list[str]:
    """Return a list of human-readable issues (empty == clean)."""
    issues: list[str] = []

    for key in REQUIRED:
        if key not in findings:
            issues.append(f"missing required key: {key}")
    if issues:
        return issues

    if not DATE_RE.match(str(findings["as_of"])):
        issues.append(f"as_of is not YYYY-MM-DD: {findings['as_of']!r}")

    win = findings.get("window") or {}
    for k in ("startDate", "endDate"):
        if not DATE_RE.match(str(win.get(k, ""))):
            issues.append(f"window.{k} is not YYYY-MM-DD: {win.get(k)!r}")

    sections = findings.get("sections")
    if not isinstance(sections, list) or not sections:
        issues.append("sections must be a non-empty list")
        sections = []
    for i, s in enumerate(sections):
        if not s.get("heading") or not s.get("body"):
            issues.append(f"sections[{i}] needs non-empty heading and body")
        if s.get("estimate"):
            body = str(s.get("body", "")).lower()
            if "estimate" not in body and "heuristic" not in body:
                issues.append(f"sections[{i}] marked estimate but body has no estimate/heuristic label")

    blob = json.dumps(findings) + (report_text or "")
    if "{{cap:" in blob:
        issues.append("output contains an unexpanded {{cap:}} token")

    if report_text is not None:
        expected = window.as_of_line(
            {"startDate": win.get("startDate"), "endDate": win.get("endDate"),
             "lag": win.get("lag", window.DEFAULT_LAG),
             **({"compareStartDate": win["compareStartDate"], "compareEndDate": win["compareEndDate"]}
                if "compareStartDate" in win else {})},
            generated_at=None,
        ).split(" \u00b7 generated")[0]
        if expected not in report_text:
            issues.append(f"report is missing the as-of line fragment: {expected!r}")
        for s in sections:
            if s.get("heading") and s["heading"] not in report_text:
                issues.append(f"report is missing section heading: {s['heading']!r}")

    if data_text is not None:
        for url in set(URL_RE.findall(blob)):
            if url not in data_text:
                issues.append(f"URL not found in source data (possible hallucination): {url}")

    return issues


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--data", default=None)
    args = ap.parse_args()

    findings = json.loads(Path(args.findings).read_text())
    report_text = Path(args.report).read_text() if args.report else None
    data_text = Path(args.data).read_text() if args.data else None

    issues = validate(findings, report_text, data_text)
    for i in issues:
        print(f"ERROR {i}")
    print("OK — findings/report satisfy the contract" if not issues else f"{len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(_main())
