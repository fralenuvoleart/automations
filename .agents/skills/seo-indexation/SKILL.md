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
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `gsc.sitemaps` | `search-console` → `sitemaps_list` {"engine": "google"} (supply: siteUrl) | Submitted sitemaps, last read, errors/warnings (the API no longer reports indexed counts) |
| `gsc.health` | `search-console` → `site_health_check` {"level": "crawl_issues", "engine": "google"} (supply: siteUrl) | Crawl/robots/sitemap blockers (report only the fields returned; not a site-wide index count) |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.inspect` | `search-console` → `inspection_inspect` {"engine": "google"} (supply: siteUrl, urls) | URL Inspection: coverage state, canonicals, last crawl (quota 2,000/day/property) |
| `gsc.indexing` | `search-console` → `indexing_submit` {"method": "standard", "engine": "google"} (supply: siteUrl, urls) | Indexing API submission — only after explicit user confirmation |

<!--/include-->

Local tools: [`seo/site_crawl.py`](../../../seo/site_crawl.py) (`sitemap`, `crawl`).

## Workflow
<!--include:evidence days=28 flags=--->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-indexation --days 28 --out-dir {run_dir}`. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
3. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify + property.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap-->, <!--cap:gsc.sites_list-->`search-console` → `sites_list` {"engine": "google"}<!--/cap-->.
2. **Sitemaps.** <!--cap:gsc.sitemaps-->`search-console` → `sitemaps_list` {"engine": "google"} (supply: siteUrl)<!--/cap--> — submitted, last read, errors/warnings per sitemap. The API no longer returns indexed counts: never state them.
3. **Crawl health.** <!--cap:gsc.health-->`search-console` → `site_health_check` {"level": "crawl_issues", "engine": "google"} (supply: siteUrl)<!--/cap--> — report only the fields it returns.
4. **Build the sample** (deterministic, record each list):
   - all priority pages (if none: the top 50 pages by clicks from <!--cap:gsc.page-->`search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap-->, current window — say so);
   - `python3 seo/site_crawl.py sitemap --site https://<domain>` → sitemap URLs **with zero impressions** in `gsc.page`, in sitemap order, up to 150 (the likeliest non-indexed pages).
5. **Inspect.** <!--cap:gsc.inspect-->`search-console` → `inspection_inspect` {"engine": "google"} (supply: siteUrl, urls)<!--/cap--> in batches of ≤ 50 URLs (quota: 2,000 inspections/day/property, 600/minute) → per URL: coverage state, Google-selected vs declared canonical, last crawl, robots/page-fetch state. Report counts **as a share of the sample**, by coverage state.
6. **hreflang & canonicals.** `python3 seo/site_crawl.py crawl --site https://<domain> --profile <domain> --limit 300` (record `--source site_crawl --name crawl`) → `hreflang_issues` (missing self-reference, missing `x-default`, non-reciprocal or broken alternates), `canonical_issues` (cross-language canonicals first), `broken_internal`.
7. **Request indexing — opt-in only.** List non-indexed priority pages for manual **Request indexing** in GSC URL Inspection (the recommended path). Call <!--cap:gsc.indexing-->`search-console` → `indexing_submit` {"method": "standard", "engine": "google"} (supply: siteUrl, urls)<!--/cap--> **only if the user explicitly confirms in this conversation**: Google's Indexing API officially supports only JobPosting/BroadcastEvent pages; other submissions may be ignored. Internal links and sitemap health remain the primary fix.
8. **Assemble.** Rank issues: priority pages first, then by number of URLs affected.

## Determinism
- The sample rule (step 4) is fixed; the report states sample size and composition.
- Inspection and crawl are live snapshots: set section `window` notes ("URL Inspection <date>", "crawl <date>, N pages").

## Output
Provenance line first. **Verdict**: is indexing healthy for priority pages, and the #1 exclusion reason in the sample. Then: sampled coverage table (state, URLs, % of sample), sitemap table, priority-page inspection table (indexed? canonical? last crawl), hreflang/canonical issues, broken internal links, and the action list (manual request-indexing list included).

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period.
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
| [`seo/orchestrate.py`](../../../seo/orchestrate.py) | seed the run + window | Execute |
| [`seo/record.py`](../../../seo/record.py) | record evidence | Execute |
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

- Findings, raw tool responses (`context.json`, `data/`) and the report contain the site's own data — keep them in the run directory and delete them when no longer needed.
- Third-party calls: none — capability calls go only to Google APIs via the configured MCP servers.
- `seo/site_crawl.py` fetches public pages directly from the target site (polite rate, identifying User-Agent).

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
