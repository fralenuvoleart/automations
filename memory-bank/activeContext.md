# Active Context

## Current Focus

`automations` — two service runtimes plus a shared Agent-Skills toolkit:

- `services/nodejs/` — Telegram bot + cache warmer (production, deployed on Sevalla).
- `services/python/` — placeholder for future AI/NLP services.
- `.agents/skills/` — Agent Skills (SEO/GEO toolkit, `kinsta-logs`, `report-export`, `web-to-pdf`).

## SEO/GEO skills toolkit (current state)

**15 skills** in `.agents/skills/`:
- **12 `seo-*` consolidated power skills** — `seo-audit`, `seo-ai-visibility`, `seo-backlink-check`, `seo-brand-split`, `seo-content-brief`, `seo-content-refresh`, `seo-indexation`, `seo-internal-links`, `seo-keyword-strategy`, `seo-paid-organic`, `seo-rank-tracking`, `seo-technical`.
- **`kinsta-logs`** — Kinsta server-log analysis.
- **`report-export`** — shared Markdown→PDF + email delivery; every report skill delegates to it.
- **`web-to-pdf`** — webpage→PDF.

**Non-skill SEO tooling** lives in `seo/`:
- `capabilities.json` — single source of truth (capability → server + tool + `args` + `runtime` + `desc`), registry v7.
- `resolve.py` — renders `{{cap:}}` / `{{site:}}` / `{{include:}}` tokens into marker blocks and re-renders them on every `--write`; `--check` / `--validate-cached` / `--validate-live` / `--map`.
- `record.py` (evidence), `gsc_metrics.py`, `site_crawl.py`, `dfs_metrics.py`, `ads_metrics.py` — deterministic run pipeline and analysis.
- `site_profile.py` — per-site profile + action history (`config/sites/<domain>.json` / `.history.md`).
- `coverage.py` — deterministic coverage block (flattened + per-language).
- `window.py` / `orchestrate.py` — deterministic windows (GSC lag 3, GA4 lag 2, snapshot; previous/YoY) + run seeding (no silent overwrite).
- `report/` — `build_report.py` (findings JSON → Markdown) + `validate_report.py` (mandatory).
- `references/` — shared contracts: `report-structure.md`, `conciseness-directives.md`, `data-source-map.md`, `capability-usage.md`, `domain-knowledge.md`, `findings-schema.json`.
- `check.sh` — CI gate, offline by default (`--check`, `--validate-cached`, profiles, compile, tests); `--live` adds live schema validation.

**MCP servers** (`.roo/mcp.json`): `search-console` (GSC/GA4/Bing/AdSense, OAuth), `analytics` (official GA4, service account), `google-ads` (service account), `google-ads-planner` (local, `seo/mcp-servers/`), `tavily`. **`dataforseo` is optional and not configured** — skills degrade gracefully and the report states the missing source.

**Credentials:** service account via `GOOGLE_APPLICATION_CREDENTIALS`; `search-console` OAuth in `~/.search-console-mcp-config.enc`; report email SMTP in `~/.config/report-export/email.json`.

## Sevalla services (current state)

- `services/nodejs/` — Telegram bot (`src/telegram-bot.js`) + cache warmer (`src/cache-warmer.js`), wired by `index.js`; shell scripts in `scripts/`; docs in `docs/WARMER.md`.
- Deployed on Sevalla — see `systemPatterns.md` for the Sevalla API rules (exec endpoint, backgrounding, bot 409 handling).

## Conventions

- Plan files → `plans/`.
- Read this memory bank before every task; update `activeContext.md` + `progress.md` after significant changes.
- Skill contract + CI: see `systemPatterns.md` and [`seo/README.md`](../seo/README.md).

## Recent Changes

- **2026-10-30**: Applied every proposal from the 2026-10-30 audit (C1–C5, H1–H16, M1–M19, L1–L11 + optional items): evidence recording and a real hallucination gate; `gsc_metrics.py` replaces the window-ignoring `seo_audit` tool; page metrics from `page` rows; `rowLimit 25000` + `engine google` pinned; site CTR curve + labelled heuristic; planner limits (20/10), first-page reads, historical-metrics tool; Indexing API opt-in; `site_crawl.py` for link graph/hreflang/robots; profile cleanup (brand terms out of priority keywords, `Category` removed, AI hosts extended, Ads language constants); status-tagged history; all 12 skills rewritten from tokens + shared includes; offline CI. `seo/check.sh` ALL GREEN (offline). `.roo/mcp.json` and how credentials are read were left unchanged.
- **2026-10-30**: Independent audit of the 12 `seo-*` skills + `seo/` → [`plans/seo-skills-audit-2026-10-30.md`](../plans/seo-skills-audit-2026-10-30.md). Rating **5.7/10**: 5 Critical (C1 evidence gate never verifies: `context.json` never populated; C2 `seo_audit`/`genai` ignore the resolved window; C3 page metrics from `query×page` lose anonymized clicks; C4 1,000-row truncation; C5 undefined CTR curve), 16 High, 19 Medium, 11 Low. 75/75 tests green but structural only. Separate: live API keys in tracked `.roo/mcp.json` in a public repo — rotate.
- **2026-10-29**: AdSense Pruning & Google Ads Isolation — permanently removed unused `adsense.accounts` and `adsense.report` capabilities from `seo/capabilities.json`; regenerated `seo/tool-map.md`; isolated the `google-ads` MCP server dependency exclusively to `seo-paid-organic`, guaranteeing that the other 11 SEO skills run with 100% independence if the AdWords server is unavailable. All 14 CI test suites passed (`seo/check.sh` ALL GREEN).
- **2026-10-29**: Physical Portfolio Consolidation (18 to 12 Power Skills) — executed physical consolidation of skills in `.agents/skills/`: created `seo-keyword-strategy` (consolidating keyword research, striking distance opportunity sizing, and competitor gap) and `seo-paid-organic` (paid vs organic GAQL waste elimination); absorbed `seo-serp-features` into `seo-content-brief`, `seo-local` into `seo-audit`, `seo-cross-engine` into `seo-rank-tracking`; pruned `seo-monetisation`, `seo-opportunity`, `seo-serp-features`, `seo-competitor-gap`, `seo-local`, `seo-cross-engine`, `seo-vs-ads`, `seo-keyword-research`. Locked in with updated CI tests. All 14 test suites passed (`seo/check.sh` ALL GREEN).
- **2026-10-29**: Portfolio Consolidation & Strategic Streamlining — pivoted `seo-monetisation` from publisher AdSense display ads to GA4 commercial conversion value and revenue attribution; merged striking distance opportunity sizing into `seo-keyword-research` (Fast-Track Quick Wins cluster with planner volume/CPC); restructured `seo-audit` into an Executive Macro Health Scorecard delegating deep tactical workflows; absorbed SERP feature capture targeting into `seo-content-brief`; integrated cross-engine divergence checks into `seo-rank-tracking`; decoupled GSC queries across skills using clean `gsc.query` (`["query"]`) and `gsc.page_query` (`["query", "page"]`) to prevent row truncation. All 14 CI test suites passed (`seo/check.sh` ALL GREEN).
- **2026-10-29**: Senior SEO/GEO Strategist upgrades implemented — updated `seo/references/domain-knowledge.md` and related skills with GEO entity disambiguation (Schema `sameAs`), AI crawler accessibility checks (`GPTBot`, `PerplexityBot`, `ClaudeBot`, etc.), international `hreflang` reciprocity checks, the Cannibalization Decision Matrix, the Information Gain & Quotability Scorecard, and healthy backlink anchor distribution benchmarks. All 14 CI test suites passed (`seo/check.sh` ALL GREEN).
- **2026-10-29**: Comprehensive SEO audit & resilience fixes applied — resolved missing `context.json` validation crash (seeded in `orchestrate.py`, graceful fallback in `validate_report.py`), fixed `KeyError: 'lag'` in `window.as_of_line()` and `KeyError: 'compareEndDate'` in `validate_report.py`, added Markdown table sanitization (pipes, newlines, None) in `build_report.py`, added schema/doc URL exclusion in hallucination validation, guarded file reading in `coverage.py`, added case-insensitive language lookup in `site_profile.py`, month enum guard in `google-ads-planner`, and filter dimension validation in `resolve.py`. All 14 CI test suites passed (`seo/check.sh` ALL GREEN).
- **2026-10-29**: `seo/README.md` brought to current state — status header (audit result + CI green), full 18-skill inventory table (answers / primary sources / degradation), `language_paths` documented, skill anatomy corrected to the real 20-section contract, GA4 capability count fixed.
- **2026-10-29**: Post-fix verification pass — full diff review (all edits intentional, config diffs minimal), adsense/dataforseo fallback coverage confirmed in all 9 referencing skills, fixed a pre-existing copy-paste bug in `seo-serp-features` Pending text, restored two `plans/` files deleted by an external process mid-session. `seo/check.sh` ALL GREEN.
- **2026-10-29**: SEO skills audit fixes applied (H1–H4, M1–M8) — registry v5 (`adsense.report` dimensions `DATE`/`DOMAIN_NAME`; new `gsc.pagespeed_a11y` capability), profile schema + `pbservices.ge.json` gain `language_paths`, `seo-monetisation` premise rewritten to AdSense URL-channel reality, `seo-technical` now covers accessibility (Lighthouse a11y category), 6 skills gained specific Troubleshooting rows, template hygiene across all 18 skills. `seo/check.sh` ALL GREEN.
- **2026-10-29**: Full audit of the 18 `seo-*` skills vs the `kinsta-logs` benchmark → [`plans/seo-skills-audit-2026-10-29.md`](../plans/seo-skills-audit-2026-10-29.md). Rating **8.5/10**. Verified green: `resolve --check`, `--validate-live`, 79/79 tests, zero residual tokens, zero broken links. Top findings: H1 `seo-monetisation` page-level AdSense premise (tool has no page dimension), H2 boilerplate Troubleshooting in 10/18 skills, H3 unlabelled per-language heuristic in `seo-brand-split`, H4 missing Indexing API caveat in `seo-indexation`, plus an accessibility coverage gap (M7).
- **2026-10-29**: Built out the SEO/GEO toolkit — 18 `seo-*` skills, the Site Profile layer (per-site criteria + action history), deterministic coverage, the report `unavailable`/`coverage` blocks, and the shared `report-export` skill (PDF + email, one config with per-skill subjects). CI gate `seo/check.sh` is green.
