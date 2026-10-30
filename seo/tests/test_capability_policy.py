"""Tests for capability `policy` metadata (retry budget vs client timeout, single retry layer)."""
import contextlib
import copy
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import resolve  # noqa: E402
from _runner import main  # noqa: E402


def _n(caps):
    with contextlib.redirect_stdout(io.StringIO()):
        return resolve.check_policies(caps)


def test_all_policies_fit_client_timeout():
    assert _n(resolve.load()[1]) == 0


def test_client_timeout_override_makes_planner_violate():
    old = os.environ.get("MCP_CLIENT_TIMEOUT_S")
    os.environ["MCP_CLIENT_TIMEOUT_S"] = "30"  # planner budget is 40
    try:
        assert _n(resolve.load()[1]) == 2      # planner.ideas + planner.historical
    finally:
        if old is None:
            os.environ.pop("MCP_CLIENT_TIMEOUT_S", None)
        else:
            os.environ["MCP_CLIENT_TIMEOUT_S"] = old


def test_planner_retries_live_in_one_layer():
    caps = copy.deepcopy(resolve.load()[1])
    for cid in ("planner.ideas", "planner.historical"):
        pol = caps[cid]["policy"]
        assert pol["retry"] == 0 and pol["timeout_budget_s"] == 40 and pol["on_error"] == "degrade"
    caps["planner.ideas"]["policy"]["retry"] = 3
    assert _n(caps) == 1


if __name__ == "__main__":
    main(globals())
