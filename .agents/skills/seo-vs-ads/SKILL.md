---
name: seo-vs-ads
description: Find money leaking between search ads and SEO — queries you pay for while already ranking organically, and paid queries with no organic coverage. Use when asked "am I paying for clicks I'd get free", "brand bidding waste", "SEO vs ads overlap", or "cut wasted ad spend with SEO".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) and the `google-ads` MCP server in .roo/mcp.json, both connected. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# SEO vs Ads

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: overlap between paid search terms and organic coverage. Does not read or write `memory-bank/`.
- **Audience**: the site owner/marketer — savings are estimates with stated assumptions.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "am I paying for clicks I'd get free", "brand bidding waste"
- "SEO vs ads overlap", "cut wasted ad spend with SEO"

## When NOT to Use
- No `search-console` server configured
- No `google-ads` server configured (organic half only — see Fallbacks)

## Requires
- The `search-console` MCP server with GSC connected (organic side).
- The `google-ads` MCP server (paid side). Customer ID: discover via `google-ads` → `customers_list_accessible_customers`.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Organic positions | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Paid search terms | `google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings) on `search_term_view` (GAQL) | available |
| Field discovery | `google-ads` → `metadata_get_resource_metadata` (supply: resource_name) | available |

## Workflow
1. **Verify.** `search-console` → `diagnostics` — GSC must be `ok`. `google-ads` → `customers_list_accessible_customers` → pick the ads customer ID.
2. **Paid search terms.** `google-ads` → `search_search` (supply: customer_id, resource, fields, conditions, orderings), last 90 days:
   - `resource`: `search_term_view`
   - `fields`: `search_term_view.search_term`, `metrics.impressions`, `metrics.clicks`, `metrics.cost_micros`, `metrics.conversions`, `metrics.absolute_top_impression_percentage`
   - `conditions`: `segments.date BETWEEN '<start>' AND '<end>'`
   - `orderings`: `metrics.cost_micros DESC`
   - Never guess fields — verify with `google-ads` → `metadata_get_resource_metadata` (supply: resource_name) first. Cost is micros: divide by 1,000,000.
3. **Organic positions.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate), dimension `["query"]`, same window.
4. **Join on query** (case-folded, trimmed) and bucket:
   - **Double-paying** — organic position ≤3 AND paid spend on the same term. Sum the spend: that's the number for the headline.
   - **Defensible** — organic ≤3 but competitors bid on the term. GAQL cannot see competitor auctions; use `absolute_top_impression_percentage` (low = weak own presence) plus a manual SERP check before calling a term defensible — say so honestly.
   - **Paid-only winners** — terms converting in ads with no organic ranking → the SEO content roadmap, pre-validated by money
   - **Organic-only converters** — strong organic queries with no ad coverage → scale candidates if the ads team wants volume
5. **Estimate savings.** For the double-paying bucket: spend × the organic click-capture you'd retain (be conservative, ~50–70% for position-1 brand terms; label it an estimate).

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** label exactly as written (savings are an estimate).

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). Headline first: "$X/quarter going to clicks you already rank #1 for." Then the four buckets as tables (term, cost, conversions, organic position), the savings estimate with its assumptions stated, and a short action list: exact negatives to add, exact pages to build.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 90 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the `google-ads` server is not configured, run the organic half only and name the missing connection instead of guessing at the paid side.
- If the ads account has no spend in the window (empty `search_term_view` result), say so — the overlap analysis is moot, not failed.

## Pending Data Sources
- **DataForSEO** (optional, not configured): not used by this skill; the overlap analysis needs only GSC + Google Ads.

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
| [`seo/report/build_report.py`](../../../seo/report/build_report.py) | renders findings JSON → Markdown | Execute |
| [`seo/report/validate_report.py`](../../../seo/report/validate_report.py) | mechanical validation | Execute (mandatory) |

## Related / Delegation
- Organic-only view → run `seo-audit`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill <name>` to select this skill's subject).
## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth; `google-ads` uses the service account (`GOOGLE_APPLICATION_CREDENTIALS`).

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
