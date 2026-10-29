# Audit — SEO Skills Set (18 `seo-*` skills)

**Date:** 2026-10-29 · **Auditor:** code mode · **Benchmark:** [`kinsta-logs`](../.agents/skills/kinsta-logs/SKILL.md) (scope-adjusted per [`seo-skills-kinsta-alignment-plan.md`](seo-skills-kinsta-alignment-plan.md) Part 10)
**Scope:** `.agents/skills/seo-*/SKILL.md` (18 skills) + the `seo/` infrastructure they depend on (registry, resolver, report pipeline, tests).

> **Status: ALL FINDINGS RESOLVED (2026-10-29).** H1–H4, M1–M8 applied; `bash seo/check.sh` ALL GREEN after the fixes (79/79 tests, live-schema validation incl. the new `gsc.pagespeed_a11y` capability). M9 (`domain-knowledge.md` review) remains for the next scheduled audit. Changes: registry v5 (`adsense.report` gains `DATE`/`DOMAIN_NAME` dimensions; new `gsc.pagespeed_a11y`), site-profile schema + profile gain `language_paths` (EN `/`, RU `/ru/`, AR `/ar/`, ZH `/zh/`), `seo-monetisation` rewritten to the URL-channel reality, 12 skill-specific Troubleshooting rows across 6 skills, path-prefix language derivation in `seo-brand-split`, Indexing API caveat in `seo-indexation`, a11y step in `seo-technical`, registry/profile AI-source reconciliation wording, and template hygiene (deduped audience sections, real `--skill` names, per-skill Privacy enumeration) across all 18 skills.

---

## 1. Verification evidence (what was mechanically checked, not assumed)

| Check | Result |
|---|---|
| `python3 seo/resolve.py --check` | ✅ OK — tokens resolve, no alias drift, expanded specs match registry, policies sane, dimension/metric names valid |
| `python3 seo/resolve.py --validate-live` (spawns each MCP server, checks tool + args against live `inputSchema`) | ✅ OK — every capability validates against live schemas (`dataforseo` skipped as optional/unconfigured) |
| Full CI gate `bash seo/check.sh` | ✅ **ALL GREEN** — 79/79 tests across 14 files (incl. `test_skill_docs.py` 6/6 doc-contract, `test_skill_findings.py` 3/3, `test_report_validate.py` 9/9) |
| Residual `{{cap:}}` / `{{site:}}` tokens in committed skills | ✅ 0 |
| All `../../../seo/...` link targets in every SKILL.md | ✅ all exist |
| Tool names referenced in skills vs. connected MCP servers (`search-console`, `analytics`, `google-ads`, `google-ads-planner`) | ✅ all exist on the live servers (incl. `seo_audit` types `striking_distance`/`cannibalization`/`low_ctr`/`quick_wins`/`recommendations`/`low_hanging_fruit`/`brand_vs_nonbrand`/`lost_queries`, `genai_query_insights`, `compare_engines`, `adsense_*`, `analytics_advanced`, `pagespeed_analyze`, `schema_validate`) |
| Registry `policy` blocks (retry/timeout/degrade) | ✅ 9 present; `adsense.*` carries `on_error: degrade` |

**Bottom line:** no run-breaking defects. The set's mechanical spine (registry → expansion → live validation → tests) is sound and actually enforced.

---

## 2. Issue register

Severity: 🔴 breaks runs or produces wrong output · 🟡 can produce misleading output or violates own contract · 🟢 cosmetic/maintainability.

### 🔴 Critical
_None found._ CI is green against live schemas; no broken links, tokens, or tool references.

### 🟡 High

| # | Location | Issue | Evidence |
|---|---|---|---|
| H1 | [`seo-monetisation/SKILL.md`](../.agents/skills/seo-monetisation/SKILL.md) — description, Data Sources, Workflow steps 2–4, Output | **Page-level AdSense earnings are not obtainable from the tool as specced.** The workflow says "earnings/impressions by page", "join on page", "Rank pages by earnings". The `adsense_report` tool's dimension enum is `DATE, WEEK, MONTH, DOMAIN_NAME, COUNTRY_NAME, PLATFORM_TYPE_NAME, AD_UNIT_*, CUSTOM_CHANNEL_*, PRODUCT_*, URL_CHANNEL_ID` — there is **no page dimension**. Page-level earnings exist only if the publisher manually configured URL channels (`URL_CHANNEL_ID`); otherwise the finest grain is `DOMAIN_NAME`. The registry default (`{"dateRange": "LAST_30_DAYS"}`, no dimensions) returns totals only. The skill's headline promise ("which pages carry the revenue") will fail or be fabricated unless it degrades to domain/URL-channel level and says so. | MCP `adsense_report` schema; [`seo/capabilities.json:42`](../seo/capabilities.json) |
| H2 | All 18 skills — Troubleshooting | **Troubleshooting tables are largely boilerplate.** 10 of 18 skills ship only the two generic rows ("Tool/server error", "Empty/zero results"). The benchmark's table ([`kinsta-logs/SKILL.md:165-178`](../.agents/skills/kinsta-logs/SKILL.md)) has 10 battle-tested, symptom-specific rows. Only `seo-keyword-research`, `seo-technical`, `seo-cross-engine`, `seo-monetisation`, `seo-indexation`, `seo-serp-features`, `seo-internal-links`, `seo-content-refresh`, `seo-brand-split` add even one specific row. `seo-audit` — the flagship — has none. | e.g. [`seo-audit/SKILL.md:96-101`](../.agents/skills/seo-audit/SKILL.md) |
| H3 | [`seo-brand-split/SKILL.md`](../.agents/skills/seo-brand-split/SKILL.md) — Workflow step 6 | **Per-language brand split is an unlabelled heuristic.** GSC has no language dimension; segmenting branded/non-branded "per language (RU/EN/ZH/AR)" requires classifying query *text* by script/language — a heuristic the skill doesn't label as such, violating its own "Keep every estimate / heuristic label" rule (which it states for other skills but not here). Also unverified whether `brand_terms` are per-language. | Workflow step 6 vs. Determinism section |
| H4 | [`seo-indexation/SKILL.md`](../.agents/skills/seo-indexation/SKILL.md) — Workflow step 6 | **`indexing_submit` presented as a routine action without the platform caveat.** The Google Indexing API officially supports only JobPosting/BroadcastEvent content; general pages go through Bing/IndexNow or are effectively nudges. The skill should state expected efficacy and method (`standard`/`index_now`) instead of implying submission = indexing. | Data Sources row 4 + Workflow step 6 |

### 🟢 Medium / Low

| # | Location | Issue |
|---|---|---|
| M1 | All 18 skills | **Duplicated audience blocks.** `## Scope & Audience` and `## Report Audience & Purpose` repeat the same audience bullet verbatim. Two sections, one fact — drift risk. Merge or keep audience in exactly one. |
| M2 | All 18 skills — Deliverable pipeline step 0 | `--skill <name>` placeholder never filled with the actual skill name; the reader must substitute mentally. `seo-audit` does the same with `--days 90` correctly, so the pattern exists. |
| M3 | All 18 skills | Missing blank line between the `report-export` delegation bullet and `## Configuration`. Renders, but sloppy and inconsistent with the rest of the formatting. |
| M4 | [`seo-audit/SKILL.md`](../.agents/skills/seo-audit/SKILL.md) step 4 | Whole-site diff of two `analytics_query` pulls with **no `rowLimit` guidance** — `seo-competitor-gap` (step 4) explicitly says "high rowLimit"; the audit that needs the fullest extract doesn't. Risk of silently truncated diffs on larger sites. |
| M5 | [`seo-content-refresh/SKILL.md`](../.agents/skills/seo-content-refresh/SKILL.md) step 6 | Broken grammar: "(importance = in `python3 ... --get priority_pages` or mapped to a `python3 ... --get services` line)". Readable but obviously unedited. |
| M6 | All 18 skills — Privacy & Retention | Uniform boilerplate: "no data leaves to a third party unless the skill explicitly uses `tavily`/`dataforseo`" — but no skill states *whether it does*. The benchmark itemizes every third-party call (ipinfo.io, probe UA, tavily). Per-skill third-party enumeration is the benchmark standard. |
| M7 | Skills set (coverage) | **Accessibility is uncovered** — no skill addresses a11y signals (alt text, ARIA, contrast) even as part of `seo-technical`. Adjacent to technical SEO and explicitly in the review criteria; currently absent. |
| M8 | [`seo-ai-visibility/SKILL.md`](../.agents/skills/seo-ai-visibility/SKILL.md) Workflow | The AI-referrer filter literal (`chatgpt.com`, `chat.openai.com`, …) is expanded inline 4× in this one skill (registry-expanded, so consistent today) — but step 2's instruction to "extend the filter if the profile adds engines" edits a registry-expanded literal by hand, creating drift the next `resolve.py --write` will silently overwrite. The filter extension path should go through the registry/site profile, not hand-editing the skill text. |
| M9 | `seo/` references | `domain-knowledge.md` content not verifiable in this audit (not read); the CTR bands `seo-opportunity` depends on live there. Flagged for the next review, not an issue per se. |

### Edge cases handled well (credit)
- Planner 429 `RESOURCE_EXHAUSTED` → bounded 40 s retry budget < 60 s MCP client timeout, documented in skill + tested (`test_planner_limits.py`, `test_planner_server.py`).
- Bing/AdSense/GBP/DataForSEO absence → explicit "state it and stop/degrade", with `findings.unavailable` rendered as a **Data availability** report section and enforced by `validate_report.py`.
- GSC ~2-day lag → "never include today" in every Determinism section.
- Savings/volume/value numbers → mandatory **estimate** labels; never-fabricate rules.
- Ads account with zero spend → "moot, not failed" (`seo-vs-ads` Fallbacks) — a genuinely thoughtful edge case.

---

## 3. Coverage of essential SEO domains

| Domain | Coverage | Notes |
|---|---|---|
| Technical SEO | ✅ `seo-technical` (CWV LCP/INP/CLS mobile+desktop, crawl health) | solid |
| Structured data | ✅ `seo-technical` (`schema_validate`, required types per page) | solid |
| Performance | ✅ CWV via PageSpeed, mobile vs desktop | solid |
| Indexation/crawl | ✅ `seo-indexation` (coverage, sitemaps, inspection, submit) | see H4 |
| On-page / content | ✅ `seo-content-brief`, `seo-serp-features`, `seo-internal-links` | strong |
| Content strategy | ✅ `seo-keyword-research`, `seo-competitor-gap`, `seo-content-refresh`, `seo-opportunity` | strong |
| Links | ✅ internal + `seo-backlink-check` (degrades honestly without DataForSEO) | honest |
| Analytics | ✅ GA4 cross-checks in `seo-audit`, `seo-ai-visibility`, `seo-backlink-check`; GSC everywhere | strong |
| Local | ⚠️ `seo-local` ships pending GBP — declared, degrades | by design |
| Monetisation | ⚠️ `seo-monetisation` — see H1 | flawed premise |
| **Accessibility** | ❌ none | **gap (M7)** |
| GEO/AI search | ✅ `seo-ai-visibility` (real GA4 referrals, heuristic labelled) | ahead of most toolkits |
| Log-file / crawl-budget SEO | ➖ out of scope (kinsta-logs covers ops logs) | not penalized |

Coverage is genuinely broad — wider than typical skill packs, and the GEO/AI-visibility angle is ahead of common practice.

---

## 4. Benchmark comparison vs `kinsta-logs` (scope-adjusted)

The benchmark solves a *script-fetchable, fixed-format* problem; SEO skills are *MCP-mediated* (the agent calls tools; scripts can't). Per alignment-plan Part 10, the correct standard is therefore "OAB adapted", not "OAB copied". Judged that way:

| Benchmark principle | SEO set status |
|---|---|
| P1/P2 OAB + LLM-never-hand-edits-report | ✅ Adapted correctly: findings JSON → `build_report.py` → **mandatory** `validate_report.py` in all 18 skills; validator test-covered |
| P3 Progressive disclosure | ✅ Lean SKILL.md (~109–141 lines) + shared `seo/references/` contracts; deliberate choice to keep small threshold tables inline (plan Tier 3) is defensible |
| P5 State files | ✅ Right-sized: `.run_state.json` via `seo/orchestrate.py` (optional), not per-skill ceremony |
| P6 Mechanical validation of LLM output | ✅ `validate_report.py` (metric/URL/as-of/unavailable/coverage checks, 9 tests) — the direct analogue of `verify_urls.py` |
| P10 Fixed SKILL.md contract | ✅ Uniform 20-section contract, **mechanically enforced** by `test_skill_docs.py` — the benchmark has no such lint |
| P11 Troubleshooting specificity | ❌ Weaker (H2) — benchmark's table is symptom-specific from production scars |
| P13 Retry/degrade + pinned versions | ✅ 9 registry `policy` blocks; planner budget pattern; `seo/requirements.txt` |
| P14 Tests w/ fixtures | ✅ 79 tests, fixtures present; benchmark-style per-skill findings tests exist (`test_skill_findings.py`) |
| P15 Determinism | ✅ `window.py` + as-of line + estimate labels in every skill |
| Single source of truth | ✅ **Stronger than benchmark**: one registry expanded everywhere + validated against *live* MCP schemas — kinsta-logs has no equivalent |
| Privacy per third-party call | ⚠️ Generic (M6) vs. benchmark's itemized list |
| Battle-tested specificity (tribal knowledge, history files) | ⚠️ Partial: site action history exists (`site_profile.py --history`) — a real differentiator; per-skill troubleshooting hasn't accumulated scars yet |

---

## 5. Rating

**8.5 / 10** (benchmark-adjusted).

Justification:
- **Architecture (10/10):** registry-as-source-of-truth with live-schema validation is *better* than the benchmark's equivalent; the OAB adaptation is the right scope call, not a shortcut.
- **Correctness (8/10):** zero run-breakers, but H1 (monetisation page-level premise) and H3/H4 (unlabelled heuristics/caveats) can produce misleading output in specific skills.
- **Reliability culture (9/10):** never-fabricate, estimate labels, mandatory validation, degradation *rendered into the report* and enforced by the validator — rare and excellent.
- **Coverage (8/10):** 18 skills spanning the domain map incl. GEO; minus accessibility and the GBP/DataForSEO halves that are pending by design (not penalized, but not creditable either).
- **Maintainability (8/10):** doc-contract tests + uniform template; minus audience duplication (M1), placeholders (M2), and boilerplate troubleshooting (H2).
- **Maturity vs benchmark (7.5/10):** kinsta-logs reads like it survived production incidents; the SEO set reads well-engineered but younger — its Troubleshooting/Privacy sections haven't accumulated operational scars.

---

## 6. Prioritized remediation

### Critical fixes — none blocking; H1 is the nearest
1. **H1 — Fix `seo-monetisation` premise.** Change Data Sources/Workflow/Output to: default = `DOMAIN_NAME`/date-level earnings; page-level only via `URL_CHANNEL_ID` with an explicit "requires URL channels configured in AdSense" caveat; if absent, record `findings.unavailable = {source: adsense_url_channels, affects: page-level earnings}` and rank **organic pages by clicks with domain-level RPM overlay** instead. Update the skill `description` ("which pages earn") to match reality.

### High-value improvements
2. **H2 — Specific Troubleshooting rows** for the 10 boilerplate-only skills (2–4 rows each from the known failure modes already documented in each skill's Fallbacks/Notes — e.g. `seo-audit`: GA4 missing → GSC-only half; `seo-opportunity`: planner 429 → estimates).
3. **H3 — Label the per-language brand split as a heuristic** in `seo-brand-split` (script/lexicon classification), and state whether `brand_terms` are per-language.
4. **H4 — Add the Indexing API caveat** to `seo-indexation` (JobPosting/BroadcastEvent limitation; prefer IndexNow/Bing for general pages; set expectations).
5. **M8 — Move the AI-referrer list into the registry/site profile** (`ai_sources` already exists in the profile) so `seo-ai-visibility` step 2 extends it through data, not hand-edits that `--write` will overwrite.

### Optional enhancements
6. **M1/M3/M5** — template hygiene: dedupe audience sections, fix the missing blank line before `## Configuration`, fix `seo-content-refresh` step 6 grammar. One sed pass + `test_skill_docs.py` stays green.
7. **M2** — fill `--skill <name>` per skill in the pipeline snippet.
8. **M4** — add "high `rowLimit`" guidance to `seo-audit` step 4 (mirror `seo-competitor-gap`).
9. **M6** — per-skill third-party enumeration in Privacy (copy the benchmark's itemized pattern).
10. **M7** — decide on accessibility: either add an a11y subsection to `seo-technical` (alt-text/ARIA checks via fetched pages) or state explicitly in Scope that a11y is out of scope.
11. **M9** — next review: read `seo/references/domain-knowledge.md` and verify the CTR bands `seo-opportunity` cites.

*Effort estimate: items 1–5 ≈ half a day total, all docs-only; none touches the registry, pipeline, or tests except adding rows/words that `test_skill_docs.py` already tolerates.*
