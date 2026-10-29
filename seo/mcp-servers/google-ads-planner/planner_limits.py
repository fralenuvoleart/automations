"""Deterministic limit helpers for Google Ads KeywordPlanIdeaService.

Stdlib-only so it can be unit-tested without the Google Ads / FastMCP deps.

KeywordPlanIdeaService methods are throttled to ~1 QPS per customer ID and do
heavy backend work; these helpers keep calls paced and retries reproducible.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Iterable

MIN_INTERVAL = 1.0  # KeywordPlanIdeaService: ~1 QPS per customer ID
BASE_DELAY = 2      # exponential-backoff base (seconds)


def dedupe(items: Iterable[str]) -> list[str]:
    """Stable de-duplication preserving first-seen order (shrinks the payload)."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def backoff_delay(attempt: int, hint: int | None = None, base: int = BASE_DELAY) -> int:
    """Deterministic exponential backoff: ``max(server hint, base * 2**attempt)``.

    No jitter, so retries stay reproducible.
    """
    exp = base * (2 ** max(0, attempt))
    return max(hint or 0, exp)


class RateGate:
    """Thread-safe, clock-injectable ``>= min_interval`` gate keyed by customer ID."""

    def __init__(self, min_interval: float = MIN_INTERVAL,
                 clock=time.monotonic, sleep=time.sleep):
        self._min = min_interval
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last: dict[str, float] = {}

    def wait(self, key: str) -> float:
        """Block until ``min_interval`` has elapsed for ``key``; return the wait (s)."""
        with self._lock:
            now = self._clock()
            last = self._last.get(key)
            wait = 0.0 if last is None else self._min - (now - last)
            if wait > 0:
                self._sleep(wait)
            self._last[key] = self._clock()
            return max(0.0, wait)
