#!/usr/bin/env python3
"""Run a skill's data plan: the scripted half of every SEO skill.

Seeds the run (fixed run folder), then executes ``seo/plans/<skill>[.<mode>].json`` step by step:
``pull`` steps call MCP tools through ``seo/mcp_client.py`` (cache first, recorded as evidence),
``local`` steps run a local script whose output is evidence (crawler, profile), ``compute`` steps
run the analysis scripts into ``{run_dir}/computed/<name>.json``. Later steps can use earlier
outputs (e.g. inspect the pages the decay analysis flagged). The AI then only reads ``computed/``
and writes the findings.

Optional steps that fail, and steps whose ``when`` does not hold (server not configured, profile
value missing), become ``unavailable`` entries in the findings skeleton; a required step that fails
stops the run (exit 1). ``pipeline.json`` in the run folder lists every step and its status.

Usage:
    python3 seo/pipeline.py --skill seo-audit --site pbservices.ge
    python3 seo/pipeline.py --skill seo-rank-tracking --site pbservices.ge --mode weekly
    python3 seo/pipeline.py --skill seo-content-brief --site pbservices.ge --input keyword="внж грузии"
    python3 seo/pipeline.py --skill seo-audit --site pbservices.ge --dry-run   # resolve the plan, call nothing
    python3 seo/pipeline.py --check-plans                                       # validate every plan
Options: --as-of D --days N | --weeks N --compare --yoy --tag T --force
Exit codes: 0 = done (see pipeline.json for optional gaps), 1 = plan error or a required step failed.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mcp_client  # noqa: E402
import orchestrate  # noqa: E402
import record  # noqa: E402
import resolve  # noqa: E402
import site_profile  # noqa: E402

PLANS = HERE / "plans"
KINDS = ("pull", "local", "compute")
PERIODS = ("current", "previous", "both", "window", "weeks", "lookback")
PH_RE = re.compile(r"\{([a-zA-Z_][\w.:-]*)\}")


class PlanError(Exception):
    pass


class StepFailed(Exception):
    pass


# ---------------------------------------------------------------- clients ---
class MCPClients:
    """Lazily started MCP sessions, one per server, from .roo/mcp.json."""

    def __init__(self, timeout: float | None = None):
        self.timeout = timeout or resolve.client_timeout_s()
        try:
            self.servers = mcp_client._load_servers()
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            self.servers = {}
        self.sessions: dict = {}

    def available(self, server: str) -> bool:
        return server in self.servers

    def call(self, server: str, tool: str, args: dict) -> dict:
        if server not in self.sessions:
            self.sessions[server] = mcp_client.Session(self.servers[server], self.timeout)
        return self.sessions[server].call_tool(tool, args, self.timeout)

    def close(self) -> None:
        for s in self.sessions.values():
            s.close()


class DryRunClient:
    """Calls nothing: every pull 'fails' as dry-run, so the plan resolution is shown without side effects."""

    def __init__(self, available_servers: set[str] | None = None):
        self.servers = available_servers if available_servers is not None else set(MCPClients().servers)
        self.calls: list = []

    def available(self, server: str) -> bool:
        return server in self.servers

    def call(self, server, tool, args):
        self.calls.append({"server": server, "tool": tool, "args": args})
        raise StepFailed("dry run")

    def close(self) -> None:
        pass


# ------------------------------------------------------------------ plans ---
def plan_path(skill: str, mode: str | None = None) -> Path:
    return PLANS / (f"{skill}.{mode}.json" if mode else f"{skill}.json")


def load_plan(skill: str, mode: str | None = None) -> dict:
    p = plan_path(skill, mode)
    if not p.exists():
        raise PlanError(f"no data plan {p.relative_to(HERE.parent)}")
    return json.loads(p.read_text())


def plan_caps(plan: dict) -> list[str]:
    return sorted({s["cap"] for s in plan.get("steps", []) if "cap" in s})


def validate_plan(plan: dict, caps: dict | None = None) -> list[str]:
    caps = caps if caps is not None else resolve.load()[1]
    issues, names = [], set()
    w = plan.get("window") or {}
    if not isinstance(w, dict) or not ({"days", "weeks"} & set(w) or w.get("source") == "snapshot"):
        issues.append("window needs days, weeks or source snapshot")
    for i, st in enumerate(plan.get("steps") or []):
        kind = next((k for k in KINDS if k in st), None)
        where = f"steps[{i}]"
        if not kind:
            issues.append(f"{where}: needs one of {KINDS}")
            continue
        name = st[kind]
        if name in names and "{i}" not in name:
            issues.append(f"{where}: duplicate name '{name}'")
        names.add(name)
        if kind == "pull":
            c = caps.get(st.get("cap"))
            if not c:
                issues.append(f"{where} ({name}): unknown capability {st.get('cap')!r}")
                continue
            extra = set(st.get("args") or {}) - set(c.get("runtime") or [])
            if extra:
                issues.append(f"{where} ({name}): {sorted(extra)} are not runtime args of {st['cap']}")
            if (c.get("policy") or {}).get("write") and st.get("confirm") is not True:
                # A3: a plan may not silently submit/index anything; the step must say the user approved it
                issues.append(f"{where} ({name}): {st['cap']} changes state outside this workspace — "
                              "it needs \"confirm\": true (explicit user approval)")
            if st.get("period") and st["period"] not in PERIODS:
                issues.append(f"{where} ({name}): period must be one of {PERIODS}")
            if st.get("period") == "lookback" and not (st.get("lookback_days") and st.get("allow_window")):
                issues.append(f"{where} ({name}): period 'lookback' needs lookback_days and allow_window (the reason)")
            if (st.get("for_each") or st.get("period") == "weeks") and "{i}" not in name:
                issues.append(f"{where} ({name}): repeated pulls need '{{i}}' in the name")
        else:
            run = st.get("run")
            if not isinstance(run, list) or not run or not isinstance(run[0], str):
                issues.append(f"{where} ({name}): 'run' must be [script, args…]")
            elif not (HERE / run[0]).exists():
                issues.append(f"{where} ({name}): script {run[0]} not found")
            if st.get("for_each") and "{i}" not in name:
                issues.append(f"{where} ({name}): repeated steps need '{{i}}' in the name")
            if kind == "local" and not st.get("source"):
                issues.append(f"{where} ({name}): local steps need a 'source' label")
    return issues


# -------------------------------------------------------------- resolving ---
def _path(obj, path: str):
    """'pages[].page', 'pages[class=vanished|ranking_loss].page', 'urls[]', 'a.b' → value or list."""
    cur = [obj]
    for part in [p for p in path.split(".") if p]:
        m = re.match(r"^([\w-]*)(\[(.*)\])?$", part)
        key, br, flt = m.group(1), m.group(2), m.group(3)
        nxt = []
        for c in cur:
            v = c.get(key) if key and isinstance(c, dict) else (c if not key else None)
            if br is None:
                if v is not None:
                    nxt.append(v)
                continue
            for item in v if isinstance(v, list) else []:
                if flt:
                    fk, _, fv = flt.partition("=")
                    if str((item or {}).get(fk)) not in fv.split("|"):
                        continue
                nxt.append(item)
        cur = nxt
    return cur if "[" in path else (cur[0] if cur else None)


def _find_key(obj, key: str):
    camel = re.sub(r"_(\w)", lambda m: m.group(1).upper(), key)
    if isinstance(obj, dict):
        for k in (key, camel):
            if k in obj:
                return obj[k]
        obj = list(obj.values())
    if isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


class Context:
    def __init__(self, site: str, run_dir: Path, inputs: dict, clients, caps: dict):
        self.site, self.run_dir, self.inputs, self.clients, self.caps = site, run_dir, inputs, clients, caps
        self.state = json.loads((run_dir / ".run_state.json").read_text())
        self.win = self.state["window"]
        self.profile = site_profile.load_profile(site)
        self._gsc_property = self.profile.get("gsc_property")
        self.dry_run = False
        self.write_ok = False  # set by execute(allow_write=...): a write capability refuses without it

    # values
    def scalar(self, name: str, item=None, i: int | None = None):
        if name == "item":
            return item
        if name.startswith("item."):
            return _path(item, name[5:])
        if name == "i":
            return i
        if name.startswith("input:"):
            if name[6:] not in self.inputs:
                raise PlanError(f"missing --input {name[6:]}")
            return self.inputs[name[6:]]
        if name.startswith("profile:"):
            return self.profile.get(name[8:])
        fixed = {"site": self.site, "domain": self.profile.get("domain", self.site), "run_dir": str(self.run_dir),
                 "data": str(self.run_dir / "data"), "computed": str(self.run_dir / "computed"),
                 "window_days": self.win.get("days"), "ga4_property": self.profile.get("ga4_property"),
                 "last_week": len(self.win.get("weeks") or []) or None,
                 "prev_week": (len(self.win.get("weeks") or []) - 1) or None,
                 "ads_customer_id": re.sub(r"\D", "", str(self.profile.get("ads_customer_id") or "")) or None}
        if name in fixed:
            return fixed[name]
        if name == "gsc_property":
            return self.gsc_property()
        if name in self.win:
            return self.win[name]
        raise PlanError(f"unknown placeholder {{{name}}}")

    def gsc_property(self) -> str:
        if not self._gsc_property:  # profile unset: pick sc-domain:<domain>, else https://<domain>/ from sites_list
            raw = self.call_raw("gsc.sites_list", {})
            text = json.dumps(raw)
            dom = self.profile.get("domain", self.site)
            for cand in (f"sc-domain:{dom}", f"https://{dom}/", f"https://www.{dom}/"):
                if cand in text:
                    self._gsc_property = cand
                    break
            else:
                raise StepFailed(f"no Search Console property for {dom} in sites_list")
        return self._gsc_property

    def call_raw(self, cap: str, args: dict, confirm: bool = False) -> dict:
        c = self.caps[cap]
        if (c.get("policy") or {}).get("write") and not (confirm and self.write_ok):
            # A3: the one capability that changes state outside this workspace needs explicit approval
            raise StepFailed(f"{cap} changes state outside this workspace: it needs \"confirm\": true "
                             "on the step and a run started with --allow-write")
        res = self.clients.call(c["server"], c["tool"], {**(c.get("args") or {}), **args})
        if not isinstance(res, dict) or res.get("isError"):
            text = " ".join(x.get("text", "") for x in (res or {}).get("content", []) if isinstance(x, dict))
            raise StepFailed(text[:300] or "MCP tool returned an error")
        return res

    def value(self, v, item=None, i: int | None = None):
        """Resolve placeholders and $-expressions recursively."""
        if isinstance(v, str):
            m = PH_RE.fullmatch(v)
            if m:
                return self.scalar(m.group(1), item, i)
            return PH_RE.sub(lambda mm: str(self.scalar(mm.group(1), item, i)), v)
        if isinstance(v, list):
            return [self.value(x, item, i) for x in v]
        if isinstance(v, dict):
            if "$from" in v:
                return self.expr(v, item, i)
            if "$concat" in v:
                out = []
                for part in v["$concat"]:
                    for x in self.value(part, item, i) or []:
                        if x not in out:
                            out.append(x)
                return out
            if "$else" in v:
                for part in v["$else"]:
                    try:
                        r = self.value(part, item, i)
                    except StepFailed:
                        continue
                    if r:
                        return r
                return []
            return {k: self.value(x, item, i) for k, x in v.items()}
        return v

    def expr(self, e: dict, item=None, i=None):
        src = e["$from"]
        if src == "ai_filter":
            return site_profile.ga4_ai_filter(self.site)
        if src == "files":
            pattern = self.value(e["glob"], item, i)
            return [str(f) for f in sorted(Path(pattern).parent.glob(Path(pattern).name),
                                            key=lambda f: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", f.name)])]
        if src == "serp_payload":  # DataForSEO SERP task for a keyword, market from profile serp_locations
            import rules
            kw = self.value(e["keyword"], item, i)
            lang = rules.query_language(kw)
            loc = {k.lower(): v for k, v in (self.profile.get("serp_locations") or {}).items()}.get(lang)
            if loc is None:
                raise StepFailed(f"no serp_locations entry for language '{lang}'")
            return [{"keyword": kw, "location_code": loc, "language_code": lang, "depth": 10}]
        if src.startswith("planner:"):
            return self.planner_batches(src[8:], e)
        if src.startswith("profile:"):
            val = self.profile.get(src[8:])
        elif src.startswith("computed:") or src.startswith("data:"):
            kind, name = src.split(":", 1)
            f = self.run_dir / kind / f"{name}.json"
            if not f.exists():
                raise StepFailed(f"needs {kind}/{name}.json (not produced)")
            val = json.loads(f.read_text())
            if kind == "data":
                import gsc_metrics
                val = gsc_metrics._unwrap(val)
        else:
            raise PlanError(f"unknown $from {src!r}")
        if e.get("find"):
            return _find_key(val, e["find"])
        if e.get("path"):
            val = _path(val, e["path"])
        if isinstance(val, list) and e.get("limit"):
            val = val[: int(e["limit"])]
        return val

    def planner_batches(self, src: str, e: dict) -> list[dict]:
        """Keywords grouped by language → [{lang, language, keywords≤20}] for Keyword Planner."""
        import rules
        if src == "priority":
            groups = {k: list(v) for k, v in (self.profile.get("priority_keywords") or {}).items() if v}
        else:
            kws = self.value(e["keywords"]) if src == "list" else (self.expr({**e, "$from": src}) or [])
            groups = {}
            for kw in kws:
                groups.setdefault(rules.query_language(kw), []).append(kw)
        consts = {k.lower(): v for k, v in (self.profile.get("ads_language_constants") or {}).items()}
        out = []
        for lang in sorted(groups):
            if lang in consts:
                kws = list(dict.fromkeys(groups[lang]))[: int(e.get("limit", 20))]
                out.append({"lang": lang, "language": consts[lang], "keywords": kws})
        return out

    def period_args(self, cap: str, period: str | None, week: dict | None = None, lookback: int | None = None) -> dict:
        c = self.caps[cap]
        rt = set(c.get("runtime") or [])
        w = self.win
        args: dict = {}
        if "siteUrl" in rt:
            args["siteUrl"] = self.gsc_property()
        if "property_id" in rt:
            args["property_id"] = self.profile.get("ga4_property")
            if not args["property_id"]:
                raise StepFailed("profile ga4_property is not set")
        if not period:
            return args
        cur = (w["startDate"], w["endDate"])
        if period == "lookback":  # the N days ending with the run window (e.g. a 12-month CTR curve)
            end = dt.date.fromisoformat(w["endDate"])
            cur = ((end - dt.timedelta(days=int(lookback) - 1)).isoformat(), w["endDate"])
            period = "current"
        prev = (w.get("compareStartDate"), w.get("compareEndDate"))
        if period in ("previous", "both") and not prev[0]:
            raise PlanError(f"{cap}: period '{period}' needs a comparison window")
        if "startDate" in rt:
            s, e = week and (week["startDate"], week["endDate"]) or (prev if period == "previous" else cur)
            args.update({"startDate": s, "endDate": e})
            if "compareStartDate" in rt and prev[0]:
                args.update({"compareStartDate": prev[0], "compareEndDate": prev[1]})
        elif "date_ranges" in rt:
            rng = lambda p: {"start_date": p[0], "end_date": p[1]}  # noqa: E731
            sel = {"current": [cur], "window": [cur], "previous": [prev], "both": [cur, prev]}
            args["date_ranges"] = [rng(p) for p in ([(week["startDate"], week["endDate"])] if week else sel[period])]
        return args

    def when(self, conds) -> str | None:
        """None if every condition holds, else the reason it is skipped."""
        for c in [conds] if isinstance(conds, str) else conds or []:
            neg = c.startswith("!")
            k = c[1:] if neg else c
            if k.startswith("server:"):
                srv = k[7:]
                ok = self.clients.available(srv) and resolve.load()[0]["servers"].get(srv, {}).get("configured", True)
            elif k.startswith("profile:"):
                key, _, bad = k[8:].partition("!=")
                v = self.profile.get(key)
                ok = bool(v) and (not bad or (bad not in v if isinstance(v, list) else v != bad))
            elif k.startswith("input:"):
                ok = bool(self.inputs.get(k[6:]))
            elif k.startswith("computed:"):
                ok = (self.run_dir / "computed" / f"{k[9:]}.json").exists()
            elif k.startswith("data:"):
                ok = (self.run_dir / "data" / f"{k[5:]}.json").exists()
            else:
                raise PlanError(f"unknown condition {c!r}")
            if ok == neg:
                return f"condition {c} not met"
        return None


# -------------------------------------------------------------------- run ---
def _argv(ctx: Context, run: list) -> list[str]:
    out = []
    for tok in run[1:]:
        if isinstance(tok, dict) and "$each" in tok:
            for v in ctx.value({k: x for k, x in tok.items() if k != "$each"}) or []:
                out += [tok["$each"], str(v)]
        elif isinstance(tok, dict) and "$glob" in tok:
            pattern = ctx.value(tok["$glob"])
            files = sorted(Path(pattern).parent.glob(Path(pattern).name),
                           key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p.name)])
            if not files:
                raise StepFailed(f"no files match {pattern}")
            out += [str(f) for f in files]
        else:
            v = ctx.value(tok)
            out += [str(x) for x in v] if isinstance(v, list) else [str(v)]
    return out


def _missing_inputs(ctx: Context, argv: list[str]) -> list[str]:
    root = str(ctx.run_dir)
    return [a for a in argv if a.startswith(root) and a.endswith(".json") and not Path(a).exists()]


def _script(ctx: Context, run: list) -> tuple[list[str], str]:
    argv = _argv(ctx, run)
    missing = _missing_inputs(ctx, argv)
    if missing:
        raise StepFailed("missing input " + ", ".join(Path(m).name for m in missing))
    proc = subprocess.run([sys.executable, str(HERE / run[0]), *argv], capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise StepFailed((proc.stderr or proc.stdout).strip()[-300:] or f"{run[0]} exit {proc.returncode}")
    return argv, proc.stdout


def _items(ctx: Context, st: dict) -> list:
    if st.get("period") == "weeks":
        return [("week", w) for w in ctx.win.get("weeks") or []]
    if "for_each" not in st:
        return [(None, None)]
    vals = ctx.value(st["for_each"]) or []
    if not isinstance(vals, list):
        vals = [vals]
    if st.get("batch"):
        n = int(st["batch"])
        vals = [vals[j:j + n] for j in range(0, len(vals), n)]
    return [("item", v) for v in vals]


def _rows_returned(raw) -> int | None:
    """Data rows in an MCP response, without assuming one particular tool's envelope."""
    if not isinstance(raw, dict):
        return None
    for key in ("rows", "data", "results", "items"):
        if isinstance(raw.get(key), list):
            return len(raw[key])
    for x in raw.get("content") or []:
        if isinstance(x, dict) and isinstance(x.get("text"), str):
            try:
                n = _rows_returned(json.loads(x["text"]))
            except json.JSONDecodeError:
                n = None
            if n is not None:
                return n
    return None


def run_step(ctx: Context, st: dict, report: list) -> None:
    kind = next(k for k in KINDS if k in st)
    reason = ctx.when(st.get("when"))
    if reason:
        cond = reason.split()[1]
        # a missing server or profile value is a data gap; other conditions mean "does not apply here"
        gap = cond.startswith("server:") or (cond.startswith("profile:") and "!=" not in cond)
        report.append({"name": st[kind], "kind": kind, **({"cap": st["cap"]} if "cap" in st else {}),
                       "status": "skipped", "reason": reason, "affects": st.get("affects"),
                       **({"gap": cond} if gap else {})})
        return
    if kind == "pull":
        items = _items(ctx, st)
        for i, (tag, it) in enumerate(items, 1):
            name = ctx.value(st["pull"], it if tag == "item" else None, i)
            entry = {"name": name, "kind": "pull", "cap": st["cap"]}
            report.append(entry)
            try:
                args = ctx.period_args(st["cap"], "window" if st.get("period") == "weeks" else st.get("period"),
                                       it if tag == "week" else None, st.get("lookback_days"))
                args.update(ctx.value(st.get("args") or {}, it if tag == "item" else None, i))
                args = {k: v for k, v in args.items() if v is not None}  # unset optional inputs/profile values
                entry["args"] = args
                if st.get("skip_empty") and not args.get(st["skip_empty"]):
                    entry.update({"status": "skipped", "reason": f"no {st['skip_empty']} to process"})
                    continue
                if record.record_from_cache(ctx.run_dir, name, st["cap"], args, st.get("allow_window")):
                    entry["status"] = "cached"
                    continue
                raw = ctx.call_raw(st["cap"], args, confirm=st.get("confirm") is True)
                record.record(ctx.run_dir, name, json.dumps(raw, ensure_ascii=False), st["cap"], args=args,
                              allow_window=st.get("allow_window"))
                entry["status"] = "ok"
                rows, cap_limit = _rows_returned(raw), args.get("rowLimit") or args.get("limit")
                if rows is not None:
                    entry["rows"] = rows
                    if cap_limit and rows >= int(cap_limit):
                        # A1: cut at the server row limit — no headline figure may be built on this pull
                        entry["truncated"] = True
            except (StepFailed, TimeoutError, RuntimeError, OSError, ValueError) as e:
                if not ((st.get("optional") or ctx.dry_run) and len(items) > 1):
                    raise
                entry.update({"status": "failed", "error": str(e)[:300], "affects": st.get("affects")})  # one item; go on
        return
    for i, (tag, it) in enumerate(_items(ctx, st), 1):
        name = ctx.value(st[kind], it, i)
        entry = {"name": name, "kind": kind, "run": [st["run"][0]]}
        report.append(entry)
        run = [st["run"][0], *ctx.value(st["run"][1:], it, i)] if tag == "item" else st["run"]
        if kind == "local" and ctx.dry_run:  # local steps fetch pages: never run them in a dry run
            try:
                entry["run"] = [run[0], *_argv(ctx, run)]
            except StepFailed as e:
                entry["run"] = [run[0], f"<{e}>"]
            entry.update({"status": "skipped", "reason": "dry run: not executed"})
            continue
        argv, out = _script(ctx, run)
        entry["run"] = [st["run"][0], *argv]
        if kind == "local":
            record.record(ctx.run_dir, name, out, source=st["source"], args={"run": entry["run"]})
            entry["file"] = f"data/{name}.json"
        else:
            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                parsed = {"stdout": out.strip()}
            d = ctx.run_dir / "computed"
            d.mkdir(exist_ok=True)
            (d / f"{name}.json").write_text(json.dumps(parsed, ensure_ascii=False, indent=1) + "\n")
            entry["file"] = f"computed/{name}.json"
        entry["status"] = "ok"


def execute(skill: str, site: str, mode: str | None = None, inputs: dict | None = None, clients=None,
            as_of: dt.date | None = None, days: int | None = None, weeks: int | None = None,
            compare: bool | None = None, yoy: bool = False, tag: str | None = None, out_dir: str | None = None,
            force: bool = False, dry_run: bool = False, allow_write: bool = False) -> tuple[Path, dict]:
    plan = load_plan(skill, mode)
    caps = resolve.load()[1]
    issues = validate_plan(plan, caps)
    if issues:
        raise PlanError("; ".join(issues))
    inputs = inputs or {}
    prof = site_profile.load_profile(site)
    for k, spec in (plan.get("inputs") or {}).items():
        if k not in inputs and spec.get("default_profile"):
            v = prof.get(spec["default_profile"])
            v = v[0] if isinstance(v, list) and v else v
            if v:
                inputs[k] = v
        if k not in inputs and "default" in spec:
            inputs[k] = spec["default"]
        if spec.get("required") and not inputs.get(k):
            raise PlanError(f"--input {k}=… is required ({spec.get('desc', '')})")
    for req in plan.get("requires") or []:
        if not prof.get(req):
            raise PlanError(f"profile '{req}' must be set for {skill} (seo/config/sites/{site}.json)")
    w = plan["window"]
    run_dir = orchestrate.seed(
        skill, site, days=days or w.get("days", 28), weeks=weeks if weeks is not None else (None if days else w.get("weeks")),
        source=w.get("source", "gsc"), compare=w.get("compare", False) if compare is None else compare, yoy=yoy,
        as_of=as_of, tag=tag if tag is not None else (mode or None), out_dir=out_dir, force=force)
    own = clients is None
    clients = clients or MCPClients()
    ctx = Context(site, run_dir, inputs, clients, caps)
    ctx.dry_run = dry_run
    ctx.write_ok = allow_write
    report: list = []
    status = "ok"
    try:
        for st in plan["steps"]:
            kind = next(k for k in KINDS if k in st)
            try:
                run_step(ctx, st, report)
            except (StepFailed, TimeoutError, RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as e:
                failed = {"status": "failed", "error": str(e)[:300], "affects": st.get("affects")}
                if report and report[-1].get("status") is None:  # the entry run_step opened
                    report[-1].update(failed)
                else:
                    report.append({"name": st[kind], "kind": kind, **failed})
                if not st.get("optional") and not dry_run:
                    status = "failed"
                    break
    finally:
        if own:
            clients.close()

    unavailable: list[dict] = []
    for e in report:
        if e.get("status") == "failed":
            src = f"{ctx.caps[e['cap']]['server']} ({e['cap']})" if e.get("cap") else e["name"]
            reason = e.get("error")
        elif e.get("status") == "skipped" and e.get("gap"):
            g = e["gap"]
            src = f"{g[7:]} (not configured)" if g.startswith("server:") else f"site profile `{g[8:]}` (not set)"
            reason = None
        else:
            continue
        affects = e.get("affects") or e["name"]
        u = next((u for u in unavailable if u["source"] == src), None)
        if u is None:
            unavailable.append({"source": src, "affects": affects, **({"reason": reason} if reason else {})})
        elif affects not in u["affects"].split("; "):
            u["affects"] += f"; {affects}"
    summary = {"skill": skill, "mode": mode, "site": site, "status": status, "steps": report,
               "unavailable": unavailable, "computed": sorted(p.name for p in (run_dir / "computed").glob("*.json"))
               if (run_dir / "computed").exists() else [],
               # A1: pulls cut at the server row limit — no headline figure may be built on them
               "truncated": [e["name"] for e in report if e.get("truncated")]}
    (run_dir / "pipeline.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    fp = run_dir / "findings.json"
    f = json.loads(fp.read_text())
    if unavailable and not f.get("verdict"):  # skeleton only — never touch written findings
        f["unavailable"] = [{"source": u["source"], "affects": u["affects"]} for u in unavailable]
        fp.write_text(json.dumps(f, ensure_ascii=False, indent=2) + "\n")
    return run_dir, summary


def check_plans() -> list[str]:
    caps = resolve.load()[1]
    issues = []
    for p in sorted(PLANS.glob("*.json")):
        try:
            plan = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            issues.append(f"{p.name}: invalid JSON ({e})")
            continue
        skill = p.name.split(".")[0]
        if plan.get("skill") != skill:
            issues.append(f"{p.name}: skill must be '{skill}'")
        if not (HERE.parent / ".agents" / "skills" / skill / "SKILL.md").exists():
            issues.append(f"{p.name}: no skill {skill}")
        issues += [f"{p.name}: {i}" for i in validate_plan(plan, caps)]
    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skill")
    ap.add_argument("--site")
    ap.add_argument("--mode", help="plan variant, e.g. weekly (seo/plans/<skill>.<mode>.json)")
    ap.add_argument("--input", action="append", default=[], help="key=value for the plan's inputs")
    ap.add_argument("--as-of", dest="as_of")
    ap.add_argument("--days", type=int)
    ap.add_argument("--weeks", type=int)
    ap.add_argument("--compare", action="store_true", default=None)
    ap.add_argument("--yoy", action="store_true")
    ap.add_argument("--tag")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="resolve the plan in a temp folder; call nothing")
    ap.add_argument("--check-plans", action="store_true")
    ap.add_argument("--allow-write", action="store_true",
                    help="permit write capabilities whose step sets \"confirm\": true")
    a = ap.parse_args(argv)
    if a.check_plans:
        issues = check_plans()
        for i in issues:
            print(f"ERROR {i}")
        print("OK — every data plan is valid" if not issues else f"{len(issues)} issue(s)")
        return 1 if issues else 0
    if not a.skill or not a.site:
        ap.error("--skill and --site are required")
    inputs = dict(kv.split("=", 1) for kv in a.input if "=" in kv)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir, summary = execute(
                a.skill, a.site, a.mode, inputs, DryRunClient() if a.dry_run else None,
                dt.date.fromisoformat(a.as_of) if a.as_of else None, a.days, a.weeks, a.compare, a.yoy, a.tag,
                tmp if a.dry_run else None, a.force, dry_run=a.dry_run, allow_write=a.allow_write)
            if a.dry_run:
                for e in summary["steps"]:
                    what = e.get("cap") or (e.get("run") or [""])[0]
                    detail = (json.dumps(e["args"], ensure_ascii=False) if "args" in e
                              else " ".join(e.get("run", [])[1:]).replace(str(run_dir), "{run_dir}"))
                    print(f"{e['name']:<24} {e['kind']:<8} {what:<24} {detail[:110]}"
                          + (f"  [{e.get('reason')}]" if e.get("status") == "skipped" else
                             f"  [not run: {e.get('error')}]" if e.get("status") == "failed" and e["kind"] != "pull" else ""))
                return 0
    except (PlanError, orchestrate.SeedError) as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
    ok = sum(e.get("status") in ("ok", "cached") for e in summary["steps"])
    cached = sum(e.get("status") == "cached" for e in summary["steps"])
    print(f"run_dir: {run_dir}")
    print(f"{summary['status'].upper()} — {ok} steps done ({cached} from cache), "
          f"{len(summary['unavailable'])} unavailable, computed: {', '.join(summary['computed']) or 'none'}")
    if summary.get("truncated"):
        print(f"WARNING truncated at the server row limit: {', '.join(summary['truncated'])} — no headline "
              "figure may be reported from these pulls; split the window or page the pull")
    for u in summary["unavailable"]:
        print(f"  unavailable: {u['source']} → {u['affects']}" + (f" ({u['reason']})" if u.get("reason") else ""))
    if summary["status"] != "ok":
        failed = next(e for e in reversed(summary["steps"]) if e.get("status") == "failed")  # the required one
        print(f"ERROR required step '{failed['name']}' failed: {failed.get('error')}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
