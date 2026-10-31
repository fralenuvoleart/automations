---
name: seo-internal-links
description: Internal-link audit from a real crawl — inlinks and click depth per page, orphans vs the sitemap, weakly linked priority pages, broken internal links — and the exact source pages and anchors to add, chosen from Search Console query overlap. Use when asked "internal links", "orphan pages", "internal linking" or "link equity".
license: MIT
compatibility: Requires the `search-console` MCP server; the link graph comes from the local stdlib crawler (`seo/site_crawl.py`). Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Internal Links

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Internal link graph of the site (crawl from the homepage), joined with GSC page/query data to pick link sources and anchors for under-linked priority pages.

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
- "internal links", "internal linking", "orphan pages", "link equity"
- "which pages need more links"

## When NOT to Use
- No `search-console` server configured
- External backlinks → `seo-backlink-check`

## Requires
- **Required:** `search-console`. Local: `seo/site_crawl.py` (network access to the site).
- Profile `priority_pages` (<!--site:priority_pages-->`python3 seo/site_profile.py --site <domain> --get priority_pages`<!--/site-->), page languages from the site rules (`python3 seo/rules.py --site <domain> classify --page <url>`).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.page_query` | `search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query × page attribution (anonymized queries excluded) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |

<!--/include-->

Local tools: [`seo/site_crawl.py`](../../../seo/site_crawl.py) (`crawl`, `sitemap`), [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py) (`topic`).

## Workflow
<!--include:evidence flags=--->

**Data (scripted — never pull or record by hand).**
1. Run the data plan: `python3 seo/pipeline.py --skill seo-internal-links --site <domain>`. It seeds the fixed run folder (outside git; `python3 seo/runs.py root` shows where), makes every call in [`seo/data-plans/seo-internal-links.json`](../../../seo/data-plans/seo-internal-links.json) cache-first, records each response as evidence (`{run_dir}/data/<name>.json`) and runs every analysis script (`{run_dir}/computed/<name>.json`). It prints `run_dir: <path>` — use that path as `{run_dir}`. Exit 1 = a required source failed: report the error shown in `{run_dir}/pipeline.json` and stop.
2. Read `{run_dir}/pipeline.json`: optional sources that failed or did not apply are already listed in `findings.unavailable` — keep those entries, say so in the report, and never fill the gap from memory. Pulls over the row limit are split by date (Search Console) or paged (GA4) automatically; any still listed under `truncated` — and the outputs under `tainted` — are incomplete: their figures cannot pass validation, so report the gap instead.
3. Interpret the outputs named in the steps below — that is the whole job. Every number and URL in the findings must come from `computed/` or `data/`; `validate_report.py` rejects any other figure. A figure that is not computed (a sum, a share): compute it with a script and record the output — `… | python3 seo/record.py --run-dir {run_dir} --source derived --name <name> --response-file -`.
4. **Every call the plan does not make** — a judgment step, a fallback or a troubleshooting fix below: check the cache first — `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <name> --args '<runtime args, JSON>' --from-cache` (exit 3 = miss) — make the call, then record it with `--response-file <file or ->` instead of `--from-cache`. An unrecorded call's figures fail the number check; its statements cannot be checked at all.

<!--/include-->

1. **Targets.** Priority pages; if none, the top 20 pages by impressions (`computed/top_pages.json`) — say so.
2. **Under-linked targets.** `computed/underlinked.json` → per target: `inlinks`, `depth`, `outlinks` and the reasons (`orphan`, `weakly_linked` ≤ 1 inlink, `deep` > 3 clicks, `not_crawled`). The full graph (`top_anchors`, `orphans_vs_sitemap`, `broken_internal`) is in `data/crawl.json`; if `limit_reached`, the graph is partial: say so. URLs under `skipped_by_robots` were not fetched (the crawler respects robots.txt) — their links are unknown, not missing.
3. **Sources.** For each under-linked target, take its top non-brand queries from `data/pq_cur.json`, then `python3 seo/gsc_metrics.py topic --page-query {run_dir}/data/pq_cur.json --terms "<1–2 stem terms>"` (recorded as `--source derived`) → other pages with impressions on the same topic. Keep sources in the **same language prefix** that **do not already link** to the target (the target is absent from the source's `outlinks` in `data/crawl.json`). Pick 3–5 per target, highest impressions first.
4. **Anchors.** Use the target's main query in the page's language, varied across sources; avoid repeating one exact-match anchor everywhere.
5. **Fixes beyond links.** Orphans: link them from a relevant hub or remove from the sitemap (301 if retired). Broken internal links: fix or redirect.
6. **Assemble.** Rank by (priority page first) × the target's impressions.

## Determinism
- Graph metrics come from the recorded crawl; query overlap from `gsc_metrics.py topic`; the GSC window is 90 days from `.run_state.json`.
- Crawl section `window` note: "crawl <date>, N pages (limit L)".

## Output
Provenance line first. **Verdict**: how well priority pages are linked, and the #1 gap. Then: under-linked targets table (page, inlinks, depth, impressions, position), the link plan (source page → target page → anchor), orphans, broken internal links, and the ranked action list.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-internal-links`.

<!--/include-->

## Fallbacks
- Crawl blocked (403/5xx) → fall back to a GSC-only approximation (pages with impressions but weak position) and add `unavailable` = `{source: crawl, affects: link graph, orphans, depth}`.
- No priority pages → top-impression pages, stated.

## Pending Data Sources
- None required. JavaScript-rendered navigation is not executed by the crawler; if links appear only after JS, say the graph may undercount them.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Almost every page "weakly linked" | links injected by JavaScript | verify one page in the browser; state the limitation |
| Many orphans | sitemap lists URLs the site no longer links | link them or drop them from the sitemap |
| Crawl stops early | rate limiting / WAF | raise `--delay`, lower `--limit`, or allow the crawler's User-Agent |

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

Skill-specific: `seo/site_crawl.py` (Execute), `seo/gsc_metrics.py` (Execute).

## Related / Delegation
- External backlinks → `seo-backlink-check`; brief for a priority page → `seo-content-brief`.
- Index problems on orphans → `seo-indexation`.
- PDF/email delivery → `report-export` (`--skill seo-internal-links`).

## Configuration
<!--include:configuration-->

- Credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`.
- `search-console`: OAuth managed by the server (`~/.search-console-mcp-config.enc`).

<!--/include-->

## Privacy & Retention
<!--include:privacy-->

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — they stay in the run folder outside git (`run_root` in `seo/config/settings.json`; `python3 seo/runs.py root`); `python3 seo/runs.py prune` (or `pipeline.py --prune`) deletes runs and cache entries older than `retention_days`.
- Third-party calls: none — capability calls go only to Google APIs via the configured MCP servers.
- `seo/site_crawl.py` fetches public pages directly from the target site (polite rate, identifying User-Agent).

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
