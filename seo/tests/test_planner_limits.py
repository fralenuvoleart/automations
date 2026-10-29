"""Tests for the KeywordPlanIdeaService limit helpers (offline, no API calls).

Run:  python3 seo/tests/test_planner_limits.py   (or: python3 -m pytest seo/tests -q)
"""
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parents[1] / "mcp-servers" / "google-ads-planner"
sys.path.insert(0, str(DIR))

import planner_limits as pl  # noqa: E402


def test_dedupe_stable_order():
    assert pl.dedupe(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert pl.dedupe([]) == []


def test_backoff_is_exponential_and_honours_hint():
    assert pl.backoff_delay(0) == 2
    assert pl.backoff_delay(1) == 4
    assert pl.backoff_delay(2) == 8
    assert pl.backoff_delay(0, hint=40) == 40   # server hint wins
    assert pl.backoff_delay(3, hint=5) == 16     # exponential beats a small hint


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def test_rate_gate_first_call_no_wait():
    slept = []
    gate = pl.RateGate(min_interval=1.0, clock=FakeClock(), sleep=slept.append)
    assert gate.wait("cid") == 0.0
    assert slept == []


def test_rate_gate_enforces_interval():
    clock = FakeClock()
    slept = []

    def sleeper(s):
        slept.append(s)
        clock.advance(s)

    gate = pl.RateGate(min_interval=1.0, clock=clock, sleep=sleeper)
    gate.wait("cid")            # t=0
    clock.advance(0.3)          # t=0.3
    w = gate.wait("cid")        # must wait 0.7s
    assert abs(w - 0.7) < 1e-9
    assert abs(slept[-1] - 0.7) < 1e-9


def test_rate_gate_is_per_key():
    slept = []
    gate = pl.RateGate(min_interval=1.0, clock=FakeClock(), sleep=slept.append)
    gate.wait("a")
    assert gate.wait("b") == 0.0   # different customer ID, no wait


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
