---
name: seo-backlink-check
description: Backlink profile for any domain — referring domains, authority, anchors, new/lost links, and a side-by-side vs a competitor. Use when asked "check my backlinks", "backlink profile of X", "who links to them", or "link gap vs competitor".
license: MIT
compatibility: Requires the `analytics` MCP server (official GA4). The `dataforseo` server (Backlinks API) is optional — without it, only the GA4 referral cross-check runs. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Backlink Check

> **Mechanical steps** (window resolution, capability calls, table rendering, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within the guardrails in [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope & Audience
- **Scope**: backlink profile for a domain; the GA4 referral cross-check is the only always-available part. Does not read or write `memory-bank/`.
- **Audience**: the site owner/SEO — label every third-party metric as an estimate.

## Report Audience & Purpose
- **Audience**: the site owner/SEO (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel/content system — never a code-level fix referencing this repo's files or functions.

## Memory-Bank Isolation
This skill is a standalone SEO tool — it MUST NOT read from or write to `memory-bank/` (activeContext.md, progress.md, systemPatterns.md, productContext.md). Findings and reports stay under the run directory.

## When to Use
- "check my backlinks", "backlink profile of X"
- "who links to them", "link gap vs competitor"

## When NOT to Use
- No `analytics` server configured
- No backlink data source connected (see Requires)

## Requires
- The `analytics` MCP server (official GA4) for the referral cross-check.
- *(Optional)* The `dataforseo` MCP server with **Backlinks API** access. If it is not configured, run only the GA4 referral cross-check and state that the backlink profile requires DataForSEO — never fabricate link counts.

## Data Sources
| Need | Tool | Status |
|---|---|---|
| Backlink profile | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/summary/live"} (supply: data) | available* |
| Referring domains | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/referring_domains/live"} (supply: data) | available* |
| Anchor distribution | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/anchors/live"} (supply: data) | available* |
| Fallback | Ahrefs / Semrush | not connected |
| Referral traffic cross-check | `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions"]} (supply: property_id, date_ranges) | available |

\* requires DataForSEO credentials in `.roo/mcp.json`.

## Workflow
1. **Verify.** `analytics` → `get_account_summaries` must respond (GA4 for the cross-check).
2. **Source.** Call `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/summary/live"} (supply: data) for the profile, `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/referring_domains/live"} (supply: data) for the domain list, `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/anchors/live"} (supply: data) for anchor distribution (pass the target as `data`). If the server is unauthenticated, **stop and say which connection is missing — never fabricate link counts.**
3. **Target profile.** Pull summary + top ~100 referring domains by rank for the user's domain: total backlinks, referring domains, dofollow share, authority distribution.
4. **Competitor (if named).** Same pulls for the competitor. Compute the **link gap**: strong domains linking to them but not to the user — that's the outreach list.
5. **Quality read.** Flag: spammy anchor patterns (exact-match commercial anchors at scale), link velocity spikes, a profile dominated by low-authority domains.
6. **Traffic cross-check (own site only).** `analytics` → `run_report` {"dimensions": ["sessionSource", "sessionMedium"], "metrics": ["sessions"]} (supply: property_id, date_ranges) — referral sessions by source; note which linking domains actually send visitors.

## Determinism
- Resolve every window to **absolute dates** (`YYYY-MM-DD`) before calling a tool — never pass relative phrases. GA4 is near-real-time; resolve the window with `python3 seo/window.py --days 28 --compare` and pass the literal `date_ranges` (current vs previous period). DataForSEO backlink calls are live and take no window.
- Emit an **as-of line** (resolved window + UTC generation timestamp) at the top of the output.
- Keep every **estimate** label exactly as written (third-party link metrics are index estimates).

## Output
Begin with the **as-of line** (resolved window + UTC generation timestamp). Verdict first (profile strength in one paragraph, and the gap vs the competitor if asked), then: profile summary table, top referring domains, anchor distribution, and — when a competitor was given — the link-gap outreach list (domain, authority, page linking to competitor). All third-party numbers labeled as index estimates.

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
0. (optional) Seed the run: `python3 seo/orchestrate.py --skill <name> --days 28 --compare --out-dir {run_dir}` → writes `.run_state.json` + a findings skeleton.
1. Write findings to `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json).
2. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
3. **Validate (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
4. Present the report path.

## Fallbacks
- If no backlink data source is connected, run only the GA4 referral cross-check and state plainly that the profile requires DataForSEO/Ahrefs/Semrush. Never fabricate link counts.

## Pending Data Sources
- **DataForSEO** (optional, not configured): without the `dataforseo` server, run only the GA4 referral cross-check and state that the backlink profile requires DataForSEO.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add it and reload MCP; otherwise follow the Fallbacks ladder |
| Empty/zero results | window excludes data or filter too narrow | widen the absolute window |

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
- Competitor keyword/content gap → run `seo-competitor-gap`.

- Deliver the report as PDF/email → run `report-export` (pass `--skill <name>` to select this skill's subject).
## Configuration
- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `analytics` (GA4) uses the service account (`GOOGLE_APPLICATION_CREDENTIALS`).
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
