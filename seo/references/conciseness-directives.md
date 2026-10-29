# Conciseness & Consistency Directives (SEO)

Mandatory, grep-auditable rules for every SEO report.

1. **Never fabricate.** If a metric call fails, show the item without numbers and say why. Do not substitute third-party estimates for the site's own data.
2. **Label estimates.** Any number not from the site's own GSC/GA4 data must carry `estimate`/`heuristic` (e.g. planner volumes, DataForSEO positions, savings).
3. **As-of line first.** State the resolved window and UTC generation timestamp ([`report-structure.md`](report-structure.md)).
4. **Absolute windows only.** Pass literal `YYYY-MM-DD`; never relative phrases. GSC lags ~2 days; never include today.
5. **No code-level fixes.** SEO reports target owners/marketers; recommend actions doable in the relevant panel or content system, not edits to this repo's files/functions.
6. **Plain language.** No filler; tables over prose for lists of numbers.
7. **State the connection status.** Name any missing server rather than guessing its data.
8. **One job per skill.** If the task belongs to another skill, hand off (see each skill's "Related / Delegation").
