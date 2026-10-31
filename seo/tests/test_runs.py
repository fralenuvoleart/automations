"""Tests for seo/runs.py — fixed run layout, git-ignore guard, latest run, retention."""
import contextlib
import datetime as dt
import io
import json
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))
import orchestrate  # noqa: E402
import runs  # noqa: E402
from _runner import main  # noqa: E402


@contextlib.contextmanager
def root_at(path):
    saved = runs.settings
    runs.settings = lambda: {"run_root": str(path), "retention_days": 30, "cache": True}
    try:
        yield
    finally:
        runs.settings = saved


def _seed(skill, as_of, tag=None, verdict=""):
    args = ["--skill", skill, "--site", "pbservices.ge", "--days", "28", "--as-of", as_of] + (["--tag", tag] if tag else [])
    with contextlib.redirect_stdout(io.StringIO()):
        assert orchestrate.main(args) == 0
    d = runs.run_dir("pbservices.ge", as_of, skill, tag)
    if verdict:
        f = json.loads((d / "findings.json").read_text())
        (d / "findings.json").write_text(json.dumps({**f, "verdict": verdict}))
    return d


def test_configured_root_cannot_be_committed():
    assert runs.settings()["run_root"]
    assert runs.ignore_problem() is None  # outside the repo, or covered by .gitignore


def test_a_relative_root_inside_the_repo_must_be_git_ignored():
    assert runs.ignore_problem(runs.REPO / ".output" / "seo") is None          # in .gitignore
    assert "not in .gitignore" in (runs.ignore_problem(runs.REPO / "seo") or "")  # tracked folder: refused


def test_layout_and_name_guards():
    with tempfile.TemporaryDirectory() as root, root_at(root):
        d = _seed("seo-rank-tracking", "2026-10-30", tag="weekly")
        assert d == Path(root) / "pbservices.ge" / "2026-10-30" / "seo-rank-tracking-weekly"
        state = json.loads((d / ".run_state.json").read_text())
        assert state["site"] == "pbservices.ge" and state["tag"] == "weekly"
        for bad in (("../x", "2026-10-30", "s"), ("pbservices.ge", "2026-10-30", "a/b"), ("p.ge", "today", "s")):
            try:
                runs.run_dir(*bad)
                raise AssertionError(f"expected ValueError for {bad}")
            except ValueError:
                pass


def test_run_root_inside_repo_must_be_ignored():
    with tempfile.TemporaryDirectory(dir=runs.REPO) as inside:
        assert "not in .gitignore" in runs.ignore_problem(Path(inside))
        with root_at(inside), contextlib.redirect_stderr(io.StringIO()) as err:
            assert orchestrate.main(["--skill", "seo-audit", "--site", "pbservices.ge", "--days", "28"]) == 1
        assert "could be committed" in err.getvalue()


def test_latest_completed_run_and_max_age():
    with tempfile.TemporaryDirectory() as root, root_at(root):
        _seed("seo-audit", "2026-09-01", verdict="old")
        _seed("seo-audit", "2026-10-28", verdict="new")
        _seed("seo-audit", "2026-10-30")                       # seeded, not finished
        r = runs.latest("pbservices.ge", "seo-audit", as_of=dt.date(2026, 10, 30))
        assert r["as_of"] == "2026-10-28" and r["completed"]
        assert runs.latest("pbservices.ge", "seo-audit", max_age_days=1, as_of=dt.date(2026, 10, 30)) is None
        assert [x["as_of"] for x in runs.runs("pbservices.ge", "seo-audit")] == ["2026-10-30", "2026-10-28", "2026-09-01"]


def test_prune_by_retention():
    with tempfile.TemporaryDirectory() as root, root_at(root):
        old, new = _seed("seo-audit", "2026-08-01"), _seed("seo-audit", "2026-10-29")
        assert runs.prune(dry_run=True, as_of=dt.date(2026, 10, 30)) == [str(old.parent)]
        assert old.exists()
        runs.prune(as_of=dt.date(2026, 10, 30))
        assert not old.exists() and new.exists()


def test_export_writes_readable_csv_files_from_the_whole_history():
    with tempfile.TemporaryDirectory() as tmp:
        with root_at(Path(tmp)):
            d1 = _seed("seo-audit", "2026-10-20", verdict="ok")
            win = json.loads((d1 / ".run_state.json").read_text())["window"]
            (d1 / "computed").mkdir(exist_ok=True)
            (d1 / "computed" / "totals.json").write_text(json.dumps({
                "current": {"clicks": 100, "impressions": 1000, "ctr": 0.1, "position": 8.0},
                "previous": {"clicks": 50, "impressions": 900, "ctr": 12.5, "position": 9.0}}))
            (d1 / "pipeline.json").write_text(json.dumps({
                "skill": "seo-audit", "status": "ok", "unavailable": [],
                "steps": [{"name": "page_cur", "kind": "pull", "cap": "gsc.page", "status": "ok",
                           "seconds": 1.5, "calls": 2},
                          {"name": "totals", "kind": "compute", "status": "ok", "seconds": 0.5}]}))
            f = json.loads((d1 / "findings.json").read_text())
            (d1 / "findings.json").write_text(json.dumps({**f, "actions": [
                {"action": "Rewrite the title", "impact": "high", "effort": "low", "why": "clicks -50%",
                 "est_clicks": 12},
                "Plain string action"]}))
            (d1 / "data").mkdir(exist_ok=True)
            (d1 / "data" / "page_cur.json").write_text(json.dumps({"content": [{"type": "text", "text": json.dumps(
                {"rows": [{"keys": ["https://pbservices.ge/a/"], "clicks": 7, "impressions": 70, "ctr": 0.1,
                           "position": 4.5}]})}], "isError": False}))
            (d1 / "data" / "query_w1.json").write_text(json.dumps(
                {"rows": [{"keys": ["\u0432\u043d\u0436"], "clicks": 3, "impressions": 30, "ctr": 0.1,
                           "position": 6}]}))
            (d1 / "data" / "query_12m.json").write_text(json.dumps(
                {"rows": [{"keys": ["off-window query"], "clicks": 9, "impressions": 90, "ctr": 0.1, "position": 9}]}))
            (d1 / "context.json").write_text(json.dumps({"calls": [
                {"name": "page_cur", "cap": "gsc.page", "file": "data/page_cur.json",
                 "args": {"siteUrl": "sc-domain:pbservices.ge", "startDate": win["startDate"],
                          "endDate": win["endDate"]}},
                {"name": "query_w1", "cap": "gsc.query", "file": "data/query_w1.json",
                 "args": {"siteUrl": "sc-domain:pbservices.ge", "startDate": "2026-09-01",
                          "endDate": "2026-09-07"}},
                {"name": "query_12m", "cap": "gsc.query", "file": "data/query_12m.json",
                 "window_exception": "CTR curve lookback", "args": {"startDate": "2025-10-01",
                                                                    "endDate": "2026-10-01"}},
                {"name": "pq_cur", "cap": "gsc.page_query", "file": "data/page_cur.json",
                 "args": {"startDate": win["startDate"], "endDate": win["endDate"]}}]}))
            # a brief-style run: weekly KPIs must reach totals.csv
            d2 = _seed("seo-brief", "2026-10-27", verdict="ok")
            (d2 / "computed").mkdir(exist_ok=True)
            (d2 / "computed" / "brief.json").write_text(json.dumps({"kpis": [
                {"week": "2026-10-19", "days": 7, "clicks": 840, "impressions": 7000, "ctr": 12.0,
                 "position": 8.0}]}))

            out = Path(tmp) / "spreadsheets"
            written = runs.export("pbservices.ge", out)
            assert [p.name for p in written] == ["runs.csv", "totals.csv", "pages.csv", "queries.csv", "actions.csv"]
            assert (out / "README.md").exists() and (Path(tmp) / "pbservices.ge" / "README.md").exists()
            assert written[0].read_bytes().startswith(b"\xef\xbb\xbf")   # BOM: Excel reads UTF-8

            def table(name):
                import csv
                with (out / name).open(encoding="utf-8-sig") as fh:
                    return list(csv.DictReader(fh))

            runs_rows = table("runs.csv")
            assert [r["report"] for r in runs_rows] == ["seo-audit", "seo-brief"]       # oldest first
            # only pulls count, and their real call count (the pull made 2 calls; the compute step is not a call)
            assert runs_rows[0]["tool_calls"] == "2", runs_rows[0]
            assert runs_rows[0]["status"] == "ok" and runs_rows[0]["seconds"] == "2.0"
            totals = table("totals.csv")
            assert {(t["period"], t["clicks"], t["click_rate_percent"]) for t in totals} >= {
                ("current", "100", "10.0"), ("previous", "50", "12.5")}   # 12.5 stays 12.5: already a percentage
            assert ("week", "840", "12.0") in {(t["period"], t["clicks"], t["click_rate_percent"]) for t in totals}
            pages = table("pages.csv")
            assert pages[0]["page"] == "https://pbservices.ge/a/" and pages[0]["clicks"] == "7"  # unwrapped
            assert pages[0]["period_start"] == win["startDate"]
            queries = table("queries.csv")
            assert [q["query"] for q in queries] == ["\u0432\u043d\u0436"]      # the off-window lookback is skipped
            assert queries[0]["period_start"] == "2026-09-01" and queries[0]["period_end"] == "2026-09-07"
            actions = table("actions.csv")
            assert [a["action"] for a in actions] == ["Rewrite the title", "Plain string action"]
            assert actions[0]["estimated_clicks"] == "12" and actions[0]["impact"] == "high"
            with contextlib.redirect_stdout(io.StringIO()):
                assert runs.main(["export", "--site", "pbservices.ge", "--out", str(Path(tmp) / "x"),
                                  "--tables", "runs"]) == 0
            assert (Path(tmp) / "x" / "runs.csv").exists() and not (Path(tmp) / "x" / "totals.csv").exists()
            try:
                runs.export("pbservices.ge", out, ["nope"])
                raise AssertionError("unknown table must be rejected")
            except ValueError as e:
                assert "unknown table" in str(e)


if __name__ == "__main__":
    main(globals())
