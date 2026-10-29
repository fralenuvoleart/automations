"""Tests for seo/orchestrate.py — state file + findings skeleton."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import orchestrate  # noqa: E402


def test_orchestrate_writes_state_and_findings():
    with tempfile.TemporaryDirectory() as d:
        rc = orchestrate.main(["--skill", "seo-audit", "--days", "28",
                               "--as-of", "2026-10-29", "--compare", "--out-dir", d])
        assert rc == 0
        state = json.loads((Path(d) / ".run_state.json").read_text())
        findings = json.loads((Path(d) / "findings.json").read_text())
        assert state["skill"] == "seo-audit"
        assert state["window"]["startDate"] == "2026-09-30"
        assert state["window"]["endDate"] == "2026-10-27"
        assert state["window"]["compareStartDate"] == "2026-09-02"
        assert findings["as_of"] == "2026-10-29"
        assert findings["sections"] == []
        assert state["paths"]["report"].endswith("report.md")


def _run_all() -> int:
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
