# Project Progress

## Completed

### Platform (`services/nodejs/`)
- Repo restructured to the `automations/` layout.
- Telegram bot operational — auto-reply, forwarding, relay mode for hidden-profile users, Integrately webhook, per-user rate limiting, retries.
- Cache warmer rewritten in JS — granular per-status stats, redirect tracking, concurrency guard, retries, persisted last-run summary.
- `docs/WARMER.md` documents warmer logic, cache-header semantics, and the warmer-vs-Kinsta-Analytics discrepancy.

### SEO/GEO skills toolkit (`.agents/skills/` + `seo/`)
- 13 `seo-*` skills (12 reports + weekly `seo-brief`) + `kinsta-logs` + `report-export` + `web-to-pdf`.
- Capability registry v8 + resolver (rendered cap/site/include blocks, generated Data Sources tables, live/cached schema validation, semantic dimension/metric checks).
- Scripted data layer: `seo/pipeline.py` + `seo/data-plans/` — cache-first pulls, evidence recording, analysis into `computed/`; row limits completed (split/page), temporary failures retried, write guard, fail-closed `requires_servers`.
- Report gate: findings validated against `findings-schema.json` (stdlib Draft-7 subset `seo/report/schema_lite.py`) + cross-field rules; every URL and figure checked against evidence and computed outputs (`number_check.py`); figures from data still cut at the row limit refused.
- Site rules (`seo/config/rules/<domain>.json` + `seo/rules.py`) — classification shared with the SEO sheet; site profiles + status-tagged action history. Profile data filled (`ads_customer_id`, `priority_pages`, `competitors`, `gsc_property`, `ga4_property`); brand rule confirmed by the owner: `пб сервис` and `gecrypto` are not brand terms.
- Analysis modules: GSC (movers, striking distance, low CTR with own-data CTR curve, cannibalization, decay classes, brand/language split, value model, totals, inspection summary), GA4 by the rules (channels, page types, languages, AI share, Search Console vs GA4), crawler (robots per path, sitemaps, link graph, hreflang, canonicals, page facts; robots.txt respected), DataForSEO and Ads helpers, coverage.
- Fixed run folders + shared cache in `~/Documents/seo-reports`; weekly `seo-brief` merges and ranks actions across reports.
- Shared `report-export` — Markdown→PDF (`npx md-to-pdf`/Chromium, WeasyPrint fallback) + SMTP email; one config with per-skill subjects.
- CI gate `seo/check.sh`: resolve check, cached schemas, data plans, CTR-benchmark age (warning), profiles, compile, all test suites (incl. repo-wide Markdown links).
- Reviews actioned: 2026-10-29 audit, 2026-10-30 audit (C/H/M/L), architecture audit v8 (A1–A4, A8, A9), external findings A-01…A-08 — status table in `activeContext.md`.
- Post-fix re-review (audit v10, `9a7eacd`; the audit file itself was in `plans/`, git-ignored and deleted after actioning): the six accepted fixes verified correct; six v9 claims withdrawn after checking (A-02 90-day pulls are shared, A-03, A-04 reachability + number check, A-11, kinsta-logs scope, `--resume`); 7.3/10. Then closed: schema enforced by the stdlib subset validator (gate green on a bare interpreter, 269 cases, `jsonschema` dev-only oracle), error classification by `StepFailed.kind` with the pattern as backstop, 120 s retry-wait budget per run, `gsc.diagnostics` optional in all plans, crawl UA in the robots JSON, brief distinguishes *due* from *cannot run (missing source)*.

- **Review fixes (2026-10-30)**: `--force` split from `--refresh` (force = overwrite the run folder and reuse the saved answers, so a rerun after fixing a source is cheap; refresh = fetch every call again, also overwriting; `test_force_overwrites_and_refresh_re_fetches`); `runs.csv` `tool_calls` now sums the real calls of pull steps only (a 90-day audit = 14, not 25); `pages.csv`/`queries.csv` select pulls by **capability** from `context.json` (so `page_w{i}`/`query_w{i}` weekly pulls appear, each with its own period, off-window lookback calls excluded) and the brief's weeks land in `totals.csv`; the export's CTR percentage keeps a value already in percent (`if abs(rate) > 1`), mirroring `gsc_metrics.load_rows`.
- **Alpha QA pass (2026-10-30)** — end-to-end rehearsal: pipeline → findings → `validate_report --data` → `build_report` → real PDF (chromium, 53 KB) → `send_email --dry-run` (SMTP login OK, recipients resolved); the `seo-brief` plan path validated clean. Fixed on the way: the weekly brief's figures were **untraceable** (digest aggregated without a `computed/` artefact) → `digest.build` now writes `computed/brief.json` and `--json` echoes it, no self-fulfilling `stated` list, with a test that the brief passes the gate; crawler **page title polluted by SVG icon `<title>`s** (16 `<title>` on the live homepage) → only the document's first title counts, icon labels become the anchor text only when a link has none; dry runs no longer mark compute steps as failed; dead `import copy` removed; `runs.py export` rejects an empty table list; dangling `plans/` link removed from the memory bank. Gate: 269 cases.
- `--force` now really re-fetches: the flag only overwrote an already-seeded run folder, so it never bypassed the cache — `run_step` skips the saved answer when forcing (test: `test_force_fetches_everything_again_instead_of_reusing_saved_answers`). `seo/COMMANDS.md` opens with an 8-row Essentials table (health check first, plain-language labels: "fetch the data again", "rewrite the Excel/Google Sheets files").
- Docs: `docs/SEO.md` (report guide) + `seo/COMMANDS.md` (command reference), linked from `README.md` and `seo/README.md`; every command in them was executed or `--help`-checked, and a test asserts the scripts they name exist (2026-10-30).
- Spreadsheet export + plain rows: `python3 seo/runs.py export --site D` → `<site>/spreadsheets/<date>/runs|totals|pages|queries|actions.csv` (oldest first, UTF-8 BOM, unwraps the tool wrapper); `data/<name>.rows.json` written beside the raw evidence; plain-language `README.md` in every site and export folder (2026-10-30).
- Retention is enforceable: `python3 seo/pipeline.py --prune` (also before a run); `gsc.sitemaps`/`gsc.health` now carry a 1-day cache TTL.

## In Progress

- None.

## Upcoming

- **Security**: rotate the Sevalla, Tavily and Kinsta API keys exposed in tracked `.roo/mcp.json`; untrack the file. Review its auto-approve lists (`sevalla.deployments.start` is auto-approved).
- **DataForSEO** — connect (`.roo/mcp.json` + `servers.dataforseo.configured` in `seo/capabilities.json`) to enable `seo-backlink-check` and the SERP/competitor sections; then set `serp_locations` in the profile.
- **Search Console bulk export to BigQuery** — owner decision; only route to history beyond 16 months (no backfill: starts when enabled).
- **Move earlier runs** from the repo's `.output/seo/` into `~/Documents/seo-reports` to keep their cache and history.
- **SEO sheet Apps Script** — switch it to read `seo/config/rules/pbservices.ge.json` (needs the script code).
- **Tavily schema cache** — run `python3 seo/mcp_client.py tavily` locally so `--validate-cached` covers `web.*`.
- **Google Business Profile** — connect to unlock map-pack analysis for local markets (`seo-audit`).
- WhatsApp bot integration (future); Python AI/NLP services (future).
