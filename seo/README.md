# `seo/` — SEO tooling home (non-skill)

Everything SEO-related that is **not** an Agent Skill lives here. Skills stay in
[`.agents/skills/`](../.agents/skills/) (they must, for discovery).

> **Status (2026-10-30):** 13 `seo-*` skills (12 reports + the weekly `seo-brief`), registry v8, CI gate [`check.sh`](check.sh) ALL GREEN offline.
> Review history and the status of every review item: [`memory-bank/activeContext.md`](../memory-bank/activeContext.md).

## Layout

| Path | Purpose |
|---|---|
| [`capabilities.json`](capabilities.json) | **Single source of truth**: capability ID → MCP `server` + `tool` + fixed `args` + `runtime` + `desc` (+ `policy`). |
| [`resolve.py`](resolve.py) | Renders skills from `{{cap:}}` / `{{site:}}` / `{{include:}}` tokens into marker blocks and **re-renders every block** on each `--write`; validates names, policies and schemas. |
| [`pipeline.py`](pipeline.py) / [`data-plans/`](data-plans/) | **The data half of every skill**: runs `data-plans/<skill>[.<mode>].json` — seeds the run, makes every MCP call (cache first) through `mcp_client.py`, records it, runs every analysis script into `computed/`, and writes `pipeline.json` + the `unavailable` list. The agent only interprets. |
| [`window.py`](window.py) / [`orchestrate.py`](orchestrate.py) | Deterministic windows per source (GSC lag 3, GA4 lag 2, snapshot; previous or YoY compare; Monday–Sunday weeks with `--weeks`) and run seeding. |
| [`record.py`](record.py) | Records every raw tool response as run evidence (`context.json` + `data/`); rejects non-runtime args and off-window dates. |
| [`gsc_metrics.py`](gsc_metrics.py) | All GSC analysis: movers, striking distance, low CTR, CTR curve (site → site's last 12 months → dated post-AI-Overviews benchmark in [`config/ctr-benchmark.json`](config/ctr-benchmark.json)), cannibalization, decline classes, brand/language split, value model, topic filter, truncation and anonymized share. |
| [`site_crawl.py`](site_crawl.py) | Stdlib crawler: robots.txt verdicts per search/AI crawler, sitemaps, link graph (inlinks, depth, orphans), hreflang reciprocity, canonicals, page facts. |
| [`dfs_metrics.py`](dfs_metrics.py) / [`ads_metrics.py`](ads_metrics.py) | DataForSEO anchor mix / link gap / keyword gap; Ads × GSC paid-organic overlap. |
| [`rules.py`](rules.py) | Site classification shared with the SEO sheet: query categories (incl. brand), page tags, page languages, GA4 channels (incl. AI assistants), tracked keywords with automatic Proven / Opportunity / Generic picks, New/Lost status and top 3 countries; `targets` (does each keyword rank with its target page?); `breakdown` and 8-week `trend` per category / page type / language / keyword; jump-link (#) variants merged. |
| [`ga4_metrics.py`](ga4_metrics.py) | GA4 landing page × source/medium rows classified with the site rules: `breakdown` per channel / page type / language (sessions, engaged sessions, engagement rate, key events) and `reconcile` (Search Console clicks vs GA4 organic sessions, `(not set)` share). |
| [`site_profile.py`](site_profile.py) / [`coverage.py`](coverage.py) | Per-site facts (+ values derived from the rules, thresholds, GA4 AI filter, status-tagged action history); coverage block (GSC-impressions basis). |
| [`runs.py`](runs.py) / [`config/settings.json`](config/settings.json) | Fixed run folders outside git (`<run_root>/<site>/<date>/<skill>/`; `run_root` = `~/Documents/seo-reports`), the shared cache location, latest report per skill, retention (`prune`); settings also hold the brief's cadence per report. |
| [`digest.py`](digest.py) | The weekly brief (`seo-brief`): 8-week KPIs, actions merged and ranked across the latest reports, new vs open since, `[done]` history, due reports. |
| [`report/`](report/) | `validate_report.py` (structure, dates, labels, **evidence gate** for URLs and — via [`number_check.py`](report/number_check.py) — every figure) and `build_report.py` (refuses malformed findings; appends plain-language definitions of the metrics used). |
| [`references/`](references/) | Shared contracts and methodology; [`skill-common/`](references/skill-common/) holds the shared skill sections. |
| [`mcp_client.py`](mcp_client.py) / [`tool-schemas.json`](tool-schemas.json) | MCP stdio client (`Session`: one handshake, many calls; fails fast when a server exits) and the cached tool schemas used for offline validation. |
| [`mcp-servers/google-ads-planner/`](mcp-servers/google-ads-planner/) | Local Keyword Planner server (ideas + historical metrics; API limits enforced). |

## How a skill runs (Pipeline → Write → Validate → Build)

`python3 seo/pipeline.py --skill S --site D [--mode weekly] [--input k=v]` does the first three phases in
one command, from the skill's data plan; the agent starts at **Write**. Optional sources that are not
configured or fail become `unavailable` entries; a required one stops the run (exit 1, details in
`pipeline.json`). `--dry-run` shows every call with its resolved args and calls nothing.

- **Row limits.** A pull that comes back at the server's row limit (Search Console 25,000; GA4 the
  capability's `limit`, else 10,000) is completed automatically: Search Console windows are halved by date
  until every chunk is under the limit and the rows are summed per key (position impression-weighted, CTR
  recomputed); GA4 reports are paged with `offset`. A cached pull at the limit is fetched again. Anything
  still cut (one day over the limit, or the 64-call budget spent) is listed in `pipeline.json` `truncated`,
  the outputs built on it in `tainted`, an `unavailable` entry is added, and the number check refuses
  figures found only there — at that volume use the Search Console BigQuery export.
- **Temporary failures.** Timeouts, rate limits (429), 5xx and a crashed server are retried (`policy.retry`,
  default 2; waits 2 s then 6 s; a crashed server is restarted). Bad requests and writes are not.
  `pipeline.json` records `retries` and each step's `seconds`.
- **Fail closed.** A plan can list `requires_servers`: without them the pipeline refuses to start (e.g.
  `seo-backlink-check` without DataForSEO — no backlink report without backlink data).
- **Robots.txt.** The crawler respects robots.txt on every fetch (disallowed URLs are listed under
  `skipped_by_robots`, never fetched; an unreachable robots.txt means nothing is fetched), and the AI-crawler
  verdicts cover the homepage and every priority page (`blocked_paths`).
- **Writes.** `gsc.indexing` is the only capability that changes something outside the workspace
  (`policy.write`). A plan step using it must set `"confirm": true` (else `--check-plans` fails) and the run
  must be started with `--allow-write`; agent calls to it need the user's approval in the chat.
- **Missing data.** Absent is never zero: a Search Console row without its metrics stops the run; a blank
  GA4 value stays empty, and a property that recorded no key event gets no key-event rate
  (`key_events_recorded: false` + a note) instead of a confident 0 %.

| Phase | Mechanism |
|---|---|
| **Orchestrate** | `orchestrate.py --site D` creates the run folder `<run_root>/<site>/<date>/<skill>[-<tag>]/` (`run_root` in [`config/settings.json`](config/settings.json), outside the repo or git-ignored — it refuses a root that could be committed) and fixes the window in `.run_state.json`; that is the only window tools may receive. |
| **Record** | `record.py --from-cache` first: an identical earlier call (same capability + args, still valid) is reused from `<run_root>/<site>/_cache/`; otherwise, after the MCP/tool call, `record.py` stores the raw response, its full call spec, and a cache copy (dated windows kept; live tools per `policy.cache_ttl_days`; errors never). |
| **Compute** | `gsc_metrics.py`, `rules.py`, `ga4_metrics.py`, `coverage.py`, `site_crawl.py`, `dfs_metrics.py`, `ads_metrics.py` turn recorded data into findings-ready numbers (`computed/<name>.json`). |
| **Write** | the LLM writes `findings.json` ([schema](references/findings-schema.json)) from those outputs; actions are objects (`action`, `impact`, `effort`, `page`/`keyword`, `why`) so `seo-brief` can merge them. |
| **Validate** | `validate_report.py --data context.json`: structure, dates, labels, every URL against recorded evidence and every figure against evidence + `computed/` at the precision written (small counts, years, dates, thresholds and standard constants exempt). |
| **Build** | `build_report.py` renders Markdown; a second validation checks the rendered report. |

## Authoring skills

Write tokens, then render:

```markdown
Pull {{cap:gsc.page}} for both periods.          → <!--cap:gsc.page-->`search-console` → `analytics_query` {…}<!--/cap-->
Services: {{site:services}}                      → <!--site:services-->`python3 seo/site_profile.py …`<!--/site-->
{{include:evidence flags=-}}                     → shared "run the pipeline" section (references/skill-common/evidence.md)
{{include:datasources}}                          → table generated from the skill's plan + the calls its text makes
```

`python3 seo/resolve.py --write` renders all skills; every later `--write` re-renders all blocks, so a
registry edit or a tool rename (via `aliases`) propagates everywhere. **Never edit inside a block.**
`--check` fails on stale blocks, leftover tokens, unknown IDs/keys, legacy names, bad policies and
invalid or deprecated GA4/GSC names (e.g. `conversions`), and enforces `rowLimit: 25000` + `engine: google`
on GSC queries.

### Data plans ([`data-plans/`](data-plans/))

One JSON file per skill (`<skill>.json`, plus modes such as `seo-rank-tracking.weekly.json`): the window
(`days`/`weeks`, `compare`, `source`), optional `inputs` (`required`, `default`, `default_profile`) and
`requires` (profile keys), then ordered steps:

| Step | Does |
|---|---|
| `{"pull": name, "cap": id, "period": current\|previous\|both\|window\|weeks, "args": {…}}` | MCP call (siteUrl, property and dates filled from the profile and run window), cache first, recorded as `data/<name>.json` |
| `{"local": name, "source": label, "run": [script, …]}` | local script whose output is evidence (crawler) |
| `{"compute": name, "run": [script, …]}` | analysis script → `computed/<name>.json` |

Modifiers: `optional` + `affects` (failure → `unavailable`), `when` (`server:`, `profile:k[!=v]`, `input:`,
`data:`, `computed:`, `!` negates), `for_each` + `{i}` in the name (`batch` N), `skip_empty`. Values:
`{site}`, `{domain}`, `{data}`, `{gsc_property}`, `{ga4_property}`, `{ads_customer_id}`, window keys,
`{input:k}`, `{profile:k}`, `{item}`; `$from` (`computed:x`/`data:x` + `path` like
`pages[class=vanished|ranking_loss].page`, `profile:k`, `ai_filter`, `serp_payload`, `planner:…`, `files`),
`$else`, `$concat`, `$each`, `$glob`. Unset optional args are dropped. `resolve.py` lists every plan
capability in the skill's Data Sources table; [`tests/test_pipeline.py`](tests/test_pipeline.py) checks
that every `computed/`/`data/` file a SKILL.md names is produced by its plan.

### Skill anatomy (enforced by [`tests/test_skill_docs.py`](tests/test_skill_docs.py))
frontmatter (name/description/license/compatibility) → mechanical-vs-analytical banner → `Scope` →
`Report Audience & Purpose` → `Memory-Bank Isolation` → `When to Use` → `When NOT to Use` → `Requires` →
`Data Sources` → `Workflow` → `Determinism` → `Output` (+ deliverable pipeline) → `Fallbacks` →
`Pending Data Sources` → `Troubleshooting` → `Files` → `Related / Delegation` → `Configuration` →
`Privacy & Retention` → `Output Structure`. Shared sections come from includes.

## Skill inventory

| Skill | Answers | Required | Optional (degrades per [rule](references/data-source-map.md)) |
|---|---|---|---|
| `seo-audit` | whole-site health: delta, declining pages, quick wins, cannibalization, indexation spot-check, engagement, AI share | search-console | analytics, dataforseo |
| `seo-ai-visibility` | AI-assistant referrals, cited pages, AI share of organic, AI-crawler access | search-console | analytics (headline) |
| `seo-backlink-check` | backlink profile, anchor mix, velocity, link gap, referral cross-check | dataforseo, analytics | — |
| `seo-brand-split` | brand vs non-brand per language, unattributed share | search-console + site rules | — |
| `seo-brief` | weekly one-pager: 8-week KPIs, top actions merged from every report, changes, due reports | search-console + latest reports | — |
| `seo-content-brief` | SERP-driven brief for one keyword, create vs expand | search-console | dataforseo, tavily, planner |
| `seo-content-refresh` | declining pages with exclusive causes; evidence-gated retire | search-console | analytics, dataforseo |
| `seo-indexation` | sampled index status, sitemaps, hreflang/canonical integrity | search-console | — |
| `seo-internal-links` | crawled link graph, orphans, link plan with anchors | search-console | — |
| `seo-keyword-strategy` | footholds + value, expansion per language, competitor gap | search-console | planner (+ `ads_customer_id`), dataforseo |
| `seo-paid-organic` | Ads × organic overlap in account currency, holdout plan | search-console | google-ads |
| `seo-rank-tracking` | query-level movers (or around a dated event) | search-console | dataforseo, Bing |
| `seo-technical` | CWV on field data, accessibility, structured data, crawler access | search-console | — |

## Site rules (classification — shared with the SEO sheet)

One file per site in [`config/rules/`](config/rules/) — the **single source** for classification,
ported from the "PBS - SEO Rankings" sheet (Rules + Keyword Setup tabs) and meant to be read by its
Apps Script too: query categories (first match wins on the lowercased query; `Brand` first), page
tags and page languages (on the cleaned URL: no `#fragment`, absolute, trailing slash), GA4 channels
on `source / medium` (the `AI assistants` channel feeds the GA4 AI filter), tracked keywords (Core +
Brand) and the automatic-pick settings (Proven = most clicks, Opportunity = most impressions at
position 5–20, Generic; per-category caps, exclusions, duplicate keys). Regexes must stay portable
(no lookarounds, inline flags or backreferences) — `rules.py validate` enforces it.

```bash
python3 seo/rules.py --site pbservices.ge validate
python3 seo/rules.py --site pbservices.ge classify --query "внж по ип в грузии"
python3 seo/rules.py --site pbservices.ge breakdown --by category --cur query_cur.json --prev query_prev.json
python3 seo/rules.py --site pbservices.ge keywords --query query_cur.json --prev query_prev.json --countries geo.json
python3 seo/rules.py --site pbservices.ge targets --page-query pq_cur.json
python3 seo/rules.py --site pbservices.ge trend --by category --rows query_w1.json … query_w8.json
```

## Site profiles

One file per site in [`config/sites/`](config/sites/), validated against
[`config/site-profile.schema.json`](config/site-profile.schema.json): site facts only — `priority_pages`,
markets, competitors, `ads_customer_id`, `ads_language_constants`, `ads_geo_targets`, `serp_locations`,
`thresholds` (overrides of `gsc_metrics.DEFAULTS`). `languages`, `sections`, `services` and
`priority_keywords` (Core keywords per language) are derived from the rules file. Each site has an
append-only, status-tagged action history (`[recommended]` / `[done]`; only `[done]` suppresses
re-recommendation).

```bash
python3 seo/site_profile.py --site pbservices.ge --validate   # profile + rules
python3 seo/site_profile.py --site pbservices.ge --get priority_keywords --lang ru
python3 seo/site_profile.py --site pbservices.ge --thresholds
python3 seo/site_profile.py --site pbservices.ge --ga4-ai-filter
python3 seo/site_profile.py --site pbservices.ge --history --status done
python3 seo/site_profile.py --site pbservices.ge --append-history "Rewrote /ru/vnzh/ title" --status done
```

## Commands

| Command | Effect |
|---|---|
| `bash seo/check.sh [--live]` | CI gate: `--check`, `--validate-cached`, profiles, compile, all tests (`--live` adds live schema validation) |
| `python3 seo/resolve.py --check \| --write \| --map \| --list` | render/validate skills; regenerate [`tool-map.md`](tool-map.md) |
| `python3 seo/resolve.py --validate-cached \| --validate-live` | tool + args vs cached / live schemas |
| `python3 seo/mcp_client.py [server]` | refresh `tool-schemas.json` (one server keeps the others) |
| `python3 seo/pipeline.py --skill S --site D [--mode M] [--input k=v] [--days N\|--weeks N] [--compare\|--yoy] [--force] [--dry-run] [--allow-write]` | run a skill's data plan (seed, pull, record, compute); `--allow-write` permits confirmed write steps |
| `python3 seo/pipeline.py --check-plans` | validate every plan (capabilities, runtime args, scripts, names) |
| `python3 seo/orchestrate.py --skill S --site D (--days N [--compare\|--yoy] \| --weeks N) [--source gsc\|ga4\|snapshot] [--tag T] [--force]` | seed a run in the fixed run folder |
| `python3 seo/record.py --run-dir D --cap ID --name N --args JSON (--response-file F \| --from-cache)` | record evidence (exit 3 = cache miss) |
| `python3 seo/runs.py root \| list --site D \| latest --site D --skill S \| prune [--older-than N]` | run folders, latest report, retention |
| `python3 seo/digest.py --site D --run-dir R` | build the weekly brief's findings |
| `python3 seo/gsc_metrics.py <command> …` | GSC analyses (see the module docstring) |
| `python3 seo/site_crawl.py robots\|sitemap\|crawl\|facts …` | crawler |
| `python3 seo/coverage.py --site D --gsc data/query_cur.json [--gsc-pages data/page_cur.json]` | coverage block |
| `python3 seo/report/validate_report.py --findings F [--report R] --data D/context.json` | validation |
| `python3 seo/report/build_report.py --findings F --out R` | render |

## Configuration

Server definitions and credentials live in `.roo/mcp.json` → `mcpServers.<server>.env`. Google servers use
the service account at `GOOGLE_APPLICATION_CREDENTIALS`; `search-console` keeps its own OAuth file;
optional `dataforseo` needs `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`.

## Delivery

PDF/email is the separate [`report-export`](../.agents/skills/report-export/SKILL.md) skill (PDF via
`npx md-to-pdf`/Chromium first, WeasyPrint fallback; SMTP email). Every SEO skill hands off to it.

## Notes / limits

- The Search Console API has no Page indexing report and no longer returns sitemap indexed counts;
  `seo-indexation` reports a **sampled** URL Inspection instead.
- `site_crawl.py` reads server-rendered HTML (no JavaScript) and robots.txt (not WAF/CDN rules).
- Keyword Planner: ≤ 20 seeds and ≤ 10 geo targets per call, ~1 QPS per customer; the server retries
  within `PLANNER_MAX_RETRY_SECONDS` (default 40, keep < 55 so the 60 s client timeout is not hit).
- `tavily` is not in the cached schema snapshot yet: run `python3 seo/mcp_client.py tavily` once
  locally so `--validate-cached` covers `web.*` too.
