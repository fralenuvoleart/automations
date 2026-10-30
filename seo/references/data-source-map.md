# Data Source Map & Degradation Rule

## Sources
| Capability group | Server | Freshness / lag | Notes |
|---|---|---|---|
| `gsc.*` | `search-console` | final data 2–3 days late → windows end `today − 3` | `engine: google`, `rowLimit: 25000` pinned |
| `ga4.*` | `analytics` | processed data within ~1–2 days → `today − 2`; `run_report` is not real-time | sampling can apply on large ranges; metric `keyEvents` (not `conversions`) |
| `ads.*` | `google-ads` | same-day | cost in micros ÷ 1,000,000, account currency |
| `planner.*` | `google-ads-planner` | monthly volumes | ~1 QPS per customer ID; ≤20 seeds / ≤10 geos per call |
| `dfs.*` | `dataforseo` | live | optional, not configured; estimates |
| `web.*` | `tavily` | live | third party; not Google's ranking |
| `seo/site_crawl.py` | local (stdlib) | live HTML | public pages only; robots.txt-level checks |

## The rule (one rule, every skill)
1. **Required source missing** → stop before any analysis and name the missing connection.
2. **Optional source missing or failing** → continue; add one `findings.unavailable` entry
   (`source`, `affects`, `reason`) and skip only what depended on it.
3. **Never substitute** an estimate for the site's own data, and never fill a gap from memory.
4. Retries happen once, in one layer (`policy` in the registry; the planner server retries internally).

| Skill | Required | Optional (degrade per rule 2) |
|---|---|---|
| `seo-audit` | `search-console` | `analytics` (engagement/AI cross-check), `dataforseo` |
| `seo-ai-visibility` | `search-console` | `analytics` (headline AI referrals; without it the report is heuristic-only) |
| `seo-backlink-check` | `analytics` | `dataforseo` (the backlink profile itself) |
| `seo-brand-split` | `search-console`, site rules (Brand, page languages) | — |
| `seo-content-brief` | `search-console` | `dataforseo` (SERP), `tavily` (web-search fallback), `google-ads-planner` |
| `seo-content-refresh` | `search-console` | `analytics` (key events), `dataforseo` (backlinks) |
| `seo-indexation` | `search-console` | — (`site_crawl.py` is local) |
| `seo-internal-links` | `search-console` | — (`site_crawl.py` is local) |
| `seo-keyword-strategy` | `search-console` | `google-ads-planner` (+ profile `ads_customer_id`), `dataforseo` |
| `seo-paid-organic` | `search-console` | `google-ads` (the paid half) |
| `seo-rank-tracking` | `search-console` | `dataforseo` (SERP spot-check), Bing in `search-console` |
| `seo-technical` | `search-console` | — (`site_crawl.py` is local) |

Policy details: [`capability-usage.md`](capability-usage.md). Never-fabricate rules:
[`conciseness-directives.md`](conciseness-directives.md).
