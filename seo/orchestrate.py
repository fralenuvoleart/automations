#!/usr/bin/env python3
"""Orchestrate phase: resolve the window and seed a run directory + findings skeleton.

Writes `.run_state.json` (state carried between steps) and a `findings.json`
skeleton conforming to [`seo/references/findings-schema.json`](references/findings-schema.json),
so the Analyze step starts from known paths instead of LLM memory.

Usage:
    python3 seo/orchestrate.py --skill seo-audit --days 90 --compare --out-dir .output/seo-audit
Exit codes: 0 = written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import window  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skill", required=True)
    ap.add_argument("--days", type=int, required=True)
    ap.add_argument("--lag", type=int, default=window.DEFAULT_LAG)
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--as-of", dest="as_of", default=None, help="YYYY-MM-DD anchor (default: today UTC)")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else None
    win = window.resolve(args.days, as_of, args.lag, args.compare)
    run_dir = Path(args.out_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / ".run_state.json").write_text(json.dumps({
        "skill": args.skill,
        "window": win,
        "paths": {
            "context": str(run_dir / "context.json"),
            "findings": str(run_dir / "findings.json"),
            "report": str(run_dir / "report.md"),
        },
        "created": datetime.now(timezone.utc).isoformat(),
    }, indent=2) + "\n")

    (run_dir / "context.json").write_text("{}\n")

    (run_dir / "findings.json").write_text(json.dumps({
        "skill": args.skill,
        "as_of": win["as_of"],
        "window": win,
        "verdict": "",
        "sections": [],
    }, indent=2) + "\n")

    print(f"wrote {run_dir}/.run_state.json, context.json, and findings.json "
          f"(window {win['startDate']}\u2192{win['endDate']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
