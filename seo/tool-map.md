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

| Capability | Call | Purpose |
|---|---|---|
| `ads.customers` | `google-ads` → `customers_list_accessible_customers` | Accessible Ads customer IDs |
| `ads.metadata` | `google-ads` → `metadata_get_resource_metadata` (supply: resource_name, login_customer_id) | GAQL field discovery (verify fields before querying) |
| `ads.search` | `google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings, login_customer_id) | GAQL query (search terms, account currency) |
| `dfs.anchors` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/anchors/live"} (supply: data) | Anchor-text distribution (index estimate) |
| `dfs.backlinks_new_lost` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/timeseries_new_lost_summary/live"} (supply: data) | New/lost backlinks and referring domains over time (link velocity) |
| `dfs.backlinks_summary` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/summary/live"} (supply: data) | Backlink profile summary (index estimate) |
| `dfs.ranked_keywords` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/ranked_keywords/live"} (supply: data) | Keywords a domain ranks for (estimate) |
| `dfs.referring_domains` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/referring_domains/live"} (supply: data) | Referring domains (index estimate) |
| `dfs.serp` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/advanced"} (supply: data) | Live Google SERP incl. SERP features (featured snippet, PAA, AI Overview) |
| `ga4.ai_cited_pages` | `analytics` → `run_report` {"dimensions": ["sessionSource", "landingPagePlusQueryString"], "metrics": ["sessions", "keyEvents"]} (supply: property_id, date_ranges, dimension_filter) | Landing pages AI assistants send visitors to (same AI filter) |
| `ga4.ai_sources` | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges, dimension_filter) | AI-assistant referral sessions (filter from `site_profile.py --ga4-ai-filter`) |
| `ga4.ai_time_series` | `analytics` → `run_report` {"dimensions": ["date", "sessionSource"], "metrics": ["sessions"]} (supply: property_id, date_ranges, dimension_filter) | Daily AI-assistant referral sessions (same AI filter) |
| `ga4.channels` | `analytics` → `run_report` {"dimensions": ["sessionDefaultChannelGroup", "sessionSource", "sessionMedium"], "metrics": ["sessions", "keyEvents", "engagementRate"]} (supply: property_id, date_ranges) | Sessions/key events by channel and source (organic baseline) |
| `ga4.organic_landing_pages` | `analytics` → `run_report` {"dimensions": ["landingPagePlusQueryString"], "metrics": ["sessions", "engagementRate", "keyEvents"], "dimension_filter": {"filter": {"field_name": "sessionDefaultChannelGroup", "string_filter": {"match_type": "EXACT", "value": "Organic Search", "case_sensitive": false}}}} (supply: property_id, date_ranges) | Organic-search landing pages: sessions, engagement, key events |
| `ga4.properties` | `analytics` → `get_account_summaries` | GA4 accounts/properties (connection check) |
| `ga4.referrals` | `analytics` → `run_report` {"dimensions": ["sessionSource"], "metrics": ["sessions", "keyEvents"], "dimension_filter": {"filter": {"field_name": "sessionMedium", "string_filter": {"match_type": "EXACT", "value": "referral", "case_sensitive": false}}}} (supply: property_id, date_ranges) | Referral sessions by source domain |
| `gsc.analytics_advanced` | `search-console` → `analytics_advanced` (supply: propertyId, metricType, startDate, endDate) | Aggregate GA4 metrics via search-console (no source breakdown) |
| `gsc.anomalies` | `search-console` → `analytics_anomalies` {"engine": "google"} (supply: siteUrl, startDate, endDate) | Day-level anomaly detection |
| `gsc.compare_drop` | `search-console` → `analytics_compare` {"mode": "drop_attribution", "engine": "google"} (supply: siteUrl, startDate, endDate) | Drop attribution (which segments drove a decline) |
| `gsc.compare_engines` | `search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate) | Google vs Bing divergence (only when Bing is connected) |
| `gsc.compare_period` | `search-console` → `analytics_compare` {"mode": "period_over_period", "engine": "google"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) | Aggregate period-over-period delta |
| `gsc.compare_trends` | `search-console` → `analytics_compare` {"mode": "trends", "engine": "google"} (supply: siteUrl, startDate, endDate) | Gradual trend detection |
| `gsc.daily_totals` | `search-console` → `analytics_query` {"dimensions": ["date"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Daily site totals, including anonymized queries (reconciliation baseline) |
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.genai` | `search-console` → `genai_query_insights` {"engine": "google", "includePages": true} (supply: siteUrl, days) | AI-prompt-shaped GSC queries (heuristic; `days` = window length) |
| `gsc.geo_query` | `search-console` → `analytics_query` {"dimensions": ["country", "query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query by country (align organic with ad geo-targeting) |
| `gsc.health` | `search-console` → `site_health_check` {"level": "crawl_issues", "engine": "google"} (supply: siteUrl) | Crawl/robots/sitemap blockers (report only the fields returned; not a site-wide index count) |
| `gsc.indexing` | `search-console` → `indexing_submit` {"method": "standard", "engine": "google"} (supply: siteUrl, urls) | Indexing API submission — only after explicit user confirmation |
| `gsc.inspect` | `search-console` → `inspection_inspect` {"engine": "google"} (supply: siteUrl, urls) | URL Inspection: coverage state, canonicals, last crawl (quota 2,000/day/property) |
| `gsc.keywords_related` | `search-console` → `seo_keywords_research` {"type": "related", "engine": "google"} (supply: keywords, language, country) | Related keyword expansion (volumes are estimates) |
| `gsc.keywords_stats` | `search-console` → `seo_keywords_research` {"type": "stats", "engine": "google"} (supply: keywords, language, country) | Keyword volume estimates (planner fallback; label as estimates) |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.page_query` | `search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query × page attribution (anonymized queries excluded) |
| `gsc.pagespeed` | `search-console` → `pagespeed_analyze` (supply: url, strategy) | PageSpeed: CrUX field data (when available) + Lighthouse lab data |
| `gsc.pagespeed_a11y` | `search-console` → `pagespeed_analyze` {"category": ["accessibility"]} (supply: url, strategy) | Lighthouse accessibility category |
| `gsc.query` | `search-console` → `analytics_query` {"dimensions": ["query"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query-level clicks/impressions/CTR/position (anonymized queries excluded) |
| `gsc.schema` | `search-console` → `schema_validate` (supply: url) | Structured-data validation |
| `gsc.sitemaps` | `search-console` → `sitemaps_list` {"engine": "google"} (supply: siteUrl) | Submitted sitemaps, last read, errors/warnings (the API no longer reports indexed counts) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `planner.historical` | `google-ads-planner` → `keyword_historical_metrics` (supply: customer_id, keywords, language, geo_targets) | Keyword Planner metrics for an exact keyword list (≤1,000 per call) |
| `planner.ideas` | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords, language, geo_targets) | Keyword Planner ideas: volume, competition, bids (≤20 seeds per call; server retries internally) |
| `web.extract` | `tavily` → `tavily-extract` {"extract_depth": "basic"} (supply: urls) | Extract page content when `site_crawl.py facts` cannot fetch a page (JS-rendered/blocked) |
| `web.search` | `tavily` → `tavily-search` {"search_depth": "basic", "max_results": 10} (supply: query) | Web search fallback — not Google's ranking order; label as approximate |
