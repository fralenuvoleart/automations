---
name: seo-backlink-check
description: Backlink profile for the site or a competitor — referring domains, authority, anchor mix, new/lost links over time, link gap vs a competitor — plus which linking sites actually send visitors (GA4). Use when asked "check my backlinks", "backlink profile of X", "who links to them" or "link gap vs competitor".
license: MIT
compatibility: Requires the `analytics` MCP server (GA4). The `dataforseo` server (Backlinks API) is optional; without it only the GA4 referral cross-check runs. Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Backlink Check

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Backlink profile, anchor mix, link velocity and link gap (DataForSEO, optional) plus the always-available GA4 referral cross-check. All third-party link data are index **estimates**.

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
- "check my backlinks", "backlink profile of X"
- "who links to them", "link gap vs competitor"

## When NOT to Use
- No `analytics` server configured (the only required source)
- Internal links → `seo-internal-links`

## Requires
- **Required:** `analytics` (GA4) for the referral cross-check.
- **Optional:** `dataforseo` with Backlinks API access. Without it, run only step 7 and add an `unavailable` entry naming DataForSEO — never fabricate link counts. Rule: [`data-source-map.md`](../../../seo/references/data-source-map.md).
- Request payloads: [`dataforseo-payloads.md`](../../../seo/references/dataforseo-payloads.md).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `ga4.properties` | `analytics` → `get_account_summaries` | GA4 accounts/properties (connection check) |
| `dfs.backlinks_summary` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/summary/live"} (supply: data) | Backlink profile summary (index estimate) *(optional, not configured)* |
| `dfs.referring_domains` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/referring_domains/live"} (supply: data) | Referring domains (index estimate) *(optional, not configured)* |
| `dfs.anchors` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/anchors/live"} (supply: data) | Anchor-text distribution (index estimate) *(optional, not configured)* |
| `dfs.backlinks_new_lost` | `dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/timeseries_new_lost_summary/live"} (supply: data) | New/lost backlinks and referring domains over time (link velocity) *(optional, not configured)* |
| `ga4.referrals` | `analytics` → `run_report` {"dimensions": ["sessionSource"], "metrics": ["sessions", "keyEvents"], "dimension_filter": {"filter": {"field_name": "sessionMedium", "string_filter": {"match_type": "EXACT", "value": "referral", "case_sensitive": false}}}} (supply: property_id, date_ranges) | Referral sessions by source domain |

<!--/include-->

Local tools: [`seo/dfs_metrics.py`](../../../seo/dfs_metrics.py) (`anchor-mix`, `link-gap`).

## Workflow
<!--include:evidence flags=--->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-backlink-check --site <domain>`. It seeds the fixed run folder (outside git; `python3 seo/runs.py root` shows where), makes every call in [`seo/data-plans/seo-backlink-check.json`](../../../seo/data-plans/seo-backlink-check.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory. Pulls over the row limit are split by date (Search Console) or paged (GA4) automatically; any still listed under `truncated` — and the outputs under `tainted` — are incomplete: their figures cannot pass validation, so report the gap instead.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. **Every call the plan does not make** — a judgment step, a fallback or a troubleshooting fix below: check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`. An unrecorded call's figures fail the number check; its statements cannot be checked at all.

<!--/include-->

1. **Targets.** The user's domain (<!--site:domain-->`python3 seo/site_profile.py --site <domain> --get domain`<!--/site-->) and a competitor: the plan uses the first of <!--site:competitors-->`python3 seo/site_profile.py --site <domain> --get competitors`<!--/site-->; when the user names one, rerun with `--input competitor=<domain> --force`. No competitor → no link gap (step 5).
2. **Profile.** `data/summary.json` and `data/rd_ours.json` (top 100 referring domains by rank). These sections are live index snapshots: set their `window` note to "DataForSEO live index, <date>". DataForSEO not configured → steps 2–5 are in `unavailable`; only step 6 applies.
3. **Anchor mix.** `computed/anchor_mix.json` → brand / URL / generic / exact-match / other shares and the heuristic exact-match risk flag. Compare with the competitor's mix (an extra <!--cap:dfs.anchors-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/anchors/live"} (supply: data)<!--/cap--> call for the competitor, recorded) rather than with a fixed ideal.
4. **Link velocity.** `data/new_lost.json` (comparison start → window end, by month) → new vs lost referring domains; flag spikes not explained by a campaign/PR (heuristic).
5. **Link gap.** `computed/link_gap.json` → the outreach list (strong domains linking to the competitor, not to the user).
6. **Referral cross-check (own site).** `data/referrals.json` (current + comparison) → which linking domains send sessions and key events.

## Determinism
- GA4 window: 28 days vs the previous 28 (`--source ga4`, ends `today − 2`); DataForSEO calls are live snapshots labelled per section.
- Anchor buckets and the gap list come from `dfs_metrics.py`; brand matching uses the `Brand` category of the site rules.

## Output
Provenance line first. **Verdict**: profile strength and, if asked, the gap vs the competitor. Then: profile summary, top referring domains, anchor mix (with the risk flag, labelled heuristic), new/lost trend, link-gap outreach list (domain, rank), and the GA4 referral table. Every third-party number labelled as an index estimate (`"estimate": true`).

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-backlink-check`.

<!--/include-->

## Fallbacks
- DataForSEO not configured or 401/403 → step 6 only; the pipeline lists each missing DataForSEO source in `unavailable`.
- No competitor named and none in the profile → no link gap (step 5); say so.

## Pending Data Sources
- **DataForSEO** (optional, not configured): backlink profile, anchors, velocity and gap.
- **Ahrefs / Semrush**: not connected.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| `api_request` 40x | DataForSEO credentials missing or plan lacks Backlinks API | run the GA4 part only; name the missing access |
| Summary empty | typo in target, or the domain is not in the index | verify the target; report "no data", not "zero links" |
| `dfs_metrics.py`: unrecognised response shape | a non-JSON or error response was recorded | re-record the raw JSON body of the call |

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
| [`seo/pipeline.py`](../../../seo/pipeline.py) | run the skill's data plan (`seo/data-plans/`): seed, pull, record, compute | Execute (first) |
| [`seo/orchestrate.py`](../../../seo/orchestrate.py) | seed the run + window (called by the pipeline) | Execute |
| [`seo/record.py`](../../../seo/record.py) | record evidence (extra calls, derived figures) | Execute |
| [`seo/report/build_report.py`](../../../seo/report/build_report.py) | render findings → Markdown | Execute |
| [`seo/report/validate_report.py`](../../../seo/report/validate_report.py) | mechanical validation | Execute (mandatory) |

<!--/include-->

Skill-specific: `seo/dfs_metrics.py` (Execute), [`seo/references/dataforseo-payloads.md`](../../../seo/references/dataforseo-payloads.md) (Read).

## Related / Delegation
- Competitor keyword/content gap → `seo-keyword-strategy`.
- Internal linking → `seo-internal-links`.
- PDF/email delivery → `report-export` (`--skill seo-backlink-check`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `analytics`: service account via `GOOGLE_APPLICATION_CREDENTIALS`; the account must be added to the GA4 property.
- `dataforseo` *(optional)*: needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the run folder outside git (`run_root` in `seo/config/settings.json`; `python3 seo/runs.py root`); `python3 seo/runs.py prune` deletes runs older than `retention_days`.
- Third-party calls: target domains/keywords/URLs are sent to DataForSEO (`dataforseo`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.

<!--/include-->

## Output Structure
<!--include:output-structure-->

```
{run_dir}/             # <run_root>/<site>/<date>/<skill>/ (seo/runs.py; outside git)
  .run_state.json     # window + paths (seo/orchestrate.py)
  pipeline.json       # every plan step and its status (seo/pipeline.py)
  context.json        # evidence index (seo/record.py)
  data/*.json         # raw tool responses (seo/record.py)
  computed/*.json     # analysis outputs — the numbers the report may state (seo/pipeline.py)
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```

<!--/include-->
