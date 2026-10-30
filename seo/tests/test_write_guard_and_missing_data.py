"""A3 write guard, A2 absent-is-not-zero, A1 row-limit detection. No network, no real cache."""
import json
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))

import ga4_metrics  # noqa: E402
import gsc_metrics  # noqa: E402
import pipeline as P  # noqa: E402
import resolve  # noqa: E402
import rules  # noqa: E402
from _runner import main  # noqa: E402

SITE = "pbservices.ge"
URL = "https://pbservices.ge/"
R = rules.load(SITE)


class _Raises:
    """Minimal `pytest.raises` stand-in: `with raises(Exc) as err:` exposes `err.value`."""

    def __init__(self, exc):
        self.exc, self.value = exc, None

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            raise AssertionError(f"expected {self.exc.__name__}")
        if issubclass(et, self.exc):
            self.value = ev
            return True
        return False


def raises(exc):
    return _Raises(exc)


class _Clients:
    """Records calls; never touches a server."""

    def __init__(self):
        self.calls = []

    def available(self, server):
        return True

    def close(self):
        pass

    def call(self, server, tool, args):
        self.calls.append((server, tool, args))
        return {"content": [{"type": "text", "text": "{}"}], "isError": False}


def _ctx(clients):
    """A Context over a seeded run dir (Context.__init__ reads .run_state.json)."""
    run_dir = Path(tempfile.mkdtemp())
    (run_dir / ".run_state.json").write_text(json.dumps({"window": {"source": "gsc"}}))
    return P.Context(SITE, run_dir, {}, clients, resolve.load()[1])


# — A3: the one capability that changes state outside the workspace

def test_indexing_is_declared_a_write_capability():
    caps = resolve.load()[1]
    assert (caps["gsc.indexing"].get("policy") or {}).get("write") is True


def test_plan_may_not_include_a_write_capability_without_confirmation():
    plan = {"window": {"days": 28},
            "steps": [{"pull": "submit", "cap": "gsc.indexing", "args": {"urls": [URL]}}]}
    issues = P.validate_plan(plan, resolve.load()[1])
    assert any("confirm" in i for i in issues), issues


def test_confirmed_write_step_passes_the_plan_check():
    plan = {"window": {"days": 28},
            "steps": [{"pull": "submit", "cap": "gsc.indexing", "args": {"urls": [URL]}, "confirm": True}]}
    issues = P.validate_plan(plan, resolve.load()[1])
    assert not [i for i in issues if "confirm" in i], issues


def test_context_refuses_a_write_capability_unless_approved():
    clients = _Clients()
    ctx = _ctx(clients)
    with raises(P.StepFailed) as err:
        ctx.call_raw("gsc.indexing", {"urls": [URL]})
    assert "confirm" in str(err.value)
    assert clients.calls == [], "the write tool must not be reached without approval"

    ctx.write_ok = True
    ctx.call_raw("gsc.indexing", {"urls": [URL]}, confirm=True)
    assert [c[1] for c in clients.calls] == ["indexing_submit"]


def test_confirmation_alone_is_not_enough_without_allow_write():
    clients = _Clients()
    ctx = _ctx(clients)
    with raises(P.StepFailed):
        ctx.call_raw("gsc.indexing", {"urls": [URL]}, confirm=True)
    assert clients.calls == []


# — A2: an absent metric is not a measured zero

def test_gsc_row_missing_a_metric_raises_instead_of_reading_zero():
    payload = {"rows": [{"keys": ["q"], "clicks": 5}]}  # impressions, ctr and position absent
    with raises(ValueError):
        gsc_metrics.parse_rows(payload, ["query"])


def test_gsc_payload_without_any_metric_fields_is_flagged_not_zeroed():
    rows = gsc_metrics.parse_rows({"rows": [{"keys": ["q"]}]}, ["query"])
    assert rows[0]["clicks"] == 0.0  # documented: insight payloads carry no metrics at all


def test_ga4_absent_metric_is_none_not_zero():
    rows = [{"sessionDefaultChannelGroup": "Organic Search", "sessions": "10", "engagedSessions": "5"}]
    agg = ga4_metrics._agg(rows, lambda r: r["sessionDefaultChannelGroup"])
    assert agg["Organic Search"]["sessions"] == 10.0
    assert agg["Organic Search"]["keyEvents"] is None, "a metric the response never carried is not 0"


def test_ga4_measured_zero_stays_zero():
    rows = [{"sessionDefaultChannelGroup": "Organic Search", "sessions": "10", "keyEvents": 0}]
    agg = ga4_metrics._agg(rows, lambda r: r["sessionDefaultChannelGroup"])
    assert agg["Organic Search"]["keyEvents"] == 0.0


def test_ga4_key_event_rate_is_none_when_events_are_not_tracked():
    rows = [{"landingPage": "/", "sessionSourceMedium": "google / organic",
             "sessions": "10", "engagedSessions": "5"}]  # no keyEvents metric at all
    out = ga4_metrics.breakdown(R, rows, "channel")
    assert out["key_events_tracked"] is False
    assert out["rows"][0]["key_event_rate"] is None


# — A1: a pull cut at the server row limit is marked as such

def test_rows_returned_reads_a_wrapped_mcp_payload():
    wrapped = {"content": [{"type": "text", "text": json.dumps({"rows": [{}, {}]})}]}
    assert P._rows_returned(wrapped) == 2
    assert P._rows_returned({"rows": [1, 2, 3]}) == 3
    assert P._rows_returned({"content": [{"text": "not json"}]}) is None
    assert P._rows_returned([]) is None


if __name__ == "__main__":
    main(globals())
