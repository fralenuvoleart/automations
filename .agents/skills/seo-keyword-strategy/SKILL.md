---
name: seo-keyword-strategy
description: Comprehensive keyword strategy, striking-distance opportunity sizing, and competitor content gap — real Google volume/CPC, clustering, winnability, and estimated traffic value. Use when asked "keyword strategy", "find keywords", "keyword research", "keyword gap", "traffic value", or "striking distance opportunities".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) and `google-ads-planner` in .roo/mcp.json. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Keyword Strategy (Research, Opportunity Sizing & Gap)

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: keyword roadmap, striking-distance opportunity value, and competitor keyword gap from real Google Search Console data and Google Ads Keyword Planner. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "keyword strategy", "keyword research", "build a keyword plan"
- "what should I rank for", "striking distance keywords", "opportunity sizing"
- "keyword gap vs competitor", "traffic value"

## When NOT to Use
- You want a ready-to-write brief for a single keyword (use `seo-content-brief`)
- Tracking movement of existing rankings over time (use `seo-rank-tracking`)
- No `search-console` server in `.roo/mcp.json`

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- The `google-ads-planner` MCP server (local, in `seo/mcp-servers/google-ads-planner`).
- Optional: `dataforseo` MCP server (for competitor live ranked keywords; if missing, competitor gap defaults to site's own organic foothold + related expansions).

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Property list | `search-console` → `sites_list` | available |
| Related query expansion | `search-console` → `seo_keywords_research` {"type": "related"} (supply: keywords) | available |
| Existing rankings & footholds | `search-console` → `analytics_query` {"dimensions": ["query", "page"]} (supply: siteUrl, startDate, endDate) | available |
| Striking-distance opportunities | `search-console` → `seo_audit` {"type": "striking_distance"} (supply: siteUrl) | available |
| Real Google volume / CPC / trend (planner) | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) | available |
| Competitor ranked keywords | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/ranked_keywords/live"} (supply: data) | optional* |
| Services & priority terms | site profile (`python3 seo/site_profile.py --site <domain> --get services`) | available |

\* requires DataForSEO credentials; if unconfigured, competitor gap is marked unavailable and analysis focuses on internal striking distance + seed clustering.

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Expand the seed topic.** `search-console` → `seo_keywords_research` {"type": "related"} (supply: keywords) on seed keyword(s) — collect related query expansion.
3. **Pull existing foothold & striking distance.** `search-console` → `seo_audit` {"type": "striking_distance"} (supply: siteUrl) and `search-console` → `analytics_query` {"dimensions": ["query", "page"]} (supply: siteUrl, startDate, endDate) — identify queries the site already has impressions or positions (8–20) for.
4. **Competitor gap (optional).** If a competitor domain is provided and DataForSEO is configured, call `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/ranked_keywords/live"} (supply: data) to extract top ~500 keywords they rank for that the user's site does not. If unauthenticated, record `findings.unavailable` = `{source: dataforseo, affects: competitor keyword gap}`.
5. **Real planner metrics & value model.** `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) for the combined candidate set (seeds, striking distance, competitor gap). Pull `avg_monthly_searches`, `competition`, and top-of-page bids. For striking-distance terms, compute:
   `est. monthly value = avg_monthly_searches × expected_CTR(target position) × CPC` (see [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md)).
6. **Cluster into strategic roadmap:**
   - **Tier 1: Fast-Track Quick Wins (Striking Distance):** Position 8–20 keywords with high search volume and commercial intent. Direct action: on-page refresh and internal link consolidation on existing URLs.
   - **Tier 2: Content Gap / Competitor Conquesting:** High-value terms competitors rank for where the site has zero presence. Direct action: new pillar content.
   - **Tier 3: Long-Tail Supporting Topics:** Informational question variants for supporting cluster articles.
7. **Coverage check.** Reconcile against the site profile: `python3 seo/coverage.py --site <domain> --covered {run_dir}/covered.txt`.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** label exactly as written (planner metrics and traffic values are estimates).

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). Verdict (highest-ROI keyword cluster and striking-distance opportunity value), then: Tier 1 Quick Wins table, Tier 2 Content Gap table, and cluster roadmap. Plain language, no filler.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-keyword-strategy --days 90 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the `google-ads-planner` server is unavailable or rate-limited (429 `RESOURCE_EXHAUSTED`), use `search-console` → `seo_keywords_research` volumes and label them as estimates.
- If DataForSEO is unauthenticated, skip the competitor gap and report on the site's own striking distance and seed expansions.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without it, skip competitor live ranked keywords and SERP difficulty checks.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| Planner `RESOURCE_EXHAUSTED` | per-customer-ID quota hit | the server rate-gates and retries automatically; if persistent, batch fewer seeds or raise `PLANNER_MAX_RETRY_SECONDS` |

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
- Hand off a target keyword to outline → run `seo-content-brief`.
- Audit existing cannibalization/decay → run `seo-audit` or `seo-content-refresh`.
- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-keyword-strategy`).

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth; `google-ads-planner` uses the service account (`GOOGLE_APPLICATION_CREDENTIALS`).

## Privacy & Retention
- Findings/report files contain the site's own performance data (queries, URLs, metrics) — keep them under the run directory and prune when no longer needed.
- Third-party calls: none unless DataForSEO is configured. Data does not leave Google.
- Rendered reports are written to disk and opened in the editor; treat them as containing the site's data.

## Output Structure
```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # raw tool data
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```
