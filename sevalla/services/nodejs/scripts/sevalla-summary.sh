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
from datetime import datetime, timezone

def fmt_time(v):
    # Convert ISO-8601 UTC -> 'YYYY-MM-DD hh:mm AM/PM (UTC)'
    try:
        dt = datetime.fromisoformat(str(v).replace('Z', '+00:00')).astimezone(timezone.utc)
        return dt.strftime('%Y-%m-%d %I:%M %p (UTC)')
    except Exception:
        return str(v)

raw = sys.stdin.read()
try:
    d = json.loads(raw)
    # Exec wrapper: {\"stdout\": \"<json>\"} — otherwise treat as direct JSON
    if isinstance(d, dict) and ('stdout' in d or 'output' in d):
        s = json.loads(d.get('stdout') or d.get('output') or '{}')
    else:
        s = d
except Exception:
    s = {}

try:
    print('═══════════════════════════════════════════')
    print('           CACHE WARMER — SUMMARY           ')
    print('═══════════════════════════════════════════')
    print(f'  Started:    {fmt_time(s.get(\"started\",\"?\"))}')
    print(f'  Finished:   {fmt_time(s.get(\"finished\",\"?\"))}')
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
            by = st.get('unknownBy') or {}
            if by:
                parts = [f'{c} {str(v).upper()}' for v, c in sorted(by.items(), key=lambda kv: -kv[1])]
                line += ' | ' + ', '.join(parts)
            else:
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

    # Per-status-code breakdown (successful + failed 4xx/5xx + redirect hops)
    failed_urls = s.get('failedUrls') or []
    per_status = s.get('perStatus', {})
    redirect_codes = s.get('redirectCodes') or {}

    # Tally failed URLs by HTTP status code (network errors have no status)
    failed_by_code = {}
    for f in failed_urls:
        if isinstance(f, dict):
            st = f.get('status')
            if st is not None:
                key = str(st)
                failed_by_code[key] = failed_by_code.get(key, 0) + 1

    codes = {}
    for code, bucket in per_status.items():
        codes[code] = {'count': bucket['count'], 'failed': False, 'redirect': False}
    for code, cnt in failed_by_code.items():
        if code in codes:
            codes[code]['count'] += cnt
            codes[code]['failed'] = True
        else:
            codes[code] = {'count': cnt, 'failed': True, 'redirect': False}
    for code, cnt in redirect_codes.items():
        if code in codes:
            codes[code]['count'] += cnt
            codes[code]['redirect'] = True
        else:
            codes[code] = {'count': cnt, 'failed': False, 'redirect': True}

    total_for_pct = s.get('total') or 0
    if codes:
        print()
        print('  ── Status Codes ──')
        for code in sorted(codes.keys(), key=lambda c: (c[0], c)):
            cnt = codes[code]['count']
            pct = (cnt / total_for_pct * 100) if total_for_pct else 0
            mark = ' ✗' if codes[code]['failed'] else (' ↳' if codes[code]['redirect'] else '')
            print(f'    {code}: {cnt} ({pct:.2f}%){mark}')

    # Failed URLs with reason
    if failed_urls:
        print()
        print('  ── Failed URLs ──')
        for f in failed_urls:
            if isinstance(f, dict):
                url = f.get('url', '?')
                reason = f.get('error') or f.get('reason') or 'unknown'
                status = f.get('status')
            else:
                url = f
                reason = 'unknown'
                status = None
            tag = f' [HTTP {status}]' if status is not None else ''
            print(f'    ✗ {url}{tag}')
            print(f'      Reason: {reason}')

    print()
    print('═══════════════════════════════════════════')
except Exception as e:
    print(f'  ⚠ Could not parse summary data: {e}')
"
else
  echo "✗ Failed to fetch summary (HTTP ${HTTP_CODE})"
  echo "$BODY"
fi
