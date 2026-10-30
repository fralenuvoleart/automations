# SEO Domain Knowledge (methodology reference)

Shared interpretation guide for the SEO skills. Thresholds live in code
([`seo/gsc_metrics.py`](../gsc_metrics.py) `DEFAULTS`, overridable per site via the
profile's `thresholds`) so every report applies the same rules. Any number that is
not the site's own measured data is a **heuristic** and must be labelled as such
([`conciseness-directives.md`](conciseness-directives.md)).

## Search Console data rules (correctness)
- **Anonymized queries.** Rows that include the `query` dimension omit anonymized
  (rare) queries; page rows and daily totals include them. So: page metrics come from
  `gsc.page`, query metrics from `gsc.query`, and `gsc.page_query` is used only to
  attribute queries to pages. The gap (`gsc_metrics.py anonymized`) is reported, never hidden.
- **Row limit.** The API returns 1,000 rows by default and at most 25,000 per request; every
  `analytics_query` capability pins `rowLimit: 25000`. A pull that returns exactly the limit is
  **truncated**: items missing from it are "beyond the row cutoff", not "lost"/"new".
- **Engine.** The search-console server defaults to `engine: all` (Google + Bing); every
  capability pins `engine: google`. Bing is only compared explicitly (`gsc.compare_engines`).
- **Aggregation.** Sum clicks and impressions; CTR = clicks / impressions; average position is
  **impression-weighted**. A query's position is read from query rows, never averaged from
  query × page rows.
- **Freshness.** Final GSC data lands 2–3 days late; windows end at `today − 3`
  ([`seo/window.py`](../window.py)). GA4 processed data: `today − 2`.
- **Windows.** Every windowed call uses the run window from `.run_state.json`
  (`seo/record.py` rejects others). A tool that cannot take the window (e.g. a fixed lookback)
  must have its own period stated in that section (`sections[].window`).
- **Calendar weeks.** Weekly reporting uses Monday–Sunday weeks ending with the latest complete
  week (`orchestrate.py --weeks N`, each week listed in `window.weeks`), as in the SEO sheet. Pull
  one week per call: on this site an 8-week query × date or page × date pull exceeds 25,000 rows.
- **Jump links.** Search Console reports `page#section` jump links as separate URLs that repeat
  the page's impressions in the same result. Page-level analyses in `seo/rules.py` merge them into
  their page: clicks summed, impressions and position from the largest variant.

## Search intent taxonomy
| Intent | Signal | Page format |
|---|---|---|
| Informational | "how", "what", "guide", "why" | Guide / explainer |
| Navigational | brand + destination | Home / product / login |
| Commercial | "best", "vs", "review", "alternative" | Comparison / listicle |
| Transactional | "buy", "price", "near me", "download" | Product / landing page |

## SERP features
AI Overviews / AI Mode, featured snippet, People Also Ask (PAA), video, image pack, local
pack, shopping, sitelinks, knowledge panel. Read them from a live SERP
(`dfs.serp`, the *advanced* endpoint) — a web-search fallback shows neither Google's order nor
its features. A page ranking 2–10 for a query with a featured snippet is a snippet-capture
candidate (concise definition/list/table near the top). **FAQ and HowTo rich results no longer
appear in Google Search** (restricted 2023, FAQ removed 2026): never promise them.

## CTR by position
Expected CTR per position bucket comes from the first source with ≥ `curve_min_impressions`
(non-brand, impression-weighted; each bucket carries its `source`):
1. **`site`** — this run's window (the current SERPs, AI Overviews included where they show).
2. **`site_12m`** — the site's own last 12 months (`--curve-query`, pulled by the plans as
   `query_12m`): more data per position, still this site's queries, markets and SERP layouts.
3. **`benchmark`** (positions it covers), labelled *heuristic* — a dated, post-AI-Overviews study
   measured in Search Console, kept in [`config/ctr-benchmark.json`](../config/ctr-benchmark.json)
   (source, publication month, `max_age_months`). `python3 seo/gsc_metrics.py benchmark` shows its
   age; `check.sh` warns when it is stale — replace it with a newer study, never with a pre-2024 one
   (AI Overviews cut top-position CTR sharply, and published curves vary 2× by query mix and layout).

Buckets none of these fill are "insufficient data" — never invented. Reports state the basis
(`basis` in the computed output) whenever a benchmark value drives a finding.
- **Low CTR** (`gsc_metrics.py low-ctr`): position ≤ `low_ctr_max_position` and CTR below
  `low_ctr_ratio` × expected CTR for that position → a title/meta (or SERP-feature) problem, not
  a ranking problem.
- **Value model** (`gsc_metrics.py value`, always labelled *estimate*):
  `clicks gain = volume × (CTR at target position − current CTR)`;
  `value = clicks gain × CPC`, CPC = midpoint of the planner's low/high top-of-page bids
  (account currency). Default target position 3.

## Striking distance
Queries at average position `striking_min`–`striking_max` (default 8–20) with ≥ `min_impressions`
are the highest-ROI on-page targets; rank by impressions (`gsc_metrics.py striking`).

## Rank movers
Query-level (`gsc.query`, both periods): winner/loser when position moves ≥ `mover_min_delta`
(default 2) on a query with ≥ `min_impressions`; losers ranked by clicks lost. New/lost queries
only when neither pull is truncated. Algorithm-update questions need a **date from the user or
the Google Search Status Dashboard** (record it) — never from memory.

## Cannibalization
Detect: a query where ≥ 2 pages each hold ≥ `cannibal_min_share` (default 10 %) of its
impressions (`gsc_metrics.py cannibalization`). Decide:

| Scenario | Primary signal | Action |
|---|---|---|
| Same intent, overlapping content | Page A has more clicks/links; B thin or stale | **301** B → A; merge B's unique content into A |
| Specific landing page vs broad hub | A = service page; B = broad guide | Keep both; **canonical** only if duplicate, else contextual link B → A with the query as anchor |
| Different intents (guide vs pricing) | Both deserve rankings | **Differentiate** B's title/H1/intro toward its sub-intent; re-point internal links |

## Declining pages (decision table)
A page is **declining** when its clicks fell by ≥ `decay_pct` (default 30 %) between periods
(page rows, ≥ `min_impressions` before). Its cause is classified in this order — the first match
wins, so labels are mutually exclusive (`gsc_metrics.py decay`):

| Order | Class | Rule | Action |
|---|---|---|---|
| 1 | `vanished` | no impressions now (and the pull is not truncated) | Inspect the URL (indexing, redirect, canonical) first |
| 2 | `ranking_loss` | average position worse by ≥ `pos_drop` (1.0) | Refresh: facts, depth, internal links; check who overtook it |
| 3 | `demand_drop` | position held, impressions down ≥ `imp_drop_pct` (20 %) | Check seasonality (YoY compare); consolidate/retire only if GA4 key events **and** backlinks are also negligible |
| 4 | `ctr_loss` | position and impressions held, clicks down | Rewrite title/meta; check new SERP features taking clicks |

Never recommend retiring a page on GSC data alone; prefer 301 to deletion.

## Search Console vs GA4
- Search Console counts Google clicks; GA4 counts sessions from every search engine and can split
  a visit into two sessions — totals never match, so compare **trends**
  (`ga4_metrics.py reconcile`). Diverging trends or a high `(not set)` landing-page share
  (sessions without a page_view) point to a tracking problem before an SEO one.
- GA4 channels, page types and languages come from the site rules (`ga4.landing_source` rows
  classified by `ga4_metrics.py breakdown`), so they match the SEO sheet.

## Tracked keywords and target pages
- The tracked set = Core + Brand (in the rules file) + automatic Proven / Opportunity / Generic
  picks (`rules.py keywords`); top 3 countries per keyword come from `gsc.geo_query`.
- Each tracked keyword has a `target_page`. `rules.py targets` flags **wrong page** (Google shows
  another page more often) and **target not ranking**; fix with internal links/anchors and
  title/H1 alignment, or change the target when the ranking page is the better answer.

## Brand vs non-brand
- Brand match: the `Brand` query category of the site rules (`seo/config/rules/<domain>.json`,
  first rule, on the lowercased query; include script/spelling variants in its regex).
- Language: the page's `page_languages` rule (pages without a language folder get the default).
  Classify query × page rows, then aggregate.
- Anonymized queries cannot be classified: report them as "unattributed" (site totals − rows).
- The signal that matters is **non-brand** growth; brand tracks demand.

## Core Web Vitals
"Good" thresholds apply to **field data (CrUX), 75th percentile**: LCP ≤ 2.5 s, INP ≤ 200 ms,
CLS ≤ 0.1 (poor: > 4.0 s / > 500 ms / > 0.25). PageSpeed's Lighthouse data is a **lab** snapshot:
INP cannot be measured in the lab (Total Blocking Time is its proxy). Pass/fail is judged on
field data only; with no CrUX data for the URL or origin, say "no field data" and report lab
values as diagnostics.

## Structured data
Useful types for a services business: `Organization`/`LocalBusiness`, `Service`-describing
`WebPage`, `Article`/`BlogPosting`, `BreadcrumbList`. Validate syntax with `gsc.schema`;
"required" means required by the page's purpose, not by a rich result. FAQ/HowTo markup earns no
Google rich result (see above).

## E-E-A-T
A quality lens, not a ranking factor. Signals: named authors with credentials, cited sources,
first-hand experience, accurate dated facts, clear company/contact info. YMYL topics (money,
legal, tax) carry a higher bar.

## International SEO
- One URL per language; `hreflang` on every variant, **self-referencing**, **reciprocal**, plus
  `x-default`. Verify from crawled HTML (`seo/site_crawl.py crawl`) — URL Inspection does not
  return hreflang.
- One self-referential canonical per language variant; never canonicalise across languages.
- Do not auto-redirect by IP; offer a language switcher. Localise keywords per language.

## Local SEO
Local pack = relevance, distance, prominence; Google Business Profile is the main lever
(not available from GSC). NAP consistency across site and citations. Local-intent queries
("near me", city names) are the organic signal.

## Content quality
Answer early; match the format that ranks; cover the sub-questions (PAA); add original data
and first-hand experience; keep facts dated and current.

## Links
- Relevance and authority beat volume.
- Anchor profile: judge against the **competitors' distributions** (DataForSEO), not a fixed
  ideal. Flag (heuristic) when exact-match commercial anchors exceed
  10 % of anchors or are the largest non-brand group, and when new links spike in
  `dfs.backlinks_new_lost` without a matching campaign or PR event.
- All link counts are third-party index **estimates**.

## Keyword difficulty & winnability
Prefer keywords with a foothold (striking distance) or a direct service-line match; drop
off-topic terms even if high-volume.

## Generative engines (GEO / AEO)
### Crawler access (robots.txt — `seo/site_crawl.py robots`)
| Token | Operator | Purpose | Blocking it… |
|---|---|---|---|
| Googlebot | Google | Search index incl. AI Overviews / AI Mode | removes the site from Search |
| Bingbot | Microsoft | Bing index (grounds Copilot) | removes Bing/Copilot visibility |
| OAI-SearchBot | OpenAI | ChatGPT search index & citations | removes ChatGPT search visibility |
| ChatGPT-User | OpenAI | user-initiated fetch (robots.txt may not apply) | blocks live fetches |
| Claude-SearchBot | Anthropic | Claude search index | reduces Claude search visibility |
| Claude-User | Anthropic | user-initiated fetch | blocks live fetches |
| PerplexityBot | Perplexity | Perplexity search index (not training) | removes Perplexity visibility |
| Perplexity-User | Perplexity | user-initiated fetch (generally ignores robots.txt) | — |
| GPTBot, ClaudeBot, CCBot | OpenAI, Anthropic, Common Crawl | model training | training opt-out only |
| Google-Extended | Google | Gemini training/grounding control | **no effect on Search or AI Overviews** |
| Applebot-Extended | Apple | Apple AI training control | training opt-out only |

Blocking a *search/retrieval* agent while seeking AI visibility is a critical disconnect;
blocking *training* agents is a business choice. WAF/CDN rules are invisible to robots.txt checks.

### Citability (heuristics)
- Direct answer within the first ~45 words after the H1 (`site_crawl.py facts` → `first_45_words`).
- Specific numbers, dates and sources; comparison tables; clean, quotable declarative sentences.

### Entity grounding
`Organization`/`LocalBusiness` with `sameAs` (Wikidata, LinkedIn, official registries),
`author`/`reviewedBy` `Person` with credentials, stable `@id` across language versions.

## Paid vs organic
"Double-paying" = paid spend on terms where the site ranks ≤ 3 organically. Spend avoided by
pausing is real; the clicks organic would *not* recapture are the cost. Size it as an
**estimate** and recommend a holdout/pause test before cutting spend permanently. Report money in
the account currency (`customer.currency_code`).

## Estimates vs real data
- **Real** (the site's own): GSC clicks/impressions/positions, GA4 sessions/key events, Ads spend.
- **Estimates** (third-party or modelled): DataForSEO/Ahrefs/Semrush link and position data,
  Keyword Planner volumes/bids, `seo_keywords_research` volumes, value models, heuristic CTRs.
Always label the second group; never substitute it for the site's own data when that exists.
