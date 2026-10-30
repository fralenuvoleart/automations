#!/usr/bin/env python3
"""Deterministic analysis of DataForSEO responses (all results are index **estimates**).

Commands (print JSON):
    anchor-mix   --anchors F --site D           # brand / URL / generic / exact-match / other shares
    link-gap     --ours F --theirs F [--top N]  # strong domains linking to the competitor, not to us
    keyword-gap  --ranked F --query F [--top N] # competitor keywords with no impressions for the site
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gsc_metrics  # noqa: E402

GENERIC_ANCHORS = {
    "click here", "here", "website", "link", "read more", "learn more", "more", "this", "source", "visit",
    "home", "homepage", "подробнее", "здесь", "тут", "сайт", "ссылка", "источник", "перейти",
}
EXACT_MATCH_HEURISTIC_MAX = 0.10  # heuristic risk threshold (domain-knowledge.md → Links)


def _bare(host) -> str:
    """Lower-cased host without a leading 'www.' (Python 3.8-compatible)."""
    return re.sub(r"^www\.", "", str(host or "").lower())


def items(payload) -> list[dict]:
    """Collect result items from DataForSEO's tasks[].result[].items[] (or a bare list)."""
    payload = gsc_metrics._unwrap(payload)
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    out: list[dict] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("items"), list):
            return [x for x in payload["items"] if isinstance(x, dict)]
        for t in payload.get("tasks") or []:
            for r in (t or {}).get("result") or []:
                out.extend(x for x in (r or {}).get("items") or [] if isinstance(x, dict))
    if not out and not (isinstance(payload, dict) and "tasks" in payload):
        raise ValueError("unrecognised DataForSEO response shape")
    return out


def anchor_mix(anchor_items: list[dict], is_brand, domain: str, priority_keywords: list[str]) -> dict:
    """Anchor buckets; ``is_brand`` is the site-rules Brand classifier."""
    kws = {gsc_metrics.norm_text(k) for k in priority_keywords}
    host = _bare(domain)
    buckets = {"brand": 0.0, "url": 0.0, "generic": 0.0, "exact_match": 0.0, "other": 0.0, "empty": 0.0}
    examples: dict[str, list] = {k: [] for k in buckets}
    for it in anchor_items:
        a = str(it.get("anchor") or "").strip()
        w = float(it.get("backlinks") or it.get("referring_domains") or 1)
        n = gsc_metrics.norm_text(a)
        if not n:
            b = "empty"
        elif host in a.lower() or re.match(r"^(https?://|www\.)", a.lower()):
            b = "url"
        elif is_brand(a):
            b = "brand"
        elif n in GENERIC_ANCHORS:
            b = "generic"
        elif n in kws:
            b = "exact_match"
        else:
            b = "other"
        buckets[b] += w
        if len(examples[b]) < 5 and a:
            examples[b].append(a)
    total = sum(buckets.values()) or 1.0
    shares = {k: round(v / total, 3) for k, v in buckets.items()}
    non_brand = {k: v for k, v in shares.items() if k in ("generic", "exact_match", "other")}
    risk = shares["exact_match"] > EXACT_MATCH_HEURISTIC_MAX or (
        shares["exact_match"] > 0 and max(non_brand, key=non_brand.get) == "exact_match")
    return {"shares": shares, "examples": examples, "weighted_by": "backlinks",
            "exact_match_risk": risk, "label": "estimate (third-party index); risk flag is a heuristic"}


def link_gap(ours: list[dict], theirs: list[dict], top: int = 50) -> list[dict]:
    mine = {_bare(i.get("domain")) for i in ours}
    gap = [{"domain": i.get("domain"), "rank": i.get("rank"), "backlinks": i.get("backlinks")}
           for i in theirs if _bare(i.get("domain")) not in mine]
    return sorted(gap, key=lambda r: -(r["rank"] or 0))[:top]


def _find(d, key):
    if isinstance(d, dict):
        if key in d:
            return d[key]
        for v in d.values():
            r = _find(v, key)
            if r is not None:
                return r
    return None


def keyword_gap(ranked: list[dict], query_rows: list[dict], top: int = 100) -> list[dict]:
    have = {gsc_metrics.norm_text(r["query"]) for r in query_rows if r["impressions"] > 0}
    out = []
    for it in ranked:
        kw = _find(it, "keyword")
        if not isinstance(kw, str) or gsc_metrics.norm_text(kw) in have:
            continue
        out.append({"keyword": kw, "search_volume": _find(it, "search_volume"),
                    "competitor_position": _find(it, "rank_group"), "competitor_url": _find(it, "url")})
    return sorted(out, key=lambda r: -(r["search_volume"] or 0))[:top]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["anchor-mix", "link-gap", "keyword-gap"])
    for opt in ("anchors", "ours", "theirs", "ranked", "query", "site"):
        ap.add_argument(f"--{opt}")
    ap.add_argument("--top", type=int, default=None)
    a = ap.parse_args(argv)
    load = lambda p: items(json.loads(Path(p).read_text()))  # noqa: E731
    try:
        if a.command == "anchor-mix":
            import rules
            import site_profile
            pk = site_profile.get(a.site, "priority_keywords")
            res = anchor_mix(load(a.anchors), rules.load(a.site).is_brand, a.site, pk)
        elif a.command == "link-gap":
            res = {"link_gap": link_gap(load(a.ours), load(a.theirs), a.top or 50), "label": "estimate"}
        else:
            res = {"keyword_gap": keyword_gap(load(a.ranked), gsc_metrics.load_rows(a.query, ["query"]), a.top or 100),
                   "label": "competitor data is an estimate; site data from GSC"}
    except (ValueError, FileNotFoundError, KeyError, TypeError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
