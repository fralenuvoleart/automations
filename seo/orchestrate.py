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


class SeedError(Exception):
    """The run cannot be seeded (bad name, unsafe run_root, run already exists)."""


def seed(skill: str, site: str | None = None, days: int = 28, weeks: int | None = None, lag: int | None = None,
         source: str = "gsc", compare: bool = False, yoy: bool = False, as_of: dt.date | None = None,
         tag: str | None = None, out_dir: str | Path | None = None, force: bool = False) -> Path:
    """Resolve the window and write .run_state.json, context.json, findings.json and data/. Returns the run dir."""
    if weeks and yoy:
        raise SeedError("--yoy is not available with --weeks")
    win = (window.resolve_weeks(weeks, as_of, lag, compare, source) if weeks
           else window.resolve(days, as_of, lag, compare, yoy, source))
    try:
        if site:
            runs._name(site, "site")
        if out_dir:
            run_dir = Path(out_dir)
        elif site:
            run_dir = runs.run_dir(site, win["as_of"], skill, tag)
        else:
            raise SeedError("pass --site (fixed run folder) or --out-dir")
    except ValueError as e:
        raise SeedError(str(e)) from e
    if not out_dir:
        problem = runs.ignore_problem()
        if problem:
            raise SeedError(f"{problem}: add it to .gitignore or set run_root in seo/config/settings.json")
    targets = [run_dir / n for n in (".run_state.json", "context.json", "findings.json")]
    existing = [p for p in targets if p.exists()]
    if existing and not force:
        raise SeedError(f"run already seeded ({', '.join(p.name for p in existing)} exist in {run_dir}); "
                        f"use --tag, a new --out-dir or pass --force to overwrite")
    (run_dir / "data").mkdir(parents=True, exist_ok=True)

    (run_dir / ".run_state.json").write_text(json.dumps({
        "skill": skill,
        "site": site,
        "tag": tag,
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
        "skill": skill,
        "as_of": win["as_of"],
        "window": win,
        "verdict": "",
        "sections": [],
    }, indent=2) + "\n")
    return run_dir


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
    if args.site:
        try:
            runs._name(args.site, "site")
        except ValueError as e:
            ap.error(str(e))
    if not args.site and not args.out_dir:
        ap.error("pass --site (fixed run folder) or --out-dir")
    if args.weeks and args.yoy:
        ap.error("--yoy is not available with --weeks")
    try:
        run_dir = seed(args.skill, args.site, args.days, args.weeks, args.lag, args.source, args.compare, args.yoy,
                       dt.date.fromisoformat(args.as_of) if args.as_of else None, args.tag, args.out_dir, args.force)
    except SeedError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    win = json.loads((run_dir / ".run_state.json").read_text())["window"]
    print(f"wrote {run_dir}/.run_state.json, context.json, findings.json and data/ ({window.as_of_line(win).split(' · generated')[0]})")
    print(f"run_dir: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
