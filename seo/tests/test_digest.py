"""Tests for seo/digest.py — the weekly brief merges, ranks and tracks actions across reports."""
import contextlib
import datetime as dt
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))
sys.path.insert(0, str(SEO / "tests"))
import build_report  # noqa: E402
import digest  # noqa: E402
import orchestrate  # noqa: E402
import record  # noqa: E402
import runs  # noqa: E402
import site_profile  # noqa: E402
import validate_report  # noqa: E402
from _runner import main  # noqa: E402

SITE = "pbservices.ge"
BANK = "https://pbservices.ge/services/bank-account-georgia/"
VNZH = "https://pbservices.ge/ru/uslugi/vnzh-v-gruzii/"


@contextlib.contextmanager
def sandbox():
    saved_settings, saved_hist = runs.settings, site_profile.history_path
    with tempfile.TemporaryDirectory() as root:
        runs.settings = lambda: {"run_root": root, "cache": True, "retention_days": 180, "brief_max_age_days": 45,
                                 "cadence_days": {"seo-brief": 7, "seo-audit": 30, "seo-rank-tracking": 7,
                                                  "seo-technical": 30}}
        site_profile.history_path = lambda d: Path(root) / f"{d}.history.md"
        try:
            yield Path(root)
        finally:
            runs.settings, site_profile.history_path = saved_settings, saved_hist


def _seed(skill, as_of, days_args=("--days", "28"), tag=None):
    args = ["--skill", skill, "--site", SITE, *days_args, "--as-of", as_of] + (["--tag", tag] if tag else [])
    with contextlib.redirect_stdout(io.StringIO()):
        assert orchestrate.main(args) == 0
    return runs.run_dir(SITE, as_of, skill, tag)


def _finish(d, actions, verdict="done"):
    f = json.loads((d / "findings.json").read_text())
    (d / "findings.json").write_text(json.dumps({**f, "verdict": verdict, "actions": actions}))


def _brief(as_of, daily=None):
    d = _seed("seo-brief", as_of, ("--weeks", "8"))
    win = json.loads((d / ".run_state.json").read_text())["window"]
    rows = daily or [{"keys": [(dt.date.fromisoformat(win["startDate"]) + dt.timedelta(days=i)).isoformat()],
                      "clicks": 100 + (20 if i >= 49 else 0), "impressions": 1000, "ctr": 0.1, "position": 8.0}
                     for i in range(56)]
    record.record(d, "totals", json.dumps({"rows": rows}), cap="gsc.daily_totals",
                  args={"siteUrl": "sc-domain:pbservices.ge", "startDate": win["startDate"], "endDate": win["endDate"]})
    return d


def test_brief_merges_ranks_and_tracks_actions():
    with sandbox() as root:
        audit = _seed("seo-audit", "2026-10-20")
        _finish(audit, [
            {"action": "Point internal links to the bank account service page", "impact": "high", "effort": "low",
             "page": BANK, "why": "a blog post outranks it"},
            {"action": "Rewrite the residence permit page", "impact": "high", "effort": "high", "page": VNZH},
            "Legacy text action from an old report",
            {"action": "Fix the duplicate title", "impact": "medium", "effort": "low", "page": VNZH}])
        rank = _seed("seo-rank-tracking", "2026-10-27", ("--weeks", "8"), tag="weekly")
        _finish(rank, [{"action": "Point internal links to the bank account service page.", "impact": "high",
                        "effort": "low", "page": BANK, "est_clicks": 12}])
        old = _seed("seo-technical", "2026-08-01")
        _finish(old, [{"action": "Ancient action", "impact": "high", "effort": "low"}])
        site_profile.append_history(SITE, "Fix the duplicate title", when="2026-10-25", status="done")

        d = _brief("2026-10-30")
        f = digest.build(SITE, d, top=3)
        acts = f["actions"]
        assert acts[0]["action"].startswith("Point internal links") and acts[0]["est_clicks"] == 12  # merged, newest wording
        assert [a["action"] for a in acts] == ["Point internal links to the bank account service page.",
                                                "Legacy text action from an old report", "Rewrite the residence permit page"]
        assert all("Fix the duplicate title" != a["action"] for a in acts)                        # logged [done]
        assert all("Ancient" not in a["action"] for a in acts)                                     # older than 45 days
        top = next(s for s in f["sections"] if s["heading"] == "Top actions")
        assert top["table"][0]["from"] == "seo-rank-tracking 2026-10-27, seo-audit 2026-10-20"
        assert {r["status"] for r in top["table"]} == {"new"}
        rep = next(s for s in f["sections"] if s["heading"] == "Reports")
        assert "seo-technical (90 days old)" in rep["body"] and [r["report"] for r in rep["table"]] == ["seo-audit", "seo-rank-tracking"]
        kpi = next(s for s in f["sections"] if s["heading"] == "KPIs (last 8 weeks)")["table"]
        assert len(kpi) == 8 and kpi[-1] == {"week": "2026-10-19", "days": 7, "clicks": 840, "impressions": 7000,
                                              "ctr": 12.0, "position": 8.0}
        assert f["verdict"].startswith("Week of 2026-10-19: 840 clicks (+20.0% vs previous week)")
        calls = json.loads((d / "context.json").read_text())["calls"]
        assert {c["name"] for c in calls} >= {"totals", "run_seo_audit", "run_seo_rank_tracking"}

        # the brief itself validates and renders (URLs trace to the recorded reports)
        md = build_report.build(f, generated_at="X")
        data = "".join((d / c["file"]).read_text() for c in calls)
        assert validate_report.validate(f, report_text=md, data_text=data, evidence_calls=len(calls)) == []
        assert "## Top actions" in md and "## Definitions" in md

        # next week: carried-over actions show since when; resolved ones are counted
        _finish(rank, [{"action": "Rewrite the residence permit page", "impact": "high", "effort": "high", "page": VNZH}])
        _finish(audit, [{"action": "Rewrite the residence permit page", "impact": "high", "effort": "high", "page": VNZH}])
        d2 = _brief("2026-11-06")
        f2 = digest.build(SITE, d2, top=3)
        t2 = next(s for s in f2["sections"] if s["heading"] == "Top actions")
        assert t2["table"][0]["status"] == "open since 2026-10-30"
        assert "2 from the last brief no longer flagged" in t2["body"]


def test_brief_without_reports_or_kpis_degrades():
    with sandbox():
        d = _seed("seo-brief", "2026-10-30", ("--weeks", "8"))
        f = digest.build(SITE, d)
        assert {u["affects"].split(" (")[0] for u in f["unavailable"]} == {"weekly KPIs", "actions"}
        assert f["actions"] == [] and "seo-audit (never run)" in f["sections"][-1]["body"]
        assert validate_report.validate_structure(f) == []


def test_a_report_whose_source_is_missing_is_blocked_not_due():
    import pipeline

    class NoDFS:
        """dataforseo is the one server seo-backlink-check insists on (`plan.requires_servers`)."""
        def available(self, server):
            return server != "dataforseo"

        def close(self):
            pass

    with sandbox():
        cfg = runs.settings()  # the backlink report is on a 90-day cadence, so it is in the report list
        runs.settings = lambda: {**cfg, "cadence_days": {**cfg["cadence_days"], "seo-backlink-check": 90}}
        saved = pipeline.MCPClients
        pipeline.MCPClients = NoDFS
        try:
            f = digest.build(SITE, _brief("2026-10-30"), top=3)
        finally:
            pipeline.MCPClients = saved
        body = next(s for s in f["sections"] if s["heading"] == "Reports")["body"]
        assert "Cannot run (missing source): seo-backlink-check (needs dataforseo)" in body, body
        due_part = body.split("Due now:")[1].split("Cannot run")[0]
        assert "seo-backlink-check" not in due_part, body
        assert "cannot run (missing source)" in f["verdict"], f["verdict"]


def test_cli():
    with sandbox():
        d = _brief("2026-10-30")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            assert digest.main(["--site", SITE, "--run-dir", str(d)]) == 0
        assert "Week of 2026-10-19" in out.getvalue()
        with contextlib.redirect_stderr(io.StringIO()):
            assert digest.main(["--site", SITE, "--run-dir", str(d / "missing")]) == 1



def test_first_seen_tracks_actions_outside_the_top_and_on_demand_reports():
    with sandbox():
        brief_src = _seed("seo-content-brief", "2026-10-28")          # on demand: no cadence, still included
        _finish(brief_src, [{"action": "Write the IE guide in Arabic", "impact": "medium", "effort": "medium"},
                            {"action": "Add FAQ to the IE page", "impact": "low", "effort": "low"}])
        d1 = _brief("2026-10-30")
        f1 = digest.build(SITE, d1, top=1)
        assert f1["actions"][0]["action"] == "Write the IE guide in Arabic"
        state = json.loads((d1 / digest.STATE).read_text())
        assert len(state["first_seen"]) == 2                           # both open actions dated, not only the top 1
        assert "seo-content-brief" not in next(s for s in f1["sections"] if s["heading"] == "Reports")["body"]  # never due
        _finish(brief_src, [{"action": "Add FAQ to the IE page", "impact": "low", "effort": "low"}])
        d2 = _brief("2026-11-06")
        f2 = digest.build(SITE, d2, top=1)
        t = next(s for s in f2["sections"] if s["heading"] == "Top actions")["table"][0]
        assert t["action"] == "Add FAQ to the IE page" and t["status"] == "open since 2026-10-30"
        assert list(json.loads((d2 / digest.STATE).read_text())["first_seen"].values()) == ["2026-10-30"]  # closed one pruned


def test_the_brief_passes_the_evidence_and_number_gate():
    """Alpha guarantee: a generated brief must survive `validate_report.py --data`, like any other report."""
    with sandbox():
        src = _seed("seo-audit", "2026-10-20")
        _finish(src, [{"action": "Rewrite the bank account page title", "impact": "high", "effort": "low",
                       "page": BANK, "why": "clicks fell", "est_clicks": 12}])
        d = _brief("2026-10-30")
        digest.build(SITE, d, top=3)
        assert (d / "computed" / "brief.json").exists()      # the figures the brief states are published
        p = subprocess.run([sys.executable, str(SEO / "report" / "validate_report.py"),
                            "--findings", str(d / "findings.json"), "--data", str(d / "context.json")],
                           capture_output=True, text=True)
        assert p.returncode == 0, p.stdout + p.stderr


if __name__ == "__main__":
    main(globals())
