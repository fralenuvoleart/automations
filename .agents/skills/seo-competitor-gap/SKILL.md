---
name: seo-competitor-gap
description: Find keywords a competitor ranks for that the user's site doesn't — the content gap, prioritized by volume and winnability. Use when asked "what does competitor.com rank for", "keyword gap vs X", "steal competitor keywords", or "why do they outrank us".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC). The `dataforseo` server (Labs) is optional — without it, only the "your keywords" half runs. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Competitor Gap

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: keyword/content gap between the user's site and a named competitor. Does not read or write `memory-bank/`.
- **Audience**: the site owner/SEO — distinguish estimates (competitor) from real (your GSC) numbers.

## Report Audience & Purpose
- **Audience**: the site owner/SEO (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "what does competitor.com rank for", "keyword gap vs X"
- "steal competitor keywords", "why do they outrank us"

## When NOT to Use
- No `search-console` server configured
- No competitor-domain data source connected (see Requires)

## Requires
- The `search-console` MCP server with GSC connected (your side).
- *(Optional)* The `dataforseo` MCP server with **Labs API** access. If it is not configured, run only the "your keywords" half and state that the competitor side requires DataForSEO — never fabricate competitor positions.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Your queries | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Competitor keywords | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/ranked_keywords/live"} (supply: data) | available* |
| Competitor overview | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/domain_rank_overview/live"} (supply: data) | available* |
| Fallback | Ahrefs / Semrush organic-keywords | not connected |

\* requires DataForSEO credentials in `.roo/mcp.json`.

## Workflow
1. **Verify.** `search-console` → `diagnostics` — GSC must be `ok`.
2. **Competitor's keywords.** `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/ranked_keywords/live"} (supply: data) for the competitor domain. Pull top ~500 by volume. If the server is unauthenticated, **stop and say which connection is missing.**
3. **Competitor overview.** `dataforseo` → `api_request` {"method": "POST", "path": "/v3/dataforseo_labs/google/domain_rank_overview/live"} (supply: data) — their estimated organic traffic and keyword count, for context.
4. **Your keywords.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate), dimension `["query"]`, last 90 days, high rowLimit — the full set of queries the user's site gets impressions for.
5. **Diff into three buckets:**
   - **Gap** — competitor ranks top 20, you have zero impressions → new content needed
   - **Behind** — you both rank but they're ≥5 spots ahead → improve existing page
   - **Ahead** — you outrank them (report briefly; it's the moat)
6. **Prioritize** the Gap and Behind buckets by volume × relevance to the user's product. Drop branded competitor terms unless the user wants comparison pages — then list them separately as "vs / alternative" page candidates.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** label exactly as written (competitor metrics are estimates; your GSC numbers are real).

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). Verdict (how big the gap is, in keywords and estimated traffic), then: Gap table (keyword, their position, volume, suggested page), Behind table (keyword, their pos, your pos, your page, fix), and a top-10 action list. Note explicitly which numbers are estimates (theirs) vs real (yours).

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 90 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If no competitor data source is connected, run the "your keywords" half only and state plainly that the competitor side requires DataForSEO/Ahrefs/Semrush. Never fabricate competitor positions.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without the `dataforseo` server, run only the "your keywords" half and state that the competitor side requires DataForSEO.

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
- Content brief for a chosen gap keyword → run `seo-content-brief`.

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth.
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
