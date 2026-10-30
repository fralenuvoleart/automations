---
name: seo-technical
description: Technical SEO audit of representative page templates per language — Core Web Vitals judged on field data (CrUX) with lab diagnostics, accessibility, structured data and entity markup, index/canonical state, crawl health and AI-crawler access. Use when asked "technical SEO", "core web vitals", "page speed audit", "why is my page slow", "accessibility" or "schema check".
license: MIT
compatibility: Requires the `search-console` MCP server (GSC + PageSpeed + schema). Page facts and robots checks use the local stdlib crawler (`seo/site_crawl.py`). Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Technical SEO

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Template-level technical health: one representative URL per template **and per language variant**; CWV, accessibility, structured data, index/canonical state, crawlability, AI-crawler access.

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
- "technical SEO", "core web vitals", "page speed audit"
- "why is my page slow", "schema check", "structured data", "accessibility"

## When NOT to Use
- No `search-console` server configured
- Whole-site performance audit → `seo-audit`; index coverage/hreflang → `seo-indexation`

## Requires
- **Required:** `search-console`. Local: `seo/site_crawl.py`.
- Profile `sections` (<!--site:sections-->`python3 seo/site_profile.py --site <domain> --get sections`<!--/site-->), page languages from the site rules (`python3 seo/rules.py --site <domain> classify --page <url>`), `priority_pages` (<!--site:priority_pages-->`python3 seo/site_profile.py --site <domain> --get priority_pages`<!--/site-->).

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `gsc.page` | `search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Page-level totals, including anonymized-query clicks |
| `gsc.pagespeed` | `search-console` → `pagespeed_analyze` (supply: url, strategy) | PageSpeed: CrUX field data (when available) + Lighthouse lab data |
| `gsc.pagespeed_a11y` | `search-console` → `pagespeed_analyze` {"category": ["accessibility"]} (supply: url, strategy) | Lighthouse accessibility category |
| `gsc.schema` | `search-console` → `schema_validate` (supply: url) | Structured-data validation |
| `gsc.inspect` | `search-console` → `inspection_inspect` {"engine": "google"} (supply: siteUrl, urls) | URL Inspection: coverage state, canonicals, last crawl (quota 2,000/day/property) |
| `gsc.health` | `search-console` → `site_health_check` {"level": "crawl_issues", "engine": "google"} (supply: siteUrl) | Crawl/robots/sitemap blockers (report only the fields returned; not a site-wide index count) |

<!--/include-->

Local tools: [`seo/site_crawl.py`](../../../seo/site_crawl.py) (`facts`, `robots`).

## Workflow
<!--include:evidence days=28 flags=--->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-technical --site <domain> --days 28`. It prints `run_dir: <path>` — the fixed, git-ignored run folder (`<run_root>/<site>/<date>/<skill>/`); use that path as `{run_dir}` below. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. **Cache first.** Before each data call, run `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args, JSON>' --from-cache`: exit 0 = the identical call was already made (same window and args, still valid) and is now recorded — skip the call; exit 3 = miss — make the call.
3. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
4. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify + property.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap-->, <!--cap:gsc.sites_list-->`search-console` → `sites_list` {"engine": "google"}<!--/cap-->.
2. **Representative URLs.** One URL per template (homepage, service page, blog post, other) **and** per language prefix — including right-to-left templates (e.g. `/ar/`). Choose from priority pages, else the top pages by clicks from <!--cap:gsc.page-->`search-console` → `analytics_query` {"dimensions": ["page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (current window); record the list (`--source user` or from the GSC pull).
3. **Core Web Vitals.** <!--cap:gsc.pagespeed-->`search-console` → `pagespeed_analyze` (supply: url, strategy)<!--/cap--> per URL, `strategy: mobile` then `desktop`. **Pass/fail uses field data** (CrUX for the URL, else the origin) at p75 against LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1. Lab (Lighthouse) values are diagnostics only; INP has no lab value (TBT is its proxy). No CrUX data → say "no field data" — never present lab numbers as a pass/fail. Section `window` note: "PageSpeed run <date>; CrUX = trailing 28 days".
4. **Accessibility.** <!--cap:gsc.pagespeed_a11y-->`search-console` → `pagespeed_analyze` {"category": ["accessibility"]} (supply: url, strategy)<!--/cap--> (`strategy: mobile`) → failing audits per template (contrast, alt text, labels, headings, ARIA).
5. **Structured data & entities.** <!--cap:gsc.schema-->`search-console` → `schema_validate` (supply: url)<!--/cap--> per URL + `python3 seo/site_crawl.py facts --url <urls>` (record) → JSON-LD types, `sameAs`, author/reviewer, invalid blocks. Expected types per [`domain-knowledge.md`](../../../seo/references/domain-knowledge.md); FAQ/HowTo markup earns no Google rich result — never recommend it for that purpose.
6. **Index/canonical state.** <!--cap:gsc.inspect-->`search-console` → `inspection_inspect` {"engine": "google"} (supply: siteUrl, urls)<!--/cap--> for the representative URLs — coverage state, Google vs declared canonical, last crawl.
7. **Crawl health & AI crawlers.** <!--cap:gsc.health-->`search-console` → `site_health_check` {"level": "crawl_issues", "engine": "google"} (supply: siteUrl)<!--/cap--> (fields returned only) and `python3 seo/site_crawl.py robots --site https://<domain>` (record) → search/retrieval vs training bots table.
8. **Assemble.** Rank issues by severity × number of templates (and languages) affected.

## Determinism
- The URL list is recorded before testing; every test runs on that list in both strategies.
- CWV verdicts use the published thresholds on field data only.

## Output
Provenance line first. **Verdict**: technically healthy or not, and the #1 blocker. Then: CWV table (template, language, field LCP/INP/CLS mobile & desktop, lab diagnostics), accessibility findings, structured-data table (template, types, errors, `sameAs`/author), index/canonical table, crawler-access table, and the prioritized fix list — each issue names the template and the exact change.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-technical`.

<!--/include-->

## Fallbacks
- PageSpeed fails/rate-limited → retry once, then mark the URL unmeasured; still report structured data, inspection and crawl health.
- `schema_validate` unavailable → use the `facts` JSON-LD summary and say validation was not run.
- Site blocks the crawler → `facts`/`robots` sections become `unavailable` with the status code.

## Pending Data Sources
- None required (field data availability depends on the site's Chrome traffic).

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| "No field data" everywhere | low traffic per URL | use origin-level CrUX if present; otherwise report lab diagnostics only |
| Lab LCP good, field LCP poor | real users on slower devices/networks | trust field data; investigate images/fonts/server time |
| JSON-LD `invalid_blocks` > 0 | malformed JSON in a script tag | fix the markup syntax first |

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
- Index coverage/hreflang → `seo-indexation`; whole-site audit → `seo-audit`.
- AI visibility beyond crawler access → `seo-ai-visibility`.
- PDF/email delivery → `report-export` (`--skill seo-technical`).

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
  context.json        # evidence index (seo/record.py)
  data/*.json         # raw tool responses (seo/record.py)
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```

<!--/include-->
