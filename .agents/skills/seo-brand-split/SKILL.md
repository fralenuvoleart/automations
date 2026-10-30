---
name: seo-brand-split
description: Brand vs non-brand performance from Search Console — overall and per language — with the unattributable (anonymized) share stated, so non-brand growth, the real SEO signal, is visible. Use when asked "brand vs non-brand", "branded traffic", "non-brand growth" or "how much is brand".
license: MIT
compatibility: Requires the `search-console` MCP server and the site's rules file (`seo/config/rules/<domain>.json`: Brand category, page languages). Tool names canonicalized in [`seo/tool-map.md`](../../../seo/tool-map.md).
---

# Brand vs Non-Brand

> **Mechanical steps** (window, capability calls, recording, computing, validation) must be followed exactly; **analytical steps** (severity, root cause, prioritization) use judgment within [`seo/references/conciseness-directives.md`](../../../seo/references/conciseness-directives.md).

## Scope
- Branded vs non-branded clicks/impressions/position from the site's own GSC, overall and per language (language from the page path), current vs previous period.

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
- "brand vs non-brand", "branded traffic", "how much is brand"
- "non-brand growth", "branded vs organic"

## When NOT to Use
- No `search-console` server configured
- Whole-site audit → `seo-audit`; position movers → `seo-rank-tracking`

## Requires
- **Required:** `search-console`; the site rules (`python3 seo/rules.py --site <domain> validate`): brand = the `Brand` query category (first rule, plus tracked Brand keywords), language = `page_languages`. If the rules file is missing, **stop and ask** the user — never guess which terms are branded.

## Data Sources
<!--include:datasources-->

| Capability | Call | Purpose |
|---|---|---|
| `gsc.diagnostics` | `search-console` → `diagnostics` | Connection check (`google` must report ok) |
| `gsc.sites_list` | `search-console` → `sites_list` {"engine": "google"} | Verified Search Console properties |
| `gsc.page_query` | `search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Query × page attribution (anonymized queries excluded) |
| `gsc.daily_totals` | `search-console` → `analytics_query` {"dimensions": ["date"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate) | Daily site totals, including anonymized queries (reconciliation baseline) |

<!--/include-->

Local tools: [`seo/gsc_metrics.py`](../../../seo/gsc_metrics.py) (`brand-split`).

## Workflow
<!--include:evidence days=28 flags=--compare-->

**Run setup and evidence (mandatory).**
1. Seed the run: `python3 seo/orchestrate.py --skill seo-brand-split --site <domain> --days 28 --compare`. It prints `run_dir: <path>` — the fixed, git-ignored run folder (`<run_root>/<site>/<date>/<skill>/`); use that path as `{run_dir}` below. The window in `{run_dir}/.run_state.json` is the only one you may pass to tools.
2. **Cache first.** Before each data call, run `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args, JSON>' --from-cache`: exit 0 = the identical call was already made (same window and args, still valid) and is now recorded — skip the call; exit 3 = miss — make the call.
3. After **every** tool call, save the raw response: `python3 seo/record.py --run-dir {run_dir} --cap <capability ID> --name <short_name> --args '<the runtime args you supplied, JSON>' --response-file <file or ->`. The capability ID is the one in the HTML comment around each call below (e.g. `gsc.page`). Non-MCP data (crawler, profile, user input) uses `--source site_crawl|site_profile|user`. `record.py` rejects non-runtime args and off-window dates.
4. Compute with the scripts named in the steps, from the recorded `{run_dir}/data/*.json` files — never by eye. Every number and URL in the findings must come from a recorded response.

<!--/include-->

1. **Verify + property.** <!--cap:gsc.diagnostics-->`search-console` → `diagnostics`<!--/cap-->, then <!--cap:gsc.sites_list-->`search-console` → `sites_list` {"engine": "google"}<!--/cap--> → the user's domain.
2. **Rows.** For both periods: <!--cap:gsc.page_query-->`search-console` → `analytics_query` {"dimensions": ["query", "page"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (`pq_cur`, `pq_prev`) and <!--cap:gsc.daily_totals-->`search-console` → `analytics_query` {"dimensions": ["date"], "rowLimit": 25000, "engine": "google"} (supply: siteUrl, startDate, endDate)<!--/cap--> (`totals_cur`, `totals_prev`).
3. **Compute.** `python3 seo/gsc_metrics.py brand-split --cur {run_dir}/data/pq_cur.json --prev {run_dir}/data/pq_prev.json --totals-cur {run_dir}/data/totals_cur.json --totals-prev {run_dir}/data/totals_prev.json --site <domain>` →
   - brand / non-brand per language: language = the page's `page_languages` rule (default for pages without a language folder), classified per query × page row, then aggregated;
   - **unattributed** clicks (anonymized queries: in site totals, not classifiable) — always reported;
   - top non-brand queries.
4. **Trend.** Compare current vs previous per language. The signal is **non-brand** growth; brand mostly tracks demand.
5. **Language anomalies.** If one language's non-brand clicks fall while another's rise for the same queries, flag possible hreflang/canonical issues and hand off to `seo-indexation` (it verifies hreflang from crawled HTML).

## Determinism
- One window (28 vs previous 28) from `.run_state.json`.
- Brand = the rules' `Brand` category on the lowercased query; the report names the rules file so the split is reproducible.
- All numbers come from the `brand-split` output; nothing is re-derived by hand.

## Output
Provenance line first. **Verdict**: is non-brand growing (overall and in which languages)? Then: table per language × brand/non-brand/unattributed (clicks, impressions, position, current vs previous), top non-brand queries, and the rules file used.

<!--include:pipeline-->

### Deliverable pipeline (mechanical — never hand-edit the rendered report)
1. Write `{run_dir}/findings.json` per [`findings-schema.json`](../../../seo/references/findings-schema.json); copy `window` verbatim from `.run_state.json`; set `sections[].window` when a section's data covers a different period. Write each action as an object — `{"action", "impact": high|medium|low, "effort": low|medium|high, "page" or "keyword", "why"}` (+ `est_clicks` only from a computed estimate) — so `seo-brief` can merge and rank actions across reports.
2. Validate the findings: `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json` — fix every error first.
3. Render: `python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md`.
4. **Validate the report (mandatory):** `python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md --data {run_dir}/context.json`.
5. Present the report path. PDF/email delivery → `report-export` with `--skill seo-brand-split`.

<!--/include-->

## Fallbacks
- No rules file → stop and ask (see Requires).

## Pending Data Sources
- None — this skill uses only GSC and the site profile.

## Troubleshooting
Shared issues: [`skill-common/troubleshooting.md`](../../../seo/references/skill-common/troubleshooting.md).

| Symptom | Cause | Fix |
|---|---|---|
| Branded share looks too low | brand variants missing (other script, misspellings) | add the variant to the `Brand` rule in the rules file and re-run |
| Many pages land in the default language | URLs outside the `page_languages` rules (other host/subdomain) | add a rule to the rules file or note the host |
| Large unattributed share | many anonymized queries | report it; trends are still valid for the attributable part |

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

Skill-specific: `seo/gsc_metrics.py` (Execute), `seo/site_profile.py` (Execute).

## Related / Delegation
- Whole-site audit → `seo-audit`; position movers → `seo-rank-tracking`.
- hreflang verification → `seo-indexation`.
- PDF/email delivery → `report-export` (`--skill seo-brand-split`).

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
  context.json        # evidence index (seo/record.py)
  data/*.json         # raw tool responses (seo/record.py)
  findings.json       # LLM output (findings-schema.json)
  report.md           # rendered by build_report.py
```

<!--/include-->
