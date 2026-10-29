# MCP Tool Map (SEO)

Generated from [`capabilities.json`](capabilities.json) by `python3 seo/resolve.py --map`. Do not edit by hand.

## Servers

| Server | Package | Auth | Configured |
|---|---|---|---|
| `search-console` | npx search-console-mcp@2.1.4 | oauth | yes |
| `analytics` | ~/.venvs/analytics-mcp (official GA4) | service-account | yes |
| `google-ads` | googleads/google-ads-mcp | service-account | yes |
| `google-ads-planner` | seo/mcp-servers/google-ads-planner | service-account | yes |
| `dataforseo` | npx dataforseo-mcp-server@3.1.3 | api-key | no (optional) |
| `tavily` | npx tavily-mcp@0.2.3 | api-key | yes |

## Capabilities

| Capability | Call |
|---|---|
| `ads.customers` | `google-ads` → `customers_list_accessible_customers` |
| `ads.metadata` | `google-ads` → `metadata_get_resource_metadata` (supply: resource_name) |
| `ads.search` | `google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings) |
| `adsense.accounts` | `search-console` → `adsense_accounts` {"mode": "configured"} |
| `adsense.report` | `search-console` → `adsense_report` {"dateRange": "LAST_30_DAYS"} (supply: accountId) |
| `dfs.anchors` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/anchors/live"} (supply: data) |
| `dfs.backlinks_summary` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/summary/live"} (supply: data) |
| `dfs.domain_overview` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/domain_rank_overview/live"} (supply: data) |
| `dfs.ranked_keywords` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/ranked_keywords/live"} (supply: data) |
| `dfs.referring_domains` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/referring_domains/live"} (supply: data) |
| `dfs.serp` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/regular"} (supply: data) |
| `ga4.ai_cited_pages` | `analytics` → `run_report` {"dimensions": ["sessionSource", "landingPagePlusQueryString"], "metrics": ["sessions", "conversions"], "dimension_filter": {"filter": {"field_name": "sessionSource", "in_list_filter": {"values": ["chatgpt.com", "chat.openai.com", "perplexity.ai", "gemini.google.com", "claude.ai", "copilot.microsoft.com"], "case_sensitive": false}}}} (supply: property_id, date_ranges) |
| `ga4.conversions_by_source` | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "conversions", "engagementRate"]} (supply: property_id, date_ranges) |
| `ga4.landing_pages` | `analytics` → `run_report` {"dimensions": ["landingPagePlusQueryString"], "metrics": ["sessions", "conversions"]} (supply: property_id, date_ranges) |
| `ga4.page_performance` | `analytics` → `run_report` {"dimensions": ["pagePath"], "metrics": ["sessions", "engagementRate", "averageSessionDuration"]} (supply: property_id, date_ranges) |
| `ga4.properties` | `analytics` → `get_account_summaries` |
| `ga4.referrals` | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions"]} (supply: property_id, date_ranges) |
| `ga4.time_series` | `analytics` → `run_report` {"dimensions": ["date"], "metrics": ["sessions"]} (supply: property_id, date_ranges) |
| `ga4.traffic_sources` | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions"], "dimension_filter": {"filter": {"field_name": "sessionSource", "in_list_filter": {"values": ["chatgpt.com", "chat.openai.com", "perplexity.ai", "gemini.google.com", "claude.ai", "copilot.microsoft.com"], "case_sensitive": false}}}} (supply: property_id, date_ranges) |
| `gsc.analytics_advanced` | `search-console` → `analytics_advanced` (supply: propertyId, metricType) |
| `gsc.anomalies` | `search-console` → `analytics_anomalies` (supply: siteUrl, startDate, endDate) |
| `gsc.brand_split` | `search-console` → `seo_audit` {"type": "brand_vs_nonbrand"} (supply: siteUrl, brandKeywords) |
| `gsc.cannibalization` | `search-console` → `seo_audit` {"type": "cannibalization"} (supply: siteUrl) |
| `gsc.compare_drop` | `search-console` → `analytics_compare` {"mode": "drop_attribution"} (supply: siteUrl, startDate, endDate) |
| `gsc.compare_engines` | `search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate) |
| `gsc.compare_period` | `search-console` → `analytics_compare` {"mode": "period_over_period"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) |
| `gsc.compare_trends` | `search-console` → `analytics_compare` {"mode": "trends"} (supply: siteUrl, startDate, endDate) |
| `gsc.diagnostics` | `search-console` → `diagnostics` |
| `gsc.genai` | `search-console` → `genai_query_insights` (supply: siteUrl) |
| `gsc.health` | `search-console` → `site_health_check` {"level": "crawl_issues"} (supply: siteUrl) |
| `gsc.indexing` | `search-console` → `indexing_submit` (supply: siteUrl, urls) |
| `gsc.inspect` | `search-console` → `inspection_inspect` (supply: siteUrl, urls) |
| `gsc.keywords_related` | `search-console` → `seo_keywords_research` {"type": "related"} (supply: keywords) |
| `gsc.keywords_stats` | `search-console` → `seo_keywords_research` {"type": "stats"} (supply: keywords) |
| `gsc.keywords_traffic` | `search-console` → `seo_keywords_research` {"type": "traffic"} (supply: keywords) |
| `gsc.lost_queries` | `search-console` → `seo_audit` {"type": "lost_queries"} (supply: siteUrl) |
| `gsc.low_ctr` | `search-console` → `seo_audit` {"type": "low_ctr"} (supply: siteUrl) |
| `gsc.low_hanging_fruit` | `search-console` → `seo_audit` {"type": "low_hanging_fruit"} (supply: siteUrl) |
| `gsc.pagespeed` | `search-console` → `pagespeed_analyze` (supply: url, strategy) |
| `gsc.query` | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) |
| `gsc.quick_wins` | `search-console` → `seo_audit` {"type": "quick_wins"} (supply: siteUrl) |
| `gsc.recommendations` | `search-console` → `seo_audit` {"type": "recommendations"} (supply: siteUrl) |
| `gsc.schema` | `search-console` → `schema_validate` (supply: url) |
| `gsc.sitemaps` | `search-console` → `sitemaps_list` (supply: siteUrl) |
| `gsc.sites_list` | `search-console` → `sites_list` |
| `gsc.striking_distance` | `search-console` → `seo_audit` {"type": "striking_distance"} (supply: siteUrl) |
| `planner.ideas` | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) |
