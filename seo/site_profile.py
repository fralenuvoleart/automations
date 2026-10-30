#!/usr/bin/env python3
"""Resolve a site's personalised SEO profile (deterministic, modular).

Profiles live in ``seo/config/sites/<domain>.json`` and are validated against
``seo/config/site-profile.schema.json``. Skills reference profile values as
``{{site:<key>}}`` tokens, rendered to the retrieval command below.

``priority_keywords`` is grouped by language; ``--get priority_keywords``
flattens across languages, ``--lang <code>`` returns one language.

Usage:
    python3 seo/site_profile.py --list
    python3 seo/site_profile.py --site pbservices.ge --get priority_keywords [--lang ru]
    python3 seo/site_profile.py --site pbservices.ge --validate
    python3 seo/site_profile.py --site pbservices.ge --dump
    python3 seo/site_profile.py --site pbservices.ge --thresholds          # defaults merged with overrides
    python3 seo/site_profile.py --site pbservices.ge --ga4-ai-filter       # GA4 dimension_filter from ai_sources
    python3 seo/site_profile.py --site pbservices.ge --history [--status done]
    python3 seo/site_profile.py --site pbservices.ge --append-history "text" --status recommended|done
Exit codes: 0 = ok, 1 = error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config"
SITES = CONFIG / "sites"
SCHEMA = CONFIG / "site-profile.schema.json"
STATUSES = ("recommended", "done")
HISTORY_LINE_RE = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\* \[(recommended|done)\] (.+)$")


def load_schema() -> dict:
    return json.loads(SCHEMA.read_text())


def profile_path(domain: str) -> Path:
    return SITES / f"{domain}.json"


def load_profile(domain: str) -> dict:
    p = profile_path(domain)
    if not p.exists():
        raise FileNotFoundError(f"no profile for '{domain}' ({p})")
    return json.loads(p.read_text())


def list_sites() -> list[str]:
    return sorted(p.stem for p in SITES.glob("*.json"))


# ----------------------------------------------------------------- history ---
def history_path(domain: str) -> Path:
    return SITES / f"{domain}.history.md"


def read_history(domain: str, status: str | None = None) -> str:
    """Whole log, or only the entries with ``status`` (done entries suppress re-recommendation)."""
    p = history_path(domain)
    if not p.exists():
        return ""
    text = p.read_text()
    if not status:
        return text
    return "".join(ln + "\n" for ln in text.splitlines() if (m := HISTORY_LINE_RE.match(ln)) and m.group(2) == status)


def append_history(domain: str, text: str, when: str | None = None, status: str = "recommended") -> Path | None:
    """Append a dated, status-tagged entry; an identical status+text entry is not duplicated."""
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    p = history_path(domain)
    body = " ".join(text.split())
    if p.exists():
        for ln in p.read_text().splitlines():
            m = HISTORY_LINE_RE.match(ln)
            if m and m.group(2) == status and m.group(3) == body:
                return None
    stamp = when or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    entry = f"- **{stamp}** [{status}] {body}\n"
    if not p.exists():
        p.write_text(f"# Action history — {domain}\n\n{entry}")
    else:
        with p.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    return p


# -------------------------------------------------------------- validation ---
def _type_ok(val, t: str) -> bool:
    if t == "string":
        return isinstance(val, str)
    if t == "array":
        return isinstance(val, list)
    if t == "object":
        return isinstance(val, dict)
    if t == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if t == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    if t == "boolean":
        return isinstance(val, bool)
    return True


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", str(s).casefold()).split())


def _check_value(key: str, val, spec: dict, issues: list[str]) -> None:
    t = spec.get("type")
    if t and not _type_ok(val, t):
        issues.append(f"{key}: expected {t}, got {type(val).__name__}")
        return
    if t == "array":
        item = spec.get("items", {})
        for i, it in enumerate(val):
            if item.get("type") and not _type_ok(it, item["type"]):
                issues.append(f"{key}[{i}]: expected {item['type']}")
            elif item.get("pattern") and isinstance(it, str) and not re.match(item["pattern"], it):
                issues.append(f"{key}[{i}]: {it!r} does not match {item['pattern']}")
        if spec.get("maxItems") is not None and len(val) > spec["maxItems"]:
            issues.append(f"{key}: at most {spec['maxItems']} items")
    if t == "string" and spec.get("pattern") and not re.match(spec["pattern"], val):
        issues.append(f"{key}: {val!r} does not match {spec['pattern']}")
    if t == "object":
        props = spec.get("properties")
        ap = spec.get("additionalProperties")
        for k, v in val.items():
            if props is not None and k in props:
                _check_value(f"{key}.{k}", v, props[k], issues)
            elif isinstance(ap, dict):
                _check_value(f"{key}.{k}", v, ap, issues)
            elif ap is False:
                issues.append(f"{key}: unknown key '{k}'")


def validate(profile: dict, schema: dict | None = None) -> list[str]:
    """Return a list of human-readable issues (empty == valid)."""
    schema = schema or load_schema()
    issues: list[str] = []
    for key in schema.get("required", []):
        if key not in profile:
            issues.append(f"missing required key: {key}")
    props = schema.get("properties", {})
    for key, val in profile.items():
        spec = props.get(key)
        if spec is None:
            issues.append(f"unknown key: {key}")
            continue
        _check_value(key, val, spec, issues)

    langs_val = profile.get("languages")
    langs = {str(x).lower() for x in langs_val} if isinstance(langs_val, list) else set()
    for field in ("priority_keywords", "language_paths", "ads_language_constants", "serp_locations"):
        v = profile.get(field)
        if isinstance(v, dict) and langs:
            for k in v:
                if k.lower() not in langs:
                    issues.append(f"{field}.{k}: not in languages {sorted(langs)}")
    lp = profile.get("language_paths")
    if isinstance(lp, dict):
        for k, prefix in lp.items():
            if isinstance(prefix, str) and not (prefix.startswith("/") and prefix.endswith("/")):
                issues.append(f"language_paths.{k}: prefix {prefix!r} must start and end with '/'")
    brands = {_norm(b) for b in profile.get("brand_terms") or [] if isinstance(b, str)}
    pk = profile.get("priority_keywords")
    if isinstance(pk, dict) and brands:
        for lang, items in pk.items():
            for kw in items if isinstance(items, list) else []:
                if isinstance(kw, str) and _norm(kw) in brands:
                    issues.append(f"priority_keywords.{lang}: '{kw}' is a brand term — keep brand terms only in brand_terms")
    return issues


# ------------------------------------------------------------------ access ---
def get(domain: str, key: str, lang: str | None = None) -> object:
    profile = load_profile(domain)
    if key not in profile:
        raise KeyError(f"'{key}' not in profile for '{domain}'")
    val = profile[key]
    if key == "priority_keywords" and isinstance(val, dict):
        if lang:
            target = lang.lower()
            for k, items in val.items():
                if k.lower() == target:
                    return items
            return []
        out: list[str] = []
        for k in sorted(val):
            out.extend(val[k])
        return out
    if lang and isinstance(val, dict):
        for k, v in val.items():
            if k.lower() == lang.lower():
                return v
        return None
    return val


def thresholds(domain: str) -> dict:
    """Analysis thresholds: gsc_metrics defaults overridden by the profile's `thresholds`."""
    sys.path.insert(0, str(HERE))
    import gsc_metrics
    return {**gsc_metrics.DEFAULTS, **(load_profile(domain).get("thresholds") or {})}


def ga4_ai_filter(domain: str) -> dict:
    """GA4 Data API dimension_filter matching every profile `ai_sources` host and its subdomains."""
    hosts = [h.strip().lower() for h in load_profile(domain).get("ai_sources") or [] if h.strip()]
    if not hosts:
        raise KeyError(f"profile '{domain}' has no ai_sources")
    alt = "|".join(re.escape(h) for h in sorted(set(hosts)))
    return {"filter": {"field_name": "sessionSource",
                       "string_filter": {"match_type": "FULL_REGEXP", "value": f"^(.*\\.)?({alt})$",
                                         "case_sensitive": False}}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", help="domain, e.g. pbservices.ge")
    ap.add_argument("--get", help="profile key to print")
    ap.add_argument("--lang", help="language code filter (priority_keywords / per-language maps)")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--thresholds", action="store_true")
    ap.add_argument("--ga4-ai-filter", dest="ga4_ai_filter", action="store_true")
    ap.add_argument("--history", action="store_true", help="print the site's action history")
    ap.add_argument("--append-history", dest="append_history", default=None)
    ap.add_argument("--status", choices=STATUSES, default=None,
                    help="history entry status (append default: recommended; read: filter)")
    args = ap.parse_args(argv)

    if args.list:
        for s in list_sites():
            print(s)
        return 0
    if not args.site:
        ap.error("--site is required (or use --list)")
    try:
        if args.append_history:
            p = append_history(args.site, args.append_history, status=args.status or "recommended")
            print(f"appended to {p}" if p else "already recorded (no duplicate written)")
            return 0
        if args.history:
            print(read_history(args.site, args.status), end="")
            return 0
        if args.validate:
            issues = validate(load_profile(args.site))
            for i in issues:
                print(f"ERROR {i}")
            print("OK — profile valid" if not issues else f"{len(issues)} issue(s)")
            return 1 if issues else 0
        if args.thresholds:
            print(json.dumps(thresholds(args.site), indent=2))
            return 0
        if args.ga4_ai_filter:
            print(json.dumps(ga4_ai_filter(args.site), ensure_ascii=False))
            return 0
        if args.get:
            print(json.dumps(get(args.site, args.get, args.lang), ensure_ascii=False, indent=2))
            return 0
        if args.dump:
            print(json.dumps(load_profile(args.site), ensure_ascii=False, indent=2))
            return 0
    except (FileNotFoundError, KeyError, ValueError) as e:
        print(f"ERROR {e}")
        return 1
    ap.error("choose one of --get/--validate/--dump/--list/--thresholds/--ga4-ai-filter/--history")
    return 2


if __name__ == "__main__":
    sys.exit(main())
