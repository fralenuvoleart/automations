---
name: seo-content-refresh
description: Find decaying pages and rank them by refresh priority — clicks lost period-over-period weighted by page importance — with a refresh / consolidate / retire call. Use when asked "content decay", "which pages to refresh", "declining pages", or "content audit".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) in .roo/mcp.json. Page importance comes from the site profile. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Content Refresh

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: decaying-page detection and refresh prioritisation from the site's own GSC. Does not read or write `memory-bank/`.
- **Audience**: the site owner/content editor — each row ends in refresh / consolidate / retire.

## Report Audience & Purpose
- **Audience**: the site owner/content editor (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "content decay", "declining pages", "which pages to refresh"
- "content audit", "why is traffic dropping on old posts"

## When NOT to Use
- No `search-console` server configured
- Rank movement over time (use `seo-rank-tracking`)
- Whole-site organic audit (use `seo-audit`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- A site profile with `priority_pages` / `services` ([`seo/site_profile.py`](../../../seo/site_profile.py)).

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Period delta | `search-console` → `analytics_compare` {"mode": "period_over_period"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate) | available |
| Page-level data | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Priority pages | site profile (`python3 seo/site_profile.py --site <domain> --get priority_pages`) | available |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Two windows.** Default: last 90 days vs previous 90. GSC lags ~2 days — never include today.
3. **Aggregate delta.** `search-console` → `analytics_compare` {"mode": "period_over_period"} (supply: siteUrl, startDate, endDate, compareStartDate, compareEndDate).
4. **Per-page delta.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) once per period; join on `page`; compute clicks and impressions deltas.
5. **Classify the decline.** Distinguish **decay** (clicks and impressions both down → freshness/competition) from a **ranking loss** (position down, impressions held) from a **demand drop** (impressions down, position held).
6. **Prioritise.** Rank decaying pages by **clicks lost × page importance** (importance = in `python3 seo/site_profile.py --site <domain> --get priority_pages` or mapped to a `python3 seo/site_profile.py --site <domain> --get services` line). Thresholds: default clicks down >30% period-over-period (override via site profile `thresholds`).
7. **Recommend.** For each: **refresh** (decay), **consolidate** (overlaps another page), or **retire** (no demand). State the reason.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90 --compare` and pass the literal `startDate`/`endDate`/`compareStartDate`/`compareEndDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** / **heuristic** label exactly as written.

## Output
Begin with the **as-of line**. Verdict (how much of the drop is decay vs demand), then: decaying-pages table (page, clicks before→after, impressions, position, importance, action), and a ranked refresh list. Each row names the page and the action.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 90 --compare --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If `analytics_compare` is unavailable, derive the delta from two `analytics_query` pulls and label it derived.
- If the site profile has no `priority_pages`, weight importance by impressions only and state that.

## Pending Data Sources
- **DataForSEO** (optional, not configured): not used by this skill.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| Everything looks "decaying" | comparing against an unusually strong prior period | widen to 90d or use a trend compare (`analytics_compare` trends) |

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
- Position movers over time → run `seo-rank-tracking`.
- Brief for the refreshed page → run `seo-content-brief`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill <name>` to select this skill's subject).
## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth.

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
