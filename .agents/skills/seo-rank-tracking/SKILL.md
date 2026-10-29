---
name: seo-rank-tracking
description: Rank tracking without a tracker subscription — position movers between any two periods from real Search Console data. Use when asked "how are my rankings", "what moved this week/month", "track my keywords", or "did the update hit me".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) in .roo/mcp.json; the `dataforseo` server (live SERP spot-check) is optional. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Rank Tracking

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: position movers between two periods from the site's own GSC data. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the site owner/SEO (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "how are my rankings", "what moved this week/month"
- "track my keywords", "did the update hit me"

## When NOT to Use
- No `search-console` server configured
- Full site audit (use `seo-audit`)

## Requires
The `search-console` MCP server with GSC connected. Verify with `search-console` → `diagnostics`.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Property list | `search-console` → `sites_list` | available |
| Aggregate period delta | `search-console` → `analytics_compare` {"mode": "period_over_period"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) | available |
| Gradual trends | `search-console` → `analytics_compare` {"mode": "trends"} (supply: siteUrl, startDate, endDate) | available |
| Query and page rankings | `search-console` → `analytics_query` {"dimensions": ["query", "page"]} (supply: siteUrl, startDate, endDate) | available |
| Cross-engine comparison | `search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate) | available* |
| Lost queries | `search-console` → `seo_audit` {"type": "lost_queries"} (supply: siteUrl) | available |
| Live SERP spot-check | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/regular"} (supply: data) | optional* |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Two windows.** Default: last 28 days vs previous 28. If the user names an event ("since the March update"), split around that date. GSC data lags ~2 days — never include today.
3. **Pull both periods & cross-engine check.** `search-console` → `analytics_compare` {"mode": "period_over_period"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) for the aggregate. Call `search-console` → `analytics_query` {"dimensions": ["query", "page"]} (supply: siteUrl, startDate, endDate) once per period and diff on `query` and `page`. If Bing is connected, optionally spot-check engine divergence via `search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate) with `dimension: "query"`.
4. **Join and diff.** Match queries across periods; compute position delta, clicks delta, impressions delta.
5. **Classify:**
   - **Winners** — position improved ≥2 spots on queries with real impressions
   - **Losers** — dropped ≥2 spots (sort by clicks lost, not by delta — a 4→7 drop on a money query beats a 40→80 crash on a nothing query)
   - **New** — queries appearing only in the recent period
   - **Lost** — queries that vanished → `search-console` → `seo_audit` {"type": "lost_queries"} (supply: siteUrl), else derive from the two pulls
6. **Spot-verify (optional).** For the 3–5 most important losers, call `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/regular"} (supply: data) to see who took the spot. Skip if the server is unauthenticated.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28 --compare` and pass the literal `startDate`/`endDate`/`compareStartDate`/`compareEndDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). Verdict first (net up/down and the single biggest move), then four tables: Winners, Losers, New, Lost — query, positions before→after, clicks delta. If the user asked about a specific algorithm update, answer that question explicitly with the before/after evidence.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-rank-tracking --days 28 --compare --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the specialized `seo_*` tools are not exposed, derive every finding from `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) using the thresholds above.
- If the `dataforseo` server is unavailable, skip the live SERP spot-check.

## Recurring
If the user wants this weekly, suggest scheduling it rather than re-running by hand.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without the `dataforseo` server, skip the live SERP spot-check.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| Losers list empty | window too short or the update too recent | widen to 28/90 days; GSC lags ~2 days — never include today |
| Deltas look inverted | misaligned periods (seasonality/weekday mix) | align weekdays; use `analytics_compare` `trends` mode for gradual moves |

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
- Full site audit → run `seo-audit`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-rank-tracking` to select this skill's subject).

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth.
- Optional `dataforseo` needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

## Privacy & Retention
- Findings/report files contain the site's own performance data (queries, URLs, metrics) — keep them under the run directory and prune when no longer needed.
- Third-party calls: when `dataforseo` is connected, the target domain/keywords are sent to DataForSEO; otherwise capability calls go only to the configured MCP servers (GSC/GA4/Google Ads).
- Rendered reports are written to disk and opened in the editor; treat them as containing the site's data.

## Output Structure
```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # raw tool data
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```
