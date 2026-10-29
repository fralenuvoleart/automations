#!/usr/bin/env python3
"""Resolve SEO capability IDs to deterministic MCP call specs.

Skills reference logical capabilities as ``{{cap:<id>}}`` tokens. This script
expands them to `` `server` -> `tool` { args } (supply: runtime) `` from
``seo/capabilities.json`` so the LLM executes deterministically.

Usage:
    python3 seo/resolve.py --check          # verify tokens resolve; report alias drift
    python3 seo/resolve.py --validate-live  # spawn each server; validate tool + args vs live inputSchema
    python3 seo/resolve.py --write          # rewrite skills in place (expand tokens + remap aliases)
    python3 seo/resolve.py --list           # list capabilities and their current call spec

Exit codes: 0 = clean, 1 = issues found (--check / --validate-live).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REGISTRY = HERE / "capabilities.json"
MCP_JSON = ROOT / ".roo" / "mcp.json"
SKILLS = ROOT / ".agents" / "skills"

TOKEN_RE = re.compile(r"\{\{cap:([A-Za-z0-9_.]+)\}\}")
SITE_TOKEN_RE = re.compile(r"\{\{site:([A-Za-z0-9_.]+)\}\}")
SITE_SCHEMA = HERE / "config" / "site-profile.schema.json"


def site_keys() -> set[str]:
    """Allowed ``{{site:<key>}}`` keys, from the site-profile schema."""
    try:
        return set(json.loads(SITE_SCHEMA.read_text()).get("properties", {}))
    except FileNotFoundError:
        return set()


def site_display(key: str) -> str:
    """Render a ``{{site:<key>}}`` token as the deterministic retrieval command."""
    return f"`python3 seo/site_profile.py --site <domain> --get {key}`"

# Curated allowlists for the *semantic* check (--check). The live inputSchema
# only says "array of strings", so a typo'd GA4 dimension/metric or GSC
# dimension passes --validate-live. These sets catch that class of error.
GA4_DIMENSIONS = {
    "date", "dateHour", "year", "month", "week", "day", "hour", "minute",
    "eventName", "pagePath", "pagePathPlusQueryString", "pageTitle",
    "pageLocation", "landingPage", "landingPagePlusQueryString", "fullPageUrl",
    "hostName", "sessionSource", "sessionMedium", "sessionCampaignName",
    "source", "medium", "campaignName", "defaultChannelGroup",
    "firstUserSource", "firstUserMedium", "firstUserCampaignName",
    "country", "region", "city", "continent", "deviceCategory",
    "operatingSystem", "browser", "platform", "language",
    "unifiedScreenName", "screenName", "audienceName",
}
GA4_METRICS = {
    "sessions", "sessionsPerUser", "totalUsers", "activeUsers", "newUsers",
    "eventCount", "screenPageViews", "screenPageViewsPerSession",
    "averageSessionDuration", "userEngagementDuration", "engagementRate",
    "engagedSessions", "bounceRate", "conversions", "totalRevenue",
    "purchaseRevenue", "transactions", "eventValue", "keyEvents",
}
GSC_DIMENSIONS = {"query", "page", "country", "device", "date", "searchAppearance"}


def display(cap: dict) -> str:
    """Render a capability as `server` -> `tool` { args } (supply: runtime)."""
    base = f"`{cap['server']}` → `{cap['tool']}`"
    parts = []
    if cap.get("args"):
        parts.append(json.dumps(cap["args"]))
    if cap.get("runtime"):
        parts.append("(supply: " + ", ".join(cap["runtime"]) + ")")
    return base + (" " + " ".join(parts) if parts else "")


def load():
    data = json.loads(REGISTRY.read_text())
    caps = data["capabilities"]
    disp = {cid: display(c) for cid, c in caps.items()}
    alias = {}
    for cid, c in caps.items():
        for a in c.get("aliases", []):
            alias[a] = disp[cid]
    return data, caps, disp, alias


def skill_files():
    return sorted(SKILLS.glob("*/SKILL.md"))


def _balanced_json(text: str, start: int) -> str | None:
    """Return the brace-balanced JSON object substring at ``text[start] == '{'`` (string-aware)."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def check_expanded() -> int:
    """Verify every `tool` {json} in a skill matches a registry capability's args.

    Catches drift *after* expansion (hand-edited or stale call specs) that the
    token/alias checks cannot see once ``{{cap:}}`` tokens are materialized.
    """
    _, caps, _disp, _alias = load()
    tools = {c["tool"] for c in caps.values()}
    valid = {(c["tool"], json.dumps(c.get("args") or {}, sort_keys=True)) for c in caps.values()}
    issues = 0
    call_re = re.compile(r"`([A-Za-z0-9_.]+)`[ \t]*(\{)")
    for f in skill_files():
        text = f.read_text()
        for m in call_re.finditer(text):
            tool = m.group(1)
            if tool not in tools:
                continue
            blob = _balanced_json(text, m.start(2))
            if blob is None:
                continue
            try:
                parsed = json.loads(blob)
            except json.JSONDecodeError:
                print(f"ERROR {f.relative_to(ROOT)}: invalid JSON args for `{tool}`: {blob}")
                issues += 1
                continue
            if (tool, json.dumps(parsed, sort_keys=True)) not in valid:
                line = text.count("\n", 0, m.start()) + 1
                print(f"DRIFT {f.relative_to(ROOT)}:{line}: `{tool}` {blob} matches no capability args")
                issues += 1
    return issues


def client_timeout_s() -> float:
    """MCP client request timeout (s); override with MCP_CLIENT_TIMEOUT_S."""
    return float(os.environ.get("MCP_CLIENT_TIMEOUT_S", "60"))


def check_policies() -> int:
    """Ensure each capability's retry budget fits inside the MCP client timeout."""
    _, caps, _disp, _alias = load()
    budget = client_timeout_s()
    issues = 0
    for cid, c in caps.items():
        tb = (c.get("policy") or {}).get("timeout_budget_s")
        if tb is not None and tb >= budget:
            print(f"ERROR {cid}: policy.timeout_budget_s {tb} >= client timeout {budget}")
            issues += 1
    return issues


def check_semantics() -> int:
    """Validate GA4/GSC dimension + metric names against curated allowlists.

    Catches semantic typos (e.g. a non-existent GA4 dimension) that the loose
    live ``inputSchema`` ("array of strings") cannot.
    """
    _, caps, _disp, _alias = load()
    issues = 0
    for cid, c in caps.items():
        args = c.get("args") or {}
        if c["server"] == "analytics":
            for d in args.get("dimensions", []):
                if d not in GA4_DIMENSIONS:
                    print(f"ERROR {cid}: unknown GA4 dimension '{d}'")
                    issues += 1
            for m in args.get("metrics", []):
                if m not in GA4_METRICS:
                    print(f"ERROR {cid}: unknown GA4 metric '{m}'")
                    issues += 1
            df = args.get("dimension_filter")
            if isinstance(df, dict):
                def _check_filter(fobj):
                    nonlocal issues
                    if not isinstance(fobj, dict):
                        return
                    if "filter" in fobj and "field_name" in fobj["filter"]:
                        fn = fobj["filter"]["field_name"]
                        if fn not in GA4_DIMENSIONS:
                            print(f"ERROR {cid}: unknown GA4 filter dimension '{fn}'")
                            issues += 1
                    for grp in ("and_group", "or_group"):
                        if grp in fobj and isinstance(fobj[grp], dict):
                            for expr in fobj[grp].get("expressions", []):
                                _check_filter(expr)
                    if "not_expression" in fobj:
                        _check_filter(fobj["not_expression"])
                _check_filter(df)
        if c["server"] == "search-console" and c["tool"] == "analytics_query":
            for d in args.get("dimensions", []):
                if d not in GSC_DIMENSIONS:
                    print(f"ERROR {cid}: unknown GSC dimension '{d}'")
                    issues += 1
    return issues


def check() -> int:
    _, caps, _disp, alias = load()
    issues = 0
    for f in skill_files():
        text = f.read_text()
        for m in TOKEN_RE.finditer(text):
            if m.group(1) not in caps:
                print(f"ERROR {f.relative_to(ROOT)}: unknown capability token {m.group(0)}")
                issues += 1
        for a, d in alias.items():
            if re.search(rf"`{re.escape(a)}`", text):
                print(f"DRIFT {f.relative_to(ROOT)}: legacy tool `{a}` -> should be {d}")
                issues += 1
        keys = site_keys()
        for m in SITE_TOKEN_RE.finditer(text):
            if m.group(1) not in keys:
                print(f"ERROR {f.relative_to(ROOT)}: unknown site-profile key {m.group(0)}")
                issues += 1
    issues += check_expanded()
    issues += check_policies()
    issues += check_semantics()
    print("OK — tokens resolve, no alias drift, expanded specs match the registry, "
          "policies sane, dimension/metric names valid"
          if issues == 0 else f"{issues} issue(s)")
    return 1 if issues else 0


def _check_type(cid: str, key: str, val, prop: dict) -> int:
    issues = 0
    t = prop.get("type")
    ok = True
    if t == "string":
        ok = isinstance(val, str)
    elif t in ("number", "integer"):
        ok = isinstance(val, (int, float)) and not isinstance(val, bool)
    elif t == "boolean":
        ok = isinstance(val, bool)
    elif t == "array":
        ok = isinstance(val, list)
    elif t == "object":
        ok = isinstance(val, dict)
    if not ok:
        print(f"ERROR {cid}: arg '{key}' expected {t}, got {type(val).__name__}")
        issues += 1
    enum = prop.get("enum")
    if enum and val not in enum:
        print(f"ERROR {cid}: arg '{key}' value {val!r} not in enum {enum}")
        issues += 1
    return issues


def _validate_args(cid: str, cap: dict, schema: dict) -> int:
    issues = 0
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    args = cap.get("args") or {}
    runtime = set(cap.get("runtime") or [])
    for k, v in args.items():
        if k not in props:
            print(f"ERROR {cid}: arg '{k}' not in `{cap['tool']}` schema")
            issues += 1
            continue
        issues += _check_type(cid, k, v, props[k])
    for k in runtime:
        if k not in props:
            print(f"ERROR {cid}: runtime arg '{k}' not in `{cap['tool']}` schema")
            issues += 1
    missing = required - set(args) - runtime
    if missing:
        print(f"ERROR {cid}: required {sorted(missing)} not covered by args/runtime")
        issues += 1
    return issues


def validate_live() -> int:
    """Spawn each server, fetch tools/list, validate tool + args against inputSchema."""
    sys.path.insert(0, str(HERE))
    from mcp_client import list_tools  # noqa: E402

    data, caps, _disp, _alias = load()
    servers = data["servers"]
    mcp = json.loads(MCP_JSON.read_text())["mcpServers"]
    issues = 0
    for srv in servers:
        if srv not in mcp:
            print(f"SKIP {srv}: not in .roo/mcp.json (optional)")
            continue
        try:
            tools = {t["name"]: t.get("inputSchema", {}) for t in list_tools(mcp[srv])}
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {srv}: {e}")
            issues += 1
            continue
        for cid, c in caps.items():
            if c["server"] != srv:
                continue
            if c["tool"] not in tools:
                print(f"ERROR {cid}: tool '{c['tool']}' not on {srv}")
                issues += 1
                continue
            issues += _validate_args(cid, c, tools[c["tool"]])
    print("OK — every capability tool + args validate against the live schemas" if issues == 0 else f"{issues} issue(s)")
    return 1 if issues else 0


def write() -> int:
    _, _caps, disp, alias = load()
    changed = 0
    for f in skill_files():
        text = orig = f.read_text()
        text = TOKEN_RE.sub(lambda m: disp.get(m.group(1), m.group(0)), text)
        text = SITE_TOKEN_RE.sub(lambda m: site_display(m.group(1)), text)
        for a, d in alias.items():
            text = re.sub(rf"`{re.escape(a)}`", d, text)
        if text != orig:
            f.write_text(text)
            changed += 1
            print(f"updated {f.relative_to(ROOT)}")
    print(f"{changed} file(s) updated")
    return 0


def write_map() -> int:
    """Regenerate seo/tool-map.md from the registry."""
    data, caps, disp, _alias = load()
    out = ["# MCP Tool Map (SEO)", "",
           "Generated from [`capabilities.json`](capabilities.json) by `python3 seo/resolve.py --map`. Do not edit by hand.", "",
           "## Servers", "", "| Server | Package | Auth | Configured |", "|---|---|---|---|"]
    for s, v in data["servers"].items():
        out.append(f"| `{s}` | {v.get('package', '')} | {v.get('auth', '')} | {'yes' if v.get('configured', True) else 'no (optional)'} |")
    out += ["", "## Capabilities", "", "| Capability | Call |", "|---|---|"]
    for cid in sorted(caps):
        out.append(f"| `{cid}` | {disp[cid]} |")
    (HERE / "tool-map.md").write_text("\n".join(out) + "\n")
    print("wrote seo/tool-map.md")
    return 0


def list_caps() -> int:
    _, caps, disp, _alias = load()
    for cid in sorted(caps):
        print(f"{cid:24} -> {disp[cid]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="verify tokens resolve; report alias drift")
    g.add_argument("--validate-live", action="store_true", help="validate tool + args against live schemas")
    g.add_argument("--write", action="store_true", help="rewrite skills in place")
    g.add_argument("--list", action="store_true", help="list capabilities")
    g.add_argument("--map", action="store_true", help="regenerate seo/tool-map.md from the registry")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.validate_live:
        return validate_live()
    if args.write:
        return write()
    if args.map:
        return write_map()
    return list_caps()


if __name__ == "__main__":
    sys.exit(main())
