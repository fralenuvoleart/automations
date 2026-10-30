#!/usr/bin/env python3
"""Render an SEO findings JSON into a Markdown report (mechanical, deterministic).

The LLM writes findings JSON ([`seo/references/findings-schema.json`](../references/findings-schema.json));
this script validates its structure first (refusing malformed input instead of crashing), then
renders the header (from `templates/base.md`) and every section. Narrative stays exactly as written.

Usage:
    python3 seo/report/build_report.py --findings findings.json --out report.md [--generated-at ISO8601]
Exit codes: 0 = written, 1 = invalid findings (nothing written).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # seo/
sys.path.insert(0, str(HERE))
import validate_report  # noqa: E402
import window  # noqa: E402

TEMPLATE = HERE / "templates" / "base.md"
DEFINITIONS = HERE.parent / "references" / "definitions.json"


def _clean_cell(val: object) -> str:
    if val is None:
        return ""
    s = str(val).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return s.replace("|", "\\|").strip()


def _render_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    header = "| " + " | ".join(_clean_cell(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(_clean_cell(r.get(c, "")) for c in cols) + " |" for r in rows]
    return "\n".join([header, sep, *body])


def _section_window(sw: dict) -> str:
    if sw.get("startDate") and sw.get("endDate"):
        span = f"{sw['startDate']}→{sw['endDate']}"
        return f"_Data window: {span}{' — ' + sw['note'] if sw.get('note') else ''}_"
    return f"_Data window: {sw['note']}_"


def build(findings: dict, generated_at: str | None = None) -> str:
    issues = validate_report.validate_structure(findings)
    if issues:
        raise ValueError("invalid findings: " + "; ".join(issues))
    tmpl = TEMPLATE.read_text()
    line = window.as_of_line(findings["window"], generated_at=generated_at)
    out = (tmpl
           .replace("{{title}}", findings["skill"])
           .replace("{{as_of_line}}", line)
           .replace("{{verdict}}", findings["verdict"])).rstrip() + "\n"

    unavailable = findings.get("unavailable") or []
    if unavailable:
        out += "\n## Data availability\n\n"
        for u in unavailable:
            tail = f" ({u['reason']})" if u.get("reason") else ""
            out += f"- **{u['source']}** — {u['affects']}{tail}\n"

    coverage = findings.get("coverage") or {}
    if coverage:
        kw = coverage.get("priority_keywords") or []
        pages = coverage.get("priority_pages") or []
        covered = coverage.get("covered") or []
        missing = coverage.get("missing") or []
        gsc = coverage.get("basis") == "gsc_impressions"
        yes, no = ("with impressions in the window", "with no impressions") if gsc else ("covered", "missing")
        out += "\n## Coverage vs site profile\n\n"
        out += f"- Priority keywords: {len(kw)} total · {len(covered)} {yes} · {len(missing)} {no}\n"
        if pages:
            pc = coverage.get("pages_covered")
            out += f"- Priority pages: {len(pages)} total" + (f" · {len(pc)} {yes}" if pc is not None else "") + "\n"
        by_lang = coverage.get("by_language") or {}
        if by_lang:
            out += "\n**By language:**\n"
            for lang in sorted(by_lang):
                d = by_lang[lang] or {}
                out += f"- {lang}: {d.get('covered', 0)}/{d.get('total', 0)} {yes} ({d.get('missing', 0)} {no})\n"
        if missing:
            label = "No impressions" if gsc else "Missing"
            if len(missing) > 10:
                out += f"\n**{label} ({len(missing)}):** " + ", ".join(f"`{m}`" for m in missing) + "\n"
            else:
                out += f"\n**{label}:**\n" + "\n".join(f"- {m}" for m in missing) + "\n"

    for s in findings["sections"]:
        out += f"\n## {s['heading'].strip()}\n\n"
        if s.get("window"):
            out += _section_window(s["window"]) + "\n\n"
        out += s["body"].strip() + "\n"
        if s.get("table"):
            out += "\n" + _render_table(s["table"]) + "\n"

    actions = findings.get("actions") or []
    if actions:
        out += "\n## Action list\n\n" + "\n".join(f"{i + 1}. {a}" for i, a in enumerate(actions)) + "\n"
    return out + definitions(out)


def definitions(report_text: str) -> str:
    """'Definitions' block for the glossary terms the report uses (empty when none)."""
    import re
    terms = json.loads(DEFINITIONS.read_text())["terms"]
    used = [t for t in terms if any(
        re.search(r"\b" + re.escape(m), report_text, 0 if t.get("case") else re.I) for m in t["match"])]
    if not used:
        return ""
    return "\n## Definitions\n\n" + "\n".join(f"- **{t['term']}** — {t['text']}" for t in used) + "\n"


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--generated-at", default=None, help="ISO8601 UTC (default: now)")
    args = ap.parse_args()
    try:
        findings = json.loads(Path(args.findings).read_text())
        md = build(findings, generated_at=args.generated_at)
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"ERROR {e}")
        return 1
    Path(args.out).write_text(md)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
