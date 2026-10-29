# SEO Domain Knowledge (methodology reference)

Shared interpretation guide for the SEO skills. This is **methodology and
definitions**, not a fact database — any numeric benchmark below is an
industry rule-of-thumb, not a measured fact, and must be labelled as a
heuristic in reports (see [`conciseness-directives.md`](conciseness-directives.md)).

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
grouping GSC `query` × `page`; the fix is consolidation (merge, canonical, or
re-target one page), not more content.

## Content decay
A page whose clicks fall materially period-over-period while impressions hold
is decaying (content freshness, lost links, or a competitor overtaking it).
Distinguish decay (both down) from a ranking loss (position down, impressions
held) from a demand drop (impressions down).

## AI / generative visibility
AI engines (ChatGPT, Perplexity, Claude, Gemini, Copilot) send traffic that
GA4 records as referral or direct — so GA4 AI-referral counts are a **lower
bound**, never the full picture. Pages that get cited tend to lead with a direct
answer, use clean headings, include stats/definitions, and carry schema. GSC
"generative-shaped query" heuristics are an **undercount**, not AI traffic.

## Estimates vs real data
- **Real** (the site's own): GSC positions/clicks/impressions, GA4 sessions/conversions.
- **Estimates** (third-party): DataForSEO/Ahrefs/Semrush link and position data,
  Keyword Planner volumes/bids, `seo_keywords_research` volumes.
Always label the second group. Never substitute an estimate for the site's own
data when the site's own data is available.
