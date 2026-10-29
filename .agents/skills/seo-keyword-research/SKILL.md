---
name: seo-keyword-research
description: Keyword research from a seed topic — ideas, real Google volume/CPC, intent, difficulty, clustered into a plan. Use when asked to "find keywords", "keyword research for X", "what should I rank for", or "build a keyword plan".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) and the `google-ads-planner` MCP server (volumes) in .roo/mcp.json. The `google-ads` server (first-party CPC actuals) and `dataforseo` (intent/difficulty) are optional. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Keyword Research

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: keyword research from a seed topic (ideas, volume/CPC, intent, clustering). Does not read or write `memory-bank/`.
- **Audience**: the site owner/marketer — never invent volumes; label estimates.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "find keywords", "keyword research for X"
- "what should I rank for", "build a keyword plan"

## When NOT to Use
- No `search-console` server configured
- Writing the article itself (use `seo-content-brief`)

## Requires
- The `search-console` MCP server with GSC connected. Verify with `search-console` → `diagnostics`.
- The `google-ads-planner` MCP server for real volumes/CPC (Basic Google Ads API access). If unavailable, fall back to `seo_keywords_research` estimates.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Related queries + volume estimates | `search-console` → `seo_keywords_research` {"type": "related"} (supply: keywords) | available |
| Keyword performance stats | `search-console` → `seo_keywords_research` {"type": "stats"} (supply: keywords) | available |
| Traffic estimates | `search-console` → `seo_keywords_research` {"type": "traffic"} (supply: keywords) | available |
| What the site already ranks for | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Real Google volume / CPC / trend (planner) | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) | available |
| Real CPC actuals (terms the account has served on) | `google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings) on `search_term_view` | available |
| Intent / difficulty / SERP features | DataForSEO (optional, not configured) | skipped |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Expand the seed.** `search-console` → `seo_keywords_research` {"type": "related"} (supply: keywords) with `type: "related"` on the seed keyword(s) — collect the related-query set.
3. **Real planner metrics.** `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) with the seed keyword(s) — returns `avg_monthly_searches`, `competition`, low/high top-of-page bids, and a 12-month `monthly_trend`. Batch multiple seeds per call — `KeywordPlanIdeaService` has a tight per-customer-ID quota (~1 QPS); the server rate-gates ≥1s between calls and retries with backoff, so do not fire parallel calls. `seo_keywords_research` estimates are the fallback if the planner call fails; label them as estimates.
4. **Real CPC where the account has data (optional).** `google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings) on `search_term_view` — fields `search_term_view.search_term`, `metrics.impressions`, `metrics.average_cpc`, `metrics.cost_micros`; condition `segments.date BETWEEN '<start>' AND '<end>'` (last 12 months). Where a candidate keyword matches a served search term, prefer this "actual" CPC over planner bids. Verify fields with `google-ads` → `metadata_get_resource_metadata` (supply: resource_name); never guess.
5. **What they already rank for.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) (filtered to the topic) — mark keywords the site already has positions for; those are optimize-not-create.
6. **Cluster.** Group by intent and topic into content clusters: pillar + supporting pages. For each cluster: target keyword, supporting keywords, total volume, intent, existing page (if any) or "new page".

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** label exactly as written (planner/`seo_keywords_research` volumes are estimates).

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). One table per cluster (keyword, volume, CPC, intent, current position if any), then a ranked plan: which clusters to attack first and why (volume × winnability — favor clusters where the site already has striking-distance positions). Plain language, no filler.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 90 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the `google-ads-planner` server is unavailable or rate-limited (429 `RESOURCE_EXHAUSTED`), use `search-console` → `seo_keywords_research` volumes and label them as estimates.
- If the `google-ads` server is unavailable, skip the first-party CPC actuals and use planner bids.

## Rules
- Never invent volumes. If a metrics call fails, show the keyword without numbers and say why.
- CPC belongs in the output when available — it tells the user what the traffic is worth, and this doubles as an ads negative-keyword source.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without the `dataforseo` server, skip search intent / keyword difficulty / SERP features.

## Notes
- `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) requires the `google-ads-planner` MCP server ([`seo/mcp-servers/google-ads-planner/server.py`](../../../seo/mcp-servers/google-ads-planner/server.py)) and **Basic** Google Ads API access (Explorer restricts `KeywordPlanIdeaService`). Customer ID via `google-ads` → `customers_list_accessible_customers`.
- `KeywordPlanIdeaService` is throttled upstream (429 `RESOURCE_EXHAUSTED`, "Request per service per method"). When it is exhausted the planner is temporarily unavailable: the server retries within a bounded budget (default 40s; `PLANNER_MAX_RETRY_SECONDS`) so it returns before the MCP client's 60s timeout. Fall back to `seo_keywords_research` estimates and state that the planner was rate-limited — do not retry in a loop.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| Planner `RESOURCE_EXHAUSTED` | per-customer-ID quota | fall back to `seo_keywords_research` estimates; do not loop |

## Files

| File | Purpose | Action |
|---|---|---|
| [`seo/capabilities.json`](../../../seo/capabilities.json) | capability registry (single source of truth) | Read |
| [`seo/references/report-structure.md`](../../../seo/references/report-structure.md) | report section contract | Read |
| [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md) | tone/label rules | Read |
| [`seo/references/data-source-map.md`](../../../seo/references/data-source-map.md) | freshness + degradation ladder | Read |
| [`seo/references/capability-usage.md`](../../../seo/references/capability-usage.md) | capability tokens, `args` vs `runtime`, `policy` | Read |
| [`seo/references/domain-knowledge.md`](../../../seo/references/domain-knowledge.md) | SEO interpretation methodology | Read |
| [`seo/report/build_report.py`](../../../seo/report/build_report.py) | renders findings JSON → Markdown | Execute |
| [`seo/report/validate_report.py`](../../../seo/report/validate_report.py) | mechanical validation | Execute (mandatory) |

## Related / Delegation
- Brief for a chosen keyword → run `seo-content-brief`.

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth; `google-ads-planner` and `google-ads` use the service account (`GOOGLE_APPLICATION_CREDENTIALS`).
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
