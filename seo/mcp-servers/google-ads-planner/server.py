"""MCP server exposing Keyword Planner via KeywordPlanIdeaService.

Reuses ads_mcp.utils for auth (ADC via GOOGLE_APPLICATION_CREDENTIALS).
Run with the google-ads-mcp venv python. Stdio transport.
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

MAX_SEEDS = 100
MAX_GEOS = 100
MAX_PAGE_SIZE = 1000
# Total retry budget (s). Kept below the MCP client's 60s request timeout so the
# server returns the real error instead of the client timing out first.
MAX_RETRY_SECONDS = float(os.environ.get("PLANNER_MAX_RETRY_SECONDS", "40"))


def _money(micros: Any) -> float:
    """Micros -> account-currency units, tolerant of missing values."""
    return round((micros or 0) / 1_000_000, 2)


def _idea_to_dict(idea: Any) -> dict:
    m = idea.keyword_idea_metrics
    out = {
        "keyword": idea.text,
        "avg_monthly_searches": m.avg_monthly_searches,
        "competition": getattr(m.competition, "name", str(m.competition)),
        "competition_index": m.competition_index,
        "low_top_of_page_bid": _money(m.low_top_of_page_bid_micros),
        "high_top_of_page_bid": _money(m.high_top_of_page_bid_micros),
    }
    trend = []
    for v in m.monthly_search_volumes:
        raw_m = int(v.month)
        month_no = max(1, min(12, raw_m - 1)) if raw_m >= 2 else 1  # Month enum: JANUARY=2
        trend.append({"month": f"{v.year}-{month_no:02d}", "searches": v.monthly_searches})
    out["monthly_trend"] = sorted(trend, key=lambda t: t["month"])
    return out


@mcp.tool
def generate_keyword_ideas(
    customer_id: str,
    keywords: list[str] | None = None,
    page_url: str | None = None,
    language: str | None = None,
    geo_targets: list[str] | None = None,
    page_size: int = 25,
) -> list[dict]:
    """Google Ads Keyword Planner: real volume, competition, top-of-page bids and 12-month trend.

    Provide `keywords` (seed terms) and/or `page_url` (URL seed) — at least one is required.
    `language` is a resource name like "languageConstants/1000" (English); omit for all languages.
    `geo_targets` are resource names like "geoTargetConstants/2840" (US); omit for all locations.
    Bids are returned in account currency (converted from micros).
    """
    if not keywords and not page_url:
        raise ValueError("Provide at least one of `keywords` or `page_url`.")
    if keywords and len(keywords) > MAX_SEEDS:
        raise ValueError(f"Too many keywords ({len(keywords)}); max {MAX_SEEDS}.")
    if geo_targets and len(geo_targets) > MAX_GEOS:
        raise ValueError(f"Too many geo_targets ({len(geo_targets)}); max {MAX_GEOS}.")
    page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))

    cid = clean_customer_id(customer_id)
    service = get_googleads_service("KeywordPlanIdeaService")
    request = get_googleads_type("GenerateKeywordIdeasRequest")
    request.customer_id = cid
    if keywords:
        request.keyword_seed.keywords.extend(dedupe(keywords))
    if page_url:
        request.url_seed.url = page_url
    if language:
        request.language = language
    if geo_targets:
        request.geo_target_constants.extend(geo_targets)
    request.page_size = page_size

    # GenerateKeywordIdeas has a strict per-method quota; honor the API's retry hint.
    started = time.monotonic()
    for attempt in range(4):
        _gate.wait(cid)  # KeywordPlanIdeaService: ~1 QPS per customer ID
        try:
            response = service.generate_keyword_ideas(request=request)
            return [_idea_to_dict(idea) for idea in response]
        except ResourceExhausted as e:
            if attempt == 3:
                logger.warning("KeywordPlanIdeaService exhausted after 4 attempts")
                raise
            m = re.search(r"Retry in (\d+) seconds", str(e))
            hint = int(m.group(1)) + 5 if m else None
            delay = backoff_delay(attempt, hint)
            if time.monotonic() - started + delay > MAX_RETRY_SECONDS:
                logger.warning(
                    "KeywordPlanIdeaService quota exhausted; giving up within %ss budget "
                    "(next retry would wait %ss). Retry later or raise PLANNER_MAX_RETRY_SECONDS.",
                    MAX_RETRY_SECONDS, delay,
                )
                raise
            logger.info("KeywordPlanIdeaService quota hit (attempt %d/4); retrying in %ds", attempt + 1, delay)
            time.sleep(delay)


if __name__ == "__main__":
    mcp.run()
