#!/usr/bin/env python3
"""Deterministic date-window resolver for the SEO skills.

Turns a relative window ("last N days") into absolute ``YYYY-MM-DD`` dates so
tool calls are reproducible. GSC data lags ~2 days, so the default end date
excludes today.

Usage:
    python3 seo/window.py --days 28
    python3 seo/window.py --days 90 --compare
    python3 seo/window.py --days 28 --lag 2 --as-of 2026-10-29
"""
from __future__ import annotations

import argparse
import datetime as dt
import json

DEFAULT_LAG = 2


def resolve(days: int, as_of: dt.date | None = None, lag: int = DEFAULT_LAG,
            compare: bool = False) -> dict:
    """Return absolute start/end (and previous-period) dates as ISO strings.

    ``as_of`` defaults to today in UTC; pass it explicitly for reproducibility.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    if lag < 0:
        raise ValueError("lag must be >= 0")
    today = as_of or dt.datetime.now(dt.timezone.utc).date()
    end = today - dt.timedelta(days=lag)
    start = end - dt.timedelta(days=days - 1)
    out = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "days": days,
        "lag": lag,
        "as_of": today.isoformat(),
    }
    if compare:
        cend = start - dt.timedelta(days=1)
        cstart = cend - dt.timedelta(days=days - 1)
        out["compareStartDate"] = cstart.isoformat()
        out["compareEndDate"] = cend.isoformat()
    return out


def as_of_line(window: dict, generated_at: str | None = None) -> str:
    """Human-readable provenance line for report output."""
    stamp = generated_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    span = f"{window['startDate']}\u2192{window['endDate']}"
    if "compareStartDate" in window and "compareEndDate" in window:
        span += f" (vs {window['compareStartDate']}\u2192{window['compareEndDate']})"
    lag = window.get("lag", DEFAULT_LAG)
    return f"Window {span} \u00b7 GSC lag {lag}d \u00b7 generated {stamp}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, required=True)
    ap.add_argument("--lag", type=int, default=DEFAULT_LAG)
    ap.add_argument("--as-of", dest="as_of", default=None,
                    help="YYYY-MM-DD anchor date (default: today UTC)")
    ap.add_argument("--compare", action="store_true")
    args = ap.parse_args()
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else None
    window = resolve(args.days, as_of, args.lag, args.compare)
    print(json.dumps(window, indent=2))
    print(as_of_line(window), file=__import__("sys").stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
