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


if __name__ == "__main__":
    main(globals())
