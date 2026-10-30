# Active Context

## Current Focus

`automations` — two service runtimes plus a shared Agent-Skills toolkit:

- `services/nodejs/` — Telegram bot + cache warmer (production, deployed on Sevalla).
- `services/python/` — placeholder for future AI/NLP services.
- `.agents/skills/` — Agent Skills (SEO/GEO toolkit, `kinsta-logs`, `report-export`, `web-to-pdf`).

## SEO/GEO skills toolkit (current state)

**16 skills** in `.agents/skills/`: 13 `seo-*` (12 reports — `seo-audit`, `seo-ai-visibility`, `seo-backlink-check`, `seo-brand-split`, `seo-content-brief`, `seo-content-refresh`, `seo-indexation`, `seo-internal-links`, `seo-keyword-strategy`, `seo-paid-organic`, `seo-rank-tracking`, `seo-technical` — plus the weekly `seo-brief`), `kinsta-logs`, `report-export` (PDF + email for every report), `web-to-pdf`.

**How a report runs** (details in `systemPatterns.md` and [`seo/README.md`](../seo/README.md)):
1. `python3 seo/pipeline.py --skill S --site D` runs the skill's data plan (`seo/data-plans/`): seeds the run, pulls every source cache-first (Search Console windows over 25,000 rows split by date, GA4 paged, temporary failures retried), records evidence, runs the analysis scripts into `computed/`.
2. The agent only interprets `computed/` + `data/` and writes `findings.json`.
3. `validate_report.py` checks the findings against `findings-schema.json` (jsonschema), every URL and every figure against the evidence; `build_report.py` renders; the report is validated again.

**Non-skill SEO tooling** lives in `seo/`: `capabilities.json` (registry v8, single source of truth) + `resolve.py` (renders skills); `pipeline.py` + `data-plans/`; `mcp_client.py`; `record.py` (evidence + shared cache); `runs.py` + `config/settings.json`; `window.py` / `orchestrate.py`; analysis modules `gsc_metrics.py`, `ga4_metrics.py`, `rules.py`, `site_crawl.py`, `dfs_metrics.py`, `ads_metrics.py`, `coverage.py`, `digest.py`; `site_profile.py` + `config/sites/`; `config/rules/<domain>.json` (classification shared with the SEO sheet); `config/ctr-benchmark.json`; `report/` (`validate_report.py`, `number_check.py`, `build_report.py`); `references/`; `check.sh` (CI gate).

**Data location:** every run folder and the shared `_cache/` live in `run_root` = `~/Documents/seo-reports` (outside the repo; `python3 seo/runs.py root`). Runs made earlier under the repo's `.output/seo/` were not moved.

**MCP servers** (`.roo/mcp.json`): `search-console` (OAuth), `analytics` (GA4, service account), `google-ads` (service account), `google-ads-planner` (local, `seo/mcp-servers/`), `tavily`. **`dataforseo` is not configured**: optional sources in most skills (listed as unavailable), but `seo-backlink-check` requires it and refuses to run without it.

**Credentials:** service account via `GOOGLE_APPLICATION_CREDENTIALS`; `search-console` OAuth in `~/.search-console-mcp-config.enc`; report email SMTP in `~/.config/report-export/email.json`. Never change secrets, env vars or how credentials are read unless the owner asks.

## Sevalla services (current state)

- `services/nodejs/` — Telegram bot (`src/telegram-bot.js`) + cache warmer (`src/cache-warmer.js`), wired by `index.js`; shell scripts in `scripts/`; docs in `docs/WARMER.md`.
- Deployed on Sevalla — see `systemPatterns.md` for the Sevalla API rules (exec endpoint, backgrounding, bot 409 handling).

## Conventions

- Plan files → `plans/`. Audit documents there have been removed once actioned — don't link to them from durable docs (the repo-wide link test fails on dead links).
- Read this memory bank before every task; update `activeContext.md` + `progress.md` after significant changes.
- Skill contract + CI: `systemPatterns.md` and [`seo/README.md`](../seo/README.md). `kinsta-logs` is not to be used or edited.

## Review status (SEO toolkit)

| Review | Items | Status |
|---|---|---|
| Audit of the 18 skills (2026-10-29, 8.5/10) | H1–H4, M1–M8 | done; skills later consolidated to 12 + `seo-brief` |
| Audit 2026-10-30 (5.7/10) | C1–C5, H1–H16, M1–M19, L1–L11 | done (evidence gate, deterministic analysis, registry v7→v8) |
| Architecture audit v8 (8.1/10) | A1 row limits, A2 absent ≠ 0, A3 write guard, A4 record agent calls, A8 strict call log, A9 `seo/data-plans/` | done |
|  | A5 plan↔doc drift, A6 benchmark CI gate, A7 `seo-audit` as composer | rejected — Data Sources tables are generated from the plans and a test ties skill text to plan outputs; the CTR benchmark is the last, labelled tier; `seo-audit` shares the specialists' scripts and cached 90-day pulls, composing it would mix windows |
| External findings A-01…A-08 (2026-10-30) | schema not enforced, backlink fail-open, no retries, robots homepage-only / crawler ignored robots, repo links | done (jsonschema enforcement, `requires_servers`, transient retries, per-path robots verdicts + robots-respecting crawler, repo-wide link test) |
|  | composer, `gsc_metrics` split, computed-output schemas, error taxonomy, parallelism, renderer, log join | not adopted (low value here, or conflicts with the owner's "no Kinsta logs" rule) |

## Recent Changes

- **2026-10-30 — hardening** (branch `seo-hardening-2026-10-30`): `seo-backlink-check` fails closed without DataForSEO (`requires_servers`); robots.txt verdicts per priority page (`blocked_paths`) and the crawler respects robots.txt for every fetch (`skipped_by_robots`; unreachable robots.txt = nothing fetched); temporary failures retried (`policy.retry`, default 2; never writes; crashed servers restarted) with `retries` and per-step `seconds` in `pipeline.json`; findings validated with jsonschema against a strengthened `findings-schema.json` (hand-written checks only for cross-field rules); repo-wide Markdown link test; `run_root` = `~/Documents/seo-reports`; memory bank tidied.
- **2026-10-30 — v8 review fixes** (merged): row-limit completion (split/page, re-fetch of cut cache entries, `truncated`/`tainted` + number-check refusal), absent ≠ 0 in both readers + untracked key events, write guard (`policy.write`, `"confirm": true`, `--allow-write`), record instructions for every agent call, strict call log, `seo/plans/` → `seo/data-plans/`.
- **2026-10-30 — scripted data layer + number check** (merged): `seo/pipeline.py` + 14 data plans, skills' workflows reduced to interpretation, `mcp_client.Session`, `number_check.py`, new computes (totals, inspection, unseen, top pages, AI share, underlinked, SERP URLs, representatives); CTR curve = run window → site's last 12 months → dated post-AI-Overviews benchmark (`config/ctr-benchmark.json`).
- **2026-10-30 — earlier**: fixed run folder + shared cache + structured actions + `seo-brief`; SEO-sheet practices ported (target pages, top countries, Monday–Sunday weeks, GA4 by the rules, Search Console vs GA4 check, report definitions); the sheet's Rules + Keyword Setup tabs ported to `seo/config/rules/pbservices.ge.json`.
- **2026-10-29**: toolkit built and consolidated from 18 to 12 report skills; AdSense removed; `google-ads` isolated to `seo-paid-organic`.
