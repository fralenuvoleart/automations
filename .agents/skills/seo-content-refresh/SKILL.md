---
name: seo-content-refresh
description: Find declining pages and rank them by refresh priority — clicks lost weighted by page importance — with a mutually exclusive cause (ranking loss, demand drop, CTR loss, vanished) and a refresh / consolidate / retire call gated on GA4 key events and backlinks. Use when asked "content decay", "which pages to refresh", "declining pages" or "content audit".
license: MIT
compatibility: Requires the `search-console` MCP server; `analytics` (GA4) and `dataforseo` gate retire decisions. Page importance comes from the site profile. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Content Refresh

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Declining-page detection and refresh prioritisation from page-level GSC data (which includes anonymized-query clicks), with cause classification and evidence-gated actions.

## Report Audience & Purpose
<!--include:audience-->

- **Audience**: the site owner/marketer (not a developer).
- **Purpose**: every finding ends in a concrete, prioritized action doable in the relevant panel or content system — never a code-level fix referencing this repo's files.

<!--/include-->

## Memory-Bank Isolation
<!--include:memory-bank-->

While running this skill, do not read from or write to `memory-bank/` (repo-level exception recorded in `AGENTS.md`). Findings, evidence and reports stay in the run directory.

<!--/include-->

## When to Use
- "content decay", "declining pages", "which pages to refresh"
- "content audit", "why is traffic dropping on old posts"

## When NOT to Use
- No `search-console` server configured
- Query position movers → `seo-rank-tracking`; whole-site audit → `seo-audit`

## Requires
- **Required:** `search-console`.
- **Optional:** `analytics` (GA4 key events per page) and `dataforseo` (backlinks) — both needed before any **retire** call. Rule: [`data-source-map.md`](../../../seo/references/data-source-map.md).
- Profile `priority_pages` (<!--site:priority_pages-->`python3 seo/site_profile.py --site <domain> --get priority_pages`<!--/site-->) and `services` (<!--site:services-->`python3 seo/site_profile.py --site <domain> --get services`<!--/site-->) for importance.

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.daily_totals` | `search-console` → `analytics_query` {"dimensions": ["date"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Daily site totals, including anonymized queries (reconciliation baseline) |
| `gsc.compare_trends` | `search-console` → `analytics_compare` {"mode": "trends", "engine": "google"} (supply: siteUrl, startDate, endDate) | Gradual trend detection |
| `ga4.organic_landing_pages` | `analytics` → `run_report` {"dimensions": ["landingPagePlusQueryString"], "metrics": ["sessions", "engagementRate", "keyEvents"], "dimension_filter": {"filter": {"field_name": "sessionDefaultChannelGroup", "string_filter": {"match_type": "EXACT", "value": "Organic Search", "case_sensitive": false}}}} (supply: property_id, date_ranges) | Organic-search landing pages: sessions, engagement, key events |
| `dfs.referring_domains` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/referring_domains/live"} (supply: data) | Referring domains (index estimate) *(optional, not configured)* |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |

<!--/include-->

Local tools: [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py) (`decay`).

## Workflow
<!--include:evidence flags=--->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-content-refresh --site <domain>`. It seeds the fixed, git-ignored run folder, makes every call in [`seo/plans/seo-content-refresh.json`](../../../seo/plans/seo-content-refresh.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. A call the plan does not make (a judgment step below): check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`.

<!--/include-->

1. **Classify.** `computed/decay.json` → declining pages (clicks down ≥ `decay_pct`) with exactly one class, in this precedence: `vanished` → `ranking_loss` → `demand_drop` → `ctr_loss` (table in [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md)). `computed/totals.json` and `data/trends.json` → the site-wide change and gradual trends.
2. **Seasonality.** If most declining pages are `demand_drop` (or the site total fell: `computed/totals.json`), run the plan again year-over-year — `python3 seo/pipeline.py --skill seo-content-refresh --site <domain> --yoy --tag yoy` (its own run folder) — and compare its `computed/decay.json`; report whether the drop is seasonal.
3. **Importance.** Priority pages and pages mapping to a service line rank first; otherwise rank by clicks lost and say so.
4. **Key events (GA4).** `data/ga4_pages.json` → key events per declining page (join on path).
5. **Backlinks (DataForSEO).** `data/rd_*.json` → referring domains for up to 10 `demand_drop` pages (the retire candidates).
6. **Recommend** per class: `ranking_loss` → **refresh**; `ctr_loss` → **rewrite title/meta**; `vanished` → **inspect URL** (→ `seo-indexation`); `demand_drop` → **consolidate (301)** if another page covers the topic, **retire** only when GA4 shows no key events **and** the page has no referring domains — without both checks, downgrade to "consolidate after manual backlink check". Never recommend deleting without a 301.
7. <!--include:history-->

**Action history.** Before recommending, read `python3 seo/site_profile.py --site <domain> --history`: never re-recommend a `[done]` action; list open `[recommended]` ones as "previously recommended, still open". After the run, record each *new* recommendation with `--append-history "<action>" --status recommended` (exact duplicates are ignored). Use `--status done` only when the user confirms an action was carried out.

<!--/include-->

## Determinism
- Window: 90 days vs the previous 90 (or YoY) from `.run_state.json`.
- Classes, deltas and thresholds come from `decay` output (profile `thresholds` overrides: <!--site:thresholds-->`python3 seo/site_profile.py --site <domain> --get thresholds`<!--/site-->).

## Output
Provenance line first. **Verdict**: how much of the drop is ranking loss vs demand vs CTR. Then: declining-pages table (page, class, clicks before→after, impressions %, position before→after, importance, action), seasonality result, and the ranked refresh list.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-content-refresh`.

<!--/include-->

## Fallbacks
- No GA4 or no DataForSEO → no **retire** calls (downgrade as in step 6) and one `unavailable` entry per missing source.
- `gsc.compare_trends` unavailable → the pipeline lists it in `unavailable`; the page-level classification is unaffected.

## Pending Data Sources
- **DataForSEO** (optional, not configured): page-level backlinks for retire decisions.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Nearly every page "declining" | strong prior period or seasonality | run the `--yoy` comparison (step 2) |
| A page shows `vanished` | deindexed, redirected or canonicalised | inspect it (`seo-indexation`) before any content work |
| Pages listed under `beyond_row_cutoff` | the page pull hit 25,000 rows | treat as unknown, not as lost |

## Files
<!--include:files-->

| File | Purpose | Action |
|---|---|---|
| [`seo/capabilities.json`](../../../seo/capabilities.json) | capability registry (single source of truth) | Read |
| [`seo/references/report-structure.md`](../../../seo/references/report-structure.md) | report contract + validation order | Read |
| [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md) | mandatory rules | Read |
| [`seo/references/data-source-map.md`](../../../seo/references/data-source-map.md) | freshness + the degradation rule | Read |
| [`seo/references/capability-usage.md`](../../../seo/references/capability-usage.md) | runtime args, GA4 filters, policy | Read |
| [`seo/references/domain-knowledge.md`](../../../seo/references/domain-knowledge.md) | methodology + thresholds | Read |
| [`seo/references/skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md) | shared troubleshooting | Read |
| [`seo/pipeline.py`](../../../seo/pipeline.py) | run the skill's data plan (`seo/plans/`): seed, pull, record, compute | Execute (first) |
| [`seo/orchestrate.py`](../../../seo/orchestrate.py) | seed the run + window (called by the pipeline) | Execute |
| [`seo/record.py`](../../../seo/record.py) | record evidence (extra calls, derived figures) | Execute |
| [`seo/report/build_report.py`](../../../seo/report/build_report.py) | render findings → Markdown | Execute |
| [`seo/report/validate_report.py`](../../../seo/report/validate_report.py) | mechanical validation | Execute (mandatory) |

<!--/include-->

Skill-specific: `seo/gsc_metrics.py` (Execute), `seo/site_profile.py` (Execute).

## Related / Delegation
- Query movers → `seo-rank-tracking`; brief for the refreshed page → `seo-content-brief`.
- Indexing problems → `seo-indexation`.
- PDF/email delivery → `report-export` (`--skill seo-content-refresh`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).
- `analytics`: service account via `GOOGLE_APPLICATION_CREDENTIALS`; the account must be added to the GA4 property.
- `dataforseo` *(optional)*: needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the git-ignored run folder (`python3 seo/runs.py root`); `python3 seo/runs.py prune` deletes runs older than `retention_days`.
- Third-party calls: target domains/keywords/URLs are sent to DataForSEO (`dataforseo`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.

<!--/include-->

## Output Structure
<!--include:output-structure-->

```
{run_dir}/             # <run_root>/<site>/<date>/<skill>/ (seo/runs.py; git-ignored)
  .run_state.json     # window + paths (seo/orchestrate.py)
  pipeline.json       # every plan step and its status (seo/pipeline.py)
  context.json        # evidence index (seo/record.py)
  data/*.json         # raw tool responses (seo/record.py)
  computed/*.json     # analysis outputs — the numbers the report may state (seo/pipeline.py)
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```

<!--/include-->
