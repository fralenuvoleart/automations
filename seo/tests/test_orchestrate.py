"""Tests for seo/orchestrate.py — run seeding, evidence index, no silent overwrite."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import orchestrate  # noqa: E402
from _runner import main  # noqa: E402


def _run(args):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return orchestrate.main(args)


def test_orchestrate_writes_state_context_and_findings():
    with tempfile.TemporaryDirectory() as d:
        assert _run(["--skill", "seo-audit", "--days", "28", "--compare", "--as-of", "2026-10-29", "--out-dir", d]) == 0
        state = json.loads((Path(d) / ".run_state.json").read_text())
        findings = json.loads((Path(d) / "findings.json").read_text())
        assert state["window"]["endDate"] == "2026-10-26" and state["window"]["compareEndDate"] == "2026-09-28"
        assert json.loads((Path(d) / "context.json").read_text()) == {"calls": []}
        assert (Path(d) / "data").is_dir()
        assert findings["window"] == state["window"] and findings["sections"] == []


def test_refuses_to_overwrite_without_force():
    with tempfile.TemporaryDirectory() as d:
        assert _run(["--skill", "x", "--out-dir", d, "--as-of", "2026-10-29"]) == 0
        (Path(d) / "findings.json").write_text('{"keep": true}')
        assert _run(["--skill", "x", "--out-dir", d, "--as-of", "2026-10-29"]) == 1
        assert json.loads((Path(d) / "findings.json").read_text()) == {"keep": True}
        assert _run(["--skill", "x", "--out-dir", d, "--as-of", "2026-10-29", "--force"]) == 0


if __name__ == "__main__":
    main(globals())
