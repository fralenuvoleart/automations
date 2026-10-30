"""Tests for seo/pipeline.py — data plans run end to end against a fake MCP client (no network, no real cache)."""
import contextlib
import datetime as dt
import io
import json
import re
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
ROOT = SEO.parent
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))

import pipeline as P  # noqa: E402
import resolve  # noqa: E402
import runs  # noqa: E402
from _runner import main  # noqa: E402

AS_OF = dt.date(2026, 10, 30)
SITE = "pbservices.ge"
U = "https://pbservices.ge"


def _text(obj) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False)}], "isError": False}


def _rows(keys_list, cur: bool):
    """GSC rows; the current period is weaker so pages decline and queries move."""
    out = []
    for n, keys in enumerate(keys_list):
        clicks = (40 - n * 3) if cur else (60 - n * 2)
        imps = clicks * 20
        out.append({"keys": list(keys), "clicks": max(clicks, 0), "impressions": imps,
                    "ctr": round(max(clicks, 0) / imps, 4) if imps else 0, "position": 4.0 + n + (3 if cur else 0)})
    return {"rows": out}


PAGES = [f"{U}/", f"{U}/services/individual-entrepreneur-georgia/", f"{U}/ru/", f"{U}/blog/bank-account-georgia/",
         f"{U}/blog/residence-permit-georgia/"]
QUERIES = ["pb services", "individual entrepreneur georgia", "bank account georgia", "residence permit georgia",
           "open company in georgia", "georgia tax residency"]


class FakeClients:
    """Answers like the real servers (MCP content wrapper); records every call."""

    def __init__(self, servers=("search-console",), fail=()):
        self.servers, self.fail, self.calls = set(servers), set(fail), []

    def available(self, server):
        return server in self.servers

    def close(self):
        pass

    def call(self, server, tool, args):
        self.calls.append((server, tool, args))
        if tool in self.fail:
            return {"content": [{"type": "text", "text": f"{tool} is down"}], "isError": True}
        cur = args.get("startDate") != "2026-05-01" and args.get("startDate") != "2026-09-02"
        dims = args.get("dimensions") or []
        if tool == "diagnostics":
            return _text({"google": "ok", "bing": "not connected"})
        if tool == "sites_list":
            return _text({"sites": [{"siteUrl": f"{U}/"}]})
        if tool == "analytics_compare":
            return _text({"current": {"clicks": 120}, "previous": {"clicks": 200}, "change_pct": -40.0})
        if tool == "analytics_anomalies":
            return _text({"anomalies": []})
        if tool == "analytics_query":
            if dims == ["date"]:
                return _text(_rows([(f"2026-10-{d:02d}",) for d in range(1, 8)], cur))
            if dims == ["query"]:
                return _text(_rows([(q,) for q in QUERIES], cur))
            if dims == ["page"]:
                return _text(_rows([(p,) for p in PAGES], cur))
            if dims == ["query", "page"]:
                return _text(_rows([(q, PAGES[i % len(PAGES)]) for i, q in enumerate(QUERIES)], cur))
            if dims == ["country", "query"]:
                return _text(_rows([("geo", q) for q in QUERIES], cur))
        if tool == "inspection_inspect":
            return _text({"results": [{"url": u, "inspectionResult": {"indexStatusResult": {
                "verdict": "PASS", "coverageState": "Submitted and indexed", "indexingState": "INDEXING_ALLOWED"}}}
                for u in args["urls"]]})
        if tool == "site_health_check":
            return _text({"robots": "ok", "sitemaps": 1})
        raise AssertionError(f"unexpected call {server}.{tool} {args}")


@contextlib.contextmanager
def _isolated_cache():
    """Never touch the real run_root/_cache with fake data."""
    saved = runs.settings
    with tempfile.TemporaryDirectory() as root:
        runs.settings = lambda: {"run_root": root, "cache": True, "retention_days": 180}
        try:
            yield root
        finally:
            runs.settings = saved


def _run(skill, clients, **kw):
    out = tempfile.mkdtemp()
    run_dir, summary = P.execute(skill, SITE, clients=clients, as_of=AS_OF, out_dir=out, **kw)
    return run_dir, summary


def test_audit_runs_end_to_end_and_marks_ga4_unavailable():
    with _isolated_cache():
        fake = FakeClients()
        run_dir, s = _run("seo-audit", fake)
    assert s["status"] == "ok", s
    for name in ("totals", "anonymized", "decay", "low_ctr", "striking", "cannibalization", "segments_category",
                 "segments_page_tag", "segments_language", "coverage", "inspection"):
        assert f"{name}.json" in s["computed"], (name, s["computed"])
    decay = json.loads((run_dir / "computed" / "decay.json").read_text())
    assert decay["pages"], "fixture should produce declining pages"
    totals = json.loads((run_dir / "computed" / "totals.json").read_text())
    assert totals["change"]["clicks_delta"] < 0
    # every pull is recorded as evidence with its window
    calls = json.loads((run_dir / "context.json").read_text())["calls"]
    names = {c["name"] for c in calls}
    assert {"query_cur", "query_prev", "page_cur", "page_prev", "pq_cur", "totals_cur", "inspect", "query_12m"} <= names
    q_prev = next(c for c in calls if c["name"] == "query_prev")
    assert q_prev["args"]["startDate"] == "2026-05-01" and q_prev["args"]["siteUrl"] == f"{U}/"
    # the 12-month CTR-curve pull is a documented window exception, fed to low-ctr
    year = next(c for c in calls if c["name"] == "query_12m")
    assert year["args"]["startDate"] == "2025-10-28" and year["args"]["endDate"] == "2026-10-27"
    assert "CTR curve" in year["window_exception"]
    low = json.loads((run_dir / "computed" / "low_ctr.json").read_text())
    assert low["basis"]["site_12m_supplied"] is True
    # inspect used the pages the decay analysis flagged (vanished / ranking_loss first)
    inspected = next(a for _, t, a in fake.calls if t == "inspection_inspect")["urls"]
    assert inspected and set(inspected) <= set(PAGES) and len(inspected) <= 5
    # GA4 not configured → skipped, listed once, written into the findings skeleton
    unav = {u["source"]: u for u in s["unavailable"]}
    assert list(unav) == ["analytics (not configured)"], unav  # grouped per server; geo_cur is "not applicable"
    assert "engagement" in unav["analytics (not configured)"]["affects"]
    f = json.loads((run_dir / "findings.json").read_text())
    assert [u["source"] for u in f["unavailable"]] == ["analytics (not configured)"]
    geo = next(st for st in s["steps"] if st["name"] == "geo_cur")  # markets = WORLDWIDE → does not apply
    assert geo["status"] == "skipped" and "gap" not in geo
    assert (run_dir / "pipeline.json").exists()


def test_rerun_uses_the_shared_cache():
    with _isolated_cache():
        _run("seo-brand-split", FakeClients())
        fake = FakeClients()
        _, s = _run("seo-brand-split", fake)
    pulls = [st for st in s["steps"] if st["kind"] == "pull"]
    assert {st["status"] for st in pulls if st["name"] != "diagnostics"} == {"cached"}, pulls
    assert all(t == "diagnostics" for _, t, _ in fake.calls)  # live tool: not cached
    assert "brand_split.json" in s["computed"] and "totals.json" in s["computed"]


def test_optional_failure_continues_required_failure_stops():
    with _isolated_cache():
        _, s = _run("seo-audit", FakeClients(fail={"analytics_anomalies"}))
        assert s["status"] == "ok"
        assert any(u["source"] == "search-console (gsc.anomalies)" for u in s["unavailable"])
    with _isolated_cache():  # fresh cache: the run above cached every final-window pull
        _, s = _run("seo-audit", FakeClients(fail={"analytics_query"}))
    assert s["status"] == "failed"
    failed = [st for st in s["steps"] if st.get("status") == "failed"]
    assert failed[-1]["name"] == "totals_cur" and "down" in failed[-1]["error"]
    assert "decay.json" not in s["computed"]  # stopped before computing


def test_weekly_mode_pulls_one_week_per_call():
    with _isolated_cache():
        fake = FakeClients()
        run_dir, s = _run("seo-rank-tracking", fake, mode="weekly")
    assert s["status"] == "ok", [st for st in s["steps"] if st.get("status") == "failed"]
    weeks = json.loads((run_dir / ".run_state.json").read_text())["window"]["weeks"]
    assert len(weeks) == 8
    q = [a for _, t, a in fake.calls if t == "analytics_query" and a["dimensions"] == ["query"]]
    assert [(a["startDate"], a["endDate"]) for a in q] == [(w["startDate"], w["endDate"]) for w in weeks]
    for name in ("trend_category", "trend_keyword", "trend_page_tag", "trend_language", "movers", "keywords", "targets"):
        assert f"{name}.json" in s["computed"], name


def test_brief_writes_findings_and_numbers():
    with _isolated_cache():
        run_dir, s = _run("seo-brief", FakeClients())
    assert s["status"] == "ok", s
    f = json.loads((run_dir / "findings.json").read_text())
    assert f["verdict"] and f["skill"] == "seo-brief"
    assert "kpis" in json.loads((run_dir / "computed" / "brief.json").read_text())


def test_inputs_required_defaults_and_requires():
    with _isolated_cache():
        try:
            _run("seo-content-brief", FakeClients())
            raise AssertionError("keyword input should be required")
        except P.PlanError as e:
            assert "--input keyword" in str(e)
    plan = P.load_plan("seo-paid-organic")
    assert plan["requires"] == ["ads_customer_id"]


def test_unset_optional_args_are_dropped():
    with _isolated_cache():
        fake = P.DryRunClient(available_servers={"search-console", "google-ads"})
        _, s = _run("seo-paid-organic", fake, dry_run=True)
    terms = next(c for c in fake.calls if c["tool"] == "search_search" and c["args"]["resource"] == "search_term_view")
    assert "login_customer_id" not in terms["args"] and terms["args"]["customer_id"].isdigit()
    assert "BETWEEN '2026-07-30' AND '2026-10-27'" in terms["args"]["conditions"][0]


def test_every_plan_dry_runs_without_calls_or_crawls():
    with _isolated_cache():
        for p in sorted(P.PLANS.glob("*.json")):
            skill, _, mode = p.stem.partition(".")
            inputs = {"keyword": "внж грузии"} if skill == "seo-content-brief" else {}
            fake = P.DryRunClient(available_servers={"search-console", "analytics", "dataforseo", "tavily",
                                                     "google-ads", "google-ads-planner"})
            _, s = _run(skill, fake, mode=mode or None, inputs=inputs, dry_run=True)
            for st in s["steps"]:
                if st["kind"] == "local":
                    assert st["status"] == "skipped" and "dry run" in st["reason"], (p.name, st)
            for c in fake.calls:
                for k in ("startDate", "endDate"):
                    if k in c["args"]:
                        assert c["args"][k] < "2026-10-30", (p.name, c)


def test_plan_validation_catches_mistakes():
    caps = resolve.load()[1]
    bad = {"window": {}, "steps": [
        {"pull": "x", "cap": "gsc.nope"},
        {"pull": "q", "cap": "gsc.query", "args": {"rowLimit": 5}},
        {"pull": "w", "cap": "gsc.query", "period": "weeks"},
        {"compute": "c", "run": ["missing_script.py"]},
        {"local": "l", "run": ["site_crawl.py", "robots"]},
        {"compute": "c", "run": ["gsc_metrics.py"]},
    ]}
    issues = " | ".join(P.validate_plan(bad, caps))
    for frag in ("window needs", "unknown capability 'gsc.nope'", "['rowLimit'] are not runtime args",
                 "repeated pulls need", "script missing_script.py not found", "local steps need a 'source'",
                 "duplicate name 'c'"):
        assert frag in issues, (frag, issues)
    assert P.check_plans() == []


def test_docs_reference_only_outputs_the_plans_produce():
    """Every `computed/<x>.json` / `data/<x>.json` a SKILL.md workflow names is produced by its plan(s)."""
    agent_recorded = {"seo-keyword-strategy": {"ranked"}}
    for f in sorted((ROOT / ".agents" / "skills").glob("seo-*/SKILL.md")):
        skill = f.parent.name
        text = re.sub(r"<!--include:.*?<!--/include-->", "", f.read_text(), flags=re.S)
        steps = resolve._plan_steps(skill)
        assert steps, f"{skill}: no data plan"
        names = {next(st[k] for k in P.KINDS if k in st) for st in steps}
        for kind, name in re.findall(r"(computed|data)/([a-z0-9_]+(?:_\*)?)\.json", text):
            if name in agent_recorded.get(skill, set()):
                continue
            if name.endswith("_*"):
                assert any(n.startswith(name[:-1] + "{") for n in names), f"{skill}: {kind}/{name}.json"
            else:
                assert name in names, f"{skill}: {kind}/{name}.json is not produced by its plan"


def test_cli_dry_run_and_check_plans():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), _isolated_cache():
        assert P.main(["--check-plans"]) == 0
        assert P.main(["--skill", "seo-audit", "--site", SITE, "--as-of", "2026-10-30", "--dry-run"]) == 0
    out = buf.getvalue()
    assert "every data plan is valid" in out and "decay" in out and "gsc.page" in out
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert P.main(["--skill", "seo-nope", "--site", SITE, "--dry-run"]) == 1
    assert "no data plan" in err.getvalue()


if __name__ == "__main__":
    main(globals())
