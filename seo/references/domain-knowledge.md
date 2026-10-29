# SEO Domain Knowledge (methodology reference)

Shared interpretation guide for the SEO skills. This is **methodology and
definitions**, not a fact database — any numeric benchmark below is an
industry rule-of-thumb (or a published platform threshold, where noted), not a
measured fact, and must be labelled as a heuristic in reports (see
[`conciseness-directives.md`](conciseness-directives.md)).

## Search intent taxonomy
Classify every target keyword into one of four intents; the intent dictates the
page format.

| Intent | Signal | Page format |
|---|---|---|
| Informational | "how", "what", "guide", "why" | Guide / explainer |
| Navigational | brand + destination | Home / product / login |
| Commercial | "best", "vs", "review", "alternative" | Comparison / listicle |
| Transactional | "buy", "price", "near me", "download" | Product / landing page |

## SERP feature types
Featured snippet, People Also Ask (PAA), video, image pack, local pack,
shopping, sitelinks, knowledge panel. A page that already ranks 2–10 for a
query with a featured snippet is a snippet-capture candidate (restructure the
answer into a concise definition/list/table near the top).

## Position & CTR interpretation (heuristic)
CTR falls steeply with position. Treat the following as **rough heuristics only**
— actual CTR varies by query, intent, SERP features, and brand:

- Position 1: highest CTR; positions 2–3 still strong.
- Positions 4–10: materially lower; a title/meta problem is likely when CTR is
  far below the position's typical band.
- A page ranking ≤5 with very low CTR is a **title/meta** problem, not a
  ranking problem.

Never present these bands as measured values for the site; derive the site's
own CTR from its GSC data and compare against its own history.

## Striking distance
Queries ranking roughly **8–20** with meaningful impressions are the highest-ROI
optimisation targets: a small on-page improvement can move them onto page 1.
Favour high-impression striking-distance queries over low-volume ones.

## Cannibalization
Two or more URLs ranking for the same query, splitting signals. Detect by
grouping GSC `query` × `page`. Apply the **Cannibalization Decision Matrix**:

| Scenario | Primary Signal | Recommended Action |
|---|---|---|
| Same search intent, duplicate/overlapping content | Page A has higher clicks/backlinks, Page B is thin or stale | **301 Redirect** Page B → Page A; merge any unique information into Page A. |
| Specialized landing page vs broad category/hub | Page A is specific service/product; Page B is broad guide | **Canonicalize** or preserve both, adding an explicit contextual internal link from Page B to Page A with the exact target query anchor. |
| Different search intents (e.g. guide vs pricing) | Both pages deserve independent rankings | **De-optimize** secondary page (revise H1, title tag, intro) to target its distinct sub-intent; re-point internal links. |

## Content decay
A page whose clicks fall materially period-over-period while impressions hold
is decaying (content freshness, lost links, or a competitor overtaking it).
Distinguish decay (both down) from a ranking loss (position down, impressions
held) from a demand drop (impressions down).

## Core Web Vitals (published thresholds)
Google's published "good" thresholds (field data, 75th percentile):

| Metric | Good | Needs improvement | Poor |
|---|---|---|---|
| LCP (Largest Contentful Paint) | ≤ 2.5 s | 2.5–4.0 s | > 4.0 s |
| INP (Interaction to Next Paint) | ≤ 200 ms | 200–500 ms | > 500 ms |
| CLS (Cumulative Layout Shift) | ≤ 0.1 | 0.1–0.25 | > 0.25 |

PageSpeed lab data is a **snapshot**, not field data — label it as such.

## E-E-A-T (Experience, Expertise, Authoritativeness, Trust)
A quality lens, not a direct ranking factor. Signals: named authors with
credentials, cited sources, first-hand experience, accurate/updated facts,
clear contact/company info, HTTPS, no deceptive UX. For YMYL topics (money,
health, legal) the bar is higher.

## International SEO (multilingual / multi-region)
- One URL per language/region; use `hreflang` (including `x-default`) to map
  them, and keep the mapping reciprocal (if page A links to page B with `hreflang="ru"`,
  page B must link back to page A with `hreflang="en"`).
- Every language variant must reference self-referential `hreflang` plus `x-default`.
- Derive language deterministically from the URL path prefix (from the site profile's
  `language_paths`, e.g. `{"EN": "/", "RU": "/ru/"}`).
- Do not auto-redirect by IP alone; offer a visible language switcher.
- Localise keywords per language (do not translate literally) — a language's
  search demand differs from a word-for-word translation.
- Keep one self-referential canonical per language variant; avoid cross-language canonicals.

## Local SEO
- The local pack is driven by relevance, distance, and prominence — a Google
  Business Profile (GBP) is the primary lever.
- NAP consistency (name, address, phone) across the site and citations.
- Local-intent queries ("near me", city names) are the organic signal; the map
  pack itself needs GBP data (not available from GSC alone).

## Content quality (helpful-content lens)
- Answer the query directly and early; match the format that ranks.
- Depth over padding: cover the sub-questions (PAA) the SERP implies.
- Original value: data, examples, first-hand experience — not a rehash.
- Freshness: update facts/dates; a stale page decays.

## Link building (basics & anchor distribution)
- Relevance and authority beat volume; a few strong, topically-relevant links
  outperform many weak ones.
- **Healthy Anchor Profile (B2B/Services benchmark):**
  - Branded anchors (`"PB Services"`, `"PB Services Georgia"`): **50–70%**
  - Naked URLs / Domain (`"pbservices.ge"`, `"https://..."`): **15–25%**
  - Topical / Natural / Generic (`"website"`, `"learn more"`, `"click here"`): **10–15%**
  - Exact-match commercial keywords (`"open bank account georgia"`): **< 10–15%** (higher triggers Penguin/algorithmic manipulation filters).
- Link velocity spikes and low-authority-dominated profiles are risk signals.

## Keyword difficulty & winnability (heuristic)
- Prefer keywords where the site already has a foothold (striking distance) or
  a topical match over high-volume head terms it cannot win.
- Weight by relevance to a service line; drop off-topic terms even if
  high-volume.

## AI / Generative Engine Optimization (GEO & AEO)
Generative engines (SearchGPT, Perplexity, Claude, Gemini, Copilot) synthesize answers
from citable, high-information-gain pages:

### AI Crawler Accessibility
Verify that `robots.txt` and WAF/edge firewall rules permit major AI search crawlers:
- `GPTBot` (OpenAI training/search), `OAI-SearchBot` (SearchGPT real-time indexer)
- `PerplexityBot` (Perplexity search indexer)
- `ClaudeBot` (Anthropic web indexer)
- `Google-Extended` (Gemini training control)
- `Applebot-Extended` (Apple Intelligence)
Blocking search-facing user-agents while trying to rank in AI search is a critical disconnect.

### Information Gain & Quotability Scorecard
To maximize LLM extraction and citation frequency:
- **First-Fold Definition:** Direct, definitive answer within the first 45 words of the lead section (`X is Y that does Z`).
- **Data & Statistical Density:** Include specific metrics, percentages, dates, and benchmarks; LLMs bias heavily toward pages providing primary quantitative evidence.
- **Structured Synthesis Format:** Markdown/HTML tables for comparisons; bulleted lists with bold lead-ins for multi-part steps.
- **Sentence Salience:** Write clean, declarative sentences that can be quoted verbatim without requiring surrounding context.

### Entity Disambiguation & Knowledge Graph Grounding
LLMs resolve entities against structured knowledge graphs. Enhance Schema markup with:
- `sameAs` array on `Organization` / `LocalBusiness` linking to authoritative entity sources (Wikidata, Wikipedia, LinkedIn, Crunchbase, official company registries).
- Explicit `author` and `reviewedBy` objects of type `Person` with credentials to establish verified E-E-A-T.
- Clear `@id` URIs to disambiguate the subject across multilingual versions.

## Estimates vs real data
- **Real** (the site's own): GSC positions/clicks/impressions, GA4 sessions/conversions.
- **Estimates** (third-party): DataForSEO/Ahrefs/Semrush link and position data,
  Keyword Planner volumes/bids, `seo_keywords_research` volumes.
Always label the second group. Never substitute an estimate for the site's own
data when the site's own data is available.
