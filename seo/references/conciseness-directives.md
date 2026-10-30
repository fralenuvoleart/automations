# Conciseness & Consistency Directives (SEO)

Mandatory, grep-auditable rules for every SEO report.

1. **Never fabricate.** If a call fails, show the item without numbers and say why. Never fill a gap from memory or substitute third-party estimates for the site's own data.
2. **Record evidence.** Save every tool response with `seo/record.py` right after the call; numbers and URLs in the findings must come from those files.
3. **Compute, don't eyeball.** Deltas, movers, thresholds, CTR curves, splits and coverage come from `seo/gsc_metrics.py` / `seo/coverage.py` / `seo/site_crawl.py`, not mental arithmetic.
4. **Label estimates.** Any number not from the site's own GSC/GA4/Ads data carries `estimate` or `heuristic` (planner volumes, DataForSEO data, value models, heuristic CTRs, savings).
5. **Provenance line first.** State the resolved window (or snapshot date) and UTC generation time ([`report-structure.md`](report-structure.md)).
6. **Absolute windows only.** Pass literal `YYYY-MM-DD` from `.run_state.json`; never relative phrases, never today. If a tool uses its own period, state it in that section.
7. **No code-level fixes.** Reports target owners/marketers: recommend actions doable in the CMS, Search Console, Ads or hosting panel — not edits to this repo.
8. **Plain language.** No filler; tables over prose for lists of numbers.
9. **State connection status.** Name any missing source per the rule in [`data-source-map.md`](data-source-map.md).
10. **One job per skill.** Hand off per each skill's "Related / Delegation".
11. **Side effects need consent.** Never submit, delete or change anything outside the run directory (e.g. Indexing API, history `[done]` entries) without the user's explicit confirmation in this conversation.
