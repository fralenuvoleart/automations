#!/usr/bin/env bash
# SEO skills CI gate. Offline by default (portable): rendering/semantic checks, cached-schema
# validation, profile validation, compile, full test suite (SEO tooling + report-export).
# Pass --live on a machine with the MCP servers installed to also validate against live schemas.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
rc=0
live=0
[ "${1:-}" = "--live" ] && live=1

echo "== resolve --check =="
python3 seo/resolve.py --check || rc=1

echo "== resolve --validate-cached =="
python3 seo/resolve.py --validate-cached || rc=1

if [ "$live" -eq 1 ]; then
  echo "== resolve --validate-live =="
  python3 seo/resolve.py --validate-live || rc=1
fi

echo "== data plans =="
python3 seo/pipeline.py --check-plans || rc=1

echo "== CTR benchmark age =="
if ! python3 seo/gsc_metrics.py benchmark --check >/dev/null; then
  echo "WARN seo/config/ctr-benchmark.json is older than its max_age_months — replace it with a newer post-AI-Overviews study"
else
  echo "OK — CTR benchmark within max_age_months"
fi

echo "== site profiles =="
for site in $(python3 seo/site_profile.py --list); do
  python3 seo/site_profile.py --site "$site" --validate || rc=1
done

echo "== compile =="
python3 -m py_compile \
  seo/*.py seo/report/*.py \
  seo/mcp-servers/google-ads-planner/server.py \
  seo/mcp-servers/google-ads-planner/planner_limits.py \
  .agents/skills/report-export/scripts/export_pdf.py \
  .agents/skills/report-export/scripts/send_email.py || rc=1

echo "== tests =="
tmp="$(mktemp)"
for t in seo/tests/test_*.py .agents/skills/report-export/tests/test_*.py; do
  printf '%-44s ' "$t"
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
