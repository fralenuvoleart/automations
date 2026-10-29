---
name: seo-internal-links
description: Internal-link audit — under-linked and orphaned priority pages, and the exact internal links + anchors to add. Use when asked "internal links", "orphan pages", "internal linking", or "link equity".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) in .roo/mcp.json. Full link-graph analysis needs a crawl source (not configured) — the skill degrades to a GSC-page-level approximation. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Internal Links

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: internal-link health of priority pages from the site's own GSC (approximation) plus inspection. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the content editor (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "internal links", "internal linking", "orphan pages", "link equity"
- "which pages need more links"

## When NOT to Use
- No `search-console` server configured
- External backlinks (use `seo-backlink-check`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- A site profile with `priority_pages` / `priority_keywords` ([`seo/site_profile.py`](../../../seo/site_profile.py)).
- *(Optional)* A crawl source for the true link graph — **not configured**; without it the audit is a GSC-page-level approximation.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Page-level data | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Page inspection | `search-console` → `inspection_inspect` (supply: siteUrl, urls) | available |
| Priority pages | site profile (`python3 seo/site_profile.py --site <domain> --get priority_pages`) | available |
| True link graph (crawl) | crawl source | not connected |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Priority pages.** `python3 seo/site_profile.py --site <domain> --get priority_pages`. If empty, use the top pages by impressions from `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate).
3. **Signals.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) — a priority page with impressions but weak position often lacks internal links; `search-console` → `inspection_inspect` (supply: siteUrl, urls) to confirm crawlability.
4. **Candidate sources.** Match priority pages to related pages that already rank (topic overlap) — those are the best internal-link sources.
5. **Recommend.** For each under-linked priority page: 3–5 source pages + the anchor text to use. Record `findings.unavailable` = `{source: crawl, affects: full link graph}` so the report states the approximation.
6. **Assemble.** Rank by priority × impressions.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **heuristic** label exactly as written (the link graph is approximated, not crawled).

## Output
Begin with the **as-of line** and the **Data availability** section (stating the link graph is approximated). Verdict, then: under-linked-priority-pages table (page, impressions, position, suggested sources, anchors), and a ranked action list. Each row names source page, target page, and anchor.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-internal-links --days 90 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- Without a crawl source, use the GSC-page-level approximation and record it in `findings.unavailable` (the report states it under **Data availability**).
- If the site profile has no `priority_pages`, use top-impression pages and state that.

## Pending Data Sources
- **Crawl source** (not configured): a full internal link graph (orphans, link counts, depth) needs a crawler or a DataForSEO/Screaming Frog-style source. Without it, the audit is an approximation.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data (GSC lag) or filter too narrow | widen the absolute window; never include today |
| Cannot confirm orphans | no crawl source | state the approximation in **Data availability** |

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
- External backlinks → run `seo-backlink-check`.
- Brief for a priority page → run `seo-content-brief`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-internal-links` to select this skill's subject).

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth.

## Privacy & Retention
- Findings/report files contain the site's own performance data (queries, URLs, metrics) — keep them under the run directory and prune when no longer needed.
- Third-party calls: none — capability calls go only to the configured MCP servers (GSC/GA4/Google Ads); the site's data does not leave Google.
- Rendered reports are written to disk and opened in the editor; treat them as containing the site's data.

## Output Structure
```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # raw tool data
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```
