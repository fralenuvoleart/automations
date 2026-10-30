#!/usr/bin/env python3
"""Deterministic date-window resolver for the SEO skills.

Turns a relative window ("last N days") into absolute ``YYYY-MM-DD`` dates so
tool calls are reproducible. Each data source has its own default lag:
GSC final data lands 2–3 days late (default 3), GA4 processed data within
~1–2 days (default 2). A ``snapshot`` window is for live, undated data
(PageSpeed, DataForSEO live endpoints).

Usage:
    python3 seo/window.py --days 28
    python3 seo/window.py --days 90 --compare            # vs the previous 90 days
    python3 seo/window.py --days 90 --compare --yoy      # vs the same dates a year earlier
    python3 seo/window.py --days 28 --source ga4 --as-of 2026-10-29
    python3 seo/window.py --weeks 8                      # 8 calendar weeks (Mon–Sun) ending with the latest complete week
    python3 seo/window.py --source snapshot
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

DEFAULT_LAGS = {"gsc": 3, "ga4": 2, "snapshot": 0}
DEFAULT_LAG = DEFAULT_LAGS["gsc"]
SOURCES = tuple(DEFAULT_LAGS)
YOY_DAYS = 364  # 52 weeks: keeps weekdays aligned


def resolve(days: int = 28, as_of: dt.date | None = None, lag: int | None = None,
            compare: bool = False, yoy: bool = False, source: str = "gsc") -> dict:
    """Return absolute start/end (and comparison) dates as ISO strings.

    ``as_of`` defaults to today in UTC; pass it explicitly for reproducibility.
    """
    if source not in DEFAULT_LAGS:
        raise ValueError(f"source must be one of {SOURCES}")
    today = as_of or dt.datetime.now(dt.timezone.utc).date()
    if source == "snapshot":
        return {"source": "snapshot", "startDate": today.isoformat(), "endDate": today.isoformat(),
                "days": 1, "lag": 0, "as_of": today.isoformat()}
    if days < 1:
        raise ValueError("days must be >= 1")
    lag = DEFAULT_LAGS[source] if lag is None else lag
    if lag < 1:
        raise ValueError("lag must be >= 1 (never include today)")
    end = today - dt.timedelta(days=lag)
    start = end - dt.timedelta(days=days - 1)
    out = {
        "source": source,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "days": days,
        "lag": lag,
        "as_of": today.isoformat(),
    }
    if compare or yoy:
        if yoy:
            cstart, cend = start - dt.timedelta(days=YOY_DAYS), end - dt.timedelta(days=YOY_DAYS)
        else:
            cend = start - dt.timedelta(days=1)
            cstart = cend - dt.timedelta(days=days - 1)
        out["compareStartDate"] = cstart.isoformat()
        out["compareEndDate"] = cend.isoformat()
        out["compareMode"] = "yoy" if yoy else "previous"
    return out


def resolve_weeks(weeks: int = 1, as_of: dt.date | None = None, lag: int | None = None,
                  compare: bool = False, source: str = "gsc") -> dict:
    """Calendar weeks (Monday–Sunday) ending with the latest complete week the source's lag allows.

    ``weeks`` lists each week, so one pull per week stays inside the run window; ``compare``
    adds the same number of weeks just before.
    """
    if source not in ("gsc", "ga4"):
        raise ValueError("weekly windows need a dated source (gsc or ga4)")
    if weeks < 1:
        raise ValueError("weeks must be >= 1")
    today = as_of or dt.datetime.now(dt.timezone.utc).date()
    lag = DEFAULT_LAGS[source] if lag is None else lag
    if lag < 1:
        raise ValueError("lag must be >= 1 (never include today)")
    latest = today - dt.timedelta(days=lag)
    end = latest - dt.timedelta(days=(latest.weekday() + 1) % 7)  # last Sunday with data
    start = end - dt.timedelta(days=7 * weeks - 1)
    out = {
        "source": source,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "days": 7 * weeks,
        "lag": lag,
        "as_of": today.isoformat(),
        "weeks": [{"startDate": (start + dt.timedelta(days=7 * i)).isoformat(),
                   "endDate": (start + dt.timedelta(days=7 * i + 6)).isoformat()} for i in range(weeks)],
    }
    if compare:
        cend = start - dt.timedelta(days=1)
        out["compareStartDate"] = (cend - dt.timedelta(days=7 * weeks - 1)).isoformat()
        out["compareEndDate"] = cend.isoformat()
        out["compareMode"] = "previous"
    return out


def as_of_line(window: dict, generated_at: str | None = None) -> str:
    """Human-readable provenance line for report output."""
    stamp = generated_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    source = window.get("source", "gsc")
    if source == "snapshot":
        return f"Snapshot as of {window.get('as_of') or window.get('endDate')} (live data) · generated {stamp}"
    span = f"{window['startDate']}→{window['endDate']}"
    if window.get("weeks"):
        span += f" ({len(window['weeks'])} Mon–Sun week{'s' if len(window['weeks']) > 1 else ''})"
    if "compareStartDate" in window and "compareEndDate" in window:
        tag = "YoY " if window.get("compareMode") == "yoy" else ""
        span += f" (vs {tag}{window['compareStartDate']}→{window['compareEndDate']})"
    lag = window.get("lag", DEFAULT_LAGS.get(source, DEFAULT_LAG))
    return f"Window {span} · {source.upper()} lag {lag}d · generated {stamp}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--weeks", type=int, default=None, help="calendar weeks (Mon–Sun) instead of --days")
    ap.add_argument("--lag", type=int, default=None, help="override the source's default lag")
    ap.add_argument("--source", choices=SOURCES, default="gsc")
    ap.add_argument("--as-of", dest="as_of", default=None, help="YYYY-MM-DD anchor date (default: today UTC)")
    ap.add_argument("--compare", action="store_true", help="add the previous period")
    ap.add_argument("--yoy", action="store_true", help="compare with the same dates 52 weeks earlier")
    args = ap.parse_args(argv)
    as_of = dt.date.fromisoformat(args.as_of) if args.as_of else None
    if args.weeks and args.yoy:
        ap.error("--yoy is not available with --weeks")
    window = (resolve_weeks(args.weeks, as_of, args.lag, args.compare, args.source) if args.weeks
              else resolve(args.days, as_of, args.lag, args.compare, args.yoy, args.source))
    print(json.dumps(window, indent=2))
    print(as_of_line(window), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
