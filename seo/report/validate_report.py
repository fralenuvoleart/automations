#!/usr/bin/env python3
"""Mechanical validation of SEO findings/report output against the contract.

Checks the LLM's output against [`seo/references/report-structure.md`](../references/report-structure.md),
[`conciseness-directives.md`](../references/conciseness-directives.md) and the recorded evidence
(`context.json` + `data/*.json`, written by `seo/record.py`). Never raises on bad input — every
problem is returned as an issue.

Usage:
    python3 seo/report/validate_report.py --findings F --data {run_dir}/context.json            # before build
    python3 seo/report/validate_report.py --findings F --report R --data {run_dir}/context.json # after build
With --data, every URL and every figure in the findings must trace back to the recorded evidence or
to ``{run_dir}/computed/*.json`` (number rules: [`number_check.py`](number_check.py)).
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
sys.path.insert(0, str(HERE))
from number_check import Index, check as number_issues  # noqa: E402

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
SCHEMA_PATH = HERE.parent / "references" / "findings-schema.json"


def _where(path) -> str:
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def _schema_messages(err, schema) -> list[str]:
    """Readable messages for one jsonschema error (the schema's `x-message` when it has one)."""
    where = _where(err.absolute_path)
    pre = f"{where}: " if where else ""
    v = err.validator
    if v in ("oneOf", "anyOf") and err.context:
        if err.schema.get("x-message"):
            return [f"{pre}{err.schema['x-message']}"]
        # the branch whose type fits the instance explains the problem (e.g. an action object vs a string)
        wrong_type = {e.relative_schema_path[0] for e in err.context
                      if e.validator == "type" and len(e.relative_schema_path) == 2}
        sub = [e for e in err.context if e.relative_schema_path[0] not in wrong_type] or list(err.context)
        return [m for e in sub for m in _schema_messages(e, schema)]
    if err.schema.get("x-message") and v not in ("required", "additionalProperties", "type"):
        return [f"{pre}{err.schema['x-message']}"]
    if v == "required":
        return [f"{pre}missing required key: {err.message.split(chr(39))[1]}"]
    if v == "additionalProperties":
        extra = sorted(set(err.instance) - set(err.schema.get("properties") or {}))
        if isinstance(err.schema.get("additionalProperties"), dict):  # e.g. table cells: typed values
            return [f"{pre}{err.schema['additionalProperties'].get('x-message', err.message)}"]
        return [f"{pre}unknown key '{k}'" for k in extra]
    if v == "type":
        what = {"object": "a JSON object", "array": "a list", "string": "a string", "boolean": "true/false",
                "number": "a number", "integer": "an integer"}
        exp = err.validator_value if isinstance(err.validator_value, list) else [err.validator_value]
        if err.schema.get("x-message"):
            return [f"{pre}{err.schema['x-message']}"]
        return [f"{pre or 'findings: '}must be {' or '.join(what.get(t, t) for t in exp)}"]
    if v == "enum":
        return [f"{where.split('.')[-1] if where else 'value'} must be one of {tuple(err.validator_value)}"
                + (f" ({where})" if "." in where or "[" in where else "")]
    if v == "minimum":
        return [f"{pre}{where.split('.')[-1]} must be ≥ {err.validator_value}"]
    if v == "minItems":
        return [f"{pre}must not be empty"]
    if v == "dependencies":
        return [f"{pre}window needs both compareStartDate and compareEndDate (or neither)"]
    return [f"{pre}{err.message}"]


def validate_structure(findings) -> list[str]:
    """Structure from findings-schema.json (jsonschema, Draft 7), then the cross-field rules a schema
    cannot express. Safe on any input."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema is required to validate findings — pip install jsonschema (see seo/requirements.txt)"]
    schema = json.loads(SCHEMA_PATH.read_text())
    errors = sorted(jsonschema.Draft7Validator(schema).iter_errors(findings), key=lambda e: list(map(str, e.absolute_path)))
    issues = list(dict.fromkeys(m for e in errors for m in _schema_messages(e, schema)))
    if issues:
        return issues

    # cross-field rules (the shapes are guaranteed by the schema from here on)
    as_of = _date(findings["as_of"])
    if not as_of:
        issues.append(f"as_of is not a real date: {findings['as_of']!r}")
    win = findings["window"]
    start, end = _date(win["startDate"]), _date(win["endDate"])
    for k, v in (("startDate", start), ("endDate", end)):
        if not v:
            issues.append(f"window.{k} is not a real date: {win.get(k)!r}")
    source = win.get("source", "gsc")
    if start and end and start > end:
        issues.append(f"window.startDate {start} is after endDate {end}")
    if end and as_of and source != "snapshot" and end >= as_of:
        issues.append(f"window.endDate {end} is not before as_of {as_of} (never include today; respect the data lag)")
    for i, w in enumerate(win.get("weeks") or []):
        ws, we = _date(w["startDate"]), _date(w["endDate"])
        if not ws or not we or ws > we or (start and ws < start) or (end and we > end):
            issues.append(f"window.weeks[{i}] must be dated and inside the window")
    if "compareStartDate" in win:
        cs, ce = _date(win["compareStartDate"]), _date(win["compareEndDate"])
        if not cs or not ce:
            issues.append("window compare dates must be real dates")
        elif cs > ce:
            issues.append("window.compareStartDate is after compareEndDate")
        elif start and ce >= start:
            issues.append("comparison window overlaps the current window")
    for i, sec in enumerate(findings["sections"]):
        sw = sec.get("window") or {}
        if "startDate" in sw and not (_date(sw.get("startDate")) and _date(sw.get("endDate"))) and not sw.get("note"):
            issues.append(f"sections[{i}].window dates are not real dates")
    return issues


# ------------------------------------------------------------------ validate ---
def validate(findings, report_text: str | None = None, data_text: str | None = None,
             evidence_calls: int | None = None, numbers: Index | None = None) -> list[str]:
    """Return a list of human-readable issues (empty == clean). ``numbers`` enables the number check."""
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
    if numbers is not None:
        issues += number_issues(findings, numbers)
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
    index = Index.from_run(Path(args.data).parent) if data_text is not None else None
    issues = problems + validate(findings, report_text, data_text, n_calls, index)
    for i in issues:
        print(f"ERROR {i}")
    print("OK — findings/report satisfy the contract" if not issues else f"{len(issues)} issue(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(_main())
