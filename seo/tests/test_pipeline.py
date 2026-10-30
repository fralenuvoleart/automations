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
            if any(not P.server_ok(fake, srv) for srv in P.load_plan(skill, mode or None).get("requires_servers") or {}):
                continue  # covered by test_backlink_check_refuses_to_run_without_dataforseo
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


# — A1: pulls cut at the row limit are completed (GSC split by date, GA4 paged) or refused downstream

class _SplitGSC(FakeClients):
    """page × query rows: 400 new pairs per day plus one pair seen daily — 90 days = 36,001 rows > 25,000."""

    def call(self, server, tool, args):
        if tool == "analytics_query" and args.get("dimensions") == ["query", "page"]:
            self.calls.append((server, tool, args))
            a, b = dt.date.fromisoformat(args["startDate"]), dt.date.fromisoformat(args["endDate"])
            days = [(a + dt.timedelta(days=i)) for i in range((b - a).days + 1)]
            rows = [{"keys": ["shared", f"{U}/"], "clicks": len(days), "impressions": 10 * len(days), "ctr": 0.1,
                     "position": sum(1 + d.day % 3 for d in days) / len(days)}]
            rows += [{"keys": [f"q{d.isoformat()}-{k}", f"{U}/p{k % 7}/"], "clicks": 1, "impressions": 3,
                      "ctr": 0.33, "position": 12} for d in days for k in range(400)]
            return _text({"rows": rows[:25000]})
        return super().call(server, tool, args)


def test_gsc_pull_over_the_row_limit_is_split_by_date_and_summed():
    with _isolated_cache():
        fake = _SplitGSC()
        run_dir, s = _run("seo-audit", fake)
    pq = next(st for st in s["steps"] if st["name"] == "pq_cur")
    assert pq["status"] == "ok" and "truncated" not in pq and pq["chunks"] == 2 and pq["calls"] == 3, pq
    assert s["truncated"] == [] and s["tainted"] == []
    rows = P._payload(json.loads((run_dir / "data" / "pq_cur.json").read_text()))
    assert rows["_pipeline"]["complete"] is True and len(rows["rows"]) == 90 * 400 + 1
    shared = next(r for r in rows["rows"] if r["keys"][0] == "shared")
    assert shared["clicks"] == 90 and shared["impressions"] == 900 and round(shared["ctr"], 3) == 0.1
    # the recorded evidence keeps the run window, so the window guard and the number check still apply
    calls = json.loads((run_dir / "context.json").read_text())["calls"]
    assert next(c for c in calls if c["name"] == "pq_cur")["args"]["startDate"] == "2026-07-30"


def test_gsc_pull_that_cannot_be_completed_is_flagged_and_its_figures_refused():
    sys.path.insert(0, str(SEO / "report"))
    import number_check as N

    class Always(FakeClients):
        def call(self, server, tool, args):
            if tool == "analytics_query" and args.get("dimensions") == ["query", "page"]:
                self.calls.append((server, tool, args))
                return _text({"rows": [{"keys": [f"q{i}", f"{U}/"], "clicks": 7777 if i == 0 else 1, "impressions": 9000,
                                        "ctr": 0.1, "position": 3} for i in range(25000)]})
            return super().call(server, tool, args)

    saved = P.MAX_CALLS_PER_PULL
    P.MAX_CALLS_PER_PULL = 5
    try:
        with _isolated_cache():
            run_dir, s = _run("seo-brand-split", Always())
    finally:
        P.MAX_CALLS_PER_PULL = saved
    assert set(s["truncated"]) == {"pq_cur", "pq_prev"}, s["truncated"]
    assert "computed/brand_split.json" in s["tainted"]
    assert any("cut at 25,000 rows" in u["source"] for u in s["unavailable"])
    f = json.loads((run_dir / "findings.json").read_text())
    f["verdict"] = "Top query had 7,777 clicks."
    issues = N.check(f, N.Index.from_run(run_dir))
    assert issues and "cut at the row limit" in issues[0], issues


def test_ga4_report_over_the_limit_is_paged():
    class Paged(FakeClients):
        def call(self, server, tool, args):
            if tool == "run_report":
                self.calls.append((server, tool, args))
                off, lim, total = int(args.get("offset") or 0), int(args.get("limit") or 10000), 23500
                n = max(0, min(lim, total - off))
                return _text({"dimension_headers": [{"name": "sessionSource"}, {"name": "date"}],
                              "metric_headers": [{"name": "sessions"}],
                              "rows": [{"dimension_values": [{"value": f"s{off + i}"}, {"value": "20261001"}],
                                        "metric_values": [{"value": "1"}]} for i in range(n)], "row_count": total})
            return super().call(server, tool, args)

    run_dir = Path(tempfile.mkdtemp())
    (run_dir / ".run_state.json").write_text(json.dumps({"window": {"source": "ga4"}}))
    fake = Paged()
    ctx = P.Context(SITE, run_dir, {}, fake, resolve.load()[1])
    raw, info = ctx.fetch("ga4.ai_time_series", {"property_id": "1", "date_ranges": [{"start_date": "2026-09-01",
                                                                                       "end_date": "2026-09-28"}]})
    assert info == {"rows": 23500, "calls": 3}, info  # default GA4 page = 10,000 rows
    assert [a.get("offset") for _, _, a in fake.calls] == [None, 10000, 20000]
    pl = P._payload(raw)
    assert pl["_pipeline"]["complete"] is True and len({r["dimension_values"][0]["value"] for r in pl["rows"]}) == 23500


def test_an_incomplete_cached_pull_is_fetched_again():
    with _isolated_cache():
        run_dir, _ = _run("seo-brand-split", FakeClients())
        # poison the shared cache entry of pq_cur with a response that sits exactly at the row limit
        import record
        calls = json.loads((run_dir / "context.json").read_text())["calls"]
        entry = next(c for c in calls if c["name"] == "pq_cur")
        path = record._cache_path(run_dir, "gsc.page_query", entry["args"])
        stored = json.loads(path.read_text())
        stored["response"] = _text({"rows": [{"keys": [f"q{i}", f"{U}/"], "clicks": 1, "impressions": 2, "ctr": 0.5,
                                               "position": 4} for i in range(25000)]})
        path.write_text(json.dumps(stored))
        fake = FakeClients()
        _, s = _run("seo-brand-split", fake)
    pq = next(st for st in s["steps"] if st["name"] == "pq_cur")
    assert pq["status"] == "ok", pq  # not "cached": the cut response was not trusted
    assert any(a.get("dimensions") == ["query", "page"] for _, t, a in fake.calls if t == "analytics_query")


def test_ga4_paging_follows_the_reported_total_when_pages_are_smaller_than_the_limit():
    class SmallPages(FakeClients):  # a server that returns 1,000 rows per call whatever `limit` says
        def call(self, server, tool, args):
            if tool == "run_report":
                self.calls.append((server, tool, args))
                off, total = int(args.get("offset") or 0), 2500
                n = max(0, min(1000, total - off))
                return _text({"dimension_headers": [{"name": "sessionSource"}],
                              "metric_headers": [{"name": "sessions"}], "row_count": total,
                              **({"rows": [{"dimension_values": [{"value": f"s{off + i}"}],
                                            "metric_values": [{"value": "1"}]} for i in range(n)]} if n else {})})
            return super().call(server, tool, args)

    run_dir = Path(tempfile.mkdtemp())
    (run_dir / ".run_state.json").write_text(json.dumps({"window": {"source": "ga4"}}))
    fake = SmallPages()
    ctx = P.Context(SITE, run_dir, {}, fake, resolve.load()[1])
    raw, info = ctx.fetch("ga4.ai_cited_pages", {"property_id": "1", "date_ranges": [{"start_date": "2026-09-01",
                                                                                       "end_date": "2026-09-28"}]})
    assert info == {"rows": 2500, "calls": 3}, info
    assert P._payload(raw)["_pipeline"]["complete"] is True


def test_a_split_pull_that_stayed_incomplete_is_reused_from_cache_and_stays_flagged():
    class Always(FakeClients):
        def call(self, server, tool, args):
            if tool == "analytics_query" and args.get("dimensions") == ["query", "page"]:
                self.calls.append((server, tool, args))
                return _text({"rows": [{"keys": [f"q{i}", f"{U}/"], "clicks": 1, "impressions": 9, "ctr": 0.1,
                                        "position": 3} for i in range(25000)]})
            return super().call(server, tool, args)

    saved = P.MAX_CALLS_PER_PULL
    P.MAX_CALLS_PER_PULL = 3
    try:
        with _isolated_cache():
            _run("seo-brand-split", Always())
            again = Always()
            _, s = _run("seo-brand-split", again)
    finally:
        P.MAX_CALLS_PER_PULL = saved
    pq = next(st for st in s["steps"] if st["name"] == "pq_cur")
    assert pq["status"] == "cached" and pq["truncated"] is True, pq
    assert not [a for _, t, a in again.calls if t == "analytics_query" and a.get("dimensions") == ["query", "page"]]
    assert "pq_cur" in s["truncated"] and "computed/brand_split.json" in s["tainted"]


def test_merge_reads_metrics_like_the_analysis_and_refuses_missing_ones():
    merged = P._merge_gsc([{"rows": [{"keys": ["a"], "clicks": "1,000", "impressions": "2,000", "position": "2"}]},
                           {"rows": [{"keys": ["a"], "clicks": 500, "impressions": 2000, "position": 4}]}], ["query"])
    assert merged == [{"keys": ["a"], "clicks": 1500.0, "impressions": 4000.0, "ctr": 0.375, "position": 3.0}]
    try:
        P._merge_gsc([{"rows": [{"keys": ["a"], "clicks": 1}]}], ["query"])
        raise AssertionError("a row without impressions must not be merged as zero")
    except ValueError as e:
        assert "absent is not 0" in str(e)


def test_backlink_check_refuses_to_run_without_dataforseo():
    with _isolated_cache():
        fake = FakeClients(servers=("search-console", "analytics"))
        out = Path(tempfile.mkdtemp()) / "run"
        try:
            P.execute("seo-backlink-check", SITE, clients=fake, as_of=AS_OF, out_dir=str(out))
            raise AssertionError("must fail closed")
        except P.PlanError as e:
            assert "dataforseo" in str(e) and "no backlink report" in str(e)
        assert fake.calls == [] and not out.exists()  # nothing called, no run folder seeded
    plan = P.load_plan("seo-backlink-check")
    core = {st["pull"]: st for st in plan["steps"] if st.get("pull") in ("summary", "rd_ours")}
    assert not any(st.get("optional") for st in core.values())  # a DataForSEO error stops the run
    assert P.validate_plan({**plan, "requires_servers": {"nope": "x"}}, resolve.load()[1])[0].startswith("requires_servers")


# — temporary failures are retried (policy.retry, default 2), never writes or bad requests

class _Flaky(FakeClients):
    def __init__(self, fail_times, text, **kw):
        super().__init__(**kw)
        self.left, self.text = fail_times, text

    def call(self, server, tool, args):
        if tool == "analytics_query" and self.left:
            self.left -= 1
            self.calls.append((server, tool, args))
            return {"content": [{"type": "text", "text": self.text}], "isError": True}
        return super().call(server, tool, args)


def _retry_ctx(clients):
    run_dir = Path(tempfile.mkdtemp())
    (run_dir / ".run_state.json").write_text(json.dumps({"window": {"source": "gsc"}}))
    ctx = P.Context(SITE, run_dir, {}, clients, resolve.load()[1])
    waits = []
    ctx.sleep = waits.append
    return ctx, waits


def test_temporary_failures_are_retried_with_growing_waits():
    ctx, waits = _retry_ctx(_Flaky(2, "HTTP 503: backend unavailable"))
    args = {"siteUrl": f"{U}/", "startDate": "2026-10-01", "endDate": "2026-10-07"}
    assert ctx.call_raw("gsc.query", args)["isError"] is False
    assert waits == [2.0, 6.0] and ctx.retries == 2
    ctx, waits = _retry_ctx(_Flaky(3, "HTTP 429 Too Many Requests"))
    try:
        ctx.call_raw("gsc.query", args)
        raise AssertionError("3 failures exceed the default 2 retries")
    except P.StepFailed as e:
        assert "429" in str(e) and waits == [2.0, 6.0]


def test_bad_requests_writes_and_self_retrying_servers_are_not_retried():
    ctx, waits = _retry_ctx(_Flaky(1, "Invalid argument: dimension 'foo' does not exist"))
    try:
        ctx.call_raw("gsc.query", {"siteUrl": f"{U}/", "startDate": "2026-10-01", "endDate": "2026-10-07"})
        raise AssertionError("not transient")
    except P.StepFailed:
        assert waits == []
    caps = resolve.load()[1]
    assert caps["planner.ideas"]["policy"]["retry"] == 0  # the planner server retries itself: one layer only

    class Down(FakeClients):
        def call(self, server, tool, args):
            self.calls.append((server, tool, args))
            return {"content": [{"type": "text", "text": "503 unavailable"}], "isError": True}
    clients = Down()
    ctx, waits = _retry_ctx(clients)
    ctx.write_ok = True
    try:
        ctx.call_raw("gsc.indexing", {"siteUrl": f"{U}/", "urls": [f"{U}/"]}, confirm=True)
        raise AssertionError("write fails")
    except P.StepFailed:
        assert len(clients.calls) == 1 and waits == []  # a write is never repeated


def test_pipeline_json_records_seconds_and_retries():
    with _isolated_cache():
        fake = _Flaky(1, "deadline exceeded")
        saved = P.RETRY_BASE_S
        P.RETRY_BASE_S = 0
        try:
            _, s = _run("seo-brand-split", fake)
        finally:
            P.RETRY_BASE_S = saved
    assert s["status"] == "ok" and s["retries"] == 1
    assert all("seconds" in st for st in s["steps"] if st.get("status") in ("ok", "cached"))
    assert any(st.get("retries") == 1 for st in s["steps"])


def test_a_crashed_server_is_restarted_on_the_next_call():
    sys.path.insert(0, str(SEO / "tests"))
    import test_mcp_client as M
    clients = P.MCPClients(timeout=10)
    clients.servers = {"fake": M._spec()}
    try:
        try:
            clients.call("fake", "crash", {})
            raise AssertionError("crash should raise")
        except RuntimeError as e:
            assert "exited" in str(e) and P._transient(e)
        assert clients.call("fake", "echo", {"x": 1})["isError"] is False  # fresh process
    finally:
        clients.close()


if __name__ == "__main__":
    main(globals())
