---
name: seo-brief
description: Weekly one-page SEO brief for a site — 8-week KPIs from Search Console plus the top 5–7 actions merged and ranked from the latest report of every SEO skill, what changed since the last brief, and which reports are due. Use when asked for "the weekly brief", "SEO summary", "what should I do this week", "bird's-eye view" or "top SEO actions".
license: MIT
compatibility: Requires the `search-console` MCP server and completed reports from the other `seo-*` skills in the shared run folder (`python3 seo/runs.py list --site <domain>`). Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Weekly SEO Brief

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- One page per week: KPI trend (8 Monday–Sunday weeks), the top actions across all reports, changes since the last brief, and which reports to refresh. It reads the other skills' findings — it does not re-run them.

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
- "weekly brief", "SEO summary", "bird's-eye view"
- "what should I do this week", "top SEO actions"

## When NOT to Use
- No completed `seo-*` report yet → run `seo-audit` first (the brief would only show KPIs)
- A deep dive on one topic → the matching skill (e.g. `seo-rank-tracking`, `seo-content-refresh`)

## Requires
- **Required:** `search-console` (KPIs).
- **Inputs:** the latest completed report of each skill under the run folder, up to `brief_max_age_days` old (`seo/config/settings.json`); older or missing reports are listed as due, never estimated.

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.daily_totals` | `search-console` → `analytics_query` {"dimensions": ["date"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Daily site totals, including anonymized queries (reconciliation baseline) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |

<!--/include-->

Local tools: [`seo/digest.py`](../../../seo/digest.py), [`seo/runs.py`](../../../seo/runs.py).

## Workflow
<!--include:evidence flags=--->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-brief --site <domain>`. It seeds the fixed, git-ignored run folder, makes every call in [`seo/data-plans/seo-brief.json`](../../../seo/data-plans/seo-brief.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory. Pulls over the row limit are split by date (Search Console) or paged (GA4) automatically; any still listed under `truncated` — and the outputs under `tainted` — are incomplete: their figures cannot pass validation, so report the gap instead.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. **Every call the plan does not make** — a judgment step, a fallback or a troubleshooting fix below: check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`. An unrecorded call's figures fail the number check; its statements cannot be checked at all.

<!--/include-->

1. **Digest.** The plan's last step (`seo/digest.py`) wrote `{run_dir}/findings.json`: the KPI table (from `data/totals.json`), top actions (de-duplicated, minus actions logged `[done]`, ranked by impact ÷ effort, marked new or open since a date), reports included and reports due. It records each included report into the run as evidence; `computed/brief.json` lists the numbers it stated.
2. **Verdict.** Rewrite `verdict` in one or two plain sentences: the KPI trend and the single most important action. Do not change numbers, tables or actions.
3. **Done actions.** When the user confirms an action is done, log it with its exact text: `python3 seo/site_profile.py --site <domain> --append-history "<action>" --status done` — the next brief drops it.

## Determinism
- Window: 8 calendar weeks from `.run_state.json` (`--weeks 8`); KPIs are Search Console property totals (anonymized queries included).
- Everything except the verdict comes from `digest.py`; actions keep the wording of the newest report that raised them.
- Ranking: impact (high 3, medium 2, low 1) × effort (low 3, medium 2, high 1), then estimated clicks, then how many reports raised it.

## Output
Provenance line first. **Verdict**, then: KPIs (last 8 weeks), Top actions (with source report and status), Reports (date, verdict, due), and the Action list.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-brief`.

<!--/include-->

## Fallbacks
- No completed reports → KPIs only; `unavailable` names the missing reports and the brief lists them as due.
- `search-console` unavailable → stop (the KPIs are the brief's own data).

## Recurring
Weekly (`cadence_days.seo-brief` = 7), after the week's reports. Run the due reports it lists, then rerun the brief.

## Pending Data Sources
- None.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| No actions | reports older than `brief_max_age_days` or written before structured actions | rerun the due reports |
| A finished action keeps coming back | its `[done]` history text differs from the action | log it with the action's exact text |
| Same fix listed twice | two reports worded it differently | expected; they rank next to each other — mark both done |

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

Skill-specific: `seo/digest.py` (Execute), `seo/runs.py` (Execute), `seo/site_profile.py` (Execute).

## Related / Delegation
- The reports it summarizes: `seo-audit`, `seo-rank-tracking` (weekly mode), `seo-brand-split`, `seo-ai-visibility`, `seo-content-refresh`, `seo-technical`, `seo-indexation`, `seo-internal-links`, `seo-keyword-strategy`, `seo-backlink-check`, `seo-paid-organic`.
- PDF/email delivery → `report-export` (`--skill seo-brief`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the git-ignored run folder (`python3 seo/runs.py root`); `python3 seo/runs.py prune` deletes runs older than `retention_days`.
- Third-party calls: none — capability calls go only to Google APIs via the configured MCP servers.

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
