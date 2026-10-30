# SEO Skills Audit — 2026-10-30

Independent audit of the 12 `seo-*` skills in `.agents/skills/` and everything in `seo/`. No git history used; no other skill used as a benchmark. The bar is general industry practice for data-reporting tooling and for SEO methodology.

> **Status (2026-10-30): all findings and optional enhancements applied** — see `memory-bank/activeContext.md`. Owner actions still open: rotate the exposed API keys; fill `ads_customer_id`, `priority_pages`, `competitors`, `serp_locations` in the profile; confirm the brand variants; cache the Tavily schema.

## Method

- Read all 12 `SKILL.md` files and every file in `seo/`: registry, resolver, MCP client, window/orchestrate, site profile, coverage, report builder/validator, references, planner MCP server, tests and config.
- Ran `resolve.py --check` (clean) and all 12 test files: **75/75 pass**. `--validate-live` could not run here because it needs the local MCP servers.
- Probed the report validator/builder with edge-case inputs, and tested the resolver's `--write` path in a scratch copy of the repo.
- Checked external API and SEO facts against official docs (Google, DataForSEO, OpenAI, Anthropic). Sources are listed at the end.
- Note: this audit exceeds the `AGENTS.md` limit of 10 files per investigation, because the requested scope covers 12 skills plus `seo/`.

## Out of scope but critical: secrets in a public repo

`.roo/mcp.json` is tracked in git, and the repo is **public**. It contains live `SEVALLA_API_KEY`, `TAVILY_API_KEY` and `KINSTA_API_KEY` values (lines 10, 33, 49). `seo/resolve.py` and `seo/mcp_client.py` read this file.
**Fix:**
1. Rotate all three keys.
2. Move the secrets to environment variables.
3. Gitignore the file and commit a `mcp.json.example` instead.

The old values stay readable in git history even after the file is deleted. This item is excluded from the rating below.

---

## 1. Verdict and rating

**Rating: 5.7 / 10.** The architecture is strong, but the last mile is unreliable.

The scaffolding is better than most skill sets:
- a capability registry with live schema validation;
- deterministic date windows;
- a findings JSON → render → validate pipeline;
- graceful-degradation blocks and site profiles;
- consistent skill anatomy;
- a green test suite.

The problem is where the numbers come from:
- several skills silently produce wrong or unverifiable figures (undercounted page clicks, truncated pulls, mismatched windows, an invented CTR curve);
- the anti-hallucination gate that should catch this cannot work as wired.

The tests check structure, not behaviour, so none of this shows up in CI.

| Dimension | Weight | Score | Evidence |
|---|---|---|---|
| Correctness | 30% | 5 | C2–C5, H5–H8, H13–H15 |
| Robustness & safety | 15% | 5 | C1, H3, H4, M6, auto-submit to the Indexing API |
| Completeness | 15% | 6 | Good domain coverage, but steps without a data source: H8, H9, M9, M13 |
| Clarity | 15% | 7 | Uniform structure and clear delegation; contradictions in H11 and M14 |
| Maintainability | 15% | 6 | Registry is good; `--write` is broken (H4), plus boilerplate, dead capabilities and doc drift (L1–L3) |
| Testing & verification | 10% | 6 | 75 green tests and an offline planner test, but no semantic or negative tests for the failure modes above |
| **Weighted** | | **5.7** | |

**Projected score after fixes:**
- Critical fixes only: about 7.0.
- Critical plus High: about 8.5.
- Everything below: 9 or more.

---

## 2. Issue register

Severity scale:
- **Critical:** silent wrong or fabricated output, or a broken mandatory gate.
- **High:** wrong output or a broken documented workflow in common use.
- **Medium:** an edge case, nondeterminism or an outdated practice.
- **Low:** drift or hygiene.

### Critical

| ID | Location | Issue | Failure scenario | Fix |
|---|---|---|---|---|
| C1 | All 12 skills, *Output* step 3; `seo/orchestrate.py:52`; `seo/report/validate_report.py:90-105` | The hallucination cross-check cannot work. Every skill runs the mandatory validation with `--data context.json`, but **no skill tells the agent to write raw tool output to `context.json`**. `orchestrate.py` seeds it as `{}`. | Verified: if seeded, every real URL fails as a "possible hallucination", so the gate never passes for URL-bearing reports. If seeding is skipped (step 0 is optional), the file is missing and the check is skipped with only a warning. Either way, nothing is verified. | Add a mandatory "append each raw tool response to `context.json`" step (or a small `seo/record.py` helper). Make a missing or empty data file an **error** whenever findings contain URLs. |
| C2 | `seo/capabilities.json` lines 31–39 (`seo_audit` ×8, `genai_query_insights`); used in seo-audit, keyword-strategy, brand-split, rank-tracking, ai-visibility | `seo_audit` accepts **no date range** (its schema has only `siteUrl`, `type`, `brandKeywords`, `minImpressions` and `engine`). `genai_query_insights` uses `days` (default 28). Skills mix these with 28- or 90-day windows under one as-of line. | seo-audit's "90 days vs previous 90" report shows striking distance, low CTR, cannibalization and quick wins computed over the tool's own default window. The as-of line misstates the provenance. | Either derive these findings from `analytics_query` over the resolved window, or record the tool's own window per section (add `window` to sections in the findings schema). Add `days` to `gsc.genai` runtime, set to the window length. |
| C3 | seo-content-refresh step 4; seo-audit steps 4–5; internal-links and indexation "top pages by impressions" | Page-level metrics are summed from `query × page` rows. Search Console **omits anonymized queries from any row set that includes the `query` dimension**. The registry has **no `["page"]`-only capability**. | Per-page clicks are systematically undercounted, so the ">30% decay" threshold runs on partial data and flags or misses the wrong pages. | Add `gsc.page` (`dimensions: ["page"]`) and use it for every page-level metric. Keep `query × page` only for attribution. |
| C4 | All `gsc.*` `analytics_query` capabilities | No capability sets `rowLimit`, and the tool exposes no `startRow`. The API default is 1,000 rows, and seo-audit's own Troubleshooting (`seo-audit:100`) admits truncation. That fix recommends a parameter not declared in `runtime`. | 90-day `query × page` diffs: queries that fall below the row cutoff show up as **"Lost"** or **"New"** in rank-tracking and as decay in content-refresh. These are artifacts, not real movements. | Put `"rowLimit": 25000` in the args. Add a rule: if `len(rows) == rowLimit`, record truncation in `findings.unavailable`. |
| C5 | `seo-keyword-strategy:56` → `seo/references/domain-knowledge.md:26-37` | The headline value formula uses `expected_CTR(target position)` and says "see domain-knowledge.md", but that file has **no CTR table** and explicitly forbids presenting bands as values. | The agent must invent CTR percentages to produce the "$ value" headline. That breaks the repo's own never-fabricate rule. | Add a labelled heuristic CTR-by-position table, or (better) derive the site's own CTR-by-position from GSC. Cite it precisely. |

### High

| ID | Location | Issue | Fix |
|---|---|---|---|
| H1 | `seo/mcp-servers/google-ads-planner/server.py:34-35` | The server sets `MAX_SEEDS = 100` and `MAX_GEOS = 100`. The API allows **20 keywords per seed** and **10 geo targets**. keyword-strategy step 5 sends the "combined candidate set" (up to ~500 competitor-gap terms), which fails with `INVALID_ARGUMENT`. That is not a `ResourceExhausted` error, so there is no retry, and the documented fallback only covers 429s. | Set the limits to 20 and 10. Batch in ≤20-keyword chunks at 1 QPS. For metrics on exact keywords, consider `GenerateKeywordHistoricalMetrics`. |
| H2 | seo-keyword-strategy, seo-content-brief (planner `runtime: customer_id`) | No skill says where the planner's `customer_id` comes from. `ads.customers` is deliberately isolated to seo-paid-organic, and the profile schema forbids extra keys (`additionalProperties: false`). | Add `ads_customer_id` to the profile schema (or an env var) and reference it in both skills. |
| H3 | `seo-indexation:50` | The skill **automatically submits** URLs to the Indexing API: an external write action, used outside Google's supported content types, with no user confirmation. The same tool also exposes `method: "remove"`. | Make submission opt-in, after explicit confirmation. Default to listing URLs for manual "Request indexing" in GSC. Pin `method: "standard"` in the args. |
| H4 | `seo/resolve.py:325-339` | The "zero-touch server swap" is broken. After the first `--write`, the tokens are gone. **Verified in a scratch copy:** changing `gsc.query` args makes `--write` update 0 files while `--check` reports DRIFT, so skills must be hand-edited. Renaming a tool via `aliases` corrupts 8 skills into `` `search-console` → `search-console` → `sites_list_v2` ``. | Keep the source of truth regenerable: wrap expansions in markers (e.g. `<!--cap:gsc.query-->…<!--/cap-->`) and re-render between them. Add a round-trip test that changes the registry, runs `--write` and asserts the skills update. |
| H5 | `seo/report/validate_report.py:25,60,104` | Hallucination false positives. `json.dumps` escapes non-ASCII characters, so a **Cyrillic URL present verbatim in the data still fails**. A URL followed by `.` also fails (both verified). The site's main audience is RU-language. | Use `ensure_ascii=False`. Strip trailing punctuation. Compare normalized URLs (`unquote`, lowercase host). |
| H6 | `seo-ai-visibility:47` | The "AI traffic trend" step calls `ga4.time_series`, which has **no AI-source filter**. It returns total site sessions, labelled as an AI trend. | Add an `ga4.ai_time_series` capability (`date × sessionSource` with the AI filter). |
| H7 | `seo-audit:66` | Step 7 says "organic sessions … by landing page" but calls `ga4.page_performance` (`pagePath`, no channel filter), which returns all channels. `ga4.landing_pages` exists but is unused and also unfiltered. | Use `landingPagePlusQueryString` with a `sessionDefaultChannelGroup = "Organic Search"` filter. |
| H8 | seo-indexation step 2; seo-audit step 3 | The steps expect site-wide indexed and excluded counts ("Crawled – currently not indexed", etc.). **The Search Console API exposes no Page Indexing report**, and the Sitemaps API stopped populating "indexed" in 2019. Where these numbers come from is undocumented. | Define the source: URL Inspection over sitemap URLs (quota-aware), reported as a sample. Otherwise say the UI report is required. |
| H9 | seo-indexation step 5; seo-brand-split step 6 | There are hreflang reciprocity checks, but **no capability returns hreflang** (URL Inspection doesn't), and there is no page-fetch capability. | Add a fetch capability (Tavily `extract` is already configured but not in the registry), or record hreflang as `unavailable`. |
| H10 | `seo-audit:69`; `seo/config/sites/pbservices.ge.history.md:4` | The skill appends **recommended** actions to a log defined as actions **already taken**. Future runs then suppress advice that was never executed. Only 1 of 12 skills reads the history, despite the README. The skill also writes into a repo-tracked file on every run. | Split the log into `recommended` and `done` entries, and only treat `done` as suppressive. Read history in every skill that recommends actions. |
| H11 | `seo-audit:54` vs `:88`; `seo-ai-visibility:45` vs Fallbacks; `seo-backlink-check:28,47` vs `:69` | The skills contradict themselves. Workflow step 1 says "stop" if GA4 or DataForSEO is missing, while *Fallbacks* says "degrade and continue". | One rule in `data-source-map.md` (required vs optional per skill); reference it from every step. |
| H12 | All `gsc.*` capabilities | `engine` is never pinned, and the tool schemas say its default is `all` (Google plus Bing). Google-only analyses (paid-organic join, rank-tracking, CTR) may mix Bing data. Server behaviour is **unverified**. | Add `"engine": "google"` to the args. Use `compare_engines` only for explicit cross-engine work. |
| H13 | `seo-rank-tracking` steps 3–4, `:71` | Query positions are diffed from `query × page` rows. Query-level position is not the mean of page rows: it needs the query-only pull. The fallback uses 5-dimension `gsc.query_full`, which fragments rows the most. | Use `gsc.query` for movers and `gsc.page_query` only for "which page moved". Drop `query_full` from the fallback. |
| H14 | `seo-brand-split:49` | EN maps to `/`, which prefixes every URL. No longest-prefix rule exists, so the "no prefix → script detection" fallback can never trigger. Classifying *queries* (rather than query-page rows) double-counts multi-language queries. | Longest-prefix match on page paths, classified per row and then aggregated. |
| H15 | `seo-content-refresh:47`; `domain-knowledge.md:54-58` | Decay is defined two ways (first "clicks fall while impressions hold", then "both down"). The skill's three classes overlap: impressions down + position held matches both "decay" and "demand drop". Labels and actions are nondeterministic. | Use a mutually exclusive decision table on Δposition, Δimpressions and ΔCTR, with thresholds. |
| H16 | `seo-technical:48` | The skill records "LCP, INP, CLS and the pass/fail band" from PageSpeed. INP is **field-only** (lab data uses TBT as a proxy), and the thresholds are CrUX p75. Low-traffic URLs often have no field data. | Read the field data (`loadingExperience` / `originLoadingExperience`). Label lab values as lab, use TBT as the INP proxy, and report "no field data" explicitly. |

### Medium

| ID | Location | Issue | Fix |
|---|---|---|---|
| M1 | `capabilities.json` (`ga4.landing_pages`, `ai_cited_pages`, `conversions_by_source`, `monetisation`); `resolve.py:62-68` | Uses the GA4 `conversions` metric, which was renamed to `keyEvents` in 2024. Third-party connectors warn it may stop returning data. | Switch to `keyEvents` and remove `conversions` from the allowlist. |
| M2 | `seo-ai-visibility:45`, `seo-technical:51`, `domain-knowledge.md:122-129` | Training and search crawlers are conflated. Google-Extended doesn't affect Search or AI Overviews, and GPTBot and ClaudeBot are training crawlers. The list is missing `Claude-SearchBot`, `Claude-User`, `ChatGPT-User` and `Perplexity-User`. This risks wrong robots.txt advice. | Use a table of bot → purpose (training / search index / user fetch) → recommended stance. |
| M3 | `seo-technical:49` | Lists FAQ as a "required type". FAQ rich results were restricted in 2023 and no longer appear (May 2026), and "Service" is not a rich-result type. | Drop FAQ as required; keep Organization, LocalBusiness, Article and Breadcrumb; note schema's GEO value separately. |
| M4 | `capabilities.json:48,52`; profile `ai_sources` | The AI referrer list exists in 3 copies. The exact-match `in_list_filter` misses host variants and unlisted assistants (e.g. DeepSeek, Grok, Meta AI). | Single source in the profile; use a partial or regex match filter. |
| M5 | `capabilities.json:48`; `seo-audit:51` | `ga4.traffic_sources` is actually filtered to AI sources only, but seo-audit labels it "GA4 traffic sources". | Rename it to `ga4.ai_sources`. |
| M6 | `validate_report.py:52`; `build_report.py:50,91,97` | The validator crashes (`AttributeError`/`KeyError`) on malformed findings. The builder runs *before* validation and crashes first. An `actions` string renders one character per line. There is no schema validation, and no sanity check on window dates (end = today, start > end both pass). All verified. | Validate findings against `findings-schema.json` *before* building. Check `start ≤ end < as_of`. Return issues instead of tracebacks. |
| M7 | `seo-backlink-check:3,47,50` | The description promises new/lost links and link velocity, but there is no capability for backlink history. The DataForSEO `data` payload is unspecified (it requires an array of task objects with `target`, `limit` and `order_by`). | Add `dfs.backlinks_history` or drop the claim. Document the payload. |
| M8 | `seo-paid-organic:55,63` | The headline hardcodes "$" (Ads cost is in account currency). The savings formula (spend × retention) is ambiguous. There's no `login_customer_id` for manager-account access. The search-term report hides low-volume terms. | Use `customer.currency_code`. Define savings as spend avoided minus lost conversions' value, with a recommended pause test. Add the `login_customer_id` runtime. |
| M9 | `seo-content-brief:44,75` | The web-search fallback has no capability (Tavily is configured but unregistered). Web results are not Google's ranking order and carry no SERP features. With `markets = WORLDWIDE`, DataForSEO location and language are unspecified. | Register the search capability. Label the SERP as "approximate (web search)". Map markets to a location per language. |
| M10 | `capabilities.json:69` (`dfs.serp`) | `live/regular` lacks the full SERP-feature set the brief relies on (featured snippet, PAA, video). | Use `/v3/serp/google/organic/live/advanced`. |
| M11 | `gsc.keywords_*`, `planner.ideas` runtime | Language, country and geo are never passed, so volumes are all-language and all-location on a 4-language site. | Add `language` and `geo_targets` runtimes, fed from profile `languages`/`markets`. |
| M12 | `seo-content-refresh:44,49` | "Retire" is decided from GSC alone (no conversions, no backlinks). 90 days vs the previous 90 ignores seasonality. | Gate "retire" on GA4 key events and backlinks. Offer a year-over-year compare. |
| M13 | `seo-rank-tracking:3,61` | "Did the update hit me" has no data source for algorithm-update dates, so the answer comes from model memory. | Require a user-supplied date, or keep a dated reference list. |
| M14 | `seo-audit:68`, `seo-keyword-strategy:61`; `seo-rank-tracking:50`; `seo-content-refresh:48`; `seo-indexation:51` | Undefined inputs: `covered.txt` (no step creates it), "real impressions", the `thresholds` keys, and "excluded volume". | Define each one, with defaults in the profile schema. |
| M15 | `seo/check.sh:12`; `.roo/mcp.json` | CI isn't portable: `--validate-live` spawns servers from `/home/francesco/...` and `/mnt/backup/...` paths. | Split into an offline CI check (validating against cached `tool-schemas.json`) and a local live check. |
| M16 | `AGENTS.md` vs every skill's *Memory-Bank Isolation* | The repo rule says "MUST read /memory-bank before every task"; the skills say "MUST NOT read". | Add an explicit exception for SEO skill runs in `AGENTS.md`. |
| M17 | `server.py:110,60` | Iterating the client pager follows `next_page_token`, so `page_size` doesn't cap total results, and extra page fetches bypass the rate gate. **Probable; verify with one live call.** `UNKNOWN`/`UNSPECIFIED` months are silently mapped to January. | Read one page (`response.pages` → first). Skip unknown months. |
| M18 | `capabilities.json:62`; `server.py:106-118` | Retries are layered: the registry policy has 3 retries and the server has 4 attempts, so up to 12 calls on a 1-QPS quota. The time budget excludes the next call's duration, so the total can exceed the 60 s client timeout. | Retry in one layer only. Include the expected call time in the budget. |
| M19 | `seo/config/sites/pbservices.ge.json` | Brand terms are duplicated in EN `priority_keywords` (inflating coverage). There are no Cyrillic or misspelled brand variants for the RU split. `"Category"` is listed as a service. `priority_pages` and `competitors` are empty, so several workflows always fall back. | Clean up the profile, and validate that brand terms aren't in priority keywords. |

### Low

| ID | Location | Issue |
|---|---|---|
| L1 | `capabilities.json` | 10 capabilities are unused: `dfs.domain_overview`, `ga4.landing_pages`, `ga4.monetisation`, `gsc.device_performance`, `gsc.geo_query`, `gsc.keywords_stats`, `gsc.keywords_traffic`, `gsc.low_hanging_fruit`, `gsc.recommendations`, `gsc.time_series`. |
| L2 | All `SKILL.md` | Heavy boilerplate. *Memory-Bank Isolation* and *Output Structure* are identical in all 12 skills; *Files* has 2 variants, *Privacy* 4, *Configuration* 7. `test_skill_docs.py` enforces 10 sections, while the README claims the full 20-section shape is enforced. |
| L3 | `seo/README.md:22,114`; `memory-bank/systemPatterns.md:38`; `memory-bank/progress.md` | Doc drift: "seven GA4 capabilities" (there are 8); "WeasyPrint default" (report-export uses Chromium first); "18 SEO/GEO skills"; Upcoming items reference the pruned `seo-opportunity` and `seo-local`; "SearchGPT"; the SERP-feature list omits AI Overviews. |
| L4 | `seo-audit:43-44`; `seo-content-brief:41`; `seo-rank-tracking:40` | *Data Sources* tables list tools that the workflows never call, and there's a dangling `*` on `compare_engines`. |
| L5 | seo-technical, seo-backlink-check | The as-of line prints a GSC window and lag for data that isn't windowed GSC data (PageSpeed snapshots, live DataForSEO). |
| L6 | `seo/references/data-source-map.md:7`; `seo-backlink-check:54` | GA4 is called "near-real-time". `run_report` is standard processed data; only the realtime tool is real-time. |
| L7 | `seo-technical:47` | The representative-template sample ignores language variants (e.g. the RTL `/ar/` template). |
| L8 | `seo-keyword-strategy:91` vs `seo-content-brief:88` | Planner 429 advice conflicts ("raise the retry budget" vs "fall back, do not loop"), and raising it past about 55 s triggers client timeouts. |
| L9 | `seo/orchestrate.py:52-54` | Re-running overwrites an existing `findings.json` and `context.json` without warning. |
| L10 | `seo/window.py` (default lag 2) | GSC final data often lands 2–3 days later, so the last day can be partial. Consider lag 3, or check that the end date has data. |
| L11 | `domain-knowledge.md:102-110` | The anchor-text benchmark is presented as fact. Its ranges are internally inconsistent (they sum to 75–125%), the threshold "<10–15%" is ambiguous, and the shared methodology hardcodes the site's own brand. |

---

## 3. Quality vs industry practice

| Practice | Status | Notes |
|---|---|---|
| Single source of truth for integrations | ✅ Strong | The registry plus live schema validation and a semantic allowlist is rare and valuable. Weakened by H4. |
| Determinism and provenance | ⚠️ Partial | Absolute windows and the as-of line are good; C2 and L5 undermine the claim. |
| Data-correctness rules (GSC sampling, anonymization, row limits, engine) | ❌ Weak | C3, C4, H12, H13: the most common sources of wrong SEO numbers are unhandled. |
| Never-fabricate / estimate labelling | ⚠️ Partial | Strong policy, but broken enforcement (C1, H5) and a missing reference (C5). |
| Graceful degradation | ✅ Good | `unavailable` block and fallbacks are good, but H11 contradicts them. |
| Safe side effects | ❌ | H3 auto-submits; H10 writes to a tracked file. |
| Current SEO knowledge | ⚠️ | M1–M3, H16 and L3 are outdated (keyEvents, AI crawler roles, FAQ removal, INP field-only). |
| Tests | ⚠️ | Unit tests are solid; there are no behavioural or golden tests, and none of the 21 Critical/High issues is caught. |
| Maintainability | ⚠️ | Clear layout and references, but duplicated boilerplate, dead capabilities and a one-way resolver. |

---

## 4. Prioritized feedback

### Critical fixes (→ ~7.0)

1. **Make the evidence gate real (C1, H5).** Every skill gets a mandatory "persist raw tool output" step, via a `seo/record.py` helper that appends `{cap, args, timestamp, response}` to `context.json`. The validator must fail on an empty or missing data file when findings contain URLs, and must normalize URLs (no ASCII escaping, strip trailing punctuation, `unquote`).
2. **Window integrity (C2).** Add a per-section `window` to `findings-schema.json`. Recompute `seo_audit`-type findings from `analytics_query` over the resolved window, or label the tool's own window. Pass `days` to `genai_query_insights`.
3. **GSC data correctness (C3, C4, H12, H13).** Add `gsc.page` (and a no-dimension totals capability for reconciliation). Set `rowLimit: 25000` and `engine: "google"` in the args. Add a truncation rule. Document impression-weighted aggregation in `domain-knowledge.md`.
4. **Remove the invented CTR (C5).** Ship a labelled CTR-by-position heuristic, or compute the site's own CTR curve from GSC, and cite it exactly.

### High-value improvements (→ ~8.5)

5. **Planner (H1, H2, M11, M17, M18):** correct limits (20 seeds, 10 geos), batching, `ads_customer_id` in the profile, language and geo from the profile, single-page reads, a single retry layer.
6. **Indexation (H3, H8, H9):** opt-in submission with confirmation; an honest, sampled coverage method; a fetch capability for hreflang (register Tavily `extract`, or a small stdlib fetcher).
7. **Resolver (H4):** marker-based regeneration, plus round-trip and alias-rename tests.
8. **Skill logic bugs (H6, H7, H10, H14, H15, H16):** an AI-filtered time series; an organic channel filter; split recommended vs done history; longest-prefix language mapping; a mutually exclusive decay table; PageSpeed field vs lab.
9. **One degradation rule (H11)** in `data-source-map.md`, referenced by every skill.
10. **Refresh the domain knowledge (M1–M3, L3):** `keyEvents`, an AI-crawler purpose table, FAQ removal, AI Overviews as a SERP feature.
11. **Behavioural tests:**
    - Golden fixtures per skill: canned tool outputs → expected findings invariants.
    - Validator negative tests: Cyrillic URLs, punctuation, malformed findings, window sanity.
    - Planner limit tests at 20 and 10.
    - A registry-change round-trip test.

### Optional enhancements (→ 9+)

12. Move shared sections into `seo/references/skill-common.md` and generate each `SKILL.md` from a template plus a per-skill fragment (L2).
13. Remove or justify the 10 unused capabilities. Generate *Data Sources* tables from the registry so they can't drift (L1, L4).
14. Portable CI: run the offline check against a cached `tool-schemas.json` in CI and keep `--validate-live` as a local pre-release step (M15).
15. Profile hygiene: RU and misspelled brand variants, brand terms kept out of priority keywords, `markets` mapped to geo targets, and populated `priority_pages` and `competitors` (M19).
16. Use the configured Tavily `crawl`/`map` to give seo-internal-links a real link graph instead of the GSC approximation.
17. Paid-organic: account currency, and recommending pause-test (incrementality) methodology (M8).
18. Clean up doc drift in the README and memory-bank (L3), and resolve the `AGENTS.md` memory-bank conflict (M16).

---

## Sources

- [Google — Search Console performance data: filtering and limits](https://developers.google.com/search/blog/2022/10/performance-data-deep-dive): anonymized queries, 1,000-row default, 25,000 max.
- [Search Console API — searchanalytics.query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)
- [Google — Minor cleaning up in the Search Console API (2019)](https://developers.google.com/search/blog/2019/08/minor-cleaning-up-in-search-console-api): sitemap "Indexed" field no longer populated.
- [JC Chouinard — the API does not cover the Index Coverage report](https://www.jcchouinard.com/index-coverage-report/)
- [Google Ads API — KeywordSeed (≤20 keywords)](https://developers.google.com/google-ads/api/reference/rpc/v12/KeywordSeed) · [GenerateKeywordIdeasRequest (≤10 geos, pagination)](https://developers.google.com/google-ads/api/reference/rpc/v22/GenerateKeywordIdeasRequest)
- [DataForSEO — Google Organic SERP overview (Regular vs Advanced)](https://docs.dataforseo.com/v3/serp/google/organic/overview/)
- [Coupler.io — GA4 `conversions` → `keyEvents`](https://help.coupler.io/article/531-may-2024-deprecated-conversions-metrics)
- [Google — Changes to HowTo and FAQ rich results](https://developers.google.com/search/blog/2023/08/howto-faq-changes) · [SEJ — Google drops FAQ rich results (2026)](https://www.searchenginejournal.com/google-drops-faq-rich-results/574429/)
- [SEJ — Google-Extended doesn't affect Search](https://searchenginejournal.com/google-clarifies-the-google-extended-crawler-documentation/507645)
- [OpenAI — Overview of crawlers](https://developers.openai.com/api/docs/bots.md) · [Anthropic — Crawlers](https://support.claude.com/en/articles/8896518-anthropic-crawlers)
- [Chrome — CrUX data in PageSpeed Insights](https://developer.chrome.com/docs/crux/guides/pagespeed-insights?hl=en)
