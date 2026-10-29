---
name: seo-audit
description: Full SEO audit of a site from its real Search Console + GA4 data — indexation health, CTR anomalies, decaying pages, striking-distance keywords, quick wins. Use when asked to "audit my site", "SEO audit", "why is my organic traffic down", or "SEO health check".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) and the `analytics` MCP server (official GA4) in .roo/mcp.json. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# SEO Audit

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: whole-site organic audit (indexation, CTR, decay, cannibalization, quick wins) from the site's own GSC + GA4. Does not read or write `memory-bank/`.
- **Audience**: the site owner/marketer — every finding ends in a concrete, prioritized action, not a code edit.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "audit my site", "SEO audit", "SEO health check"
- "why is my organic traffic down"
- Periodic site health review

## When NOT to Use
- No `search-console` server in `.roo/mcp.json`
- Single-page technical debugging (call `search-console` → `inspection_inspect` (supply: siteUrl, urls) / `search-console` → `pagespeed_analyze` (supply: url) directly)
- Competitor analysis (use `seo-competitor-gap`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics` — `google` must report `ok`).
- The `analytics` MCP server (official GA4) with the service account added to the GA4 property.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Property list | `search-console` → `sites_list` | available |
| Indexation / crawl health | `search-console` → `site_health_check` {"level": "crawl_issues"} (supply: siteUrl) | available |
| Aggregate period delta | `search-console` → `analytics_compare` {"mode": "period_over_period"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) | available |
| Raw GSC performance | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Anomaly detection | `search-console` → `analytics_anomalies` (supply: siteUrl, startDate, endDate) | available |
| Drop root cause | `search-console` → `analytics_compare` {"mode": "drop_attribution"} (supply: siteUrl, startDate, endDate) | available |
| Striking distance | `search-console` → `seo_audit` {"type": "striking_distance"} (supply: siteUrl) | available |
| Cannibalization | `search-console` → `seo_audit` {"type": "cannibalization"} (supply: siteUrl) | available |
| Low-CTR targets | `search-console` → `seo_audit` {"type": "low_ctr"} (supply: siteUrl) | available |
| Quick wins | `search-console` → `seo_audit` {"type": "quick_wins"} (supply: siteUrl) | available |
| Recommendations | `search-console` → `seo_audit` {"type": "recommendations"} (supply: siteUrl) | available |
| Low-hanging fruit | `search-console` → `seo_audit` {"type": "low_hanging_fruit"} (supply: siteUrl) | available |
| Page inspection | `search-console` → `inspection_inspect` (supply: siteUrl, urls) | available |
| GA4 page performance | `analytics` → `run_report` {"dimensions": ["pagePath"], "metrics": ["sessions", "engagementRate", "averageSessionDuration"]} (supply: property_id, date_ranges) | available |
| GA4 traffic sources | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions"], "dimension_filter": {"filter": {"field_name": "sessionSource", "in_list_filter": {"values": ["chatgpt.com", "chat.openai.com", "perplexity.ai", "gemini.google.com", "claude.ai", "copilot.microsoft.com"], "case_sensitive": false}}}} (supply: property_id, date_ranges) | available |

## Workflow
1. **Verify connections.** `search-console` → `diagnostics` and `analytics` → `get_account_summaries`. If either fails, stop and report which is missing.
2. **Pick the property.** `search-console` → `sites_list`. Use the one matching the user's domain; confirm only when ambiguous.
3. **Indexation.** `search-console` → `site_health_check` {"level": "crawl_issues"} (supply: siteUrl). Flag large "Crawled — currently not indexed" counts or spikes in excluded pages.
4. **Performance baseline.** `search-console` → `analytics_compare` {"mode": "period_over_period"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) for the aggregate delta (last 90 days vs previous 90). Then call `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) once per period and diff on `query` and `page` to get per-query and per-page deltas.
5. **Find the problems:**
   - **Decaying pages** — clicks down >30% period-over-period
   - **CTR anomalies** — position ≤5 but CTR <2% (title/meta problem) → `search-console` → `seo_audit` {"type": "low_ctr"} (supply: siteUrl), else derive from `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate)
   - **Striking distance** — position 8–20 with high impressions → `search-console` → `seo_audit` {"type": "striking_distance"} (supply: siteUrl), else derive from `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate)
   - **Cannibalization** — same query, multiple pages → `search-console` → `seo_audit` {"type": "cannibalization"} (supply: siteUrl), else derive from `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate)
   - **Quick wins / recommendations / low-hanging fruit** — `search-console` → `seo_audit` {"type": "quick_wins"} (supply: siteUrl), `search-console` → `seo_audit` {"type": "recommendations"} (supply: siteUrl), `search-console` → `seo_audit` {"type": "low_hanging_fruit"} (supply: siteUrl)
6. **Spot-check pages.** For the 3–5 worst pages, `search-console` → `inspection_inspect` (supply: siteUrl, urls) — canonical, indexing state, last crawl.
7. **Cross-check traffic.** `analytics` → `run_report` {"dimensions": ["pagePath"], "metrics": ["sessions", "engagementRate", "averageSessionDuration"]} (supply: property_id, date_ranges) — organic sessions + engagement by landing page, same periods. A page can hold rankings but lose revenue; call that out.
8. **AI traffic.** `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions"], "dimension_filter": {"filter": {"field_name": "sessionSource", "in_list_filter": {"values": ["chatgpt.com", "chat.openai.com", "perplexity.ai", "gemini.google.com", "claude.ai", "copilot.microsoft.com"], "case_sensitive": false}}}} (supply: property_id, date_ranges) — note whether AI engines (ChatGPT, Perplexity, Claude, Gemini) are a meaningful channel.
9. **Coverage.** Compute coverage of the site profile's priority keywords/pages: `python3 seo/coverage.py --site <domain> --covered {run_dir}/covered.txt` → include the output as `findings.coverage` (flattened + per-language). List any priority keyword/page not addressed under `missing`.
10. **History.** Read the site's action history (`python3 seo/site_profile.py --site <domain> --history`) before finalizing recommendations so you don't re-recommend past work; after the run, append the actions you recommend (`python3 seo/site_profile.py --site <domain> --append-history "<action>"`).

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90 --compare` and pass the literal `startDate`/`endDate`/`compareStartDate`/`compareEndDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** / **heuristic** label exactly as written.

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). A report with: **verdict up top** (one paragraph — is the site healthy or not, and the #1 issue), then sections — Indexation, Losers, Quick wins (striking distance + CTR fixes, ranked by impressions), Cannibalization — each with a table and the specific fix. Include the **Coverage vs site profile** block (from `coverage.py`) and end with a prioritized 5-item action list.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 90 --compare --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the specialized `seo_*` tools are not exposed, derive every finding from `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) using the thresholds above.
- If GA4 is not connected, run the GSC half and state that the revenue/engagement cross-check is unavailable. Do not substitute third-party estimates for the site's own data.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without the `dataforseo` server, skip SERP context for the worst pages.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |

## Files

| File | Purpose | Action |
|---|---|---|
| [`seo/capabilities.json`](../../../seo/capabilities.json) | capability registry (single source of truth) | Read |
| [`seo/references/report-structure.md`](../../../seo/references/report-structure.md) | report section contract | Read |
| [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md) | tone/label rules | Read |
| [`seo/references/data-source-map.md`](../../../seo/references/data-source-map.md) | freshness + degradation ladder | Read |
| [`seo/references/capability-usage.md`](../../../seo/references/capability-usage.md) | capability tokens, `args` vs `runtime`, `policy` | Read |
| [`seo/references/domain-knowledge.md`](../../../seo/references/domain-knowledge.md) | SEO interpretation methodology | Read |
| [`seo/site_profile.py`](../../../seo/site_profile.py) | site profile + action history | Execute |
| [`seo/coverage.py`](../../../seo/coverage.py) | deterministic coverage block | Execute |
| [`seo/report/build_report.py`](../../../seo/report/build_report.py) | renders findings JSON → Markdown | Execute |
| [`seo/report/validate_report.py`](../../../seo/report/validate_report.py) | mechanical validation | Execute (mandatory) |

## Related / Delegation
- Paid-vs-organic overlap is available via the connected `google-ads` MCP — run the `seo-vs-ads` skill for the full analysis.
- Position movers over time → run `seo-rank-tracking`.
- Brand vs non-brand split → run `seo-brand-split`.
- Technical health → run `seo-technical`; index coverage → run `seo-indexation`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill <name>` to select this skill's subject).
## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `analytics` (GA4) uses the service account (`GOOGLE_APPLICATION_CREDENTIALS`); `search-console` manages its own OAuth.
- Optional `dataforseo` needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

## Privacy & Retention
- Findings/report files contain the site's own performance data (queries, URLs, metrics) — keep them under the run directory and prune when no longer needed.
- Capability calls go only to the configured MCP servers (GSC/GA4/Google Ads); no data leaves to a third party unless the skill explicitly uses `tavily`/`dataforseo`.
- Rendered reports are written to disk and opened in the editor; treat them as containing the site's data.

## Output Structure
```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # raw tool data
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```
