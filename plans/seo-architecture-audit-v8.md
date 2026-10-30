# SEO framework architecture audit — registry v8 (fresh baseline)

**Scope:** the 13 `.agents/skills/seo-*` contracts + the `seo/` runtime (registry, resolver, planner, pipeline, data layer, report gate, tests/CI).
**Method:** direct reads of `seo/capabilities.json`, `seo/README.md`, `seo/orchestrate.py`, `seo/check.sh`, `seo/report/validate_report.py`, `seo/gsc_metrics.py` (140–184), `seo/ga4_metrics.py` (1–55), `seo/plans/`, plus workspace-wide greps for `capabilities.json`, `pipeline.py`, `orchestrate.py`, `{{cap:}}` / `<!--cap:-->`, `"cap": "…"`, `rowLimit`, `context.json`, and every registry ID.
**Baseline superseded:** `plans/seo-architecture-audit-2026-10-30.md` and the sibling data-correctness audit are void — the code changed (registry v8, 5 SEO-sheet practices ported, plans added per skill).
**Not verified in this pass:** no live MCP session was opened and the run directories were not inspected on disk (shell output capture was garbled during this audit). Every claim below is a static-code claim with a file reference; nothing is inferred from a report having "looked right".

---

## 1. Verdict

| Dimension | Weight | Score | Δ direction vs 2026-10-30 baseline |
|---|---|---|---|
| Contract single-sourcing (registry → 13 skills) | 15% | **9.5** | ↑↑ generated, drift-gated |
| Execution determinism (pipeline / window / record) | 20% | **9.0** | ↑ agent no longer trusted with args |
| Evidence & report gate | 15% | **8.0** | ↑ `--data` now mandatory |
| Data correctness (truncation, nullability, paging) | 20% | **6.5** | ↑ detection added, remediation absent |
| Capability taxonomy (classes, side effects) | 10% | **8.5** | → no side-effect class |
| Skill decomposition / routing | 8% | **7.5** | → `seo-audit` still re-pulls |
| Tests & CI | 7% | **8.5** | ↑↑ 10-gate `check.sh` |
| Observability / ops | 5% | **7.5** | ↑ run folders + `pipeline.json` |
| **Weighted composite** | | **8.1** | profile moved: execution up, correctness still the drag |

The composite number coinciding with the previous 8.1 is arithmetic, not stasis — the two audits are on different rubrics and the *shape* changed: this framework is now a compiler for reports (registry → rendered contracts → deterministic data plan → gated report) with one soft spot (data pagination) and one unguarded edge (agent-initiated capability calls).

---

## 2. Taxonomy of the framework

Five layers, each with exactly one owner:

| Layer | Owner | Contract |
|---|---|---|
| **Vocabulary** | `seo/capabilities.json` (v8, 44 capabilities) | `{server, tool, args, runtime, aliases, policy, desc}`; `runtime` = the only args a caller may supply |
| **Contract** | `seo/resolve.py` | renders `{{cap:}}` / `{{site:}}` / `{{include:}}` into `<!--cap:-->` blocks; `--check` lints unrendered tokens, unknown cap, unknown site key, DRIFT (legacy tool outside a block), STALE block |
| **Plan** | `seo/plans/*.json` (14 files / 13 skills) | `pull` steps keyed by capability ID, executed top-down |
| **Execution** | `seo/pipeline.py` → `orchestrate.py` → `mcp_client.py` → `record.py` | cache-first calls, run folder, `.run_state.json` window, `context.json` evidence, `pipeline.json` + `unavailable` list |
| **Judgement** | the SKILL.md prose + `seo/*.py` compute scripts | agent starts at **Write** |

### 2.1 Capability taxonomy (6 servers × 44 IDs × function class)

| Server | Diagnostics | Aggregate read | Granular read | Derived/compare | Write/side-effect | Fallback |
|---|---|---|---|---|---|---|
| `search-console` (23) | `gsc.sites_list`, `gsc.diagnostics`, `gsc.health` | `gsc.daily_totals`, `gsc.query`, `gsc.page`, `gsc.genai`, `gsc.pagespeed`, `gsc.pagespeed_a11y` | `gsc.page_query`, `gsc.geo_query`, `gsc.schema`, `gsc.inspect`, `gsc.sitemaps`, `gsc.indexing` | `gsc.compare_period`, `gsc.compare_trends`, `gsc.compare_drop`, `gsc.anomalies`, `gsc.compare_engines` | **`gsc.indexing`** | `gsc.keywords_related`, `gsc.keywords_stats`, `gsc.analytics_advanced` |
| `analytics` (GA4, 8) | — | `ga4.properties` | `ga4.landing_source`, `ga4.organic_landing_pages`, `ga4.channels` | `ga4.ai_sources`, `ga4.ai_time_series`, `ga4.ai_cited_pages`, `ga4.referrals` | — | — |
| `google-ads` (3) | `ads.metadata` | `ads.search` | — | — | — | `ads.customers` |
| `google-ads-planner` (2) | — | `planner.historical` | `planner.ideas` | — | — | — |
| `dataforseo` (6) | — | `dfs.backlinks_summary`, `dfs.referring_domains` | `dfs.anchors`, `dfs.backlinks_new_lost`, `dfs.ranked_keywords`, `dfs.serp` | — | — | — |
| `tavily` (2) | — | — | `web.search`, `web.extract` | — | — | `web.extract` |

Two observations that matter structurally:

1. **Registry coverage is total.** Every one of the 44 IDs is referenced by at least one `seo/plans/*.json` step or one skill data-source table. There are no dead vocabulary entries (a real improvement; it means the registry is not an aspirational catalogue).
2. **Two execution classes share one namespace.** ~34 capabilities are plan-driven (pipeline calls + records them automatically) and ~10 are agent-call-only: `gsc.sites_list`, `gsc.indexing`, `gsc.compare_engines`, `gsc.keywords_related`, `gsc.keywords_stats`, `gsc.analytics_advanced`, `ga4.channels`, `web.extract`, `ads.metadata`, `dfs.ranked_keywords`. The registry does not mark which class a capability belongs to — that distinction lives only in rendered prose (`*(agent call, only when a step needs it)*`, e.g. `.agents/skills/seo-keyword-strategy/SKILL.md:56-58`).

### 2.2 Skill decomposition matrix (pull overlap)

| Capability | `audit` | `technical` | `indexation` | `content-refresh` | `rank-tracking` | `brand-split` | `keyword-strategy` | `content-brief` | `internal-links` | `backlink-check` | `paid-organic` | `ai-visibility` | `brief` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `gsc.query` | ✓ | | | | ✓ | | ✓ | | | | ✓ | | |
| `gsc.page` | ✓ | ✓ | ✓ | ✓ | | | | | ✓ | | | ✓ | |
| `gsc.page_query` | ✓ | | | | ✓ | ✓ | | ✓ | ✓ | | | | |
| `gsc.geo_query` | ✓ | | | | ✓ | | ✓ | | | | ✓ | | |
| `gsc.daily_totals` | ✓ | | | ✓ | | ✓ | | | | | | | ✓ |
| `gsc.sites_list` (agent) | ✓ | | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ | ✓ | ✓ |
| `ga4.landing_source` | ✓ | | | | | | | | | | | ✓ | |
| `dfs.*` | | | | ✓ (links) | | | ✓ (gap) | | | ✓ | | | |

`seo-audit` remains the widest consumer (11 plan pulls) and each specialist duplicates a 2–4 capability subset. This is deliberate (every report must stand alone) and expensive (same pulls recomputed per skill), mitigated only by the shared cache in `seo/runs.py`/`config/settings.json`.

---

## 3. What actually improved (the P0s from the previous audit landed)

| Previous P0 | Evidence it is closed |
|---|---|
| Evidence gate was a convention | `seo/report/validate_report.py` — `--data` is a **required** argument (line 285), missing `context.json` is a hard problem, and a run with zero recorded calls is flagged; every figure is re-derived via `report/number_check.py` |
| Agent free-handed MCP args | `seo/README.md:33-36` + `pipeline.py --dry-run`: the agent runs one command; window is fixed in `.run_state.json` and is "the only window tools may receive" (`README.md:40`); `record.py` rejects non-`runtime` args and off-window dates |
| Semantic validation lived in prose | `seo/resolve.py --check` validates cap names, policies and arg schemas against `tool-schemas.json`; `--validate-cached` replays cached responses through the same validators offline |
| Secrets/IDs hardcoded in skills | per-site profile via `site_profile.py --get …` (`ads_customer_id`, `ads_geo_targets`, `competitors`), `config/` git-ignored, `orchestrate.py` refuses a `run_root` that could be committed |
| No CI | `check.sh` (61 lines): `resolve --check` → `--validate-cached` → optional `--live` → `pipeline --check-plans` → CTR-benchmark age → site-profile validation → `py_compile` → every `seo/tests/test_*.py`. Unknown capability in a plan is caught at `pipeline.py:136`; unknown capability in an evidence record at `record.py:134,180` |
| Contract drift between skills | Data Sources tables are *generated*, not written: identical rendered rows (`rowLimit: 25000`, `limit: 25000`) appear verbatim across all 13 skills because they come from `capabilities.json` |

This is a genuine architectural pass, not a docs refresh. The system now has **one** place to change a tool call and **ten** gates that notice when you forgot.

---

## 4. Anti-pattern teardown

### A1 — Truncation is detected but never resolved · **Severity: high**
Every GSC pull is `rowLimit: 25000` (`capabilities.json:15-19`) and every GA4 pull is `limit: 25000`. 25,000 is the GSC *per-request maximum*, not a page size, and no `startRow`/offset loop exists. `gsc_metrics.py` (`~168-174`) infers truncation as `len(rows) >= ROW_LIMIT` and reports it; nothing pages further. A page×query pull on a mid-size site exceeds 25k rows routinely, so the report's long tail (the striking-distance and cannibalization input) is silently clipped and the only signal is a footnote.
**Fix class:** either paginate, or promote the flag to a first-class dataset status that `validate_report.py` refuses to let a truncated dataset feed a headline figure.

### A2 — Unknown is coerced to zero · **Severity: high**
`ga4_metrics.py:34-38` — `_num()` returns `0.0` for a missing/unparseable metric; the same pattern feeds GSC row reads. `keyEvents`, `engagementRate` and `position` therefore cannot distinguish "absent" from "zero", and a downstream `avg`, `rate` or `sum` cannot be corrected later. Division-style metrics are the worst case (0 key events ⇒ 0% key-event rate ⇒ a confident, wrong statement).
**Fix class:** `None` propagation + explicit "not reported" rendering; make the report gate reject a computed figure whose inputs contain a null.

### A3 — Side-effecting capability in a read registry · **Severity: high**
`gsc.indexing` (`indexing_submit`) is registered beside 43 read capabilities with no `side_effects` flag and no `policy`. The only guard is prose: "only if the user explicitly confirms in this conversation" (`.agents/skills/seo-indexation/SKILL.md:75`; table row at `:53`). `pipeline.py` executes whatever a plan lists; nothing structurally prevents that ID from entering a plan and firing a write against Google's Indexing API during an unattended run.
**Fix class:** mandatory `"side_effects": true` + `"confirm": true` metadata; pipeline/record refuse such a capability without an explicit `--confirm` flag; `--check-plans` fails if one appears in a plan.

### A4 — The evidence levee has a hole at the agent-call boundary · **Severity: medium-high**
Plan-driven calls are recorded by the pipeline automatically; the ~10 agent-call capabilities depend on the prose "(record it)" (e.g. `.agents/skills/seo-ai-visibility/SKILL.md:79,81`). Troubleshooting prose drops even that: `seo-ai-visibility/SKILL.md:105` and `:117` tell the agent to use `web.extract` with no recording instruction, and `seo-paid-organic/SKILL.md:106` similarly. `validate_report.py` cross-checks URLs against recorded calls, so a missing *page fetch* is caught; a missing *metric* call is only caught if a figure happens to have been derived from it and mapped in `number_check.py`.
**Fix class:** a `record.py --cap <id>` one-liner embedded in every agent-call block at render time, plus a gate that diffs the skill's declared capability set against `context.json` for the run.

### A5 — Plan ↔ skill drift is enforced in one direction only · **Severity: medium**
`resolve --check` guarantees skill text matches the registry. `pipeline --check-plans` guarantees plan steps reference real capabilities with valid args. Nothing asserts the two *sets* agree: a plan can pull a dataset the skill never mentions in its Data Sources table, and a skill can name an agent-call capability no plan step backs. That is the one remaining contract seam.
**Fix class:** extend `--check-plans` to compare the rendered declared set (plan pulls ∪ declared agent calls) against the plan and fail on the difference.

### A6 — A soft gate inside a hard gate · **Severity: medium**
`check.sh` fails the build on every step except the CTR-benchmark freshness check, which is a warning. That is exactly the one input that decays with time (a dated post-AI-Overviews benchmark in `config/ctr-benchmark.json`) and silently changes every striking-distance valuation.
**Fix class:** make staleness fail, with a documented refresh owner and an explicit "accept stale until <date>" override recorded in config.

### A7 — Derivation asymmetry in `seo-audit` · **Severity: medium**
`seo-audit` (11 plan pulls, 329-line plan) re-derives findings that four specialists own (`technical`, `indexation`, `ai-visibility`, `brand-split`, plus `internal-links`). Two implementations of the same judgement (e.g. index coverage in `seo-audit` vs `seo-indexation`) is the classic god-object failure: they will disagree, and the disagreement surfaces as an inconsistent site narrative rather than a bug.
**Fix class:** make `seo-audit` a *composition* skill that consumes the specialists' run folders when present and only pulls natively for the gaps.

### A8 — Compute scripts carry a second, undocumented contract · **Severity: low-medium**
`gsc_metrics.py` derives row dimensions from `context.json` and swallows `JSONDecodeError` on that read (`~168`), falling back to default dimensions; GA4 raises on an unrecognised response shape (`ga4_metrics.py:~48`) — opposite policies on the same class of problem. One silently picks a schema, the other refuses.
**Fix class:** one convention: unknown shape ⇒ raise with the run folder in the message; only *optional* sources degrade, and they degrade into `unavailable`, never into a default shape.

### A9 — Two "plans" nouns, two roots · **Severity: low**
`plans/` at the workspace root (audit/design docs, per `AGENTS.md`) vs `seo/plans/` (executable data plans). The overlap is a naming tax on every future reader and on any glob-based tooling.
**Fix class:** rename the executable ones to `seo/data-plans/` (or `seo/runbooks/`); keep `plans/` for prose.

---

## 5. Refactor blueprint

**P0 — correctness (do first, ~2 days)**
1. **Pagination or a hard truncation verdict** (A1). Smallest viable: `startRow` loop in the GSC path and `offset` in the GA4 path up to a configured ceiling; if the ceiling is hit, write `status: "truncated"` on the dataset, surface it in `pipeline.json`, and have `validate_report.py` block any headline figure derived from it.
2. **Nullability** (A2). `_num` → `None`; aggregations skip nulls; report gate rejects a computed figure with a null input.
   *Exit criteria:* a fixture with >25k rows produces either complete data or a report that refuses to state a headline number, with a test for each.

**P1 — registry class + evidence boundary (~1.5 days)**
3. **`side_effects` / `confirm` metadata** (A3) and `--check-plans` rejection of side-effect caps.
4. **Auto-record line in agent-call blocks** (A4): render `record.py --cap <id>` into the block; add the declared-set diff gate.
   *Exit criteria:* removing the record step from any agent call breaks `check.sh`.

**P2 — contract closure (~2-3 days)**
5. **Plan ↔ skill set equality** in `--check-plans` (A5).
6. **Fail the CTR-benchmark staleness gate** (A6) with an explicit override field.
   *Exit criteria:* `check.sh` fails on an injected plan/skill mismatch and on a back-dated benchmark.

**P3 — decomposition & naming (~1 week, highest blast radius)**
7. **`seo-audit` becomes a composer** (A7): prefer specialist run folders, pull only what is missing. Kills the duplicate-judgement class and cuts `seo-audit` runtime materially.
8. **Rename `seo/plans/` → `seo/data-plans/`** (A9), update `pipeline.py`, 14 plan files, `README.md`, `skill-common/files.md`.
9. **Unify shape policy** (A8) across `gsc_metrics.py` / `ga4_metrics.py`.

**Deliberately not proposed:** splitting the 13 skills further, or moving the report prose into templates. The current boundary (deterministic data/derive, LLM interpretation) is the framework's best property; every P3 change should be measured against not disturbing it.

---

## 6. Residual risk register

| Risk | Trigger | Blast radius |
|---|---|---|
| Truncated dataset quoted as complete | large site, page×query > 25k rows | headline numbers wrong, no gate fires |
| Null coerced to zero | GA4 property without key events, GSC row missing position | confident wrong rate/avg |
| Unattended write to Indexing API | `gsc.indexing` added to a plan | external side effect |
| Unrecorded metric call | agent-call path during troubleshooting | number unverifiable, gate partly blind |
| Stale CTR benchmark | benchmark ages past its window | every striking-distance valuation drifts |
| Duplicate judgement between `audit` and specialists | both run at different times | contradictory site narrative |

**Audit limits:** static analysis only; no run folder, MCP session or live API response was inspected in this pass. Items A1–A9 are code-level claims with file references and should be reproduced with a single fixture run before the P0 work starts.
