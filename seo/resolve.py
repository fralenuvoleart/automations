#!/usr/bin/env python3
"""Render and validate the SEO skills against the capability registry.

Authoring tokens (in ``.agents/skills/seo-*/SKILL.md``)::

    {{cap:<id>}}                 a capability call spec      -> <!--cap:<id>-->…<!--/cap-->
    {{site:<key>}}               a site-profile lookup        -> <!--site:<key>-->…<!--/site-->
    {{include:<name> k=v …}}     a shared/generated section   -> <!--include:<name> k=v-->…<!--/include-->

``--write`` turns tokens into marker blocks and **re-renders every block** from the
registry / shared templates, so a registry edit or tool rename propagates on the
next ``--write`` (no hand-editing). ``--check`` fails when any block is stale.

Usage:
    python3 seo/resolve.py --check            # blocks current, no stray tokens/legacy names, policies + names valid
    python3 seo/resolve.py --validate-cached  # tool + args vs seo/tool-schemas.json (offline; CI)
    python3 seo/resolve.py --validate-live    # tool + args vs the live servers (local)
    python3 seo/resolve.py --write            # render all skills in place
    python3 seo/resolve.py --map              # regenerate seo/tool-map.md
    python3 seo/resolve.py --list             # list capabilities

Exit codes: 0 = clean, 1 = issues found.
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
TOOL_SCHEMAS = HERE / "tool-schemas.json"
COMMON = HERE / "references" / "skill-common"
PLANS = HERE / "plans"
SITE_SCHEMA = HERE / "config" / "site-profile.schema.json"

TOKEN_RE = re.compile(r"\{\{cap:([A-Za-z0-9_.]+)\}\}")
SITE_TOKEN_RE = re.compile(r"\{\{site:([A-Za-z0-9_.]+)\}\}")
INCLUDE_TOKEN_RE = re.compile(r"\{\{include:([a-z0-9-]+)((?:\s+[a-z_]+=\S+?)*)\}\}")
CAP_BLOCK_RE = re.compile(r"<!--cap:([A-Za-z0-9_.]+)-->(.*?)<!--/cap-->", re.S)
SITE_BLOCK_RE = re.compile(r"<!--site:([A-Za-z0-9_.]+)-->(.*?)<!--/site-->", re.S)
INCLUDE_BLOCK_RE = re.compile(r"<!--include:([a-z0-9-]+)((?:\s+[a-z_]+=\S+?)*)-->(.*?)<!--/include-->", re.S)
ATTR_RE = re.compile(r"([a-z_]+)=(\S+)")
GENERATED = ("datasources", "configuration", "privacy")

# Curated allowlists for the *semantic* check. The live inputSchema only says
# "array of strings", so a typo'd or deprecated GA4/GSC name passes schema validation.
GA4_DIMENSIONS = {
    "date", "dateHour", "year", "month", "week", "day", "hour", "minute",
    "eventName", "pagePath", "pagePathPlusQueryString", "pageTitle",
    "pageLocation", "landingPage", "landingPagePlusQueryString", "fullPageUrl",
    "hostName", "sessionSource", "sessionMedium", "sessionCampaignName",
    "sessionDefaultChannelGroup", "sessionSourceMedium",
    "source", "medium", "campaignName", "defaultChannelGroup",
    "firstUserSource", "firstUserMedium", "firstUserCampaignName",
    "country", "region", "city", "continent", "deviceCategory",
    "operatingSystem", "browser", "platform", "language",
    "unifiedScreenName", "screenName", "audienceName",
}
# `conversions` was renamed `keyEvents` (2024) and is deliberately absent.
GA4_METRICS = {
    "sessions", "sessionsPerUser", "totalUsers", "activeUsers", "newUsers",
    "eventCount", "screenPageViews", "screenPageViewsPerSession",
    "averageSessionDuration", "userEngagementDuration", "engagementRate",
    "engagedSessions", "bounceRate", "keyEvents", "sessionKeyEventRate",
    "totalRevenue", "purchaseRevenue", "transactions", "eventValue",
}
GA4_MATCH_TYPES = {"EXACT", "BEGINS_WITH", "ENDS_WITH", "CONTAINS", "FULL_REGEXP", "PARTIAL_REGEXP"}
GSC_DIMENSIONS = {"query", "page", "country", "device", "date", "searchAppearance"}
GSC_MAX_ROWS = 25000


# ---------------------------------------------------------------- registry ---
def display(cap: dict) -> str:
    """Render a capability as `server` → `tool` {args} (supply: runtime)."""
    base = f"`{cap['server']}` → `{cap['tool']}`"
    parts = []
    if cap.get("args"):
        parts.append(json.dumps(cap["args"], ensure_ascii=False))
    if cap.get("runtime"):
        parts.append("(supply: " + ", ".join(cap["runtime"]) + ")")
    return base + (" " + " ".join(parts) if parts else "")


def load(registry: Path | None = None):
    data = json.loads((registry or REGISTRY).read_text())
    caps = data["capabilities"]
    disp = {cid: display(c) for cid, c in caps.items()}
    alias = {}
    for cid, c in caps.items():
        for a in c.get("aliases", []):
            alias[a] = cid
    return data, caps, disp, alias


def site_keys() -> set[str]:
    """Allowed ``{{site:<key>}}`` keys: schema properties plus the keys derived from the site's rules."""
    try:
        schema = json.loads(SITE_SCHEMA.read_text())
    except FileNotFoundError:
        return set()
    return set(schema.get("properties", {})) | set(schema.get("x-derived-from-rules", {}))


def site_display(key: str) -> str:
    """Render a ``{{site:<key>}}`` token as the deterministic retrieval command."""
    return f"`python3 seo/site_profile.py --site <domain> --get {key}`"


def skill_files(skills: Path | None = None):
    return sorted((skills or SKILLS).glob("seo-*/SKILL.md"))


# --------------------------------------------------------------- rendering ---
def _attrs(raw: str) -> dict:
    return dict(ATTR_RE.findall(raw or ""))


def _attr_str(attrs: dict) -> str:
    return "".join(f" {k}={v}" for k, v in attrs.items())


def _mask(text: str) -> str:
    """Blank out every marker block (same length) so scans ignore rendered content."""
    for rx in (INCLUDE_BLOCK_RE, CAP_BLOCK_RE, SITE_BLOCK_RE):
        text = rx.sub(lambda m: " " * len(m.group(0)), text)
    return text


def caps_used(text: str) -> list[str]:
    """Capability IDs referenced in the body (outside include blocks), first-use order."""
    body = INCLUDE_BLOCK_RE.sub("", text)
    seen: list[str] = []
    for m in CAP_BLOCK_RE.finditer(body):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def _plan_steps(skill: str) -> list[dict]:
    """Steps of the skill's data plans (seo/plans/<skill>.json and its modes, e.g. <skill>.weekly.json)."""
    steps: list[dict] = []
    for f in sorted(PLANS.glob(f"{skill}.json")) + sorted(PLANS.glob(f"{skill}.*.json")):
        steps += json.loads(f.read_text()).get("steps", [])
    return steps


def plan_caps(skill: str) -> list[str]:
    """Capabilities the pipeline calls for the skill, in plan order."""
    out: list[str] = []
    for st in _plan_steps(skill):
        if st.get("cap") and st["cap"] not in out:
            out.append(st["cap"])
    if any(c.startswith("gsc.") for c in out) and "gsc.sites_list" not in out:
        out.append("gsc.sites_list")  # the pipeline resolves the property with it when the profile has no gsc_property
    return out


def skill_caps(skill: str, text: str) -> list[str]:
    """Plan capabilities first, then the ones only the SKILL.md text calls (agent judgment steps)."""
    plan = plan_caps(skill)
    return plan + [c for c in caps_used(text) if c not in plan]


def _gen_datasources(caps_in: list[str], data: dict, plan: list[str] | None = None) -> str:
    caps = data["capabilities"]
    rows = ["| Capability | Call | Purpose |", "|---|---|---|"]
    for cid in caps_in:
        c = caps.get(cid)
        if not c:
            continue
        status = "" if data["servers"].get(c["server"], {}).get("configured", True) else " *(optional, not configured)*"
        who = "" if plan is None or cid in plan else " *(agent call, only when a step needs it)*"
        rows.append(f"| `{cid}` | {display(c)} | {c.get('desc', '')}{status}{who} |")
    return "\n".join(rows)


def _servers_used(caps_in: list[str], data: dict) -> list[str]:
    out: list[str] = []
    for cid in caps_in:
        s = data["capabilities"].get(cid, {}).get("server")
        if s and s not in out:
            out.append(s)
    return out


def _gen_configuration(caps_in: list[str], data: dict) -> str:
    lines = ["- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`."]
    for s in _servers_used(caps_in, data):
        spec = data["servers"].get(s, {})
        opt = " *(optional)*" if not spec.get("configured", True) else ""
        lines.append(f"- `{s}`{opt}: {spec.get('credentials', spec.get('auth', ''))}.")
    return "\n".join(lines)


def _gen_privacy(caps_in: list[str], data: dict, text: str, plan_scripts: bool = False) -> str:
    third = [(s, data["servers"][s]["third_party"]) for s in _servers_used(caps_in, data)
             if data["servers"].get(s, {}).get("third_party")]
    lines = ["- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the git-ignored run folder (`python3 seo/runs.py root`); `python3 seo/runs.py prune` deletes runs older than `retention_days`."]
    if third:
        names = ", ".join(f"{p} (`{s}`)" for s, p in third)
        lines.append(f"- Third-party calls: target domains/keywords/URLs are sent to {names} when those servers are used; everything else goes only to Google APIs via the configured MCP servers.")
    else:
        lines.append("- Third-party calls: none — capability calls go only to Google APIs via the configured MCP servers.")
    if "seo/site_crawl.py" in text or plan_scripts:
        lines.append("- `seo/site_crawl.py` fetches public pages directly from the target site (polite rate, identifying User-Agent).")
    return "\n".join(lines)


def _render_include(name: str, attrs: dict, skill: str, text: str, data: dict) -> str:
    caps_in = skill_caps(skill, text)
    if name == "datasources":
        return _gen_datasources(caps_in, data, plan_caps(skill))
    if name == "configuration":
        return _gen_configuration(caps_in, data)
    if name == "privacy":
        crawls = any((st.get("run") or [""])[0] == "site_crawl.py" for st in _plan_steps(skill))
        return _gen_privacy(caps_in, data, text, crawls)
    path = COMMON / f"{name}.md"
    if not path.exists():
        raise KeyError(f"unknown include '{name}' (no {path.relative_to(ROOT)})")
    out = path.read_text().strip("\n")
    for k, v in {"skill": skill, **attrs}.items():
        if k == "flags":  # flags=--compare_--yoy -> "--compare --yoy"; flags=- -> none
            if v == "-":
                out = out.replace(" <<flags>>", "")
            v = "" if v == "-" else v.replace("_", " ")
        out = out.replace(f"<<{k}>>", v)
    leftover = re.findall(r"<<([a-z_]+)>>", out)
    if leftover:
        raise KeyError(f"include '{name}' needs attribute(s) {sorted(set(leftover))}")
    return out


def render(text: str, skill: str, data: dict | None = None) -> str:
    """Return ``text`` with tokens converted and every marker block re-rendered."""
    data = data or load()[0]
    caps = data["capabilities"]
    alias = {a: cid for cid, c in caps.items() for a in c.get("aliases", [])}

    # 1. tokens -> blocks
    text = TOKEN_RE.sub(lambda m: f"<!--cap:{m.group(1)}--><!--/cap-->", text)
    text = SITE_TOKEN_RE.sub(lambda m: f"<!--site:{m.group(1)}--><!--/site-->", text)
    text = INCLUDE_TOKEN_RE.sub(lambda m: f"<!--include:{m.group(1)}{m.group(2)}--><!--/include-->", text)

    # 2. legacy tool names (aliases) outside blocks -> cap blocks
    if alias:
        masked = _mask(text)
        pieces, last = [], 0
        rx = re.compile(r"`(" + "|".join(re.escape(a) for a in sorted(alias, key=len, reverse=True)) + r")`")
        for m in rx.finditer(masked):
            pieces.append(text[last:m.start()])
            pieces.append(f"<!--cap:{alias[m.group(1)]}--><!--/cap-->")
            last = m.end()
        pieces.append(text[last:])
        text = "".join(pieces)

    # 3. re-render cap + site blocks (unknown IDs are left untouched; --check reports them)
    text = CAP_BLOCK_RE.sub(
        lambda m: f"<!--cap:{m.group(1)}-->{display(caps[m.group(1)])}<!--/cap-->" if m.group(1) in caps else m.group(0),
        text)
    text = SITE_BLOCK_RE.sub(lambda m: f"<!--site:{m.group(1)}-->{site_display(m.group(1))}<!--/site-->", text)

    # 4. re-render include blocks (generated ones read the cap blocks rendered above)
    def inc(m: re.Match) -> str:
        name, attrs = m.group(1), _attrs(m.group(2))
        body = _render_include(name, attrs, skill, text, data)
        return f"<!--include:{name}{_attr_str(attrs)}-->\n\n{body}\n\n<!--/include-->"

    return INCLUDE_BLOCK_RE.sub(inc, text)


# ------------------------------------------------------------------ checks ---
def client_timeout_s() -> float:
    """MCP client request timeout (s); override with MCP_CLIENT_TIMEOUT_S."""
    return float(os.environ.get("MCP_CLIENT_TIMEOUT_S", "60"))


def check_policies(caps: dict | None = None) -> int:
    """Each retry budget must fit inside the MCP client timeout; retries live in one layer."""
    caps = caps or load()[1]
    budget = client_timeout_s()
    issues = 0
    for cid, c in caps.items():
        pol = c.get("policy") or {}
        tb = pol.get("timeout_budget_s")
        if tb is not None and tb >= budget:
            print(f"ERROR {cid}: policy.timeout_budget_s {tb} >= client timeout {budget}")
            issues += 1
        ttl = pol.get("cache_ttl_days")
        if ttl is not None and (not isinstance(ttl, int) or isinstance(ttl, bool) or ttl < 0):
            print(f"ERROR {cid}: policy.cache_ttl_days must be a non-negative integer")
            issues += 1
        if c["server"] == "google-ads-planner" and pol.get("retry", 0) != 0:
            print(f"ERROR {cid}: the planner server retries internally — policy.retry must be 0 (single retry layer)")
            issues += 1
    return issues


def _check_ga4_filter(cid: str, fobj, issues: list[str]) -> None:
    if not isinstance(fobj, dict):
        return
    f = fobj.get("filter")
    if isinstance(f, dict):
        if f.get("field_name") not in GA4_DIMENSIONS:
            issues.append(f"{cid}: unknown GA4 filter dimension '{f.get('field_name')}'")
        sf = f.get("string_filter")
        if isinstance(sf, dict) and sf.get("match_type") not in GA4_MATCH_TYPES:
            issues.append(f"{cid}: unknown GA4 string_filter.match_type '{sf.get('match_type')}'")
    for grp in ("and_group", "or_group"):
        for expr in (fobj.get(grp) or {}).get("expressions", []):
            _check_ga4_filter(cid, expr, issues)
    if "not_expression" in fobj:
        _check_ga4_filter(cid, fobj["not_expression"], issues)


def check_semantics(caps: dict | None = None) -> int:
    """GA4/GSC names against curated allowlists + GSC row-limit/engine rules."""
    caps = caps or load()[1]
    issues: list[str] = []
    for cid, c in caps.items():
        args = c.get("args") or {}
        if c["server"] == "analytics":
            issues += [f"{cid}: unknown GA4 dimension '{d}'" for d in args.get("dimensions", []) if d not in GA4_DIMENSIONS]
            issues += [f"{cid}: unknown or deprecated GA4 metric '{m}'" for m in args.get("metrics", []) if m not in GA4_METRICS]
            _check_ga4_filter(cid, args.get("dimension_filter"), issues)
        if c["server"] == "search-console" and c["tool"] == "analytics_query":
            issues += [f"{cid}: unknown GSC dimension '{d}'" for d in args.get("dimensions", []) if d not in GSC_DIMENSIONS]
            if args.get("rowLimit") != GSC_MAX_ROWS:
                issues.append(f"{cid}: analytics_query must pin rowLimit {GSC_MAX_ROWS} (API default is 1000)")
        if c["server"] == "search-console" and c["tool"] != "compare_engines" and "engine" not in args \
                and c["tool"] not in ("diagnostics", "pagespeed_analyze", "schema_validate", "analytics_advanced"):
            issues.append(f"{cid}: pin engine 'google' (tool default is 'all' = Google+Bing)")
    for i in issues:
        print(f"ERROR {i}")
    return len(issues)


def check(skills: Path | None = None, registry: Path | None = None) -> int:
    data, caps, _disp, alias = load(registry)
    keys = site_keys()
    issues = 0
    for f in skill_files(skills):
        try:
            rel = f.relative_to(ROOT)
        except ValueError:
            rel = f
        text = f.read_text()
        skill = f.parent.name
        for rx, label in ((TOKEN_RE, "{{cap:}}"), (SITE_TOKEN_RE, "{{site:}}"), (INCLUDE_TOKEN_RE, "{{include:}}")):
            for m in rx.finditer(text):
                print(f"ERROR {rel}: unrendered {label} token {m.group(0)} — run --write")
                issues += 1
        for m in CAP_BLOCK_RE.finditer(text):
            if m.group(1) not in caps:
                print(f"ERROR {rel}: unknown capability <!--cap:{m.group(1)}-->")
                issues += 1
        for m in SITE_BLOCK_RE.finditer(text):
            if m.group(1) not in keys:
                print(f"ERROR {rel}: unknown site-profile key <!--site:{m.group(1)}-->")
                issues += 1
        masked = _mask(text)
        for a in alias:
            if re.search(rf"`{re.escape(a)}`", masked):
                print(f"DRIFT {rel}: legacy tool `{a}` outside a cap block — run --write")
                issues += 1
        try:
            rendered = render(text, skill, data)
        except KeyError as e:
            print(f"ERROR {rel}: {e}")
            issues += 1
            continue
        if rendered != text:
            a, b = text.splitlines(), rendered.splitlines()
            line = next((i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)) + 1)
            print(f"STALE {rel}:{line}: rendered blocks differ from the registry/templates — run --write")
            issues += 1
    issues += check_policies(caps)
    issues += check_semantics(caps)
    print("OK — blocks current, no stray tokens or legacy names, policies sane, names valid"
          if issues == 0 else f"{issues} issue(s)")
    return 1 if issues else 0


# -------------------------------------------------------- schema validation ---
def _type_ok(val, prop: dict) -> bool:
    types = [prop["type"]] if "type" in prop else [p.get("type") for p in prop.get("anyOf", []) if p.get("type")]
    if not types:
        return True
    for t in types:
        if t == "string" and isinstance(val, str):
            return True
        if t in ("number", "integer") and isinstance(val, (int, float)) and not isinstance(val, bool):
            return True
        if t == "boolean" and isinstance(val, bool):
            return True
        if t == "array" and isinstance(val, list):
            return True
        if t == "object" and isinstance(val, dict):
            return True
        if t == "null" and val is None:
            return True
    return False


def _check_type(cid: str, key: str, val, prop: dict) -> int:
    issues = 0
    if not _type_ok(val, prop):
        print(f"ERROR {cid}: arg '{key}' expected {prop.get('type') or prop.get('anyOf')}, got {type(val).__name__}")
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
    for k in sorted(runtime):
        if k not in props:
            print(f"ERROR {cid}: runtime arg '{k}' not in `{cap['tool']}` schema")
            issues += 1
    missing = required - set(args) - runtime
    if missing:
        print(f"ERROR {cid}: required {sorted(missing)} not covered by args/runtime")
        issues += 1
    return issues


def _validate_against(tool_sets: dict, data: dict, caps: dict, label: str) -> int:
    issues = 0
    for srv, spec in data["servers"].items():
        if srv not in tool_sets:
            why = "optional, not configured" if not spec.get("configured", True) else f"no {label} schema"
            print(f"SKIP {srv}: {why}")
            continue
        tools = tool_sets[srv]
        if isinstance(tools, dict) and "__error__" in tools:
            print(f"FAIL {srv}: {tools['__error__']}")
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
    return issues


def validate_cached(schemas: Path | None = None) -> int:
    """Validate against the committed tool-schemas.json snapshot (offline, portable)."""
    data, caps, _d, _a = load()
    cached = json.loads((schemas or TOOL_SCHEMAS).read_text())
    issues = _validate_against(cached, data, caps, "cached")
    print("OK — every cached capability validates" if issues == 0 else f"{issues} issue(s)")
    return 1 if issues else 0


def validate_live() -> int:
    """Spawn each configured server, fetch tools/list, validate tool + args."""
    sys.path.insert(0, str(HERE))
    from mcp_client import list_tools  # noqa: E402

    data, caps, _d, _a = load()
    mcp = json.loads(MCP_JSON.read_text())["mcpServers"]
    live: dict = {}
    for srv in data["servers"]:
        if srv not in mcp:
            continue
        try:
            live[srv] = {t["name"]: t.get("inputSchema", {}) for t in list_tools(mcp[srv])}
        except Exception as e:  # noqa: BLE001
            live[srv] = {"__error__": str(e)}
    issues = _validate_against(live, data, caps, "live")
    print("OK — every capability validates against the live schemas" if issues == 0 else f"{issues} issue(s)")
    return 1 if issues else 0


# ------------------------------------------------------------------ writers ---
def write(skills: Path | None = None) -> int:
    data = load()[0]
    changed = 0
    for f in skill_files(skills):
        text = f.read_text()
        out = render(text, f.parent.name, data)
        if out != text:
            f.write_text(out)
            changed += 1
            print(f"updated {f}")
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
    out += ["", "## Capabilities", "", "| Capability | Call | Purpose |", "|---|---|---|"]
    for cid in sorted(caps):
        out.append(f"| `{cid}` | {disp[cid]} | {caps[cid].get('desc', '')} |")
    (HERE / "tool-map.md").write_text("\n".join(out) + "\n")
    print("wrote seo/tool-map.md")
    return 0


def list_caps() -> int:
    _, caps, disp, _alias = load()
    for cid in sorted(caps):
        print(f"{cid:26} -> {disp[cid]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--validate-cached", action="store_true")
    g.add_argument("--validate-live", action="store_true")
    g.add_argument("--write", action="store_true")
    g.add_argument("--list", action="store_true")
    g.add_argument("--map", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    if a.validate_cached:
        return validate_cached()
    if a.validate_live:
        return validate_live()
    if a.write:
        return write()
    if a.map:
        return write_map()
    return list_caps()


if __name__ == "__main__":
    sys.exit(main())
