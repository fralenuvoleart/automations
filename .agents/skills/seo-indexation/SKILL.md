---
name: seo-indexation
description: Index coverage and sitemap health from Search Console — sampled URL Inspection of priority and sitemap URLs, sitemap status, hreflang reciprocity and cross-language canonicals from crawled HTML, and a manual "request indexing" list. Use when asked "index coverage", "pages not indexed", "sitemap health", "hreflang check" or "why isn't my page indexed".
license: MIT
compatibility: Requires the `search-console` MCP server. hreflang/canonical checks use the local stdlib crawler (`seo/site_crawl.py`). Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Indexation & Sitemaps

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Index status of a **deterministic sample** of URLs (URL Inspection), sitemap health, hreflang and canonical integrity from crawled HTML. The site-wide Page indexing report is **not available via the API** — this skill never invents site-wide indexed/excluded counts.

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
- "index coverage", "pages not indexed", "why isn't my page indexed"
- "sitemap health", "sitemap errors", "hreflang check"

## When NOT to Use
- No `search-console` server configured
- Speed/structured data → `seo-technical`; whole-site audit → `seo-audit`

## Requires
- **Required:** `search-console`. Local: `seo/site_crawl.py` (needs network access to the site).
- Profile `priority_pages` (<!--site:priority_pages-->`python3 seo/site_profile.py --site <domain> --get priority_pages`<!--/site-->) and page languages from the site rules (`python3 seo/rules.py --site <domain> classify --page <url>`).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.sitemaps` | `search-console` → `sitemaps_list` {"engine": "google"} (supply: siteUrl) | Submitted sitemaps, last read, errors/warnings (the API no longer reports indexed counts) |
| `gsc.health` | `search-console` → `site_health_check` {"level": "crawl_issues", "engine": "google"} (supply: siteUrl) | Crawl/robots/sitemap blockers (report only the fields returned; not a site-wide index count) |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.inspect` | `search-console` → `inspection_inspect` {"engine": "google"} (supply: siteUrl, urls) | URL Inspection: coverage state, canonicals, last crawl (quota 2,000/day/property) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `gsc.indexing` | `search-console` → `indexing_submit` {"method": "standard", "engine": "google"} (supply: siteUrl, urls) | Indexing API submission — only after explicit user confirmation *(agent call, only when a step needs it)* |

<!--/include-->

Local tools: [`seo/site_crawl.py`](../../../seo/site_crawl.py) (`sitemap`, `crawl`).

## Workflow
<!--include:evidence flags=--->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-indexation --site <domain>`. It seeds the fixed, git-ignored run folder, makes every call in [`seo/plans/seo-indexation.json`](../../../seo/plans/seo-indexation.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. A call the plan does not make (a judgment step below): check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`.

<!--/include-->

1. **Sitemaps.** `data/sitemaps.json` — submitted, last read, errors/warnings per sitemap. The API no longer returns indexed counts: never state them.
2. **Crawl health.** `data/health.json` — report only the fields it returns.
3. **The sample** (deterministic): all priority pages (if none: the top 50 pages by clicks, `computed/top_pages.json` — say so) plus `computed/unseen.json` — sitemap URLs **with zero impressions**, in sitemap order, up to 150 (the likeliest non-indexed pages).
4. **Inspection.** `computed/inspection.json` (from `data/inspect_*.json`, batches of ≤ 50; quota 2,000 inspections/day/property, 600/minute) → counts and shares **of the sample** per coverage state and verdict, the URLs not indexed, and Google-selected vs declared canonical mismatches. Last crawl and robots/page-fetch state per URL are in the raw `data/inspect_*.json`.
5. **hreflang & canonicals.** `data/crawl.json` → `hreflang_issues` (missing self-reference, missing `x-default`, non-reciprocal or broken alternates), `canonical_issues` (cross-language canonicals first), `broken_internal`.
6. **Request indexing — opt-in only.** List non-indexed priority pages for manual **Request indexing** in GSC URL Inspection (the recommended path). Call <!--cap:gsc.indexing-->`search-console` → `indexing_submit` {"method": "standard", "engine": "google"} (supply: siteUrl, urls)<!--/cap--> **only if the user explicitly confirms in this conversation**: Google's Indexing API officially supports only JobPosting/BroadcastEvent pages; other submissions may be ignored. Internal links and sitemap health remain the primary fix.
7. **Assemble.** Rank issues: priority pages first, then by number of URLs affected.

## Determinism
- The sample rule (step 3) is fixed; the report states sample size and composition.
- Inspection and crawl are live snapshots: set section `window` notes ("URL Inspection <date>", "crawl <date>, N pages").

## Output
Provenance line first. **Verdict**: is indexing healthy for priority pages, and the #1 exclusion reason in the sample. Then: sampled coverage table (state, URLs, % of sample), sitemap table, priority-page inspection table (indexed? canonical? last crawl), hreflang/canonical issues, broken internal links, and the action list (manual request-indexing list included).

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-indexation`.

<!--/include-->

## Fallbacks
- `gsc.sitemaps` unavailable → state it; continue with inspection and crawl.
- Crawl blocked (403/5xx) → hreflang/canonical sections become `unavailable` with the status code.
- Inspection quota exhausted → report the inspected part and the remaining URLs.

## Pending Data Sources
- The **Page indexing report** (site-wide indexed/excluded counts) exists only in the Search Console UI; export it manually if needed.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Inspection error "not part of this property" | URL on another host/protocol | inspect under the matching property, or fix the sitemap URLs |
| Many "Crawled – currently not indexed" in the sample | thin/duplicate pages or weak internal links | improve content, consolidate duplicates, add internal links (`seo-internal-links`) |
| hreflang "not crawled (unverified)" | crawl limit reached | raise `--limit` or crawl the language section's start URL |

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

Skill-specific: `seo/site_crawl.py` (Execute), `seo/site_profile.py` (Execute).

## Related / Delegation
- Speed/structured data → `seo-technical`; under-linked pages → `seo-internal-links`.
- Whole-site audit → `seo-audit`.
- PDF/email delivery → `report-export` (`--skill seo-indexation`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the git-ignored run folder (`python3 seo/runs.py root`); `python3 seo/runs.py prune` deletes runs older than `retention_days`.
- Third-party calls: none — capability calls go only to Google APIs via the configured MCP servers.
- `seo/site_crawl.py` fetches public pages directly from the target site (polite rate, identifying User-Agent).

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
