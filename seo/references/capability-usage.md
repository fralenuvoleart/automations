# Capability Usage

Capabilities are declared once in [`seo/capabilities.json`](../capabilities.json): `server` →
`tool` + fixed `args` + `runtime` (agent-supplied) + `desc` + optional `policy`.

## Authoring a skill
- Reference a capability, never a hard-coded tool: write `{{cap:gsc.page}}`.
- Shared/generated sections: `{{include:<name> k=v}}` — templates live in
  [`skill-common/`](skill-common/); `datasources`, `configuration` and `privacy` are generated
  from the capabilities the skill uses.
- Site-profile lookups: `{{site:<key>}}`.
- Run `python3 seo/resolve.py --write`. Tokens become marker blocks
  (`<!--cap:gsc.page-->`…`<!--/cap-->`) and **every block is re-rendered on each run**, so a
  registry edit or tool rename propagates to all skills. Never edit inside a block.
- `python3 seo/resolve.py --check` fails on stale blocks, leftover tokens, unknown IDs or keys,
  legacy tool names outside blocks, bad policies, and invalid/deprecated GA4/GSC names.

## At run time
- Plan calls are made by `seo/pipeline.py` from `seo/data-plans/<skill>.json`: it fills `siteUrl`, GA4
  `property_id`, dates and `date_ranges` from the profile and run window, and records each call itself.
  The rules below apply to calls an agent makes by hand (judgment steps).
- The block's `<!--cap:ID-->` is the ID you pass to `seo/record.py --cap ID` after the call.
- `runtime` args are the ones you supply (e.g. `siteUrl`, `date_ranges`); fixed `args` are
  already set — do not override them. `record.py` rejects non-runtime args and off-window dates.
- GA4 AI-source filters: `dimension_filter` = output of
  `python3 seo/site_profile.py --site <domain> --ga4-ai-filter` (single source: the rules' `AI assistants` channel).
- GA4 `date_ranges`: `[{"start_date": "<startDate>", "end_date": "<endDate>"}]` (+ the comparison
  range when the run has one). With two ranges GA4 adds a `dateRange` dimension
  (`date_range_0` = current, `date_range_1` = previous); `ga4_metrics.py` splits it.
- Weekly runs (`--weeks N`): pass each week from `window.weeks` as its own call; `record.py`
  accepts the run window, its comparison window and each listed week.

## Policy (retry / timeout / degrade)
```json
"policy": { "retry": 0, "timeout_budget_s": 40, "on_error": "degrade" }
```
- Retries live in **one layer**: `seo/pipeline.py` retries a temporary failure (timeout, 429, 5xx,
  "unavailable", a crashed server — which is restarted) `retry` times, default 2, waiting 2 s then 6 s.
  Bad arguments, auth errors and write capabilities are never retried. The planner server retries
  internally, so its policy has `retry: 0` — never re-call it in a loop. `pipeline.json` records
  `retries` and each step's `seconds`.
- `timeout_budget_s` must stay **below the MCP client timeout** (default 60 s;
  `MCP_CLIENT_TIMEOUT_S`) so the server returns the real error instead of the client timing out.
- `on_error: degrade` → apply the rule in [`data-source-map.md`](data-source-map.md).

## Checks
- `python3 seo/resolve.py --check` — rendering, names, policies (offline).
- `python3 seo/resolve.py --validate-cached` — tool + args vs the committed
  [`tool-schemas.json`](../tool-schemas.json) (offline; CI). Refresh the snapshot with
  `python3 seo/mcp_client.py [server]`.
- `python3 seo/resolve.py --validate-live` — tool + args vs the live servers (local machine).
