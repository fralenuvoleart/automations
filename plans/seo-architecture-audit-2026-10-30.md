# SEO Capability Framework — Architectural & Qualitative Audit

**Date:** 2026-10-30 · **Scope:** the 13 `seo-*` Agent Skills in [`.agents/skills/`](../.agents/skills/) and the supporting `seo/` runtime ([`seo/README.md`](../seo/README.md)) · **Method:** static reading of the registry, resolver, orchestration/evidence layer, shared contracts and every skill's rendered interface; no live API calls. Claims are grounded in file:line evidence.

> This is a **meta-audit of the toolkit's architecture**, not a site report. It complements the data-correctness audit in [`seo-skills-audit-2026-10-30.md`](seo-skills-audit-2026-10-30.md) (which scored *output correctness* 5.7/10). This report scores *systems design*.

---

## 0. Executive verdict

**Architecture grade: 8.1 / 10 — "Strong, well-factored, with two structural fault lines."**

The framework is materially better than typical agent-skill collections. It has a real single source of truth ([`seo/capabilities.json`](../seo/capabilities.json:1)), a deterministic render/validate loop ([`seo/resolve.py`](../seo/resolve.py:215)), a mandatory evidence pipeline ([`seo/record.py`](../seo/record.py:167)), a schema-validated findings contract ([`seo/references/findings-schema.json`](../seo/references/findings-schema.json:1)), and a portable CI gate ([`seo/check.sh`](../seo/check.sh:1)). The separation of *acquisition* (MCP servers), *evidence* (`record.py`), *computation* (`*_metrics.py`), *synthesis* (LLM → `findings.json`) and *rendering* (`build_report.py`) is a genuine layered architecture.

Two structural fault lines keep it out of the 9+ band:

1. **The deterministic/probabilistic boundary is enforced by convention, not by construction.** The registry is machine-validated, but the *workflow* that consumes it is prose addressed to an LLM. Nothing prevents the agent from skipping `record.py`, inventing a threshold, or calling a window-ignoring tool. The evidence gate is only as strong as the agent's compliance.
2. **`seo-audit` is a god-skill.** It calls 13 capabilities across 9 steps and re-implements slices of four specialist skills (declining pages, quick wins, indexation, engagement/AI). It is the single largest cohesion and redundancy liability in the portfolio.

---

## 1. Functional taxonomy matrix

### 1.1 Runtime layers (execution tiers)

| Tier | Responsibility | Artifacts | Determinism |
|---|---|---|---|
| **T0 — Orchestration** | Resolve the window, seed the run, enforce folder policy | [`orchestrate.py`](../seo/orchestrate.py:34), [`window.py`](../seo/window.py), [`runs.py`](../seo/runs.py) | Deterministic |
| **T1 — Acquisition** | Fetch raw data from external systems | 6 MCP servers + local [`site_crawl.py`](../seo/site_crawl.py) | External / non-deterministic |
| **T2 — Evidence** | Persist raw responses + provenance; shared cache | [`record.py`](../seo/record.py:167) → `context.json`, `data/`, `_cache/` | Deterministic |
| **T3 — Computation** | Turn raw JSON into metrics | [`gsc_metrics.py`](../seo/gsc_metrics.py), [`ga4_metrics.py`](../seo/ga4_metrics.py), [`dfs_metrics.py`](../seo/dfs_metrics.py), [`ads_metrics.py`](../seo/ads_metrics.py), [`coverage.py`](../seo/coverage.py), [`rules.py`](../seo/rules.py), [`digest.py`](../seo/digest.py) | Deterministic |
| **T4 — Synthesis** | Write `findings.json` (verdict, sections, actions) | LLM, per [`pipeline.md`](../seo/references/skill-common/pipeline.md:1) | **Probabilistic** |
| **T5 — Rendering & validation** | findings → Markdown; hallucination gate | [`build_report.py`](../seo/report/build_report.py), [`validate_report.py`](../seo/report/validate_report.py) | Deterministic |
| **T6 — Delivery** | Markdown → PDF / email | `report-export` skill | Deterministic |

The T0→T6 chain is a clean pipeline. The only probabilistic stage (T4) is deliberately isolated and bracketed by deterministic validation on both sides — a sound design.

### 1.2 Capability inventory (registry v8)

44 capabilities across 6 servers ([`capabilities.json`](../seo/capabilities.json:12)):

| Server | Capabilities | Count | Configured |
|---|---|---|---|
| `search-console` | `gsc.*` (query/page/page_query/geo_query, compare×3, anomalies, health, inspect, sitemaps, indexing, keywords×2, genai, pagespeed×2, schema, compare_engines, analytics_advanced, sites_list, diagnostics, daily_totals) | 23 | yes |
| `analytics` | `ga4.*` (ai_sources, ai_time_series, ai_cited_pages, channels, organic_landing_pages, landing_source, referrals, properties) | 8 | yes |
| `google-ads` | `ads.*` (customers, metadata, search) | 3 | yes |
| `google-ads-planner` | `planner.*` (ideas, historical) | 2 | yes |
| `dataforseo` | `dfs.*` (backlinks_summary, referring_domains, anchors, backlinks_new_lost, ranked_keywords, serp) | 6 | **no (optional)** |
| `tavily` | `web.*` (search, extract) | 2 | yes |

### 1.3 Skill → dependency → I/O matrix

| Skill | Domain | Required | Optional (degrade) | Caps used | Compute modules | Primary output |
|---|---|---|---|---|---|---|
| `seo-audit` | Analytics (macro) | `search-console` | `analytics`, `dataforseo` | 13 | `gsc_metrics`, `ga4_metrics`, `coverage` | Health scorecard + 5 actions |
| `seo-rank-tracking` | Analytics | `search-console` | `dataforseo`, Bing | 8 | `gsc_metrics`, `rules` | Winners/losers/new/lost + weekly trend |
| `seo-ai-visibility` | Analytics (GEO) | `search-console` | `analytics` | 10 | `site_crawl`, `site_profile` | AI share, cited pages, crawler access |
| `seo-brief` | Analytics (roll-up) | `search-console` | other skills' reports | 2 | `digest` | Weekly KPI + merged actions |
| `seo-paid-organic` | Analytics (paid) | `search-console` | `google-ads` | 6 | `ads_metrics` | Overlap buckets + savings |
| `seo-brand-split` | Content | `search-console` + rules | — | 4 | `gsc_metrics`, `rules` | Brand/non-brand by language |
| `seo-content-refresh` | Content | `search-console` | `analytics`, `dataforseo` | 7 | `gsc_metrics` | Decay classes + refresh list |
| `seo-content-brief` | Content | `search-console` | `dataforseo`, `tavily`, planner | 8 | `site_crawl`, `gsc_metrics` | One-keyword brief |
| `seo-keyword-strategy` | Content | `search-console` | planner, `dataforseo` | 8 | `gsc_metrics`, `dfs_metrics`, `coverage`, `rules` | Tiered roadmap |
| `seo-technical` | Technical | `search-console` | — (local crawl) | 8 | `site_crawl` | Template CWV/schema/crawl |
| `seo-indexation` | Technical | `search-console` | — (local crawl) | 7 | `site_crawl` | Sampled coverage + hreflang |
| `seo-internal-links` | Technical | `search-console` | — (local crawl) | 4 | `site_crawl`, `gsc_metrics` | Link plan (source→target→anchor) |
| `seo-backlink-check` | Off-page | `analytics` | `dataforseo` | 6 | `dfs_metrics` | Profile + gap + referral cross-check |

### 1.4 Dependency graph (textual)

```
orchestrate.py ──► .run_state.json (window) ──► record.py ──► context.json + data/ + _cache/
                                                     │
        ┌────────────────────────────────────────────┼───────────────────────────────┐
        ▼                    ▼                        ▼                               ▼
  search-console        analytics               google-ads(-planner)            dataforseo / tavily
   (gsc.*, 23)           (ga4.*, 8)                 (ads.*, planner.*)              (dfs.*, web.*)
        │                    │                        │                               │
        └──────────► *_metrics.py / rules.py / coverage.py / digest.py ◄─────────────┘
                                     │
                              findings.json (LLM)
                                     │
                    validate_report.py ──► build_report.py ──► report.md ──► report-export
```

**Cross-cutting contracts:** `data-source-map.md` (one degradation rule), `findings-schema.json` (I/O schema), `skill-common/*` (8 shared includes), `capabilities.json` (integration registry).

---

## 2. Architectural evaluation

Scored 1–10 per axis. "Technical precision" = correctness of the *interface/contract* design (not output data, which the sibling audit covers).

| Domain | Modularity | Scalability | Maintainability | Technical precision | Weighted |
|---|---|---|---|---|---|
| **Technical SEO** (`seo-technical`, `seo-indexation`, `seo-internal-links`) | 9 | 6 | 9 | 9 | **8.3** |
| **Content Strategy** (`seo-content-brief`, `seo-keyword-strategy`, `seo-content-refresh`, `seo-brand-split`) | 9 | 8 | 9 | 8 | **8.5** |
| **Off-Page** (`seo-backlink-check`) | 7 | 7 | 8 | 7 | **7.3** |
| **Analytics** (`seo-audit`, `seo-rank-tracking`, `seo-ai-visibility`, `seo-brief`, `seo-paid-organic`) | 6 | 7 | 8 | 8 | **7.3** |
| **Framework core** (registry, resolver, evidence, CI) | 9 | 8 | 8 | 8 | **8.3** |

### 2.1 Justifications

**Technical SEO — 8.3.** Cleanest domain. Each skill owns one responsibility; the shared local acquisition module [`site_crawl.py`](../seo/site_crawl.py) is a textbook reusable component (stdlib, no key, polite rate). Precision is high: field-vs-lab CWV is explicitly separated ([`seo-technical/SKILL.md`](../.agents/skills/seo-technical/SKILL.md:73)), indexation is honestly sampled rather than fabricated ([`seo-indexation/SKILL.md`](../.agents/skills/seo-indexation/SKILL.md:13)). **Scalability is the weak axis:** the crawler is single-threaded with `--limit 300/500` and PageSpeed runs per-URL sequentially — fine for a 4-language brochure site, a bottleneck for a 50k-URL catalogue.

**Content Strategy — 8.5.** Best-decomposed domain. The four skills partition cleanly by *cardinality* (one keyword / a roadmap / declining pages / brand split) with no overlap. Planner batching (≤20 seeds, ≤10 geos) is encoded in the registry policy ([`capabilities.json`](../seo/capabilities.json:50)) and enforced by the server. Value estimates are labelled and derived from the site's own CTR curve, not invented.

**Off-Page — 7.3.** Architecturally sound but *capability-thin*: the entire domain rests on one optional, unconfigured third-party server. The GA4 referral cross-check ([`seo-backlink-check/SKILL.md`](../.agents/skills/seo-backlink-check/SKILL.md:76)) is a good first-party fallback, but there is no first-party link-graph signal. This is a *coverage* limitation, not a design flaw.

**Analytics — 7.3.** The domain carries the framework's two fault lines. `seo-rank-tracking`, `seo-ai-visibility` and `seo-brief` are well-scoped. `seo-audit` is not (see §3.1). Window discipline is strong for date-bearing tools but leaks for `gsc.genai` (`days`) and any tool without a window.

**Framework core — 8.3.** The registry + resolver + evidence + CI stack is the strongest part of the system. The resolver's marker-block re-rendering ([`resolve.py`](../seo/resolve.py:239)) fixes the one-way-render defect flagged in the prior audit. Semantic allowlists ([`resolve.py`](../seo/resolve.py:53)) catch deprecated GA4/GSC names that schema validation cannot. The CI gate is offline-portable ([`check.sh`](../seo/check.sh:14)).

---

## 3. Critical teardown

### 3.1 Anti-pattern: the god-skill (`seo-audit`)

`seo-audit` calls **13 capabilities across 9 workflow steps** ([`seo-audit/SKILL.md`](../.agents/skills/seo-audit/SKILL.md:79)) and re-implements slices of four specialists:

| `seo-audit` step | Duplicates |
|---|---|
| Step 5 "declining pages" | `seo-content-refresh` |
| Step 5 "quick wins / striking distance" | `seo-keyword-strategy` |
| Step 7 "indexation spot-check" | `seo-indexation` |
| Step 8–9 "engagement & AI share" | `seo-ai-visibility` |

**Impact:** four independent implementations of overlapping logic drift apart; a threshold change in `seo-content-refresh` does not propagate to `seo-audit`. It also violates the Single Responsibility Principle — the skill's own `Scope` ([`seo-audit/SKILL.md`](../.agents/skills/seo-audit/SKILL.md:13)) admits it is a "macro health" roll-up that "delegates deep dives", yet it still computes them inline.

**Fix direction:** `seo-audit` should *consume* the specialist skills' `findings.json` (as `seo-brief` already does via [`digest.py`](../seo/digest.py)) rather than recompute. This is the single highest-leverage refactor.

### 3.2 Anti-pattern: convention-enforced determinism (the soft evidence gate)

The evidence pipeline is mandatory in prose ([`evidence.md`](../seo/references/skill-common/evidence.md:1)) and `record.py` enforces real guards — runtime-arg validation, window matching ([`record.py`](../seo/record.py:57)), cache TTLs ([`record.py`](../seo/record.py:98)). But **nothing in the runtime forces the agent to call `record.py`.** If the agent skips it, `context.json` stays `{"calls": []}` (seeded at [`orchestrate.py`](../seo/orchestrate.py:94)) and the hallucination gate in `validate_report.py` has nothing to check against.

**Impact:** the framework's central safety property — "every number traces to recorded evidence" — is a *policy*, not an *invariant*. This is the architectural root of the sibling audit's C1.

**Fix direction:** make the gate fail-closed. `validate_report.py` should error when findings contain URLs but `context.json.calls` is empty. Optionally, have `build_report.py` refuse to render a report whose `context.json` has zero calls.

### 3.3 Anti-pattern: leaky window contract

The "one window" invariant is enforced by `record.py` only for `startDate`/`endDate`/`date_ranges` ([`record.py`](../seo/record.py:66)). Capabilities that express time differently escape it:

- `gsc.genai` uses `days` ([`capabilities.json`](../seo/capabilities.json:30)) — the skill must manually set a section `window` note ([`seo-ai-visibility/SKILL.md`](../.agents/skills/seo-ai-visibility/SKILL.md:81)).
- `gsc.pagespeed`, `gsc.schema`, `dfs.*` are live snapshots with no window at all.

**Impact:** the as-of line can misstate provenance; the invariant is not universally enforceable. The `sections[].window` field in the schema ([`findings-schema.json`](../seo/references/findings-schema.json:97)) is the correct escape hatch, but its use is discretionary.

### 3.4 Anti-pattern: server-coupled semantic validation (Open/Closed violation)

`resolve.py` hardcodes per-server knowledge: GA4 dimension/metric allowlists ([`resolve.py`](../seo/resolve.py:53)), GSC dimension + row-limit + engine rules ([`resolve.py`](../seo/resolve.py:307)). Adding a new server (e.g. a first-party backlink source) requires editing `resolve.py` itself.

**Impact:** the registry is open for *data* but closed for *validation logic*. The semantic layer does not scale with the server count.

### 3.5 Bottleneck: no shared materialized view across skills

Eight skills independently pull `gsc.query` / `gsc.page` / `gsc.page_query` for the same site and window. The shared cache ([`record.py`](../seo/record.py:119)) deduplicates *identical* calls, but each skill seeds its own run directory and the cache is keyed per site+args — so cross-skill reuse works only when windows and args coincide exactly. There is no "site analytics mart" that all skills read.

**Impact:** redundant API calls, redundant compute, and a risk that two skills disagree because their windows differ by a day.

### 3.6 Bottleneck: sequential, single-threaded acquisition

`site_crawl.py` (limit 300–500) and per-URL PageSpeed calls are sequential. For the current 4-language site this is acceptable; it does not scale to large catalogues.

### 3.7 Redundancy: duplicated section scaffolding

The 8 shared includes ([`skill-common/`](../seo/references/skill-common/)) are good DRY, but the 20-section `SKILL.md` skeleton is still copy-pasted per skill, and `test_skill_docs.py` enforces only 10 sections. The includes cover *content*; the *structure* is not generated.

### 3.8 Observability gap

`context.json` is the only execution trace. There is no per-call latency, no failure taxonomy beyond exit codes (0/1/3), no run-level metrics. Debugging a bad report means reading raw JSON by hand.

### 3.9 Security coupling (carried from sibling audit)

Live API keys sit in a tracked `.roo/mcp.json` in a public repo. Architecturally, secrets are coupled to a version-controlled config that the resolver and MCP client read directly ([`resolve.py`](../seo/resolve.py:36)). This should be an environment-injected secret store.

---

## 4. Prioritized refactoring blueprint

Ordered by leverage ÷ effort. Each item is production-ready and independently shippable.

### P0 — Structural integrity (do first)

1. **Make the evidence gate fail-closed.** In [`validate_report.py`](../seo/report/validate_report.py), error when findings contain URLs but `context.json.calls` is empty; in [`build_report.py`](../seo/report/build_report.py), refuse to render with zero recorded calls. *Effort: S. Impact: closes the framework's central safety hole.*

2. **Decompose `seo-audit` into a roll-up.** Replace its inline declining-pages / quick-wins / indexation / engagement steps with reads of the specialist skills' `findings.json` via `digest.py` (the pattern `seo-brief` already uses). Keep only the macro scorecard and the cross-skill synthesis. *Effort: M. Impact: removes the largest cohesion/redundancy liability.*

3. **Rotate and externalize secrets.** Move `SEVALLA_API_KEY`, `TAVILY_API_KEY`, `KINSTA_API_KEY` out of tracked `.roo/mcp.json` into environment variables; commit `mcp.json.example`. *Effort: S. Impact: eliminates a live credential exposure.*

### P1 — Contract hardening

4. **Generalize the window contract.** Add a `window_arg` descriptor to each capability in the registry (e.g. `{"kind": "days", "field": "days"}`) and have `record.py` enforce it uniformly, so `gsc.genai` and any future windowed tool cannot escape the invariant. *Effort: M.*

5. **Move semantic validation into the registry.** Replace the hardcoded GA4/GSC allowlists in [`resolve.py`](../seo/resolve.py:53) with per-server `validation` blocks in `capabilities.json` (dimension/metric allowlists, required pins). *Effort: M. Impact: Open/Closed compliance; new servers need no code change.*

6. **Generate the `SKILL.md` skeleton from a template.** Extend the resolver so the 20-section structure is rendered from a base template + per-skill fragment, not copy-pasted. *Effort: M. Impact: eliminates structural drift; makes `test_skill_docs` meaningful.*

### P2 — Efficiency & scale

7. **Introduce a per-site analytics mart.** A `seo/mart.py` that materializes the canonical `gsc.query`/`gsc.page`/`gsc.page_query`/`ga4.*` pulls for a site+window once, and lets every skill read from it. *Effort: L. Impact: removes redundant calls and cross-skill window drift.*

8. **Parallelize acquisition.** Add bounded concurrency to `site_crawl.py` and PageSpeed fan-out (respecting rate limits). *Effort: M. Impact: unlocks large-site scale.*

9. **Add execution observability.** Emit a `run_metrics.json` (per-call latency, cache hit/miss, retries, failures) from `record.py`. *Effort: S. Impact: makes runs debuggable without reading raw JSON.*

### P3 — Coverage & hygiene

10. **First-party link signal.** Register a local link-graph capability (the crawler already computes inlinks) so `seo-backlink-check` has a non-third-party baseline. *Effort: M.*

11. **Prune or justify soft-used capabilities.** Audit capabilities referenced only in fallback prose (e.g. `gsc.compare_drop`, `gsc.compare_trends`) and either wire them into a workflow or remove them. *Effort: S.*

12. **Behavioural/golden tests.** Add canned tool-output fixtures per skill asserting findings invariants, plus negative tests for the evidence gate and window contract. *Effort: L. Impact: converts the green-but-structural suite into a behavioural one.*

---

## 5. Scorecard summary

| Dimension | Score | Note |
|---|---|---|
| Architectural modularity & composability | 8.5 | Excellent layering; `seo-audit` is the exception |
| Interface & schema design | 8.0 | Strong registry + findings schema; window contract leaks |
| Resilience & error handling | 7.5 | Good degradation rule; evidence gate is soft; retry layering |
| Domain efficacy & algorithmic alignment | 8.5 | Modern (keyEvents, field CWV, AI-crawler taxonomy, GEO) |
| Maintainability & CI | 8.5 | Registry + resolver + offline CI are best-in-class |
| **Overall** | **8.1** | Strong system; two fault lines to close |

**Projected after P0+P1:** ~9.0. **After P2+P3:** ~9.4.

---

## Sources (internal, file:line)

- Registry: [`seo/capabilities.json`](../seo/capabilities.json:1) · Resolver: [`seo/resolve.py`](../seo/resolve.py:215) · Orchestration: [`seo/orchestrate.py`](../seo/orchestrate.py:34) · Evidence: [`seo/record.py`](../seo/record.py:167)
- Contracts: [`pipeline.md`](../seo/references/skill-common/pipeline.md:1), [`evidence.md`](../seo/references/skill-common/evidence.md:1), [`data-source-map.md`](../seo/references/data-source-map.md:14), [`findings-schema.json`](../seo/references/findings-schema.json:1)
- CI: [`seo/check.sh`](../seo/check.sh:1) · Sibling data audit: [`seo-skills-audit-2026-10-30.md`](seo-skills-audit-2026-10-30.md)
