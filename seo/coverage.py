#!/usr/bin/env python3
"""Compute the report ``coverage`` block from a site profile + a covered list.

Deterministic: given the site profile's priority keywords/pages and the set of
items the report actually addressed, emit the coverage block (flattened +
per-language) for ``findings.json``. Matching is case- and whitespace-insensitive.

Usage:
    python3 seo/coverage.py --site pbservices.ge --covered covered.txt
    python3 seo/coverage.py --site pbservices.ge --covered '["kw1","kw2"]'
    python3 seo/coverage.py --site pbservices.ge --covered covered.txt --pages pages.txt
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
    if value.strip().startswith("["):
        return [str(x) for x in json.loads(value)]
    return [x.strip() for x in value.split(",") if x.strip()]


def compute(domain: str, covered: list[str], pages: list[str]) -> dict:
    profile = site_profile.load_profile(domain)
    pk = profile.get("priority_keywords") or {}
    if isinstance(pk, list):  # tolerate a flat list
        pk = {"": pk}
    covered_set = {_norm(c) for c in covered}
    pages_set = {_norm(p) for p in pages}

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
        "priority_keywords": flat,
        "priority_pages": priority_pages,
        "covered": cov,
        "missing": miss,
        "by_language": by_lang,
    }
    if priority_pages:
        out["pages_covered"] = [p for p in priority_pages if _norm(p) in pages_set]
        out["pages_missing"] = [p for p in priority_pages if _norm(p) not in pages_set]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", required=True)
    ap.add_argument("--covered", default=None, help="file / JSON array / CSV of covered keywords")
    ap.add_argument("--pages", default=None, help="file / JSON array / CSV of covered pages")
    args = ap.parse_args(argv)
    try:
        out = compute(args.site, _read_list(args.covered), _read_list(args.pages))
    except (FileNotFoundError, KeyError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
