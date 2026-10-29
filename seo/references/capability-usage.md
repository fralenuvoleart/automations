# Capability Usage

Capabilities are declared once in [`seo/capabilities.json`](../capabilities.json) — the single
source of truth for `server` → `tool` + fixed `args` + `runtime` (agent-supplied) + optional
`policy`. Skills reference them as `{{cap:<id>}}` tokens; [`seo/resolve.py`](../resolve.py)
expands tokens to the full call spec and validates them against the live server schemas.

## Authoring
- Reference a capability, don't hard-code a tool: ``Call {{cap:gsc.query}} for the period.``
- `resolve.py --write` materialises tokens into the committed skills.
- Legacy tool names under a capability's `aliases` are remapped automatically.

## Runtime vs args
- `args` are fixed arguments the resolver emits.
- `runtime` are the arguments **the agent supplies at call time** (e.g. `siteUrl`, `date_ranges`).

## Policy (retry / timeout / degrade)
Optional per capability:
```json
"policy": { "retry": 3, "backoff_s": [2, 4, 8], "timeout_budget_s": 40, "on_error": "degrade" }
```
- `timeout_budget_s` must stay **below the MCP client timeout** (default 60s; override with `MCP_CLIENT_TIMEOUT_S`) so the server returns the real error instead of the client timing out.
- `on_error`: `degrade` (fall back per [`data-source-map.md`](data-source-map.md)) or `fail` (stop and report).

## Checks
- `python3 seo/resolve.py --check` — tokens resolve, no alias drift, expanded specs match, policies sane.
- `python3 seo/resolve.py --validate-live` — tool + args vs the live `inputSchema`.
