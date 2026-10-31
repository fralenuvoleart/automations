# Shared troubleshooting (all SEO skills)

| Symptom | Cause | Fix |
|---|---|---|
| Tool/server error | server missing or not reloaded in `.roo/mcp.json` | add/reload it; then apply the degradation rule in [`data-source-map.md`](../data-source-map.md) |
| `pipeline.py` exit 1 | a required step failed (see `pipeline.json`) or the plan needs an input | fix the source (server, credentials, profile value) and rerun with `--force` (overwrites the run folder, reuses the answers that already succeeded) or `--refresh` (fetches every call again); pass inputs with `--input key=value`; `--dry-run` shows every call it would make |
| `pipeline.py`: "server not configured" | the server is not in `.roo/mcp.json` | optional steps are skipped and listed in `unavailable`; add the server for the full report |
| Empty/zero rows | window inside the data lag, wrong property (`sc-domain:` vs URL-prefix) | use the window from `.run_state.json`; confirm the property with `gsc.sites_list` |
| `truncated: true` from `gsc_metrics.py` | the pull hit 25,000 rows | report "beyond the row cutoff" items as such; narrow with a filter or shorter window if needed |
| `record.py` rejects a call | non-runtime arg, or dates ≠ run window | pass only runtime args; use the run window (or `--allow-window "<reason>"` for a deliberate exception, stated in the section) |
| `validate_report.py`: URL not in evidence | URL typed by hand or from memory | use the URL exactly as it appears in a recorded response, or drop it |
| `validate_report.py`: number not found | figure typed from memory, rounded differently, or computed in prose | copy it from `computed/` or `data/` at the precision shown; compute anything new with a script and record it (`--source derived`) |
| `validate_report.py`: endDate not before as_of | window copied wrong | copy `window` verbatim from `.run_state.json` |
| GA4 returns no rows for the AI filter | AI visits arrive as `(direct)`/unlisted hosts | keep the lower-bound label; add the host to the `AI assistants` channel rule in `seo/config/rules/<domain>.json` |
| GA4 metric error on `conversions` | deprecated metric | use `keyEvents` (the registry already does) |
