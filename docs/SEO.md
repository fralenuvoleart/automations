# SEO reports — how the toolkit works and what each report is for

This is the owner-facing guide to the SEO toolkit in [`.agents/skills/`](../.agents/skills/) and
[`seo/`](../seo/). It explains what each report answers, what it needs, where the output lands, and
what to do when a source is missing. For every command mentioned here, see
[`seo/COMMANDS.md`](../seo/COMMANDS.md); for the internals, see [`seo/README.md`](../seo/README.md).

## What it is

13 reports, each an Agent Skill with a fixed data plan behind it. You ask for a report; the toolkit
pulls the numbers from Search Console (and, when configured, GA4, Google Ads, Keyword Planner,
DataForSEO), saves every answer as evidence, calculates the figures in code, and the assistant only
writes the interpretation. Nothing in a report is free-hand: every URL and every number is checked
against what was actually returned, otherwise the report is refused.

Two consequences worth knowing up front:

- **A report cannot invent data.** Missing sources appear as an "Data availability" line instead of
  being estimated or remembered. One exception: `seo-backlink-check` refuses to run at all without
  DataForSEO, because a backlink report with no backlinks is worse than no report.
- **The same report run twice on the same day costs almost nothing** the second time: identical calls
  are answered from a local cache.

## The 13 reports

| Report | The question it answers | Needs | Notes |
|---|---|---|---|
| `seo-audit` | "How is the site doing overall, and what are the five things to fix first?" | Search Console (GA4 optional) | The composite view: 90 days vs the previous 90. Declining pages, quick wins, cannibalization, an indexation spot-check, engagement, AI share. Start here. |
| `seo-brief` | "What should I do this week?" | Search Console + the latest report of every other skill | One page: 8-week trend, the top actions merged from all reports, what changed since last week, which reports are due (or cannot run). Meant for a weekly cadence. |
| `seo-technical` | "Is anything technically holding the site back?" | Search Console (+ PageSpeed, schema, crawl when available) | Core Web Vitals on real-user data, accessibility, structured data, crawler access, robots.txt per priority page. Reports field vs lab data honestly. |
| `seo-indexation` | "Are the right pages in Google, and is the sitemap clean?" | Search Console | Sampled URL Inspection (the API has no full index report), sitemap status, hreflang reciprocity, canonicals. Gives you a "request indexing" list. |
| `seo-internal-links` | "Which pages are too deep or under-linked, and where do I add links?" | Search Console + a local crawl | Real link graph: inlinks, click depth, orphans against the sitemap, broken internal links, plus the exact source page and anchor to add. |
| `seo-content-refresh` | "Which pages lost traffic, and what do I do with each?" | Search Console (GA4/DataForSEO optional) | Every declining page gets one cause — ranking loss, demand drop, CTR loss, vanished — and a refresh / consolidate / retire call, gated on contacts and backlinks. |
| `seo-content-brief` | "What should this article cover to rank?" | Search Console (+ SERP/web search/planner when available) | SERP-driven brief for one keyword: what ranks, the outline, questions, internal links, and whether to create or expand. Takes a keyword as input. |
| `seo-keyword-strategy` | "Where can we realistically win, and what is it worth?" | Search Console (+ Keyword Planner/DataForSEO optional) | Footholds valued with the site's own click-through history, expansion per language, competitor gap, tiered roadmap. |
| `seo-rank-tracking` | "What moved, and which queries did it?" | Search Console (+ DataForSEO/Bing optional) | Query-level winners and losers between two periods (or around a dated event), with the page that moved. Weekly variant for Monday–Sunday weeks. |
| `seo-brand-split` | "How much of our traffic is brand vs non-brand?" | Search Console + the site's rules file | Brand and non-brand per language, unattributed share. Small and fast — useful as a sanity check. |
| `seo-ai-visibility` | "Do ChatGPT and Perplexity send us visitors, and can their crawlers even reach us?" | Search Console (+ GA4 optional) | AI-assistant referrals, the pages they cite, AI share of organic, and robots.txt verdicts per AI crawler on your priority pages. |
| `seo-backlink-check` | "Who links to us, and what do we lack next to a competitor?" | **DataForSEO (required)** + GA4 | Referring domains, authority, anchor mix, new/lost links, link gap, and which linking sites actually send visitors. Fails closed without DataForSEO. |
| `seo-paid-organic` | "Am I paying Google for clicks I already get free?" | Search Console + Google Ads | Paid/organic overlap in the account currency, brand-bidding waste, paid terms with no organic coverage, plus a test plan before cutting spend. The Google Ads server is used only here. |

## How a report is produced

1. **Run one command** — [`python3 seo/pipeline.py --skill <skill> --site <domain>`](../seo/COMMANDS.md).
   It fixes the date window, makes every call the report needs (cache first), saves each answer, and
   calculates the figures into `computed/`.
2. **The assistant interprets** those calculated figures and writes `findings.json` — no API calls, no
   mental arithmetic.
3. **The gate checks it** — every URL must appear in the saved answers and every number must match what
   was returned or calculated, at the precision written.
4. **It becomes a report** — Markdown → PDF → email, via the shared `report-export` skill.

If a required source fails, the run stops with a readable error (`exit 1`) and says what to fix. If an
optional source fails, it is listed as unavailable and the report says so.

## Where the output lands

Everything lives outside the repository, under `~/Documents/seo-reports/<domain>/`:

```
README.md                  plain-language map of the folder
<date>/<report>/           one report run: report.md (send this), findings.json,
                           data/ (what each tool answered; *.rows.json = the same answer as plain rows),
                           computed/ (the calculated figures), pipeline.json (what ran and what was skipped)
spreadsheets/<date>/       runs.csv, totals.csv, pages.csv, queries.csv, actions.csv — for Excel or Sheets
_cache/                    answers already given, reused by later reports
```

Refresh the spreadsheets at any time with `python3 seo/runs.py export --site <domain>`.
Old runs are kept until pruned: `retention_days` is 180 and nothing prunes automatically —
`python3 seo/pipeline.py --prune` applies it (also valid before a run).

## A sensible cadence

| How often | Reports |
|---|---|
| Weekly | `seo-brief`, `seo-rank-tracking` (weekly variant), `seo-brand-split`, `seo-ai-visibility` |
| Monthly | `seo-audit`, `seo-technical`, `seo-indexation`, `seo-internal-links`, `seo-content-refresh`, `seo-keyword-strategy` |
| Quarterly / on change | `seo-backlink-check`, `seo-paid-organic` |
| On demand | `seo-content-brief` (before writing or rewriting a page) |

The cadence lives in [`seo/config/settings.json`](../seo/config/settings.json) (`cadence_days`); `seo-brief`
uses it to say which reports are due, and distinguishes "due" from "cannot run — missing source".

## Each site needs two files

| File | Holds | Validated by |
|---|---|---|
| [`seo/config/sites/<domain>.json`](../seo/config/sites/) | site facts only: `gsc_property`, `ga4_property`, priority pages, markets, competitors, Ads customer id, threshold overrides | `python3 seo/site_profile.py --site <domain> --validate` |
| [`seo/config/rules/<domain>.json`](../seo/config/rules/) | the classification: brand terms, query categories, page tags and languages, GA4 channels, tracked keywords with their target pages | `python3 seo/rules.py --site <domain> validate` |

The rules file is the single source for "what counts as brand", "which language a page is", and "which
keyword we track" — shared with the SEO sheet. The profile holds facts and never classification, so the
two cannot disagree.

## Known limits (deliberate, and stated in the reports)

- **No JavaScript rendering.** The crawler reads server-rendered HTML, so a client-side-rendered site
  would look empty to it. Fine for a WordPress site; the report says so when it matters.
- **Sampled indexing.** Search Console's API has no Page indexing report, so indexation is a sample of
  priority URLs, never a site-wide count. Sitemap indexed counts no longer exist in the API at all.
- **Estimates are labelled.** Keyword volumes, link authority and competitor traffic are third-party
  estimates and are marked as such; where a number is a heuristic, the report says which basis it used.
- **robots.txt only.** CDN/WAF bot rules are not visible from here — the report tells you to check the
  host's firewall for those.
- **One window per report.** Each report keeps its own window (28, 90 days, or 8 weeks) and states it;
  two reports can legitimately quote different click totals for "the same" question.

## When something looks wrong

| Symptom | First thing to try |
|---|---|
| A report stops with `exit 1` | read the error in `{run_dir}/pipeline.json` — it names the source and the reason |
| "Data availability" lists a source | that source is not configured or failed; the rest of the report is still valid |
| The report quotes a figure you cannot find | it must appear in `data/` or `computed/` of that run folder, otherwise validation would have refused it |
| A second run today seems instant | the saved answers from earlier today were reused (by design) — add `--force` to fetch everything again |
| You want the numbers in a spreadsheet | `python3 seo/runs.py export --site <domain>` |

Health check of the toolkit itself: `bash seo/check.sh` (offline, no dependencies). It must print
`ALL GREEN` before you trust any report.
