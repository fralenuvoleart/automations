# DataForSEO request payloads (`dfs.*` capabilities)

DataForSEO is optional and not configured; verify against <https://docs.dataforseo.com/v3/> before
first use. Every `dfs.*` capability takes `data` = a JSON **array of task objects**. All returned
numbers are third-party index **estimates**. Location/language come from the profile
`serp_locations` (language → `location_code`); if unset, ask the user which market to sample.

| Capability | `data` |
|---|---|
| `dfs.backlinks_summary` | `[{"target": "example.com", "include_subdomains": true}]` |
| `dfs.referring_domains` | `[{"target": "example.com", "limit": 100, "order_by": ["rank,desc"]}]` |
| `dfs.anchors` | `[{"target": "example.com", "limit": 100, "order_by": ["backlinks,desc"]}]` |
| `dfs.backlinks_new_lost` | `[{"target": "example.com", "date_from": "<YYYY-MM-DD>", "date_to": "<YYYY-MM-DD>", "group_range": "month"}]` |
| `dfs.ranked_keywords` | `[{"target": "competitor.com", "location_code": <int>, "language_code": "ru", "limit": 500}]` |
| `dfs.serp` (advanced) | `[{"keyword": "<keyword>", "location_code": <int>, "language_code": "ru", "depth": 10}]` |
