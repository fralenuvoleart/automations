"""Tests for seo/report/build_report.py — deterministic rendering."""
import json
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "report"))

import build_report  # noqa: E402

FIXTURE = SEO / "tests" / "fixtures" / "findings_example.json"
FINDINGS = json.loads(FIXTURE.read_text())


def test_build_contains_header_asof_and_sections():
    md = build_report.build(FINDINGS, generated_at="2026-10-29T06:00Z")
    assert "# seo-audit" in md
    assert "Window 2026-09-30\u21922026-10-27" in md
    assert "generated 2026-10-29T06:00Z" in md
    assert "## Losers" in md
    assert "| query | clicks_delta |" in md
    assert "## Action list" in md
    assert "1. Rewrite the titles" in md


def test_build_is_deterministic():
    a = build_report.build(FINDINGS, generated_at="2026-10-29T06:00Z")
    b = build_report.build(FINDINGS, generated_at="2026-10-29T06:00Z")
    assert a == b


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
