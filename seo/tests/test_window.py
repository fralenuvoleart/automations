"""Tests for seo/window.py — deterministic, date-anchored window resolution.

Run:  python3 seo/tests/test_window.py   (or: python3 -m pytest seo/tests -q)
"""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import window  # noqa: E402


def test_resolve_basic_lag():
    r = window.resolve(28, dt.date(2026, 10, 29), lag=2)
    assert r["endDate"] == "2026-10-27"
    assert r["startDate"] == "2026-09-30"
    assert r["days"] == 28 and r["lag"] == 2 and r["as_of"] == "2026-10-29"


def test_resolve_compare_window():
    r = window.resolve(28, dt.date(2026, 10, 29), lag=2, compare=True)
    assert r["compareEndDate"] == "2026-09-29"
    assert r["compareStartDate"] == "2026-09-02"


def test_resolve_no_lag():
    r = window.resolve(7, dt.date(2026, 1, 10), lag=0)
    assert r["endDate"] == "2026-01-10" and r["startDate"] == "2026-01-04"


def test_single_day_window():
    r = window.resolve(1, dt.date(2026, 3, 1), lag=0)
    assert r["startDate"] == r["endDate"] == "2026-03-01"


def test_invalid_inputs_raise():
    for bad in (0, -5):
        try:
            window.resolve(bad, dt.date(2026, 1, 1))
            raise AssertionError("expected ValueError for days=%r" % bad)
        except ValueError:
            pass
    try:
        window.resolve(7, dt.date(2026, 1, 1), lag=-1)
        raise AssertionError("expected ValueError for lag=-1")
    except ValueError:
        pass


def test_as_of_line_is_stable_given_timestamp():
    r = window.resolve(28, dt.date(2026, 10, 29), lag=2, compare=True)
    line = window.as_of_line(r, generated_at="2026-10-29T05:46Z")
    assert line == "Window 2026-09-30\u21922026-10-27 (vs 2026-09-02\u21922026-09-29) \u00b7 GSC lag 2d \u00b7 generated 2026-10-29T05:46Z"


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
