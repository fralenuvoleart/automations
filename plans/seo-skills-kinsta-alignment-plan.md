# Plan — Align the SEO skills with the `kinsta-logs` best-practice reference

**Status:** proposed, **tiered** — see Part 10 for what is a genuine best practice vs. what is Kinsta-specific and should NOT be transplanted wholesale. No code changed by this plan.
**Author:** code mode
**Reference of record:** [`.agents/skills/kinsta-logs/SKILL.md`](../.agents/skills/kinsta-logs/SKILL.md) and its [`references/architecture-blueprint.md`](../.agents/skills/kinsta-logs/references/architecture-blueprint.md)
**Target:** `.agents/skills/seo-*` (8 skills) + `seo/` infrastructure + `README.md`/`SKILL.md` docs + tests

---

## Part 0 — What `kinsta-logs` does that we should copy (evidence)

| # | Principle | Evidence in reference |
|---|---|---|
| P1 | **Orchestrate-Analyze-Build (OAB)**: scripts gather data → LLM writes strict JSON → script builds the artifact | [`architecture-blueprint.md:25-52`](../.agents/skills/kinsta-logs/references/architecture-blueprint.md) |
| P2 | **LLM never hand-edits complex Markdown**; it emits JSON, a script renders | [`architecture-blueprint.md:60`](../.agents/skills/kinsta-logs/references/architecture-blueprint.md) |
| P3 | **Progressive disclosure**: lean `SKILL.md`, dense rules in `references/*.md`, linked + read on demand | [`architecture-blueprint.md:61`](../.agents/skills/kinsta-logs/references/architecture-blueprint.md), [`SKILL.md:191-197`](../.agents/skills/kinsta-logs/SKILL.md) |
| P4 | **Dynamic prompt assembly**: inject only the rules that apply to this run into the data payload | [`architecture-blueprint.md:62`](../.agents/skills/kinsta-logs/references/architecture-blueprint.md) |
| P5 | **State files** (`.run_state.json`) carry paths/state between scripts — never rely on LLM memory | [`architecture-blueprint.md:64`](../.agents/skills/kinsta-logs/references/architecture-blueprint.md), [`orchestrator.py:82-86`](../.agents/skills/kinsta-logs/scripts/orchestrator.py) |
| P6 | **Mechanical validation** of LLM output against source data (catch hallucinations) | [`architecture-blueprint.md:63`](../.agents/skills/kinsta-logs/references/architecture-blueprint.md), `verify_urls.py` in [`SKILL.md:183`](../.agents/skills/kinsta-logs/SKILL.md) |
| P7 | **Mechanical vs analytical** steps explicitly bounded | [`SKILL.md:10`](../.agents/skills/kinsta-logs/SKILL.md) |
| P8 | **Scope / memory-bank isolation** stated up front | [`SKILL.md:24-25`](../.agents/skills/kinsta-logs/SKILL.md) |
| P9 | **Report audience & purpose** (who reads it, what fix is acceptable) | [`SKILL.md:36-38`](../.agents/skills/kinsta-logs/SKILL.md) |
| P10 | **Fixed SKILL.md contract**: When to Use / When NOT / Requires / Steps / Troubleshooting / Files / Config / Privacy / Output Structure | [`SKILL.md:12-38,159-229`](../.agents/skills/kinsta-logs/SKILL.md) |
| P11 | **Troubleshooting table** (symptom → cause → fix) | [`SKILL.md:159-172`](../.agents/skills/kinsta-logs/SKILL.md) |
| P12 | **Files table** with an explicit Action column (Execute / Read / Edit) | [`SKILL.md:176-197`](../.agents/skills/kinsta-logs/SKILL.md) |
| P13 | **Retry / degrade policy** + pinned tool versions | [`SKILL.md:163,180`](../.agents/skills/kinsta-logs/SKILL.md) |
| P14 | **Tests with fixtures**, run after script changes | [`SKILL.md:184`](../.agents/skills/kinsta-logs/SKILL.md) |
| P15 | **Determinism notes** (what's deterministic vs not; a flag to disable nondeterminism) | [`SKILL.md:181`](../.agents/skills/kinsta-logs/SKILL.md) |
| P16 | **Fail fast** on unrecoverable discovery errors | [`orchestrator.py:33-35,69-71`](../.agents/skills/kinsta-logs/scripts/orchestrator.py) |

**Gap today:** the SEO skills are pure prose. They call MCP tools directly, emit free-form Markdown, have no state file, no mechanical validation, no references, no per-skill tests, and inconsistent section structure. `seo/` already has a strong *orchestration* primitive (`capabilities.json` + `resolve.py`) that plays the role of `orchestrator.py`, but nothing plays the role of `build_report.py` / `verify_urls.py`.

---

## Part 1 — Target architecture (SEO OAB)

### 1.1 Directory layout

```
seo/
  capabilities.json            # registry (exists) — the orchestration contract
  resolve.py                   # (exists) token/alias/expanded-spec validation
  mcp_client.py                # (exists) live schema probe
  window.py                    # (exists) deterministic date windows
  report/                      # NEW — shared Build/Validate engine
    build_report.py            # JSON findings + data -> Markdown (deterministic)
    validate_report.py         # mechanical checks of LLM output vs source data
    templates/                 # report skeletons (no LLM editing)
  references/                  # NEW — shared cross-skill contracts
    report-structure.md        # section contract for every SEO report
    conciseness-directives.md  # tone/labels/"never fabricate" rules (grep-auditable)
    capability-usage.md        # how to call {{cap:}} + runtime/args semantics
    data-source-map.md         # capability -> source -> freshness/lag notes
  tests/                       # (exists) + new tests below
  check.sh                     # NEW — one-command CI gate

.agents/skills/seo-<name>/
  SKILL.md                     # lean, fixed contract (Part 2)
  references/
    <name>-framework.md        # skill-specific thresholds/analytical rules
  scripts/
    collect.py                 # NEW: resolves window + writes run_state/context stub
    tests/
      test_<name>.py
  config/
    defaults.json              # NEW: default siteUrl/property_id/windows/thresholds
```

### 1.2 Phase mapping (SEO ↔ OAB)

| OAB phase | kinsta-logs | SEO equivalent (proposed) |
|---|---|---|
| **Orchestrate** | `orchestrator.py` fetches logs, writes `.run_state.json` | `seo/window.py` resolves dates → skill `scripts/collect.py` writes `$RUN_DIR/.run_state.json` + `context.json`; the agent then issues the fixed capability calls from `capabilities.json` |
| **Analyze** | LLM writes `{ts}_analyst_findings.json` | LLM writes `{ts}_findings.json` against a strict schema (per skill) |
| **Build** | `build_report.py` renders Markdown | `seo/report/build_report.py` renders Markdown from `context.json` + `findings.json` |
| **Validate** | `verify_urls.py` + `analyze_logs.py --validate` | `seo/report/validate_report.py` (metric/URL/quote/as-of checks) |

> **Key design note:** unlike Kinsta (scripts call the API directly), SEO data arrives via **agent-invoked MCP tools**. So `collect.py` cannot fetch GSC/GA4 itself; it produces the *contract* (window, ids, expected capability list) and the agent fills `context.json`. This keeps the mechanical/analytical split while respecting the MCP execution model. The registry (`capabilities.json`) remains the single source of the call specs.

---

## Part 2 — Skill structure changes (`SKILL.md` contract)

Standardize **all 8** SEO `SKILL.md` files to this ordered template (mirroring [`kinsta-logs/SKILL.md`](../.agents/skills/kinsta-logs/SKILL.md)):

1. **Frontmatter** — `name`, `description`, `license`, `compatibility` (already present; keep).
2. **Mechanical/Analytical banner** — one line stating which steps are exact vs judgment (P7).
3. **When to Use** / **When NOT to Use** (present; normalize wording).
4. **Requires** — servers + access level + preflight command.
5. **Scope & Isolation** — what the skill does/does not do; explicit "does not read/write `memory-bank/`" unless intended (P8).
6. **Report Audience & Purpose** — who reads it and what counts as an acceptable action (P9).
7. **Data Sources** — table: Need → `{{cap:id}}` or call spec → Status → Freshness/lag.
8. **Workflow** — numbered steps, mechanical vs analytical labeled.
9. **Determinism** (already added) — window resolution, as-of line, estimate labels.
10. **Output** — points to `seo/references/report-structure.md`; the LLM writes **findings JSON**, not Markdown.
11. **Fallbacks / Degradation ladder** — table (server missing → behavior).
12. **Troubleshooting** — symptom → cause → fix (P11).
13. **Files** — file → purpose → action (P12).
14. **Related / Delegation** — which other SEO skill to hand off to.

**Move out of `SKILL.md` into `references/`:**
- Threshold tables (e.g. decay >30%, position ≤5/CTR <2%, striking distance 8–20) → `references/<name>-framework.md`.
- The long capability call specs repeated inline → rely on `capabilities.json` + a short "Data Sources" table.
- Tone/label rules → shared `seo/references/conciseness-directives.md`.

---

## Part 3 — Delegation boundaries

| Boundary | Rule | SEO action |
|---|---|---|
| **Mechanical (exact)** | window math, capability args, de-dup, arithmetic, table render, validation | Move to `scripts/*` + `seo/report/*`; forbid LLM arithmetic in prose |
| **Analytical (judgment)** | severity, root cause, prioritization, narrative | Constrain with `references/<name>-framework.md`; require the finding-card format |
| **Cross-skill hand-off** | one skill = one job; hand off explicitly | Add "Related / Delegation": `seo-audit`→`seo-vs-ads`; `seo-content-brief`→`seo-keyword-research`; `seo-rank-tracking`→`seo-audit` |
| **Infra vs skill** | `seo/` = non-skill tooling; `.agents/skills/seo-*` = skills | Keep the existing split ([`seo/README.md:1-4`](../seo/README.md)); skills must not duplicate registry logic |
| **Memory-bank** | isolation like Kinsta | State explicitly that SEO skills do not write `memory-bank/` |

---

## Part 4 — Error handling, retry, timeout

Formalize into `seo/references/data-source-map.md` + registry fields (P13, P16):

1. **Preflight** — every skill step 1 runs the server's `diagnostics` (GSC) / `get_account_summaries` (GA4) and **fails fast**, naming the missing connection (already partly present; make uniform).
2. **Registry retry/timeout metadata** — extend `capabilities.json` with optional per-capability:
   ```json
   "ga4.traffic_sources": { "server": "analytics", "tool": "run_report",
     "args": { ... }, "runtime": [...],
     "policy": { "retry": 2, "backoff_s": [2, 4], "timeout_budget_s": 40, "on_error": "degrade" } }
   ```
   `resolve.py --validate-live` gains a check that `policy.timeout_budget_s` < the MCP client timeout (60s) — this generalizes the planner fix.
3. **Degradation ladder** — a single shared table:
   `dataforseo absent → skip SERP/backlink` · `analytics absent → GSC-only` · `google-ads absent → organic-only` · `planner 429 → seo_keywords_research estimates`.
4. **Bounded retries** — reuse [`seo/mcp-servers/google-ads-planner/planner_limits.py`](../seo/mcp-servers/google-ads-planner/planner_limits.py) pattern (`RateGate` + `backoff_delay` + total budget) as the shared retry idiom; document `PLANNER_MAX_RETRY_SECONDS`-style env overrides.
5. **Never fabricate** — promote to a mandatory rule in `conciseness-directives.md` (already stated in several skills).
6. **Pinned versions** — already done for npm; add the same discipline to the Python deps ([`seo/requirements.txt`](../seo/requirements.txt)).

---

## Part 5 — Documentation consistency

### 5.1 `README.md` (seo/)
Add sections:
- **Skill anatomy** — the Part 2 template, one diagram.
- **OAB mapping** — the Part 1.2 table.
- **Adding a skill** — step-by-step: add capability → `resolve.py --check` → author with `{{cap:}}` → `--write` → add tests.
- **Validation & CI** — `seo/check.sh` (runs `--check`, `--validate-live`, all tests).
- **Troubleshooting** — symptom/cause/fix table (mirrors Kinsta).
- Keep/refresh: Commands table, Notes, determinism + planner-quota notes.

### 5.2 `SKILL.md` (each)
- Apply the Part 2 template verbatim (section order + names).
- Replace inline repeated call specs with `{{cap:id}}` references + the Data Sources table.
- Add Troubleshooting + Files tables.
- Ensure the `compatibility:` line is accurate per skill (e.g. backlink-check must not claim `search-console`).

### 5.3 Consistency lint (mechanical)
New `seo/tests/test_skill_docs.py`:
- Every `seo-*` `SKILL.md` has the required section headers in order.
- Frontmatter has `name`/`description`/`license`/`compatibility`; `name` matches the directory.
- No residual `{{cap:}}` tokens in committed skills (already true) and every referenced capability exists.
- Internal links resolve (`../../../seo/...`, `references/...`).
- Every `SKILL.md` cross-link to `seo/references/report-structure.md` exists.

---

## Part 6 — Test coverage

| Test file | Covers | Status |
|---|---|---|
| `seo/tests/test_resolve.py` | registry integrity, arg/enum validation, camelCase guard, expanded-spec drift | ✅ exists (11) |
| `seo/tests/test_window.py` | deterministic windows | ✅ exists (6) |
| `seo/tests/test_planner_limits.py` | rate gate, backoff, de-dup | ✅ exists (5) |
| `seo/tests/test_planner_server.py` | retry loop, budget, validation | ✅ exists (9) |
| `seo/tests/test_skill_docs.py` | **NEW** — SKILL.md contract + links + frontmatter | ⬜ |
| `seo/tests/test_report_build.py` | **NEW** — `build_report.py` golden-file render from fixtures | ⬜ |
| `seo/tests/test_report_validate.py` | **NEW** — validator catches a planted bad metric/URL/missing as-of line | ⬜ |
| `seo/tests/test_capability_policy.py` | **NEW** — every `policy.timeout_budget_s` < 60s | ⬜ |
| `seo/tests/fixtures/` | **NEW** — sample `context.json` + `findings.json` per skill | ⬜ |
| `seo/check.sh` | **NEW** — `--check` + `--validate-live` + all tests (one command) | ⬜ |

Coverage targets: 100% of `seo/report/*` functions; every skill has at least a doc-contract test and a findings-schema test.

---

## Part 7 — Per-skill action matrix

| Skill | References to add | Scripts/tests | Doc fixes |
|---|---|---|---|
| `seo-audit` | `seo-audit-framework.md` (thresholds) | `scripts/tests/test_seo_audit_findings.py` | template; move thresholds out; add Troubleshooting/Files |
| `seo-ai-visibility` | `ai-visibility-framework.md` | findings-schema test | template; canonicalize `analytics_advanced`; keep lower-bound label |
| `seo-backlink-check` | `backlink-framework.md` | findings-schema test | template; keep corrected gate |
| `seo-competitor-gap` | `competitor-gap-framework.md` | findings-schema test | template |
| `seo-content-brief` | `content-brief-framework.md` | brief-schema test | template; canonical tool refs |
| `seo-keyword-research` | `keyword-research-framework.md` | planner fallback test | template; planner quota note (done) |
| `seo-rank-tracking` | `rank-tracking-framework.md` | findings-schema test | template |
| `seo-vs-ads` | `vs-ads-framework.md` | findings-schema test | template; savings-estimate assumptions |

---

## Part 8 — Phased execution plan

**Phase A — Shared contracts (no behavior change)**
1. Add `seo/references/{report-structure,conciseness-directives,capability-usage,data-source-map}.md`.
2. Add `seo/check.sh`.
- *Acceptance:* `bash seo/check.sh` passes; no `SKILL.md` edited yet.

**Phase B — Validate first; Build only for tables (see Part 10)**
3. Add `seo/report/validate_report.py` (+ `test_report_validate.py`, `fixtures/`) — **always adopt**; cheap and catches hallucinated metrics/URLs.
4. Add `seo/report/build_report.py` + `templates/` **only for the fixed tabular sections** (not the narrative), and only if the report contract proves rigid enough; add `test_report_build.py`.
- *Acceptance:* validator fails on a planted bad metric; builder golden-file tests pass (if adopted).

**Phase C — Registry policy + generalized timeout**
5. Extend `capabilities.json` with `policy` blocks; teach `resolve.py --validate-live` to check `timeout_budget_s < 60`.
6. Add `test_capability_policy.py`.
- *Acceptance:* `--check`/`--validate-live` green; budget test green.

**Phase D — Skill restructure (one skill per PR)**
7. For each of the 8 skills: apply the Part 2 template, add `references/<name>-framework.md`, add `scripts/collect.py` + `config/defaults.json`, switch Output to findings-JSON.
8. Add `test_skill_docs.py`.
- *Acceptance:* all doc-contract tests green; every skill references the shared report-structure contract.

**Phase E — Docs**
9. Rewrite `seo/README.md` sections (Part 5.1); refresh each `SKILL.md` compatibility line.
- *Acceptance:* doc-lint green; README links resolve.

**Phase F — CI + regression**
10. Wire `seo/check.sh` into pre-commit/CI.
- *Acceptance:* a deliberate registry change and a deliberate bad metric both fail CI.

**Rollback:** each phase is additive and gated by tests; Phases B–E touch skills one file at a time, so any skill can be reverted independently without affecting `seo/` infrastructure.

---

## Part 9 — Risks & mitigations

| Risk | Mitigation |
|---|---|
| Over-engineering prose skills into scripts | Keep `collect.py` thin; only mechanical steps move to code |
| MCP tools can't be called from scripts | `collect.py` writes the contract; the agent performs the calls (documented in Part 1.2) |
| Skill self-containment vs shared references | Shared contracts live in `seo/references/` (non-skill home) and are explicitly linked; per-skill rules stay local |
| Determinism vs LLM variance | Findings-JSON schema + mechanical validation + fixed window/as-of line |
| Test sprawl | One doc-contract test + one findings-schema test per skill; shared engine tests once |

---

## Part 10 — Critical assessment: best practice vs. Kinsta-specific (honest)

Not every item above is an unqualified best practice. `kinsta-logs` solves a *different* problem: a high-volume, deterministic log→fixed-format report pipeline. Adopt a Kinsta mechanism for SEO **only when both hold**: (a) the skill produces a **fixed-format artifact from mechanical data**, and (b) the step **repeats across runs**. Otherwise the SEO skill should stay lean.

### Tier 1 — Genuine best practices and clear improvements (adopt)
- **Fixed minimum `SKILL.md` contract** (When to Use / When NOT / Requires / Troubleshooting / Files) — matches Agent Skills conventions; improves discovery and failure handling.
- **Progressive disclosure** — lean `SKILL.md`, dense/conditional rules in `references/`.
- **Explicit mechanical-vs-analytical boundary** — improves reliability and testability.
- **Fail-fast preflight + explicit degradation ladder + never-fabricate** — improves trustworthiness.
- **Determinism** (window + as-of line) — *already implemented*; verified.
- **Pinned dependencies** (Python + npm) — *already implemented*.
- **Retry/timeout budget below the client timeout** — *already implemented for the planner*; generalize.
- **Tests, incl. a doc-contract test** — catches the exact class of defect we already found.

### Tier 2 — Adopt selectively (improvement only under conditions)
- **Report validator** (`validate_report.py`) — **adopt always**: it mechanically checks LLM numbers/URLs against source data. Low cost, high value.
- **Report builder** (`build_report.py`) — **only for fixed tabular sections**, not the narrative. A full JSON→Markdown renderer for judgment-driven SEO analysis risks constraining output quality for little gain.
- **Findings JSON** — adopt a **loose** schema (required keys, free-text values), not a rigid one.
- **Registry `policy` blocks** (`retry`/`backoff_s`/`timeout_budget_s`/`on_error`) — low cost, high value; adopt.
- **Per-skill `config/defaults.json`** — adopt only if skills get repeated scheduled runs.

### Tier 3 — Do NOT transplant wholesale (Kinsta-specific or boilerplate)
- **State files (`.run_state.json`) per SEO skill** — ceremony without a multi-script pipeline; SEO skills do 1–2 tool calls then reason.
- **Dynamic prompt assembly** (`context.json` `llm_instructions`) — justified only by very large/conditional rule sets; SEO data is small.
- **Per-skill `scripts/collect.py`** — redundant with [`seo/window.py`](../seo/window.py) and cannot fetch MCP data itself (the agent does).
- **Moving small threshold tables out of `SKILL.md`** — SEO thresholds are short and *are* the core guardrail; a read hop can cause them to be skipped. **Keep inline** (opposite of the initial plan).
- **Identical template for all 8 skills** — use a **minimum required set**, not identical: `seo-content-brief`/`seo-keyword-research` produce deliverables, not audit reports, so Audience/Troubleshooting sections may be boilerplate.
- **Memory-bank isolation boilerplate** — include only if a real conflict exists.
- **Hardcoding 60 s** in `--validate-live` — make it configurable/documented, since the client timeout varies.

**Net:** the plan's Part 2/3/4/5/6 core is sound; the *degree* of OAB adoption in Parts 1 and 8 is the part that needs right-sizing (Phase B now scoped accordingly).

---

## Appendix — Immediate quick wins (low-risk, can ship before Phase A)
- Add the **Troubleshooting** + **Files** tables to all 8 `SKILL.md` (pure docs).
- Add **Scope & Isolation** and **Report Audience** sections (mirror [`kinsta-logs/SKILL.md:24-38`](../.agents/skills/kinsta-logs/SKILL.md)).
- Add `test_skill_docs.py` to lock the section contract in place before restructuring.
