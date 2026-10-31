# Commands worth remembering

Every command runs **from the repository root** with `python3` (nothing to install). Paths like
`{run_dir}` come from the `run_dir:` line the pipeline prints. Each script also answers `--help`.

- Owner-facing guide to the reports: [`docs/SEO.md`](../docs/SEO.md)
- Internals, contracts and layout: [`README.md`](README.md)

## Essentials

The routine commands, ready to copy. `pbservices.ge` is the only site configured today.

| You want to… | Command |
|---|---|
| Confirm the toolkit still works (it must say `ALL GREEN`) | `bash seo/check.sh` |
| Run the weekly brief | `python3 seo/pipeline.py --skill seo-brief --site pbservices.ge` |
| Run the monthly audit | `python3 seo/pipeline.py --skill seo-audit --site pbservices.ge` |
| Run any other report | `python3 seo/pipeline.py --skill seo-technical --site pbservices.ge` |
| See which data a report will request, without requesting it | `python3 seo/pipeline.py --skill seo-audit --site pbservices.ge --dry-run` |
| Fetch the data again from Search Console instead of today's saved copy | `python3 seo/pipeline.py --skill seo-audit --site pbservices.ge --refresh` |
| Rewrite the Excel / Google Sheets files | `python3 seo/runs.py export --site pbservices.ge` |
| Delete saved runs and saved answers older than 180 days | `python3 seo/pipeline.py --prune` |

Where things land: `~/Documents/seo-reports/pbservices.ge/` holds one folder per run (the report inside it is
`report.md`) plus a `spreadsheets/` folder with the CSV copies — that is what the "spreadsheets" row rewrites.
A second run on the same day needs `--tag` (keep both runs), `--force` (replace it, reusing today's answers) or
`--refresh` (replace it, fetching again). Turning the report into a PDF, emailing it and checking it before
publishing are in §4; finding an older run is in §2.

Everything else — windows, tags, write approvals, evidence, cache, sites, by-hand analysis, troubleshooting —
is in the sections below.

---

## 1. Run a report

```bash
python3 seo/pipeline.py --skill seo-audit --site pbservices.ge            # the normal way
python3 seo/pipeline.py --skill seo-brief --site pbservices.ge --weeks 8  # Monday–Sunday weeks
python3 seo/pipeline.py --skill seo-rank-tracking --mode weekly --site pbservices.ge --weeks 8
python3 seo/pipeline.py --skill seo-content-brief --site pbservices.ge --input keyword="внж по ип в грузии"
python3 seo/pipeline.py --skill seo-audit --site pbservices.ge --dry-run  # show every call, make none
python3 seo/pipeline.py --skill seo-audit --site pbservices.ge --force    # rerun into the same folder
python3 seo/pipeline.py --skill seo-audit --site pbservices.ge --refresh  # fetch every call again
python3 seo/pipeline.py --skill seo-audit --site pbservices.ge --tag rerun # second run the same day
python3 seo/pipeline.py --skill seo-indexation --site pbservices.ge --allow-write  # only for confirmed submissions
```

| Flag | Why you would use it |
|---|---|
| `--days N` / `--weeks N` | override the plan's window (default from the plan, e.g. 90 days for the audit) |
| `--compare` / `--yoy` | compare with the previous period / the same period last year |
| `--as-of YYYY-MM-DD` | anchor the window to a past date (reproduce an older report) |
| `--dry-run` | print every call and its arguments, call nothing — the fastest way to see what a report does |
| `--force` | overwrite an already-seeded run folder; the answers that already succeeded are reused (a cheap rerun after fixing a source) |
| `--refresh` | fetch every call again instead of reusing the saved answers (also overwrites the run folder) |
| `--tag NAME` | a second run of the same skill on the same day, keeping the first one |
| `--allow-write` | permits a confirmed write step (`gsc.indexing`); never use it casually |

**Exit codes:** `0` = done, `1` = a required source failed (read `{run_dir}/pipeline.json`).

```bash
python3 seo/pipeline.py --check-plans                 # are all 14 data plans valid?
python3 seo/pipeline.py --prune                       # apply retention_days (180) now, and only that
python3 seo/pipeline.py --skill seo-audit --site pbservices.ge --prune   # prune, then run
```

---

## 2. See what you already have

```bash
python3 seo/runs.py root                              # where the data lives (~/Documents/seo-reports)
python3 seo/runs.py list --site pbservices.ge         # every run, newest first, with completed/report flags
python3 seo/runs.py list --site pbservices.ge --skill seo-audit
python3 seo/runs.py latest --site pbservices.ge --skill seo-audit
python3 seo/runs.py prune --dry-run                   # what retention would delete
python3 seo/runs.py prune --older-than 90             # delete runs and cache entries older than 90 days
```

The weekly brief's numbers, without writing a report:

```bash
python3 seo/digest.py --site pbservices.ge --run-dir {run_dir} --json
```

The site's action history (what was recommended, what is done):

```bash
python3 seo/site_profile.py --site pbservices.ge --history
python3 seo/site_profile.py --site pbservices.ge --history --status done
python3 seo/site_profile.py --site pbservices.ge --append-history "Rewrote the /ru/vnzh/ title" --status done
```

`[done]` entries are what stops a finished action being recommended again.

---

## 3. Spreadsheets (Excel / Google Sheets)

```bash
python3 seo/runs.py export --site pbservices.ge                    # all five tables, oldest first
python3 seo/runs.py export --site pbservices.ge --tables runs,actions
python3 seo/runs.py export --site pbservices.ge --out ~/Desktop/seo
```

Writes `runs.csv`, `totals.csv`, `pages.csv`, `queries.csv`, `actions.csv` into
`~/Documents/seo-reports/<site>/spreadsheets/<today>/` (UTF-8 with BOM, so both spreadsheets read the
Cyrillic/Georgian text correctly). Import with **File → Import → CSV**.

---

## 4. Check and publish a report

```bash
python3 seo/report/validate_report.py --findings {run_dir}/findings.json --data {run_dir}/context.json
python3 seo/report/validate_report.py --findings {run_dir}/findings.json --report {run_dir}/report.md \
        --data {run_dir}/context.json                       # after rendering
python3 seo/report/build_report.py --findings {run_dir}/findings.json --out {run_dir}/report.md
```

```bash
python3 .agents/skills/report-export/scripts/export_pdf.py --md {run_dir}/report.md --out {run_dir}/report.pdf \
        --title "SEO audit — pbservices.ge"
python3 .agents/skills/report-export/scripts/send_email.py --attachment {run_dir}/report.pdf --skill seo-audit
python3 .agents/skills/report-export/scripts/send_email.py --attachment {run_dir}/report.pdf --dry-run
```

`validate_report.py` is the gate: it refuses a URL that is not in the saved answers and a number that
does not match what was returned or calculated. Never skip it — an unvalidated report is not evidence.

---

## 5. Evidence and cache

Every call is saved; a call the plan does not make must be saved too, otherwise its figures cannot pass
the gate. For an extra (judgement/fallback) call, check the cache first:

```bash
python3 seo/record.py --run-dir {run_dir} --cap gsc.inspect --name inspect_a \
        --args '{"siteUrl":"sc-domain:pbservices.ge","urls":["https://pbservices.ge/"]}' --from-cache
# exit 3 = cache miss: make the call, then record it
python3 seo/record.py --run-dir {run_dir} --cap gsc.inspect --name inspect_a \
        --args '{...}' --response-file response.json          # or --response-file - for stdin
python3 seo/record.py --run-dir {run_dir} --source site_crawl --name crawl --response-file crawl.json
```

| Exit code | Meaning |
|---|---|
| `0` | recorded |
| `1` | rejected (unknown capability, non-runtime argument, date outside the run window) |
| `3` | cache miss — make the call, then record it |

Where the cache lives, and how to clear one call:

```bash
ls ~/Documents/seo-reports/pbservices.ge/_cache/             # one folder per capability
ls ~/Documents/seo-reports/pbservices.ge/_cache/gsc.page/    # one file per distinct call
rm ~/Documents/seo-reports/pbservices.ge/_cache/gsc.page/*.json   # force those pulls to be made again
```

Cache lifetime, in one line: a dated window is kept once final; PageSpeed/schema/URL Inspection/robots
health 7 days (sitemaps and crawl health 1 day); planner, keyword and backlink estimates 30 days; errors
and the Indexing API never.

---

## 6. Keep the toolkit healthy

```bash
bash seo/check.sh                # the gate: rendering, schemas, plans, profiles, compile, all tests
bash seo/check.sh --live         # the same, plus validation against the live MCP servers
```

Must end with `ALL GREEN`. If not, nothing else is trustworthy.

```bash
python3 seo/resolve.py --check            # are the skills' generated blocks current?
python3 seo/resolve.py --write            # re-render every block after editing capabilities.json
python3 seo/resolve.py --map              # regenerate tool-map.md after a registry edit
python3 seo/resolve.py --list             # every capability, its server and its tool
python3 seo/resolve.py --validate-cached  # registry arguments vs the cached tool schemas
python3 seo/resolve.py --validate-live    # ... vs the live servers (workstation only)
python3 seo/mcp_client.py                 # refresh tool-schemas.json for every server
python3 seo/mcp_client.py tavily          # refresh one server, keep the others
```

Editing rules: write `{{cap:…}}` / `{{site:…}}` / `{{include:…}}` tokens in a skill, never the rendered
text, and run `--write`. `--check` fails on stale blocks, leftover tokens and unknown names.

---

## 7. Sites and classification

```bash
python3 seo/site_profile.py --list                                   # sites with a profile
python3 seo/site_profile.py --site pbservices.ge --validate          # profile + rules
python3 seo/site_profile.py --site pbservices.ge --dump
python3 seo/site_profile.py --site pbservices.ge --get priority_pages
python3 seo/site_profile.py --site pbservices.ge --thresholds        # the numbers the analyses use
python3 seo/site_profile.py --site pbservices.ge --ga4-ai-filter     # the GA4 filter for AI assistants

python3 seo/rules.py --site pbservices.ge validate                   # after every rules edit
python3 seo/rules.py --site pbservices.ge classify --query "внж по ип в грузии"
python3 seo/rules.py --site pbservices.ge classify --page https://pbservices.ge/ru/uslugi/vnzh-v-gruzii/
python3 seo/rules.py --site pbservices.ge breakdown --by category --cur query_cur.json --prev query_prev.json
python3 seo/rules.py --site pbservices.ge keywords --query query_cur.json --prev query_prev.json
python3 seo/rules.py --site pbservices.ge targets --page-query pq_cur.json
python3 seo/rules.py --site pbservices.ge representatives --page page_cur.json
python3 seo/rules.py --site pbservices.ge trend --by category --rows w1.json w2.json w3.json
```

Two files per site, and they never overlap: `config/sites/<domain>.json` = facts, `config/rules/<domain>.json`
= classification (brand, categories, page tags, languages, channels, tracked keywords).

---

## 8. Digging into a number by hand

All of these read **recorded files**, not the live APIs, so they can be re-run as often as you like.

```bash
# Search Console
python3 seo/gsc_metrics.py totals --cur data/totals_cur.json --prev data/totals_prev.json
python3 seo/gsc_metrics.py movers --cur data/query_cur.json --prev data/query_prev.json --site pbservices.ge
python3 seo/gsc_metrics.py striking --query data/query_cur.json --site pbservices.ge
python3 seo/gsc_metrics.py low-ctr --query data/query_cur.json --site pbservices.ge
python3 seo/gsc_metrics.py cannibalization --page-query data/pq_cur.json
python3 seo/gsc_metrics.py decay --cur data/page_cur.json --prev data/page_prev.json --site pbservices.ge
python3 seo/gsc_metrics.py brand-split --cur data/pq_cur.json --prev data/pq_prev.json --site pbservices.ge
python3 seo/gsc_metrics.py curve --query data/query_cur.json --site pbservices.ge
python3 seo/gsc_metrics.py benchmark                 # the dated post-AI-Overviews CTR benchmark
python3 seo/gsc_metrics.py benchmark --check         # exit 2 when it is older than max_age_months
python3 seo/gsc_metrics.py top-pages --page data/page_cur.json --by clicks --limit 50
python3 seo/gsc_metrics.py inspection --inspect data/inspect_1.json data/inspect_2.json
python3 seo/gsc_metrics.py unseen --page data/page_cur.json --urls sitemap.json
python3 seo/gsc_metrics.py truncation --file data/query_cur.json

# GA4
python3 seo/ga4_metrics.py breakdown --site pbservices.ge --ga4 data/ga4_lp.json --by channel
python3 seo/ga4_metrics.py reconcile --site pbservices.ge --ga4 data/ga4_lp.json \
        --gsc-totals data/totals_cur.json
python3 seo/ga4_metrics.py top-pages --site pbservices.ge --ga4 data/ga4_lp.json --organic
python3 seo/ga4_metrics.py misses --site pbservices.ge --ga4 data/ga4_lp.json --gsc-pages data/page_cur.json

# Crawler (live, no key needed)
python3 seo/site_crawl.py robots --site https://pbservices.ge --url https://pbservices.ge/ru/uslugi/
python3 seo/site_crawl.py sitemap --site https://pbservices.ge --limit 5000
python3 seo/site_crawl.py crawl --site https://pbservices.ge --limit 300 --delay 0.5 --profile pbservices.ge
python3 seo/site_crawl.py facts --url https://pbservices.ge/
python3 seo/site_crawl.py underlinked --crawl data/crawl.json --url https://pbservices.ge/x/

# Coverage, third-party estimates, paid/organic overlap
python3 seo/coverage.py --site pbservices.ge --gsc data/query_cur.json --gsc-pages data/page_cur.json
python3 seo/dfs_metrics.py serp-urls --serp data/serp.json --top 3
python3 seo/dfs_metrics.py anchor-mix --anchors data/anchors.json --site pbservices.ge
python3 seo/dfs_metrics.py link-gap --ours data/rd_ours.json --theirs data/rd_theirs.json --top 50
python3 seo/ads_metrics.py overlap --ads data/ads.json --query data/query_cur.json --currency EUR
```

---

## 9. Run folder anatomy

```
~/Documents/seo-reports/<site>/
  README.md                        plain-language map (written once)
  <date>/<skill>/                  one run
    report.md                      the report
    findings.json                  the same report as data (actions are structured for the brief)
    data/<name>.json               what the tool answered, exactly as received
    data/<name>.rows.json          the same answer as plain rows (only when it is a table)
    computed/<name>.json           the calculated figures the report quotes
    pipeline.json                  per-step status, seconds, retries, unavailable, truncated
    .run_state.json                the window; the only dates tools may receive
    context.json                   the evidence index (what was called, with which arguments)
  spreadsheets/<date>/*.csv        the history for Excel/Sheets + its own README.md
  _cache/<capability>/<hash>.json  saved answers reused by later runs
```

---

## 10. When something breaks

| Symptom | Command / fix |
|---|---|
| Gate red | `bash seo/check.sh`, then read the failing suite — it prints the failing assertion |
| Gate red on `resolve --check` | `python3 seo/resolve.py --write` |
| Gate red on `--validate-cached` | `python3 seo/mcp_client.py` (refresh the cached tool schemas) |
| `plan uses X, not a runtime arg` | the registry owns the fixed args; only `runtime` arguments may be passed |
| `window … matches neither the run window …` | the call's dates do not belong to this run; use `--allow-window "reason"` only to document an exception |
| `needs the 'dataforseo' server` | `seo-backlink-check` fails closed; add DataForSEO to `.roo/mcp.json` and set `servers.dataforseo.configured` |
| Figure refused by the number check | it is not in `data/` or `computed/` — the report is quoting something that was never returned |
| `run already seeded` | use `--tag`, a new day, or `--force` |
| Nothing older than N days to prune | retention works; runs are recent |

---

## 11. Where to change what

| I want to… | File |
|---|---|
| add or fix a capability (server/tool/args) | [`capabilities.json`](capabilities.json) → `resolve.py --write` → `--map` |
| change what a report says or checks | the skill's `SKILL.md` in [`.agents/skills/`](../.agents/skills/) (tokens, then `--write`) |
| add/remove a data step for a report | [`data-plans/<skill>.json`](data-plans/) → `--check-plans` |
| change a threshold (decay, striking distance, CTR) | [`config/sites/<domain>.json`](config/sites/) `thresholds` |
| change brand terms, categories, tracked keywords | [`config/rules/<domain>.json`](config/rules/) → `rules.py validate` |
| change retention, cadence, run location | [`config/settings.json`](config/settings.json) |
| change the report layout or wording rules | [`references/report-structure.md`](references/report-structure.md), [`references/conciseness-directives.md`](references/conciseness-directives.md) |
| change what the findings file may contain | [`references/findings-schema.json`](references/findings-schema.json) (+ `report/schema_lite.py` if a new keyword is needed) |
