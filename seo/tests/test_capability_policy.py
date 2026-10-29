"""Tests for capability `policy` metadata (retry budget vs client timeout)."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import resolve  # noqa: E402


def test_all_policies_fit_client_timeout():
    assert resolve.check_policies() == 0


def test_client_timeout_override_makes_planner_violate():
    old = os.environ.get("MCP_CLIENT_TIMEOUT_S")
    os.environ["MCP_CLIENT_TIMEOUT_S"] = "30"  # planner budget is 40
    try:
        assert resolve.check_policies() == 1
    finally:
        if old is None:
            os.environ.pop("MCP_CLIENT_TIMEOUT_S", None)
        else:
            os.environ["MCP_CLIENT_TIMEOUT_S"] = old


def test_planner_policy_values():
    _, caps, _, _ = resolve.load()
    pol = caps["planner.ideas"]["policy"]
    assert pol["timeout_budget_s"] == 40
    assert pol["on_error"] == "degrade"
    assert pol["backoff_s"] == [2, 4, 8]


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
