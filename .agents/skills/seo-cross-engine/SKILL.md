---
name: seo-cross-engine
description: Google vs Bing performance from Search Console — per-engine query/page matrix, where Bing over- or under-indexes the site. Use when asked "Bing SEO", "Google vs Bing", "should I care about Bing", or "cross-engine".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC, with Bing connected) in .roo/mcp.json. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Cross-Engine (Google vs Bing)

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: per-engine performance comparison from the site's own GSC. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "Bing SEO", "Google vs Bing", "should I care about Bing"
- "cross-engine", "other search engines"

## When NOT to Use
- No `search-console` server configured, or Bing not connected to it
- Whole-site organic audit (use `seo-audit`)

## Requires
- The `search-console` MCP server with **both Google and Bing** connected (verify with `search-console` → `diagnostics`).

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Engine comparison | `search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate) | available |
| Raw queries | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics` — both `google` and `bing` must report `ok`. If Bing is not connected, stop and say so.
2. **Comparison.** `search-console` → `compare_engines` (supply: siteUrl, dimension, startDate, endDate) with `dimension: "query"` (then `"page"`) — per-engine clicks/impressions/position.
3. **Divergence.** Identify queries/pages where Bing over-indexes (Bing position materially better than Google) and vice-versa.
4. **Cross-check.** `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) with `engine` set per engine, to confirm the divergence.
5. **Assemble.** Verdict (is Bing worth attention?), then the per-engine matrix and the divergence lists.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 28` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.

## Output
Begin with the **as-of line**. Verdict (Bing share and whether it's worth work), then: a per-engine summary table, a divergence table (query/page, Google position, Bing position), and an action list. State clearly if Bing is not connected.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-cross-engine --days 28 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If Bing is not connected to `search-console`, state it plainly and stop — do not fabricate Bing data.
- If `compare_engines` is unavailable, derive the split from two `analytics_query` pulls (`engine: google` / `engine: bing`) and label it derived.

## Pending Data Sources
- **Bing** (must be connected to `search-console`): without it the comparison is impossible. The report states this under **Data availability**.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Bing empty | Bing not connected to the property | connect Bing in `search-console`; state it otherwise |
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
- Whole-site organic audit → run `seo-audit`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-cross-engine` to select this skill's subject).

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth (Google + Bing).

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
