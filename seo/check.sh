#!/usr/bin/env bash
# SEO skills CI gate: registry checks + live schema validation + full test suite.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
rc=0

echo "== resolve --check =="
python3 seo/resolve.py --check || rc=1

echo "== resolve --validate-live =="
python3 seo/resolve.py --validate-live || rc=1

echo "== compile =="
python3 -m py_compile \
  seo/resolve.py seo/mcp_client.py seo/window.py seo/orchestrate.py \
  seo/report/build_report.py seo/report/validate_report.py \
  seo/mcp-servers/google-ads-planner/server.py \
  seo/mcp-servers/google-ads-planner/planner_limits.py || rc=1

echo "== tests =="
tmp="$(mktemp)"
for t in seo/tests/test_*.py; do
  printf '%-40s ' "$t"
  if python3 "$t" >"$tmp" 2>&1; then
    tail -n 1 "$tmp"
  else
    echo "FAILED"
    tail -n 20 "$tmp"
    rc=1
  fi
done
rm -f "$tmp"

echo
if [ "$rc" -eq 0 ]; then echo "ALL GREEN"; else echo "FAILURES (rc=$rc)"; fi
exit "$rc"
