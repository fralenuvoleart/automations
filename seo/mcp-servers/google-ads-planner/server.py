"""MCP server exposing Keyword Planner via KeywordPlanIdeaService.

Reuses ads_mcp.utils for auth (ADC via GOOGLE_APPLICATION_CREDENTIALS).
Run with the google-ads-mcp venv python. Stdio transport.

API limits honoured (Google Ads API reference): KeywordSeed ≤ 20 keywords,
geo_target_constants ≤ 10, ~1 QPS per customer ID. Retries live only here
(the registry policy sets retry 0), within a budget below the client timeout.
"""

import logging
import os
import re
import time
from typing import Any

from google.api_core.exceptions import ResourceExhausted

from fastmcp import FastMCP

from ads_mcp.utils import clean_customer_id, get_googleads_service, get_googleads_type

try:
    from planner_limits import RateGate, backoff_delay, dedupe
except ImportError:  # script dir not on sys.path
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from planner_limits import RateGate, backoff_delay, dedupe

logger = logging.getLogger("google-ads-planner")

mcp = FastMCP("google-ads-planner")

_gate = RateGate()

MAX_SEEDS = 20            # KeywordSeed: "no more than 20 keywords"
MAX_GEOS = 10             # geo_target_constants: "Maximum is 10"
MAX_PAGE_SIZE = 1000      # we return a single page only (see _first_page)
MAX_HIST_KEYWORDS = 1000  # API allows 10,000; capped to keep responses LLM-sized
# Total retry budget (s), including the expected duration of the next call. Kept
# below the MCP client's 60s request timeout so the server returns the real error.
MAX_RETRY_SECONDS = float(os.environ.get("PLANNER_MAX_RETRY_SECONDS", "40"))


def _money(micros: Any) -> float:
    """Micros -> account-currency units, tolerant of missing values."""
    return round((micros or 0) / 1_000_000, 2)


def _trend(metrics: Any) -> list[dict]:
    trend = []
    for v in getattr(metrics, "monthly_search_volumes", None) or []:
        raw_m = int(v.month)
        if raw_m < 2:  # MonthOfYear UNSPECIFIED=0 / UNKNOWN=1: no calendar month — skip, never guess
            continue
        trend.append({"month": f"{v.year}-{raw_m - 1:02d}", "searches": v.monthly_searches})  # JANUARY=2
    return sorted(trend, key=lambda t: t["month"])


def _metrics_dict(text: str, m: Any) -> dict:
    return {
        "keyword": text,
        "avg_monthly_searches": m.avg_monthly_searches,
        "competition": getattr(m.competition, "name", str(m.competition)),
        "competition_index": m.competition_index,
        "low_top_of_page_bid": _money(m.low_top_of_page_bid_micros),
        "high_top_of_page_bid": _money(m.high_top_of_page_bid_micros),
        "monthly_trend": _trend(m),
    }


def _idea_to_dict(idea: Any) -> dict:
    return _metrics_dict(idea.text, idea.keyword_idea_metrics)


def _first_page(response: Any) -> list:
    """Results of the first page only. Iterating a GAPIC pager would follow
    next_page_token and fire extra, un-gated API calls."""
    results = getattr(response, "results", None)
    return list(results) if results is not None else list(response)


def _validate_targeting(language: str | None, geo_targets: list[str] | None) -> None:
    if geo_targets and len(geo_targets) > MAX_GEOS:
        raise ValueError(f"Too many geo_targets ({len(geo_targets)}); the API allows at most {MAX_GEOS}.")
    for g in geo_targets or []:
        if not re.fullmatch(r"geoTargetConstants/\d+", g):
            raise ValueError(f"geo target {g!r} must look like 'geoTargetConstants/2840'.")
    if language and not re.fullmatch(r"languageConstants/\d+", language):
        raise ValueError(f"language {language!r} must look like 'languageConstants/1000'.")


def _call_with_retry(cid: str, fn):
    """Rate-gated call with bounded exponential backoff on RESOURCE_EXHAUSTED."""
    started = time.monotonic()
    last_call_s = 0.0
    for attempt in range(4):
        _gate.wait(cid)  # KeywordPlanIdeaService: ~1 QPS per customer ID
        t0 = time.monotonic()
        try:
            return fn()
        except ResourceExhausted as e:
            last_call_s = max(0.0, time.monotonic() - t0)
            if attempt == 3:
                logger.warning("KeywordPlanIdeaService exhausted after 4 attempts")
                raise
            m = re.search(r"Retry in (\d+) seconds", str(e))
            hint = int(m.group(1)) + 5 if m else None
            delay = backoff_delay(attempt, hint)
            if time.monotonic() - started + delay + last_call_s > MAX_RETRY_SECONDS:
                logger.warning(
                    "KeywordPlanIdeaService quota exhausted; giving up within %ss budget "
                    "(next retry would wait %ss + ~%.1fs call). Retry later.", MAX_RETRY_SECONDS, delay, last_call_s)
                raise
            logger.info("KeywordPlanIdeaService quota hit (attempt %d/4); retrying in %ds", attempt + 1, delay)
            time.sleep(delay)


@mcp.tool
def generate_keyword_ideas(
    customer_id: str,
    keywords: list[str] | None = None,
    page_url: str | None = None,
    language: str | None = None,
    geo_targets: list[str] | None = None,
    page_size: int = 25,
) -> list[dict]:
    """Google Ads Keyword Planner ideas: volume, competition, top-of-page bids and 12-month trend.

    Provide `keywords` (≤20 seed terms — batch larger sets) and/or `page_url`.
    `language` is a resource name like "languageConstants/1000" (English); omit for all languages.
    `geo_targets` (≤10) are resource names like "geoTargetConstants/2840" (US); omit for all locations.
    Returns the first page only (≤ page_size ideas). Bids are in account currency.
    """
    if not keywords and not page_url:
        raise ValueError("Provide at least one of `keywords` or `page_url`.")
    seeds = dedupe(keywords or [])
    if len(seeds) > MAX_SEEDS:
        raise ValueError(f"Too many keywords ({len(seeds)}); the API allows at most {MAX_SEEDS} seeds — batch them.")
    _validate_targeting(language, geo_targets)
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))

    cid = clean_customer_id(customer_id)
    service = get_googleads_service("KeywordPlanIdeaService")
    request = get_googleads_type("GenerateKeywordIdeasRequest")
    request.customer_id = cid
    if seeds:
        request.keyword_seed.keywords.extend(seeds)
    if page_url:
        request.url_seed.url = page_url
    if language:
        request.language = language
    if geo_targets:
        request.geo_target_constants.extend(geo_targets)
    request.page_size = page_size

    response = _call_with_retry(cid, lambda: service.generate_keyword_ideas(request=request))
    return [_idea_to_dict(idea) for idea in _first_page(response)[:page_size]]


@mcp.tool
def keyword_historical_metrics(
    customer_id: str,
    keywords: list[str],
    language: str | None = None,
    geo_targets: list[str] | None = None,
) -> list[dict]:
    """Keyword Planner metrics for an exact keyword list (no idea expansion).

    Use this to size known keywords (e.g. striking-distance queries). ≤1,000 keywords per call;
    near-duplicates ("car"/"cars") may be merged by the API. Same `language`/`geo_targets`
    format as generate_keyword_ideas. Bids are in account currency.
    """
    kws = dedupe(keywords or [])
    if not kws:
        raise ValueError("Provide at least one keyword.")
    if len(kws) > MAX_HIST_KEYWORDS:
        raise ValueError(f"Too many keywords ({len(kws)}); max {MAX_HIST_KEYWORDS} per call — batch them.")
    _validate_targeting(language, geo_targets)

    cid = clean_customer_id(customer_id)
    service = get_googleads_service("KeywordPlanIdeaService")
    request = get_googleads_type("GenerateKeywordHistoricalMetricsRequest")
    request.customer_id = cid
    request.keywords.extend(kws)
    if language:
        request.language = language
    if geo_targets:
        request.geo_target_constants.extend(geo_targets)

    response = _call_with_retry(cid, lambda: service.generate_keyword_historical_metrics(request=request))
    return [_metrics_dict(r.text, r.keyword_metrics) for r in getattr(response, "results", [])]


if __name__ == "__main__":
    mcp.run()
