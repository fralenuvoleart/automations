#!/usr/bin/env python3
"""Orchestrate phase: resolve the window and seed a run directory.

Writes `.run_state.json` (window + paths), an empty evidence index `context.json`
(`{"calls": []}`, filled by `seo/record.py`), a `data/` folder for raw tool
responses, and a `findings.json` skeleton conforming to
[`seo/references/findings-schema.json`](references/findings-schema.json).
Refuses to overwrite an existing run unless `--force` is given.

The run folder is fixed (seo/runs.py): `<run_root>/<site>/<as_of>/<skill>[-<tag>]/`, with
`run_root` from seo/config/settings.json; it must be git-ignored. Prints `run_dir: <path>`.
`--out-dir` overrides the location (tests, one-off runs).

Usage:
    python3 seo/orchestrate.py --skill seo-audit --site pbservices.ge --days 90 --compare
    python3 seo/orchestrate.py --skill seo-technical --site pbservices.ge --source snapshot
    python3 seo/orchestrate.py --skill seo-rank-tracking --site pbservices.ge --weeks 8 --tag weekly
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
import runs  # noqa: E402
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
    ap.add_argument("--site", help="domain, e.g. pbservices.ge (run folder under run_root)")
    ap.add_argument("--tag", help="suffix for a second run of the same skill on one day, e.g. weekly")
    ap.add_argument("--out-dir", help="explicit run folder (overrides the run_root layout)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing run directory's files")
    args = ap.parse_args(argv)

    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else None
    if args.weeks and args.yoy:
        ap.error("--yoy is not available with --weeks")
    win = (window.resolve_weeks(args.weeks, as_of, args.lag, args.compare, args.source) if args.weeks
           else window.resolve(args.days, as_of, args.lag, args.compare, args.yoy, args.source))
    if args.site:
        try:
            runs._name(args.site, "site")
        except ValueError as e:
            ap.error(str(e))
    if args.out_dir:
        run_dir = Path(args.out_dir)
    elif args.site:
        try:
            run_dir = runs.run_dir(args.site, win["as_of"], args.skill, args.tag)
        except ValueError as e:
            ap.error(str(e))
        problem = runs.ignore_problem()
        if problem:
            print(f"ERROR {problem}: add it to .gitignore or set run_root in seo/config/settings.json", file=sys.stderr)
            return 1
    else:
        ap.error("pass --site (fixed run folder) or --out-dir")
    targets = [run_dir / n for n in (".run_state.json", "context.json", "findings.json")]
    existing = [p for p in targets if p.exists()]
    if existing and not args.force:
        print(f"ERROR run already seeded ({', '.join(p.name for p in existing)} exist in {run_dir}); "
              f"use --tag, a new --out-dir or pass --force to overwrite", file=sys.stderr)
        return 1
    (run_dir / "data").mkdir(parents=True, exist_ok=True)

    (run_dir / ".run_state.json").write_text(json.dumps({
        "skill": args.skill,
        "site": args.site,
        "tag": args.tag,
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
    print(f"run_dir: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
