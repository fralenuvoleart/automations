#!/usr/bin/env python3
"""Orchestrate phase: resolve the window and seed a run directory.

Writes `.run_state.json` (window + paths), an empty evidence index `context.json`
(`{"calls": []}`, filled by `seo/record.py`), a `data/` folder for raw tool
responses, and a `findings.json` skeleton conforming to
[`seo/references/findings-schema.json`](references/findings-schema.json).
Refuses to overwrite an existing run unless `--force` is given.

Usage:
    python3 seo/orchestrate.py --skill seo-audit --days 90 --compare --out-dir .output/seo-audit
    python3 seo/orchestrate.py --skill seo-technical --source snapshot --out-dir .output/seo-technical
    python3 seo/orchestrate.py --skill seo-rank-tracking --weeks 8 --out-dir .output/seo-rank-tracking
Exit codes: 0 = written, 1 = refused (run exists).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import window  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--weeks", type=int, default=None, help="calendar weeks (Mon–Sun) instead of --days")
    ap.add_argument("--lag", type=int, default=None)
    ap.add_argument("--source", choices=window.SOURCES, default="gsc")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--yoy", action="store_true")
    ap.add_argument("--as-of", dest="as_of", default=None, help="YYYY-MM-DD anchor (default: today UTC)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--force", action="store_true", help="overwrite an existing run directory's files")
    args = ap.parse_args(argv)

    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else None
    if args.weeks and args.yoy:
        ap.error("--yoy is not available with --weeks")
    win = (window.resolve_weeks(args.weeks, as_of, args.lag, args.compare, args.source) if args.weeks
           else window.resolve(args.days, as_of, args.lag, args.compare, args.yoy, args.source))
    run_dir = Path(args.out_dir)
    targets = [run_dir / n for n in (".run_state.json", "context.json", "findings.json")]
    existing = [p for p in targets if p.exists()]
    if existing and not args.force:
        print(f"ERROR run already seeded ({', '.join(p.name for p in existing)} exist in {run_dir}); "
              f"use a new --out-dir or pass --force to overwrite", file=sys.stderr)
        return 1
    (run_dir / "data").mkdir(parents=True, exist_ok=True)

    (run_dir / ".run_state.json").write_text(json.dumps({
        "skill": args.skill,
        "window": win,
        "paths": {
            "context": str(run_dir / "context.json"),
            "data": str(run_dir / "data"),
            "findings": str(run_dir / "findings.json"),
            "report": str(run_dir / "report.md"),
        },
        "created": dt.datetime.now(dt.timezone.utc).isoformat(),
    }, indent=2) + "\n")
    (run_dir / "context.json").write_text(json.dumps({"calls": []}, indent=2) + "\n")
    (run_dir / "findings.json").write_text(json.dumps({
        "skill": args.skill,
        "as_of": win["as_of"],
        "window": win,
        "verdict": "",
        "sections": [],
    }, indent=2) + "\n")

    print(f"wrote {run_dir}/.run_state.json, context.json, findings.json and data/ ({window.as_of_line(win).split(' · generated')[0]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
