---
name: seo-opportunity
description: Size the money in SEO — estimated monthly traffic value of striking-distance and gap keywords (volume × expected CTR × CPC), ranked by winnability. Use when asked "what's the opportunity", "how much is this worth", "prioritise my SEO", or "traffic value".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC) and the `google-ads-planner` MCP server (CPC) in .roo/mcp.json. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Opportunity Sizing

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- **Scope**: estimate the monetary value of the site's realistic SEO opportunities. Does not read or write `memory-bank/`.

## Report Audience & Purpose
- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "what's the opportunity", "how much is this worth"
- "prioritise my SEO", "traffic value", "SEO ROI"

## When NOT to Use
- No `search-console` server configured
- Keyword discovery (use `seo-keyword-research`)
- Paid-vs-organic overlap (use `seo-vs-ads`)

## Requires
- The `search-console` MCP server with GSC connected (verify with `search-console` → `diagnostics`).
- The `google-ads-planner` MCP server for CPC. If unavailable, fall back to `seo_keywords_research` estimates.
- A site profile with `services` ([`seo/site_profile.py`](../../../seo/site_profile.py)).

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Striking-distance keywords | `search-console` → `seo_audit` {"type": "striking_distance"} (supply: siteUrl) | available |
| Raw query data | `search-console` → `analytics_query` {"dimensions": ["query", "page", "date", "country", "device"]} (supply: siteUrl, startDate, endDate) | available |
| Real volume / CPC | `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) | available |
| Services (relevance) | site profile (`python3 seo/site_profile.py --site <domain> --get services`) | available |

## Workflow
1. **Verify + property.** `search-console` → `diagnostics`, then `search-console` → `sites_list` → pick the user's domain.
2. **Candidate keywords.** `search-console` → `seo_audit` {"type": "striking_distance"} (supply: siteUrl) for position 8–20 with impressions; add the site profile's `python3 seo/site_profile.py --site <domain> --get priority_keywords` not yet ranking.
3. **Real volume / CPC.** `google-ads-planner` → `generate_keyword_ideas` (supply: customer_id, keywords) for the candidate set — `avg_monthly_searches` and top-of-page bid. Label as estimates.
4. **Value model (estimate).** For each keyword: `est. monthly value = avg_monthly_searches × expected_CTR(target position) × CPC`. Use a conservative CTR band (see [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md)); state the assumption.
5. **Winnability.** Weight by current position (8–20 = winnable) and relevance to a `python3 seo/site_profile.py --site <domain> --get services` line. Drop irrelevant terms.
6. **Rank and assemble.** Order by `value × winnability`; group by service line **and by language** (the profile's `priority_keywords` per language: `python3 seo/site_profile.py --site <domain> --get priority_keywords --lang <code>`).

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GSC lags ~2 days: `endDate = today − 2`, never include today. Compute with `python3 seo/window.py --days 90` and pass the literal `startDate`/`endDate`.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** label exactly as written (all values here are estimates).

## Output
Begin with the **as-of line**. Verdict (the size of the opportunity, in estimated monthly value), then: an opportunity table (keyword, current position, target, est. volume, CPC, est. monthly value, service line), the CTR assumption stated explicitly, and a ranked action list. Every number labelled an estimate.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill seo-opportunity --days 90 --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If `google-ads-planner` is unavailable or rate-limited (429 `RESOURCE_EXHAUSTED`), use `search-console` → `seo_keywords_research` volumes and label them as estimates.
- If no CPC is available at all, rank by volume × winnability only and state that no monetary value is shown.

## Pending Data Sources
- **DataForSEO** (optional, not configured): not used by this skill.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Planner `RESOURCE_EXHAUSTED` | per-customer-ID quota | fall back to `seo_keywords_research` estimates; do not loop |
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
- Keyword discovery → run `seo-keyword-research`.
- Brief for a chosen opportunity → run `seo-content-brief`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill seo-opportunity` to select this skill's subject).

## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console` manages its own OAuth; `google-ads-planner` uses the service account (`GOOGLE_APPLICATION_CREDENTIALS`).

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
