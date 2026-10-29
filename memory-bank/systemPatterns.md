# System Patterns


## 🛠️ Developer Working Method
- **Standard:** Modular, elegant, SEO-performant.
- **Verification:** Trace every claim through the full call chain before asserting a pattern is followed or a regression is avoided — use `search_files`/grep, never assume from a function name or comment alone.
- **Zero Regression Policy:** Check this file before every file write to ensure changes don't violate an established architectural invariant above.

---

## 🌐 Sevalla API Rules (Hard-Learned)

### Exec endpoint (`POST /v3/applications/{id}/processes/{pid}/exec`)

| Rule | Detail |
|---|---|
| **Always check OpenAPI spec first** | `curl -s https://api.sevalla.com/v3/openapi.json` — search for the endpoint path. Never guess the schema. |
| `command` is an **array of strings** | `["npm","run","warmer"]` not `"npm run warmer"` |
| `timeout` is **1–60 seconds** (integer) | Default 15. Sending 300 returns 400. Max is 60. |
| **No shell features** | No pipes, redirects, `&`, `nohup`, globbing. Use `sh -c "..."` as workaround. |
| **Long-running commands need backgrounding** | Use `["sh","-c","nohup <cmd> &"]` with `timeout:5`. Otherwise command gets killed at timeout. |
| **Short commands** (`ls`, `npm run logs`, `echo`) | Fine to run directly with default timeout. |
| Response format | `{"stdout":"...","stderr":"...","exit_code":0}` — not `"output"` or `"error"` |

### Deployment & Process behavior

| Rule | Detail |
|---|---|
| **Bot 409 conflict on deploy** | Old pod + new pod both poll Telegram. Fix: retry `bot.launch()` on 409 with delay. |
| **`bot.launch()` is a Promise** | Must be `await`ed or `.catch()`ed. Unhandled rejection crashes process in Node.js v24. |
| **Warmer & bot share process** | Cron warmer dies if bot crashes. Manual `npm run warmer` spawns separate process. |
| **Exec into crashed pod fails** | If the main process crashes, there's nothing to exec into. Exec requires a running container. |

---

## 🔎 SEO Skills — MCP servers

The 8 SEO/GEO skills in `.agents/skills/` run on a **multi-server** MCP stack (not Ryze). All non-skill SEO files live in [`seo/`](../seo/): the registry [`seo/capabilities.json`](../seo/capabilities.json) (capability → server + tool + structured `args` + `runtime`), the resolver [`seo/resolve.py`](../seo/resolve.py), the live-schema client [`seo/mcp_client.py`](../seo/mcp_client.py), the readable map [`seo/tool-map.md`](../seo/tool-map.md), and local servers under [`seo/mcp-servers/`](../seo/mcp-servers/). Skills reference capabilities as `{{cap:<id>}}` tokens; the resolver expands them to `` `server` → `tool` {args} (supply: runtime) `` so execution is deterministic even when several capabilities share one tool (`run_report`, `api_request`, `analytics_compare`). **To swap a server: edit `capabilities.json` → `python3 seo/resolve.py --write`** — never hand-edit tool names in skills. Validate with `--check` (tokens/aliases) and `--validate-live` (spawns each server, checks tool + args against the live `inputSchema`).

| Concern | Server | Tools |
|---|---|---|
| GSC (queries, compare, anomalies, indexation, inspection, sitemaps, keyword stats, SEO intelligence, AI-query heuristic, PageSpeed/schema) | `search-console` | `analytics_query`, `analytics_compare`, `analytics_anomalies`, `site_health_check`, `inspection_inspect`, `sitemaps_*`, `indexing_*`, `seo_keywords_research`, `seo_audit`, `genai_query_insights`, `pagespeed_analyze`, `schema_validate`, `sites_list`, `diagnostics` |
| GA4 (traffic sources / AI referrers, landing pages, page performance, funnel, realtime) | `analytics` (official GA4 MCP) | `run_report`, `run_funnel_report`, `run_realtime_report`, `get_account_summaries`, `get_property_details`, `get_custom_dimensions_and_metrics` |
| Google Ads (GAQL, search terms, CPC) | `google-ads` | `search_search`, `metadata_get_resource_metadata`, `customers_list_accessible_customers` |
| Keyword Planner (volumes, bids, trend) | `google-ads-planner` | `generate_keyword_ideas` |
| SERP / Backlinks / Competitor (Labs) | `dataforseo` | `api_request` (endpoint paths in the map) |

Rules:
- Never fabricate volumes, positions, or link counts. Label estimates (DataForSEO/Ahrefs/Semrush) vs real (GSC/GA4).
- A skill with an unmet data source must state the missing connection, not guess.
- Auth: `analytics`, `google-ads`, `google-ads-planner` use the service account (`GOOGLE_APPLICATION_CREDENTIALS`); `search-console` manages its own OAuth; `dataforseo` needs `DATAFORSEO_LOGIN`/`DATAFORSEO_PASSWORD`.
- Pending: **DataForSEO** requires API credentials in `.roo/mcp.json`; **Google Ads** and the **Keyword Planner** are connected.

---

*This file describes durable architectural rules, not a changelog. When a pattern changes, update the entry in place.*
