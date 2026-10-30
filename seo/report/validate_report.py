#!/usr/bin/env python3
"""Mechanical validation of SEO findings/report output against the contract.

Checks the LLM's output against [`seo/references/report-structure.md`](../references/report-structure.md),
[`conciseness-directives.md`](../references/conciseness-directives.md) and the recorded evidence
(`context.json` + `data/*.json`, written by `seo/record.py`). Never raises on bad input — every
problem is returned as an issue.

Usage:
    python3 seo/report/validate_report.py --findings F --data {run_dir}/context.json            # before build
    python3 seo/report/validate_report.py --findings F --report R --data {run_dir}/context.json # after build
Exit codes: 0 = clean, 1 = issues.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # seo/
import window  # noqa: E402

URL_RE = re.compile(r"https?://[^\s)\]\"'<>|`]+")
TRAILING = ".,;:!?)]}'\"»”’…"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
REQUIRED = ("skill", "as_of", "window", "verdict", "sections")
TOKENS = ("{{cap:", "{{site:", "{{include:", "<!--cap:", "<!--include:")
IGNORED_HOSTS = {
    "json-schema.org", "schema.org", "developers.google.com", "support.google.com",
    "pagespeed.web.dev", "search.google.com", "status.search.google.com", "web.dev",
    "github.com", "dataforseo.com", "w3.org", "developers.openai.com", "support.claude.com",
}


# ------------------------------------------------------------------- helpers ---
def _date(v) -> dt.date | None:
    if isinstance(v, str) and DATE_RE.match(v):
        try:
            return dt.date.fromisoformat(v)
        except ValueError:
            return None
    return None


def clean_url(u: str) -> str:
    while u and u[-1] in TRAILING:
        u = u[:-1]
    return u


def norm_url(u: str) -> str:
    p = urlparse(unquote(clean_url(u)))
    return f"{p.scheme.lower()}://{(p.netloc or '').lower()}{p.path.rstrip('/')}{'?' + p.query if p.query else ''}"


def find_urls(text: str) -> set[str]:
    return {clean_url(u) for u in URL_RE.findall(text or "")}


def load_evidence(context_path: str | Path) -> tuple[str | None, int, list[str]]:
    """Return (evidence text, number of recorded calls, problems) from context.json + data files."""
    p = Path(context_path)
    if not p.exists():
        return None, 0, [f"evidence file not found: {p} (seed the run with seo/orchestrate.py and record every tool response with seo/record.py)"]
    try:
        ctx = json.loads(p.read_text())
    except json.JSONDecodeError as e:
        return None, 0, [f"evidence file is not valid JSON: {e}"]
    calls = ctx.get("calls", []) if isinstance(ctx, dict) else []
    parts, problems = [p.read_text()], []
    for c in calls:
        f = c.get("file") if isinstance(c, dict) else None
        if not f:
            continue
        fp = p.parent / f
        if fp.exists():
            parts.append(fp.read_text())
        else:
            problems.append(f"recorded evidence file missing: {f}")
    return "\n".join(parts), len(calls), problems


# ----------------------------------------------------------------- structure ---
def validate_structure(findings) -> list[str]:
    """Shape/type/date checks (findings-schema.json); safe on any input."""
    if not isinstance(findings, dict):
        return [f"findings must be a JSON object, got {type(findings).__name__}"]
    issues = [f"missing required key: {k}" for k in REQUIRED if k not in findings]
    if issues:
        return issues
    for k in ("skill", "verdict"):
        if not isinstance(findings[k], str) or not findings[k].strip():
            issues.append(f"{k} must be a non-empty string")
    as_of = _date(findings["as_of"])
    if not as_of:
        issues.append(f"as_of is not YYYY-MM-DD: {findings['as_of']!r}")

    win = findings["window"]
    if not isinstance(win, dict):
        issues.append("window must be an object")
        win = {}
    start, end = _date(win.get("startDate")), _date(win.get("endDate"))
    for k, v in (("startDate", start), ("endDate", end)):
        if not v:
            issues.append(f"window.{k} is not YYYY-MM-DD: {win.get(k)!r}")
    source = win.get("source", "gsc")
    if source not in window.SOURCES:
        issues.append(f"window.source must be one of {window.SOURCES}")
    if start and end and start > end:
        issues.append(f"window.startDate {start} is after endDate {end}")
    if end and as_of and source != "snapshot" and end >= as_of:
        issues.append(f"window.endDate {end} is not before as_of {as_of} (never include today; respect the data lag)")
    for i, w in enumerate(win.get("weeks") or []):
        ws, we = _date((w or {}).get("startDate")), _date((w or {}).get("endDate"))
        if not ws or not we or ws > we or (start and ws < start) or (end and we > end):
            issues.append(f"window.weeks[{i}] must be dated and inside the window")
    if ("compareStartDate" in win) != ("compareEndDate" in win):
        issues.append("window needs both compareStartDate and compareEndDate (or neither)")
    elif "compareStartDate" in win:
        cs, ce = _date(win.get("compareStartDate")), _date(win.get("compareEndDate"))
        if not cs or not ce:
            issues.append("window compare dates must be YYYY-MM-DD")
        elif cs > ce:
            issues.append("window.compareStartDate is after compareEndDate")
        elif start and ce >= start:
            issues.append("comparison window overlaps the current window")

    sections = findings["sections"]
    if not isinstance(sections, list) or not sections:
        issues.append("sections must be a non-empty list")
        sections = []
    for i, s in enumerate(sections):
        if not isinstance(s, dict):
            issues.append(f"sections[{i}] must be an object")
            continue
        if not isinstance(s.get("heading"), str) or not s["heading"].strip() \
                or not isinstance(s.get("body"), str) or not s["body"].strip():
            issues.append(f"sections[{i}] needs non-empty string heading and body")
        if "\n" in str(s.get("heading", "")):
            issues.append(f"sections[{i}].heading must be a single line")
        t = s.get("table")
        if t is not None and (not isinstance(t, list) or not all(isinstance(r, dict) for r in t)):
            issues.append(f"sections[{i}].table must be a list of objects")
        elif t:
            for r in t:
                if any(isinstance(v, (dict, list)) for v in r.values()):
                    issues.append(f"sections[{i}].table cells must be scalars")
                    break
        sw = s.get("window")
        if sw is not None:
            if not isinstance(sw, dict) or not (sw.get("note") or (_date(sw.get("startDate")) and _date(sw.get("endDate")))):
                issues.append(f"sections[{i}].window needs startDate+endDate (YYYY-MM-DD) or a note")
        if "estimate" in s and not isinstance(s["estimate"], bool):
            issues.append(f"sections[{i}].estimate must be true/false")

    acts = findings.get("actions")
    if acts is not None and not isinstance(acts, list):
        issues.append("actions must be a list")
    for i, a in enumerate(acts if isinstance(acts, list) else []):
        issues += [f"actions[{i}]: {m}" for m in action_issues(a)]
    un = findings.get("unavailable")
    if un is not None:
        if not isinstance(un, list):
            issues.append("unavailable must be a list")
        else:
            for i, u in enumerate(un):
                if not isinstance(u, dict) or not isinstance(u.get("source"), str) or not isinstance(u.get("affects"), str):
                    issues.append(f"unavailable[{i}] needs string source and affects")
    cov = findings.get("coverage")
    if cov is not None and not isinstance(cov, dict):
        issues.append("coverage must be an object")
    return issues


IMPACTS, EFFORTS = ("high", "medium", "low"), ("low", "medium", "high")
ACTION_KEYS = {"action", "impact", "effort", "page", "keyword", "category", "why", "est_clicks"}


def action_issues(a) -> list[str]:
    """A structured action {action, impact, effort, …} or a legacy non-empty string."""
    if isinstance(a, str):
        return [] if a.strip() else ["empty action"]
    if not isinstance(a, dict):
        return ["must be an object (or a string)"]
    out = [f"unknown key '{k}'" for k in sorted(set(a) - ACTION_KEYS)]
    if not isinstance(a.get("action"), str) or not a["action"].strip():
        out.append("needs a non-empty 'action'")
    if a.get("impact") not in IMPACTS:
        out.append(f"impact must be one of {IMPACTS}")
    if a.get("effort") not in EFFORTS:
        out.append(f"effort must be one of {EFFORTS}")
    for k in ("page", "keyword", "category", "why"):
        if k in a and not isinstance(a[k], str):
            out.append(f"{k} must be a string")
    if "page" in a and isinstance(a["page"], str) and not a["page"].startswith(("http://", "https://")):
        out.append("page must be an absolute URL")
    if "est_clicks" in a and (not isinstance(a["est_clicks"], (int, float)) or isinstance(a["est_clicks"], bool)
                              or a["est_clicks"] < 0):
        out.append("est_clicks must be a non-negative number")
    return out


# ------------------------------------------------------------------ validate ---
def validate(findings, report_text: str | None = None, data_text: str | None = None,
             evidence_calls: int | None = None) -> list[str]:
    """Return a list of human-readable issues (empty == clean)."""
    issues = validate_structure(findings)
    if issues:
        return issues
    win = findings["window"]
    sections = findings["sections"]

    for i, s in enumerate(sections):
        if s.get("estimate"):
            body = s["body"].lower()
            if "estimate" not in body and "heuristic" not in body:
                issues.append(f"sections[{i}] marked estimate but body has no estimate/heuristic label")

    blob = json.dumps(findings, ensure_ascii=False) + (report_text or "")
    for tok in TOKENS:
        if tok in blob:
            issues.append(f"output contains an authoring token {tok!r}")

    if report_text is not None:
        expected = window.as_of_line(win, generated_at="X").split(" · generated")[0]
        if expected not in report_text:
            issues.append(f"report is missing the as-of line fragment: {expected!r}")
        for s in sections:
            if f"## {s['heading'].strip()}" not in report_text:
                issues.append(f"report is missing section heading: {s['heading'].strip()!r}")
        for u in (findings.get("unavailable") or []):
            if u["source"] not in report_text:
                issues.append(f"report is missing unavailable source: {u['source']!r}")
        cov = findings.get("coverage") or {}
        for m in cov.get("missing") or []:
            if str(m) not in report_text:
                issues.append(f"report is missing coverage 'missing' item: {m!r}")
        for lang in cov.get("by_language") or {}:
            if str(lang) not in report_text:
                issues.append(f"report is missing coverage language: {lang!r}")

    urls = set()
    for u in find_urls(blob):
        host = (urlparse(u).hostname or "").lower()
        if not any(host == h or host.endswith("." + h) for h in IGNORED_HOSTS):
            urls.add(u)
    if data_text is not None or evidence_calls is not None:
        if urls and not evidence_calls and evidence_calls is not None:
            issues.append("findings cite URLs but no tool responses were recorded — record every call with seo/record.py")
        data = (data_text or "").replace("\\/", "/")
        data = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), data)  # JSON-escaped non-ASCII
        data = unquote(data)
        data_norm = {norm_url(u) for u in find_urls(data)}
        data_paths = {urlparse(u).path for u in data_norm}
        for u in sorted(urls):
            n = norm_url(u)
            path = urlparse(unquote(u)).path
            host = (urlparse(u).hostname or "").lower()
            if n in data_norm:
                continue
            # GA4 reports paths (landingPagePlusQueryString), not full URLs
            if len(path.rstrip("/")) > 1 and (path in data or path.rstrip("/") + "/" in data or path.rstrip("/") in data_paths):
                continue
            if path in ("", "/") and host and host in data.lower():
                continue
            issues.append(f"URL not found in recorded evidence (possible hallucination): {u}")
    return issues


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--report", default=None)
    ap.add_argument("--data", required=True, help="{run_dir}/context.json (evidence index from seo/record.py)")
    args = ap.parse_args()

    try:
        findings = json.loads(Path(args.findings).read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR cannot read findings: {e}")
        return 1
    report_text = Path(args.report).read_text() if args.report else None
    data_text, n_calls, problems = load_evidence(args.data)
    issues = problems + validate(findings, report_text, data_text, n_calls)
    for i in issues:
        print(f"ERROR {i}")
    print("OK — findings/report satisfy the contract" if not issues else f"{len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(_main())
