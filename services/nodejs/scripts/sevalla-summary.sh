#!/bin/bash
# Show formatted last-run cache warmer summary from Sevalla via API exec

APP_ID="73d65fa7-eff3-4382-ab89-aa95f795ffa5"
PROCESS_ID="527976bf-8fc1-4c4f-90e6-d1b81a3fa6d2"
API_KEY="svl_570f93edd991bc4f9c38c00012536840da5b35e61e5fe1b2de26d5b79f62ea26"

# Fetch last-run summary JSON
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  "https://api.sevalla.com/v3/applications/${APP_ID}/processes/${PROCESS_ID}/exec" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"command":["cat","cache-warmer-last-run.json"],"timeout":5}')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
  echo "✓ Summary fetched (HTTP ${HTTP_CODE})"
  echo ""
  echo "$BODY" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    s = json.loads(d.get('stdout','') or d.get('output','{}'))
except:
    # Direct JSON (no exec wrapper)
    s = json.loads(sys.stdin.read() if hasattr(sys.stdin, 'read') else sys.stdin)

try:
    print('═══════════════════════════════════════════')
    print('           CACHE WARMER — SUMMARY           ')
    print('═══════════════════════════════════════════')
    print(f'  Started:    {s.get(\"started\",\"?\")}')
    print(f'  Finished:   {s.get(\"finished\",\"?\")}')
    print(f'  Total:      {s.get(\"total\",\"?\")} URLs')
    print(f'  Successful: {s.get(\"successful\",\"?\")}')
    print(f'  Failed:     {s.get(\"failed\",\"?\")}')
    print()

    kinsta = s.get('kinsta', {})
    cdn = s.get('cdn', {})
    edge = s.get('edge', {})

    def fmt_layer(name, st):
        line = f'  {name.ljust(11)}{st.get(\"hit\",0)} HIT, {st.get(\"miss\",0)} MISS, {st.get(\"bypass\",0)} BYPASS'
        unknown = st.get('unknown', 0)
        if unknown > 0:
            line += f' | {unknown} UNKNOWN'
        print(line)

    if kinsta:
        fmt_layer('Kinsta:', kinsta)
    if cdn:
        fmt_layer('CDN:', cdn)
    if edge:
        fmt_layer('Edge:', edge)

    if (cdn.get('unknown', 0) > 0) or (edge.get('unknown', 0) > 0):
        print()
        print('  [!] CDN/Edge UNKNOWN = requests bypassed Cloudflare (normal from Sevalla)')

    # Per-status-code breakdown
    per_status = s.get('perStatus', {})
    if per_status:
        print()
        print('  ── Status Codes ──')
        for code in sorted(per_status.keys(), key=lambda c: (c[0], c)):
            bucket = per_status[code]
            pct = (bucket['count'] / s.get('successful', 1) * 100) if s.get('successful') else 0
            print(f'    {code}: {bucket[\"count\"]} ({pct:.1f}%)')

    print()
    print('═══════════════════════════════════════════')
except Exception as e:
    print(f'  ⚠ Could not parse summary data: {e}')
"
else
  echo "✗ Failed to fetch summary (HTTP ${HTTP_CODE})"
  echo "$BODY"
fi
