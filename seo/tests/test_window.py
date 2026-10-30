"""Tests for seo/window.py — deterministic windows per source, compare/YoY, provenance line."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import window  # noqa: E402
from _runner import main  # noqa: E402

AS_OF = dt.date(2026, 10, 29)


def test_gsc_default_lag_is_three_days():
    r = window.resolve(28, AS_OF)
    assert (r["startDate"], r["endDate"], r["lag"], r["source"]) == ("2026-09-29", "2026-10-26", 3, "gsc")


def test_ga4_default_lag_is_two_days():
    r = window.resolve(28, AS_OF, source="ga4")
    assert r["endDate"] == "2026-10-27" and r["lag"] == 2


def test_previous_period_compare():
    r = window.resolve(28, AS_OF, compare=True)
    assert (r["compareStartDate"], r["compareEndDate"], r["compareMode"]) == ("2026-09-01", "2026-09-28", "previous")


def test_yoy_compare_is_weekday_aligned():
    r = window.resolve(28, AS_OF, yoy=True)
    s, cs = dt.date.fromisoformat(r["startDate"]), dt.date.fromisoformat(r["compareStartDate"])
    assert (s - cs).days == 364 and s.weekday() == cs.weekday() and r["compareMode"] == "yoy"


def test_snapshot_window():
    r = window.resolve(source="snapshot", as_of=AS_OF)
    assert r["startDate"] == r["endDate"] == "2026-10-29" and r["source"] == "snapshot"
    assert window.as_of_line(r, "X") == "Snapshot as of 2026-10-29 (live data) · generated X"


def test_invalid_inputs_raise():
    for kwargs in ({"days": 0}, {"days": 7, "lag": 0}, {"days": 7, "source": "nope"}):
        try:
            window.resolve(as_of=AS_OF, **kwargs)
            raise AssertionError(f"expected ValueError for {kwargs}")
        except ValueError:
            pass


def test_as_of_line_is_stable():
    r = window.resolve(28, AS_OF, lag=2, compare=True)
    assert window.as_of_line(r, "2026-10-29T05:46Z") == (
        "Window 2026-09-30→2026-10-27 (vs 2026-09-02→2026-09-29) · GSC lag 2d · generated 2026-10-29T05:46Z")
    y = window.resolve(28, AS_OF, yoy=True, source="ga4")
    assert "(vs YoY " in window.as_of_line(y, "X") and "GA4 lag 2d" in window.as_of_line(y, "X")



def test_calendar_weeks_end_with_the_latest_complete_week():
    w = window.resolve_weeks(8, dt.date(2026, 10, 30))  # Friday; GSC data through Tue 27 Oct
    assert (w["startDate"], w["endDate"], w["days"]) == ("2026-08-31", "2026-10-25", 56)  # the SEO sheet's 8 weeks
    assert w["weeks"][-1] == {"startDate": "2026-10-19", "endDate": "2026-10-25"} and len(w["weeks"]) == 8
    assert all(dt.date.fromisoformat(x["startDate"]).weekday() == 0 for x in w["weeks"])
    w = window.resolve_weeks(1, dt.date(2026, 10, 27), compare=True)  # data through Sat 24 Oct → week ending 18 Oct
    assert (w["startDate"], w["endDate"], w["compareStartDate"], w["compareEndDate"]) == \
        ("2026-10-12", "2026-10-18", "2026-10-05", "2026-10-11")
    assert window.resolve_weeks(1, dt.date(2026, 10, 28))["endDate"] == "2026-10-25"  # data through Sunday itself
    assert "(8 Mon–Sun weeks)" in window.as_of_line(window.resolve_weeks(8, dt.date(2026, 10, 30)), generated_at="X")
    for bad in (lambda: window.resolve_weeks(0), lambda: window.resolve_weeks(2, source="snapshot")):
        try:
            bad()
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


if __name__ == "__main__":
    main(globals())
