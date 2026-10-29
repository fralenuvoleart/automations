# SEO Skills — Gap Closure Plan

**Status:** proposed
**Date:** 2026-10-29
**Scope:** close the coverage gaps flagged in the SEO-value review, and add a deterministic, modular layer for personalised SEO/GEO criteria.

---

## 0. Context & invariants

The existing `seo/` layer is the template to follow. Every addition must preserve these invariants:

1. **Capability registry is the single source of truth** — [`seo/capabilities.json`](../seo/capabilities.json); skills reference `{{cap:<id>}}` tokens; [`seo/resolve.py`](../seo/resolve.py) expands them. Never hand-edit tool names.
2. **Deterministic windows** — [`seo/window.py`](../seo/window.py); absolute `YYYY-MM-DD`; as-of line in every report.
3. **Mechanical report pipeline** — findings JSON ([`findings-schema.json`](../seo/references/findings-schema.json)) → [`build_report.py`](../seo/report/build_report.py) → **mandatory** [`validate_report.py`](../seo/report/validate_report.py) `--data`.
4. **Skill contract** — frontmatter + required sections (enforced by [`test_skill_docs.py`](../seo/tests/test_skill_docs.py)); one job per skill; `## Fallbacks` + `## Pending Data Sources` in every skill.
5. **Graceful degradation** — a missing source is *stated*, never guessed ([`conciseness-directives.md`](../seo/references/conciseness-directives.md) rule 1/7).
6. **CI gate** — [`seo/check.sh`](../seo/check.sh) (`--check` + `--validate-live` + tests).

**Two standing constraints from the user:**
- **`seo-ai-visibility` is a primary skill** (AI engines ≈ 10% of searches) — it is *not* a "nice to have"; treat it as tier-1.
- **DataForSEO is absent by design.** Every skill that *could* use it must degrade gracefully **and the report must say so** — this drives a new report-level requirement (§5).

---

## 1. Foundation — Site Profile layer (personalised criteria, deterministic & modular)

### Answer to the question: **Yes — and it fits the existing architecture exactly.**

SEO/GEO strategy is personalised (priority keywords, priority pages, services, markets, competitors, brand terms). Today that knowledge lives only in the LLM's head per run — non-deterministic and unauditable. The `{{cap:}}` pattern already solves the identical problem for *tools*; the same pattern solves it for *strategy*.

### Design (mirrors the capability registry)

| Artifact | Purpose |
|---|---|
| [`seo/config/site-profile.schema.json`](../seo/config/site-profile.schema.json) | JSON Schema for a site profile (validated in CI). |
| `seo/config/sites/<domain>.json` | One profile per site: `brand_terms`, `priority_keywords`, `priority_pages`, `services`, `markets` (country/language), `competitors`, `ai_sources`, `thresholds` (per-site overrides). |
| [`seo/site_profile.py`](../seo/site_profile.py) | Loader/resolver: `--site <domain> --get <key>` → deterministic JSON; `--validate` checks the schema; `--list` shows profiles. |
| `{{site:<key>}}` tokens | Skills reference profile values; [`resolve.py`](../seo/resolve.py) `--write` expands them (extend `TOKEN_RE` to `\{\{(cap|site):…\}\}`). |
| `resolve.py --check` | Fails on an unknown `{{site:}}` key or a profile that violates the schema. |

### Why this is the right call
- **Deterministic** — the same profile yields the same report inputs; no per-run guessing of "which keywords matter".
- **Modular** — one file per site; adding a site is data, not code.
- **Auditable** — schema + tests; the strategy is version-controlled.
- **Composable** — skills consume it uniformly; `validate_report.py` can enforce *coverage* (§5).
- **Consistent** — identical mechanics to `{{cap:}}`, so no new mental model.

### Guardrails
- The profile is **data only** (no logic, no thresholds-as-code beyond numeric overrides).
- Keep it small: only fields a skill actually consumes.
- Never let a profile *fabricate* data — it selects/prioritises, it does not invent metrics.

---

## 2. Registry additions (new capabilities)

Add to [`seo/capabilities.json`](../seo/capabilities.json) (then `resolve.py --check` + `--map`):

| Capability | Server → tool | Args | Used by |
|---|---|---|---|
| `gsc.brand_split` | `search-console` → `seo_audit` | `{"type": "brand_vs_nonbrand"}` | `seo-brand-split` |
| `gsc.quick_wins` | `search-console` → `seo_audit` | `{"type": "quick_wins"}` | `seo-audit` |
| `gsc.recommendations` | `search-console` → `seo_audit` | `{"type": "recommendations"}` | `seo-audit` |
| `gsc.low_hanging_fruit` | `search-console` → `seo_audit` | `{"type": "low_hanging_fruit"}` | `seo-audit` |
| `gsc.sitemaps` *(exists, unused)* | `search-console` → `sitemaps_list` | `{}` | `seo-indexation` |
| `gsc.indexing` *(exists, unused)* | `search-console` → `indexing_submit` | `{}` | `seo-indexation` |
| `gsc.compare_engines` *(exists, unused)* | `search-console` → `compare_engines` | `{}` | `seo-cross-engine` |
| `ga4.realtime` *(exists, unused)* | `analytics` → `run_realtime_report` | `{"dimensions": ["unifiedScreenName"], "metrics": ["activeUsers"]}` | `seo-audit` (optional) |
| `adsense.report` *(new)* | `search-console` → `adsense_report` | `{}` | `seo-monetisation` (conditional) |
| `adsense.accounts` *(new)* | `search-console` → `adsense_accounts` | `{}` | `seo-monetisation` (conditional) |

`ga4.funnel` is now unused (replaced in `seo-ai-visibility`) — keep it in the registry (harmless) or remove it; either way `--check` stays green.

---

## 3. New skills

Each follows the full contract: frontmatter (`name`/`description`/`license`/`compatibility`), mechanical-vs-analytical banner, `Scope & Audience`, `Report Audience & Purpose`, `Memory-Bank Isolation`, `When to Use`, `When NOT to Use`, `Requires`, `Data Sources`, `Workflow`, `Determinism`, `Output` (+ pipeline), `Fallbacks`, `Pending Data Sources`, `Troubleshooting`, `Files`, `Related / Delegation`, `Configuration`, `Privacy & Retention`, `Output Structure`.

### Tier 1 (highest value)
1. **`seo-technical`** — technical SEO + Core Web Vitals.
   - Sources: `pagespeed_analyze`, `schema_validate`, `inspection_inspect`, `site_health_check`.
   - Output: CWV (LCP/INP/CLS) per priority page, mobile vs desktop, structured-data coverage, crawlability flags.
   - Degradation: PageSpeed API unavailable → state it; still report schema + inspection.
2. **`seo-indexation`** — index coverage + sitemap health.
   - Sources: `site_health_check` (`crawl_issues`), `sitemaps_list`, `inspection_inspect`, `indexing_submit`.
   - Output: indexed vs excluded, "Crawled — currently not indexed", sitemap status, submit list for priority pages.
   - Degradation: none (GSC-only).
3. **`seo-brand-split`** — brand vs non-brand.
   - Sources: `seo_audit` (`brand_vs_nonbrand`), `analytics_query`, site-profile `brand_terms`.
   - Output: branded vs non-branded clicks/impressions trend, non-brand growth (the real SEO signal).
   - Degradation: none (GSC-only).
4. **`seo-content-refresh`** — decay + refresh priority.
   - Sources: `analytics_compare` (`period_over_period`), `analytics_query`, site-profile `priority_pages`.
   - Output: decaying pages ranked by clicks lost × priority weight; refresh vs consolidate vs retire.
   - Degradation: none (GSC-only).

### Tier 2
5. **`seo-opportunity`** — traffic value / opportunity sizing.
   - Sources: `analytics_query`, `google-ads-planner` (`generate_keyword_ideas` for CPC), site-profile `services`.
   - Output: estimated monthly value of striking-distance + gap keywords (traffic × CPC), labelled **estimate**.
   - Degradation: planner unavailable → use `seo_keywords_research` estimates, labelled.
6. **`seo-serp-features`** — snippet / PAA capture.
   - Sources: `dataforseo` SERP (optional) → fallback web search; `analytics_query` for current positions.
   - Output: featured-snippet + PAA opportunities on priority keywords, with the answer format to use.
   - Degradation: **DataForSEO absent → build from web search, state it** (per the standing constraint).
7. **`seo-internal-links`** — internal link audit.
   - Sources: `analytics_query` (page dimension), `inspection_inspect`; **needs a crawl** for true orphan/link-equity analysis.
   - Output: orphan/under-linked priority pages, suggested internal links + anchors.
   - Degradation: no crawler → GSC-page-level approximation, stated; flag "full audit needs a crawl source".
8. **`seo-cross-engine`** — Google vs Bing.
   - Sources: `compare_engines`, `analytics_query`.
   - Output: per-engine query/page matrix, where Bing over/under-indexes.
   - Degradation: Bing not connected → state it.

### Tier 3 (conditional)
9. **`seo-local`** — local pack / Google Business Profile. **Pending data source** (no GBP API wired) → skill ships with `## Pending Data Sources` and degrades to "local intent queries from GSC" only.
10. **`seo-monetisation`** — AdSense earnings vs organic. **Conditional** on the site monetising; ships only if `adsense.*` is configured.

---

## 4. Enhancements to existing skills

- **`seo-audit`** — wire the purpose-built `seo_audit` types (`quick_wins`, `recommendations`, `low_hanging_fruit`) instead of deriving quick wins by hand; add an optional realtime snapshot (`ga4.realtime`); delegate brand split to `seo-brand-split`.
- **`seo-ai-visibility`** — **elevate to tier-1** (10% of searches): add the site-profile `ai_sources` list to the filter, and a "AI share of organic" headline metric.
- **`seo-backlink-check` / `seo-competitor-gap`** — keep the graceful degradation, and make the **report** state the unavailable half explicitly (§5). No behaviour change beyond wording + the report block.
- **All skills** — consume `{{site:priority_keywords}}` / `{{site:priority_pages}}` where relevant so prioritisation is deterministic.

---

## 5. Report pipeline changes (graceful degradation *in the report*)

This is the direct answer to "important it degrades gracefully in the reports".

1. **`findings-schema.json`** — add two optional top-level blocks:
   - `"unavailable": [{"source": "dataforseo", "affects": "backlink profile", "reason": "not configured"}]`
   - `"coverage": {"priority_keywords": [...], "priority_pages": [...], "covered": [...], "missing": [...]}`
2. **`build_report.py`** — render a **"Data availability"** section (from `unavailable`) and a **"Coverage vs site profile"** section (from `coverage`), both near the top.
3. **`validate_report.py`** — enforce:
   - every `unavailable` source is named in the report;
   - every site-profile priority keyword/page is either covered or listed under `missing` (no silent omission);
   - existing checks (as-of line, estimate labels, URL-vs-source) unchanged.
4. **`report-structure.md`** — document the two new sections in the required order.

---

## 6. Tests & CI

- `seo/tests/test_site_profile.py` — schema validation, `--get` determinism, unknown-key failure.
- Extend `seo/tests/test_resolve.py` — `{{site:}}` token expansion + unknown-key failure.
- Extend `seo/tests/test_skill_docs.py` — new skills must carry the full section set (already enforced).
- Extend `seo/tests/test_report_build.py` / `test_report_validate.py` — `unavailable` + `coverage` rendering and enforcement.
- `seo/check.sh` unchanged (picks up new tests automatically).

---

## 7. Rollout order

| Phase | Deliverable | Why first |
|---|---|---|
| **1** | Site Profile layer (§1) + registry additions (§2) + report `unavailable`/`coverage` blocks (§5) | Foundation everything else consumes. |
| **2** | `seo-technical`, `seo-indexation`, `seo-brand-split`, `seo-content-refresh` | Highest-value gaps; all GSC/PageSpeed-only (no DataForSEO dependency). |
| **3** | `seo-opportunity`, `seo-serp-features`, `seo-internal-links`, `seo-cross-engine` | Second-order; some need DataForSEO/crawl (degrade gracefully). |
| **4** | `seo-local`, `seo-monetisation` | Conditional on data sources / monetisation. |
| **5** | `seo-audit` enhancements + `seo-ai-visibility` elevation | Consolidation once the new skills exist. |

---

## 8. Acceptance criteria

- `python3 seo/resolve.py --check` clean (tokens, aliases, expanded specs, policies, **semantic names**, **site-profile keys**).
- `bash seo/check.sh` green (all tests).
- Every new skill: full section set, `## Fallbacks` + `## Pending Data Sources`, degrades gracefully, and its report names any unavailable source.
- A report generated with DataForSEO absent **explicitly states** the missing backlink/competitor/SERP half.
- Site-profile priority keywords/pages are either covered or listed as `missing` in every report.
- No skill hand-edits tool names; no `{{cap:}}`/`{{site:}}` tokens survive into a rendered report.
