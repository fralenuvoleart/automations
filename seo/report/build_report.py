#!/usr/bin/env python3
"""Render an SEO findings JSON into a Markdown report (mechanical, deterministic).

The LLM writes findings JSON ([`seo/references/findings-schema.json`](../references/findings-schema.json));
this script renders the header (from `templates/base.md`) and every section — tables are rendered
mechanically. The narrative stays exactly as the LLM wrote it (no rewriting).

Usage:
    python3 seo/report/build_report.py --findings findings.json --out report.md [--generated-at ISO8601]
Exit codes: 0 = written.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # seo/
import window  # noqa: E402

TEMPLATE = HERE / "templates" / "base.md"


def _render_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
    return "\n".join([header, sep, *body])


def build(findings: dict, generated_at: str | None = None) -> str:
    tmpl = TEMPLATE.read_text()
    win = findings.get("window") or {}
    line = window.as_of_line(win, generated_at=generated_at)
    out = (tmpl
           .replace("{{title}}", str(findings.get("skill", "SEO Report")))
           .replace("{{as_of_line}}", line)
           .replace("{{verdict}}", str(findings.get("verdict", "")))).rstrip() + "\n"

    for s in findings.get("sections", []):
        out += f"\n## {s['heading']}\n\n{s['body'].strip()}\n"
        if s.get("table"):
            out += "\n" + _render_table(s["table"]) + "\n"

    actions = findings.get("actions") or []
    if actions:
        out += "\n## Action list\n\n" + "\n".join(f"{i + 1}. {a}" for i, a in enumerate(actions)) + "\n"
    return out


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--findings", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--generated-at", default=None, help="ISO8601 UTC (default: now)")
    args = ap.parse_args()

    findings = json.loads(Path(args.findings).read_text())
    md = build(findings, generated_at=args.generated_at)
    Path(args.out).write_text(md)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
