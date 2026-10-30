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
<!--include:evidence days=28 flags=--compare_--source_ga4-->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-backlink-check --days 28 --compare --source ga4 --out-dir {run_dir}`. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
3. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify.** <!--cap:ga4.properties-->`analytics` → `get_account_summaries`<!--/cap--> (required). Check whether `dataforseo` is configured (see [`tool-map.md`](../../../seo/tool-map.md)); if not, jump to step 7.
2. **Targets.** The user's domain (<!--site:domain-->`python3 seo/site_profile.py --site <domain> --get domain`<!--/site-->) and a competitor if named (else <!--site:competitors-->`python3 seo/site_profile.py --site <domain> --get competitors`<!--/site-->; if empty, skip step 6).
3. **Profile.** <!--cap:dfs.backlinks_summary-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/summary/live"} (supply: data)<!--/cap--> and <!--cap:dfs.referring_domains-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/referring_domains/live"} (supply: data)<!--/cap--> (top 100 by rank) for the user's domain. These sections are live index snapshots: set their `window` note to "DataForSEO live index, <date>".
4. **Anchor mix.** <!--cap:dfs.anchors-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/anchors/live"} (supply: data)<!--/cap--> → `python3 seo/dfs_metrics.py anchor-mix --anchors {run_dir}/data/anchors.json --site <domain>` → brand / URL / generic / exact-match / other shares and the heuristic exact-match risk flag. Compare with the competitor's mix when available rather than with a fixed ideal.
5. **Link velocity.** <!--cap:dfs.backlinks_new_lost-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/timeseries_new_lost_summary/live"} (supply: data)<!--/cap--> with `date_from` = comparison start, `date_to` = window end, `group_range: month` → new vs lost referring domains; flag spikes not explained by a campaign/PR (heuristic).
6. **Link gap (competitor).** Same <!--cap:dfs.referring_domains-->`dataforseo` → `api_request` {"method": "POST", "path": "/v3/backlinks/referring_domains/live"} (supply: data)<!--/cap--> pull for the competitor → `python3 seo/dfs_metrics.py link-gap --ours {run_dir}/data/rd_ours.json --theirs {run_dir}/data/rd_comp.json` → the outreach list (strong domains linking to them, not to the user).
7. **Referral cross-check (own site).** <!--cap:ga4.referrals-->`analytics` → `run_report` {"dimensions": ["sessionSource"], "metrics": ["sessions", "keyEvents"], "dimension_filter": {"filter": {"field_name": "sessionMedium", "string_filter": {"match_type": "EXACT", "value": "referral", "case_sensitive": false}}}} (supply: property_id, date_ranges)<!--/cap--> with `date_ranges` = current + comparison → which linking domains send sessions and key events.

## Determinism
- GA4 window: 28 days vs the previous 28 (`--source ga4`, ends `today − 2`); DataForSEO calls are live snapshots labelled per section.
- Anchor buckets and the gap list come from `dfs_metrics.py`; brand matching uses the `Brand` category of the site rules.

## Output
Provenance line first. **Verdict**: profile strength and, if asked, the gap vs the competitor. Then: profile summary, top referring domains, anchor mix (with the risk flag, labelled heuristic), new/lost trend, link-gap outreach list (domain, rank), and the GA4 referral table. Every third-party number labelled as an index estimate (`"estimate": true`).

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-backlink-check`.

<!--/include-->

## Fallbacks
- DataForSEO not configured or 401/403 → step 7 only; `unavailable` = `{source: dataforseo, affects: backlink profile, anchors, velocity and gap}`.
- No competitor named and none in the profile → skip step 6 and say so.

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
| [`seo/orchestrate.py`](../../../seo/orchestrate.py) | seed the run + window | Execute |
| [`seo/record.py`](../../../seo/record.py) | record evidence | Execute |
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

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — keep them in the run directory and delete them when no longer needed.
- Third-party calls: target domains/keywords/URLs are sent to DataForSEO (`dataforseo`) when those servers are used; everything else goes only to Google APIs via the configured MCP servers.

<!--/include-->

## Output Structure
<!--include:output-structure-->

```
{run_dir}/
  .run_state.json     # window + paths (seo/orchestrate.py)
  context.json        # evidence index (seo/record.py)
  data/*.json         # raw tool responses (seo/record.py)
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```

<!--/include-->
