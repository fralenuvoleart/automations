"""Integration test of seo/mcp-servers/google-ads-planner/server.py — offline.

Loads the *real* server module with stubbed Google/FastMCP deps and a fake
KeywordPlanIdeaService, then drives the actual retry loop, rate gate, backoff,
de-dup and validation. Makes NO network/API calls.

Run:  python3 seo/tests/test_planner_server.py   (or: python3 -m pytest seo/tests -q)
"""
import importlib.util
import sys
import time
import types
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1] / "mcp-servers" / "google-ads-planner"
SERVER_PY = SERVER_DIR / "server.py"


# ---- stub the external deps the server imports --------------------------------
class _StubMCP:
    def __init__(self, *a, **k):
        pass

    def tool(self, fn=None):
        if fn is None:
            return lambda f: f
        return fn

    def run(self):
        pass


class ResourceExhausted(Exception):
    pass


def _install_stubs():
    fastmcp = types.ModuleType("fastmcp")
    fastmcp.FastMCP = _StubMCP
    sys.modules["fastmcp"] = fastmcp

    google = types.ModuleType("google")
    api_core = types.ModuleType("google.api_core")
    exceptions = types.ModuleType("google.api_core.exceptions")
    exceptions.ResourceExhausted = ResourceExhausted
    api_core.exceptions = exceptions
    google.api_core = api_core
    sys.modules.update({
        "google": google,
        "google.api_core": api_core,
        "google.api_core.exceptions": exceptions,
    })

    ads_mcp = types.ModuleType("ads_mcp")
    utils = types.ModuleType("ads_mcp.utils")
    STATE: dict = {"service": None}
    utils.clean_customer_id = lambda x: x
    utils.get_googleads_service = lambda name: STATE["service"]
    utils.get_googleads_type = lambda name: FakeRequest()
    ads_mcp.utils = utils
    sys.modules.update({"ads_mcp": ads_mcp, "ads_mcp.utils": utils})
    return utils, STATE


# ---- fakes --------------------------------------------------------------------
class _NS:
    def __init__(self, **k):
        self.__dict__.update(k)


class FakeRequest:
    def __init__(self):
        self.customer_id = None
        self.keyword_seed = _NS(keywords=[])
        self.url_seed = _NS(url=None)
        self.language = None
        self.geo_target_constants = []
        self.page_size = None


class _Competition:
    name = "MEDIUM"


class _Vol:
    def __init__(self, month, year, searches):
        self.month = month          # Google Ads MonthOfYear enum: JANUARY=2, FEBRUARY=3
        self.year = year
        self.monthly_searches = searches


class FakeIdea:
    def __init__(self):
        self.text = "kw"
        self.keyword_idea_metrics = _NS(
            avg_monthly_searches=1000,
            competition=_Competition(),
            competition_index=50,
            low_top_of_page_bid_micros=1_500_000,
            high_top_of_page_bid_micros=3_000_000,
            monthly_search_volumes=[_Vol(3, 2026, 10), _Vol(2, 2026, 20)],
        )


class FakeService:
    def __init__(self, fail_times=0):
        self.fail_times = fail_times
        self.calls = 0
        self.last_request = None

    def generate_keyword_ideas(self, request=None):
        self.calls += 1
        self.last_request = request
        if self.calls <= self.fail_times:
            raise ResourceExhausted("RESOURCE_EXHAUSTED")  # no 'Retry in' hint
        return [FakeIdea()]


class FakeGate:
    def __init__(self):
        self.calls = []

    def wait(self, key):
        self.calls.append(key)
        return 0.0


# ---- load the real server module ---------------------------------------------
utils, STATE = _install_stubs()
spec = importlib.util.spec_from_file_location("planner_server", SERVER_PY)
server = importlib.util.module_from_spec(spec)
sys.modules["planner_server"] = server
spec.loader.exec_module(server)


def _setup(fail_times=0):
    """Wire a fresh fake service + gate + sleep recorder; return (service, sleeps, gate)."""
    service = FakeService(fail_times=fail_times)
    STATE["service"] = service
    sleeps = []
    gate = FakeGate()
    server._gate = gate
    server.time = types.SimpleNamespace(sleep=lambda s: sleeps.append(s), monotonic=lambda: 0.0)
    return service, sleeps, gate


# ---- tests --------------------------------------------------------------------
def test_success_first_try():
    service, sleeps, gate = _setup(0)
    out = server.generate_keyword_ideas(customer_id="123", keywords=["a", "a", "b"])
    assert len(out) == 1
    assert service.calls == 1
    assert sleeps == []
    assert gate.calls == ["123"]
    assert service.last_request.keyword_seed.keywords == ["a", "b"]  # de-duped


def test_retries_then_succeeds_with_backoff():
    service, sleeps, gate = _setup(2)
    out = server.generate_keyword_ideas(customer_id="123", keywords=["a"])
    assert len(out) == 1
    assert service.calls == 3
    assert sleeps == [2, 4]            # no server hint -> exponential base 2
    assert gate.calls == ["123", "123", "123"]  # gate runs before every attempt


def test_persistent_exhaustion_raises_after_four():
    service, sleeps, _ = _setup(99)
    try:
        server.generate_keyword_ideas(customer_id="123", keywords=["a"])
        raise AssertionError("expected ResourceExhausted")
    except ResourceExhausted:
        pass
    assert service.calls == 4
    assert sleeps == [2, 4, 8]


def test_honours_server_retry_hint():
    service, sleeps, _ = _setup(1)

    class Hinted(FakeService):
        def generate_keyword_ideas(self, request=None):
            self.calls += 1
            self.last_request = request
            if self.calls == 1:
                raise ResourceExhausted("Quota exceeded. Retry in 30 seconds")
            return [FakeIdea()]

    STATE["service"] = Hinted()
    server.generate_keyword_ideas(customer_id="123", keywords=["a"])
    assert sleeps == [35]              # max(hint 30+5, exp 2)


def test_requires_a_seed():
    _setup(0)
    for kw, url in ((None, None), ([], "")):
        try:
            server.generate_keyword_ideas(customer_id="1", keywords=kw, page_url=url)
            raise AssertionError("expected ValueError")
        except ValueError:
            pass


def test_rejects_too_many_seeds():
    _setup(0)
    try:
        server.generate_keyword_ideas(customer_id="1", keywords=[f"k{i}" for i in range(21)])
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "20" in str(e)
    server.generate_keyword_ideas(customer_id="1", keywords=[f"k{i}" for i in range(20)])  # API max is fine


def test_rejects_bad_geo_targets_and_language():
    _setup(0)
    for kwargs in ({"geo_targets": [f"geoTargetConstants/{i}" for i in range(11)]},
                   {"geo_targets": ["2840"]}, {"language": "ru"}):
        try:
            server.generate_keyword_ideas(customer_id="1", keywords=["a"], **kwargs)
            raise AssertionError(f"expected ValueError for {kwargs}")
        except ValueError:
            pass


class _Pager:
    """GAPIC-like pager: `.results` is page 1; iterating would fetch more pages."""
    def __init__(self, items):
        self.results = items

    def __iter__(self):
        raise AssertionError("iterating the pager fetches extra pages (un-gated API calls)")


def test_reads_first_page_only():
    service, _, gate = _setup(0)

    class PagedService(FakeService):
        def generate_keyword_ideas(self, request=None):
            self.calls += 1
            return _Pager([FakeIdea(), FakeIdea()])

    STATE["service"] = PagedService()
    out = server.generate_keyword_ideas(customer_id="1", keywords=["a"], page_size=1)
    assert len(out) == 1 and gate.calls == ["1"]


def test_unknown_month_is_skipped_not_mapped_to_january():
    _setup(0)
    idea = FakeIdea()
    idea.keyword_idea_metrics.monthly_search_volumes = [_Vol(1, 2026, 99), _Vol(2, 2026, 20)]  # UNKNOWN, JANUARY
    assert server._idea_to_dict(idea)["monthly_trend"] == [{"month": "2026-01", "searches": 20}]


def test_historical_metrics_tool():
    _setup(0)

    class Hist(FakeService):
        def generate_keyword_historical_metrics(self, request=None):
            self.calls += 1
            self.last_request = request
            return _NS(results=[_NS(text="kw", keyword_metrics=FakeIdea().keyword_idea_metrics)])

    hist = Hist()
    STATE["service"] = hist
    orig = server.get_googleads_type
    server.get_googleads_type = lambda name: _NS(customer_id=None, keywords=[], language=None, geo_target_constants=[])
    try:
        out = server.keyword_historical_metrics(customer_id="1", keywords=["kw", "kw"], language="languageConstants/1031")
    finally:
        server.get_googleads_type = orig
    assert out[0]["keyword"] == "kw" and out[0]["avg_monthly_searches"] == 1000
    assert hist.last_request.keywords == ["kw"] and hist.last_request.language == "languageConstants/1031"


def test_page_size_is_clamped():
    service, _, _ = _setup(0)
    server.generate_keyword_ideas(customer_id="1", keywords=["a"], page_size=99999)
    assert service.last_request.page_size == server.MAX_PAGE_SIZE
    server.generate_keyword_ideas(customer_id="1", keywords=["a"], page_size=0)
    assert service.last_request.page_size == 1


def test_idea_mapping_and_month_enum():
    _setup(0)
    out = server.generate_keyword_ideas(customer_id="1", keywords=["a"])
    idea = out[0]
    assert idea["keyword"] == "kw"
    assert idea["competition"] == "MEDIUM"
    assert idea["low_top_of_page_bid"] == 1.5
    assert idea["high_top_of_page_bid"] == 3.0
    # month enum 2 -> JANUARY (2026-01), 3 -> FEBRUARY (2026-02); sorted ascending
    assert idea["monthly_trend"] == [
        {"month": "2026-01", "searches": 20},
        {"month": "2026-02", "searches": 10},
    ]


def test_budget_bails_before_exceeding_client_timeout():
    """A long retry must not outlive the MCP client's 60s window."""
    service, sleeps, _ = _setup(99)
    old = server.MAX_RETRY_SECONDS
    server.MAX_RETRY_SECONDS = 1.0
    try:
        try:
            server.generate_keyword_ideas(customer_id="123", keywords=["a"])
            raise AssertionError("expected ResourceExhausted")
        except ResourceExhausted:
            pass
    finally:
        server.MAX_RETRY_SECONDS = old
    assert service.calls == 1        # bailed on the first throttled attempt
    assert sleeps == []              # did not sleep past the budget


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
