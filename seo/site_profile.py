#!/usr/bin/env python3
"""Resolve a site's personalised SEO profile (deterministic, modular).

Profiles live in ``seo/config/sites/<domain>.json`` and are validated against
``seo/config/site-profile.schema.json``. Skills reference profile values as
``{{site:<key>}}`` tokens; ``resolve.py --write`` expands them to the retrieval
command so prioritisation is deterministic instead of LLM-guessed.

``priority_keywords`` is grouped by language; ``--get priority_keywords``
flattens across languages, ``--lang <code>`` returns one language.

Usage:
    python3 seo/site_profile.py --list
    python3 seo/site_profile.py --site pbservices.ge --get priority_keywords
    python3 seo/site_profile.py --site pbservices.ge --get priority_keywords --lang ru
    python3 seo/site_profile.py --site pbservices.ge --validate
    python3 seo/site_profile.py --site pbservices.ge --dump
Exit codes: 0 = ok, 1 = error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config"
SITES = CONFIG / "sites"
SCHEMA = CONFIG / "site-profile.schema.json"


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


def history_path(domain: str) -> Path:
    return SITES / f"{domain}.history.md"


def read_history(domain: str) -> str:
    p = history_path(domain)
    return p.read_text() if p.exists() else ""


def append_history(domain: str, text: str, when: str | None = None) -> Path:
    """Append a dated entry to the site's action history (append-only)."""
    p = history_path(domain)
    stamp = when or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    entry = f"- **{stamp}**: {text.strip()}\n"
    if not p.exists():
        p.write_text(f"# Action history — {domain}\n\n{entry}")
    else:
        with p.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    return p


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
        t = spec.get("type")
        if t and not _type_ok(val, t):
            issues.append(f"{key}: expected {t}, got {type(val).__name__}")
            continue
        if t == "array" and spec.get("items", {}).get("type") == "string":
            for i, item in enumerate(val):
                if not isinstance(item, str):
                    issues.append(f"{key}[{i}]: expected string")
        if t == "object":
            ap = spec.get("additionalProperties")
            if isinstance(ap, dict) and ap.get("type") == "array":
                for k, v in val.items():
                    if not isinstance(v, list):
                        issues.append(f"{key}.{k}: expected array")
                        continue
                    for i, item in enumerate(v):
                        if not isinstance(item, str):
                            issues.append(f"{key}.{k}[{i}]: expected string")
    # cross-field: priority_keywords language keys should be in `languages`
    langs_val = profile.get("languages")
    langs = {str(l).lower() for l in langs_val} if isinstance(langs_val, list) else set()
    pk = profile.get("priority_keywords")
    if isinstance(pk, dict) and langs:
        for k in pk:
            if k.lower() not in langs:
                issues.append(f"priority_keywords.{k}: not in languages {sorted(langs)}")
    return issues


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
    return val


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", help="domain, e.g. pbservices.ge")
    ap.add_argument("--get", help="profile key to print")
    ap.add_argument("--lang", help="language code filter (for priority_keywords)")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--dump", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--history", action="store_true", help="print the site's action history")
    ap.add_argument("--append-history", dest="append_history", default=None,
                    help="append a dated entry to the site's action history")
    args = ap.parse_args(argv)

    if args.list:
        for s in list_sites():
            print(s)
        return 0
    if not args.site:
        ap.error("--site is required (or use --list)")
    try:
        if args.append_history:
            p = append_history(args.site, args.append_history)
            print(f"appended to {p}")
            return 0
        if args.history:
            print(read_history(args.site), end="")
            return 0
        if args.validate:
            issues = validate(load_profile(args.site))
            for i in issues:
                print(f"ERROR {i}")
            print("OK — profile valid" if not issues else f"{len(issues)} issue(s)")
            return 1 if issues else 0
        if args.get:
            print(json.dumps(get(args.site, args.get, args.lang), ensure_ascii=False, indent=2))
            return 0
        if args.dump:
            print(json.dumps(load_profile(args.site), ensure_ascii=False, indent=2))
            return 0
    except (FileNotFoundError, KeyError) as e:
        print(f"ERROR {e}")
        return 1
    ap.error("choose one of --get/--validate/--dump/--list")
    return 2


if __name__ == "__main__":
    sys.exit(main())
