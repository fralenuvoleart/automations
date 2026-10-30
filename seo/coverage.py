#!/usr/bin/env python3
"""Compute the report ``coverage`` block from a site profile.

Two deterministic bases:
- ``--gsc <query rows>`` (preferred): a priority keyword is **covered** when the
  site had ≥1 impression for it in the window (exact match after case/space
  normalisation); ``--gsc-pages <page rows>`` does the same for priority pages.
  "Missing" then means *no search visibility* — a content/ranking gap.
- ``--covered <list>`` (manual): the keywords the report explicitly addressed.

Usage:
    python3 seo/coverage.py --site pbservices.ge --gsc {run_dir}/data/query_cur.json [--gsc-pages {run_dir}/data/page_cur.json]
    python3 seo/coverage.py --site pbservices.ge --covered '["kw1","kw2"]'
Exit codes: 0 = printed to stdout, 1 = error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import site_profile  # noqa: E402


def _norm(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def _norm_url(u: str) -> str:
    return _norm(u).rstrip("/")


def _read_list(value: str | None) -> list[str]:
    """Accept a file path (newline- or JSON-array), an inline JSON array, or CSV."""
    if not value:
        return []
    p = Path(value)
    if p.exists():
        text = p.read_text().strip()
        if text.startswith("["):
            return [str(x) for x in json.loads(text)]
        return [ln.strip() for ln in text.splitlines() if ln.strip()]
    if value.lower().endswith((".txt", ".json", ".csv", ".tsv")):
        raise FileNotFoundError(f"file not found: '{value}'")
    if value.strip().startswith("["):
        return [str(x) for x in json.loads(value)]
    return [x.strip() for x in value.split(",") if x.strip()]


def visible_items(path: str, dim: str) -> list[str]:
    """Items (queries or pages) with ≥1 impression in a recorded GSC response."""
    import gsc_metrics
    rows = gsc_metrics.load_rows(path, [dim])
    return [r[dim] for r in rows if r["impressions"] > 0]


def compute(domain: str, covered: list[str], pages: list[str], basis: str = "manual") -> dict:
    profile = site_profile.load_profile(domain)
    pk = profile.get("priority_keywords") or {}
    if isinstance(pk, list):  # tolerate a flat list
        pk = {"": pk}
    covered_set = {_norm(c) for c in covered}
    pages_set = {_norm_url(p) for p in pages}

    flat: list[str] = []
    cov: list[str] = []
    miss: list[str] = []
    by_lang: dict[str, dict] = {}
    for lang in sorted(pk):
        items = pk[lang]
        lc = lm = 0
        for kw in items:
            flat.append(kw)
            if _norm(kw) in covered_set:
                cov.append(kw)
                lc += 1
            else:
                miss.append(kw)
                lm += 1
        by_lang[lang] = {"total": len(items), "covered": lc, "missing": lm}

    priority_pages = profile.get("priority_pages") or []
    out: dict = {
        "basis": basis,
        "priority_keywords": flat,
        "priority_pages": priority_pages,
        "covered": cov,
        "missing": miss,
        "by_language": by_lang,
    }
    if priority_pages:
        out["pages_covered"] = [p for p in priority_pages if _norm_url(p) in pages_set]
        out["pages_missing"] = [p for p in priority_pages if _norm_url(p) not in pages_set]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--gsc", help="recorded gsc.query response (covered = ≥1 impression)")
    g.add_argument("--covered", help="file / JSON array / CSV of keywords the report addressed")
    ap.add_argument("--gsc-pages", help="recorded gsc.page response (pages with ≥1 impression)")
    ap.add_argument("--pages", help="file / JSON array / CSV of covered pages (manual basis)")
    args = ap.parse_args(argv)
    try:
        if args.gsc:
            kws = visible_items(args.gsc, "query")
            pages = visible_items(args.gsc_pages, "page") if args.gsc_pages else _read_list(args.pages)
            out = compute(args.site, kws, pages, basis="gsc_impressions")
        else:
            out = compute(args.site, _read_list(args.covered), _read_list(args.pages), basis="manual")
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
