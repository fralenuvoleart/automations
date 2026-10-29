---
name: seo-content-brief
description: SERP-driven content brief for a target keyword — what ranks, what to cover, headings, questions, internal links from your own data. Use when asked for a "content brief", "outline to rank for X", "what should this article cover", or before writing any SEO page.
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) in .roo/mcp.json. The `dataforseo` (SERP) and `google-ads-planner` (volumes) servers are optional enrichments. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Content Brief

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: a SERP-driven brief for one target keyword. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: a writer/editor (not a developer).
- **Purpose**: the brief is built from a real SERP and is ready to write from — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "content brief", "outline to rank for X"
- "what should this article cover"
- Before writing any SEO page

## When NOT to Use
- No `search-console` server configured
- Keyword planning across many topics (use `seo-keyword-research`)

## Requires
The `search-console` MCP server with GSC connected. Verify with `search-console` → `diagnostics`.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Live SERP top 10 | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/regular"} (supply: data) | optional* (fallback: web search) |
| Secondary keywords + volumes | `search-console` → `seo_keywords_research` {"type": "related"} (supply: keywords) | available (estimates) |
| Real volumes / CPC (planner) | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) | optional (real volumes replace estimates) |
| Existing foothold | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Page speed / schema checks | `search-console` → `pagespeed_analyze` (supply: url), `search-console` → `schema_validate` (supply: url) | available |

## Workflow
1. **The SERP.** Call `dataforseo` → `api_request` {"method": "POST", "path": "/v3/serp/google/organic/live/regular"} (supply: data) for the live Google top 10 of the target keyword — titles, URLs, SERP features (featured snippet, PAA, video). If the server is unauthenticated, fetch the top results via web search instead; the brief must be built from a real SERP either way.
2. **Read the top 3.** Fetch and skim the top-ranking pages: their structure, depth, angle, what they all cover (table stakes) and what none cover (the opening).
3. **Keyword set.** `search-console` → `seo_keywords_research` {"type": "related"} (supply: keywords) seeded with the target — secondary keywords and question variants worth folding in. Label volumes as estimates.
4. **Your existing foothold.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) filtered to the topic — queries the site already gets impressions for (work them into headings), and existing pages on adjacent topics (internal-link sources; also flag if one already half-covers this and should be expanded instead of a new page).
5. **Assemble the brief:**
   - Target keyword + secondaries with volumes
   - Search intent and required format (guide/listicle/comparison/tool page), inferred from what actually ranks
   - Proposed title + meta (write for the CTR, under 60/155 chars)
   - H2/H3 outline with a one-line note per section on what it must say
   - Questions to answer (PAA + question keywords)
   - Table stakes vs the differentiating angle
   - Internal links: 3–5 existing pages to link from, with anchors
   - Target length: match the ranking median, don't pad

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90` and pass the literal `startDate`/`endDate`.
- Keep every **estimate** label exactly as written.

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). The brief, ready to hand to a writer (or to write from directly).

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-content-brief --days 90 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If the `dataforseo` server is unavailable, build the SERP from web search — the brief must still be built from a real SERP.
- If the `google-ads-planner` server is unavailable or rate-limited, use `search-console` → `seo_keywords_research` volumes and label them as estimates.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without the `dataforseo` server, build the SERP from web search — the brief must still be built from a real SERP.
- **Google Ads** (optional): `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) supplies real volumes/CPC that replace the `seo_keywords_research` estimates.

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
- Cluster/keyword planning across many topics → run `seo-keyword-research`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-content-brief` to select this skill's subject).

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth; `google-ads-planner` uses the service account (`GOOGLE_APPLICATION_CREDENTIALS`).
- Optional `dataforseo` needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

## Privacy & Retention
- Findings/report files contain the site's own performance data (queries, URLs, metrics) — keep them under the run directory and prune when no longer needed.
- Third-party calls: when `dataforseo` is connected, the target domain/keywords are sent to DataForSEO; otherwise capability calls go only to the configured MCP servers (GSC/GA4/Google Ads). The web-search SERP fallback sends the target keyword to the configured search provider.
- Rendered reports are written to disk and opened in the editor; treat them as containing the site's data.

## Output Structure
```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # raw tool data
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```
