# Data Source Map & Degradation Ladder

## Sources
| Capability group | Server | Freshness / lag | Notes |
|---|---|---|---|
| `gsc.*` | `search-console` | GSC lags ~2 days | exclude today; absolute dates |
| `ga4.*` | `analytics` | near-real-time (realtime tool) | sampling may apply |
| `ads.*` | `google-ads` | same-day | cost in micros ÷ 1,000,000 |
| `planner.*` | `google-ads-planner` | weekly-ish volumes | ~1 QPS per CID; 429-prone |
| `dfs.*` | `dataforseo` | live | optional, not configured |

## Degradation ladder (apply in order)
1. `dataforseo` absent → skip SERP/backlink/competitor enrichments; state it.
2. `analytics` absent → GSC-only; state that revenue/engagement is unavailable.
3. `google-ads` absent → organic-only; state the paid side is unavailable.
4. `planner` 429/timeout → fall back to `search-console` → `seo_keywords_research` and label volumes as estimates.

## Rules
- Never fabricate a missing source's data ([`conciseness-directives.md`](conciseness-directives.md)).
- Retries must stay within `policy.timeout_budget_s` ([`capability-usage.md`](capability-usage.md)).
