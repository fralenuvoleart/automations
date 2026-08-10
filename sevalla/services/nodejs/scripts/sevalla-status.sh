#!/bin/bash
# Show cache warmer live status from Sevalla via API exec

APP_ID="73d65fa7-eff3-4382-ab89-aa95f795ffa5"
PROCESS_ID="527976bf-8fc1-4c4f-90e6-d1b81a3fa6d2"
API_KEY="svl_570f93edd991bc4f9c38c00012536840da5b35e61e5fe1b2de26d5b79f62ea26"

# Fetch live progress
PROGRESS=$(curl -s -X POST \
  "https://api.sevalla.com/v3/applications/${APP_ID}/processes/${PROCESS_ID}/exec" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"command":["cat","cache-warmer-progress.json"],"timeout":5}')

# Parse progress
PROGRESS_STDOUT=$(echo "$PROGRESS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stdout',''))" 2>/dev/null)
PROGRESS_EXIT=$(echo "$PROGRESS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('exit_code',1))" 2>/dev/null)

echo ""
echo "═══════════════════════════════════════════"
echo "           CACHE WARMER — STATUS           "
echo "═══════════════════════════════════════════"

# ── Live progress ──
if [ "$PROGRESS_EXIT" = "0" ] && [ -n "$PROGRESS_STDOUT" ]; then
  echo "$PROGRESS_STDOUT" | python3 -c "
import sys, json
try:
    p = json.load(sys.stdin)
    if p.get('running'):
        current = p['current']
        total = p['total']
        pct = (current / total * 100) if total > 0 else 0
        elapsed_min = '?'
        if p.get('started') and p.get('updated'):
            from datetime import datetime
            try:
                started = datetime.fromisoformat(p['started'].replace('Z','+00:00'))
                updated = datetime.fromisoformat(p['updated'].replace('Z','+00:00'))
                elapsed_sec = (updated - started).total_seconds()
                elapsed_min = f'{elapsed_sec/60:.1f}'
                if current > 0:
                    rate = elapsed_sec / current
                    remaining_sec = (total - current) * rate
                    remaining_min = f'{remaining_sec/60:.1f}'
                else:
                    remaining_min = '?'
            except:
                remaining_min = '?'
        else:
            remaining_min = '?'

        print(f'  Status:     ● RUNNING')
        print(f'  Started:    {p.get(\"started\",\"?\")}')
        print(f'  Progress:   {current}/{total} URLs ({pct:.0f}%)')
        print(f'  Elapsed:    {elapsed_min} min')
        print(f'  ETA:        ~{remaining_min} min remaining')
        if p.get('lastUrl'):
            url = p['lastUrl']
            short = url[:80] + ('...' if len(url) > 80 else '')
            print(f'  Last URL:   {short}')
    else:
        print('  Status:     ○ IDLE (progress file says not running)')
except:
    print('  Status:     ⚠ Could not parse progress data')
"
else
  echo "  Status:     ○ IDLE (no warmer running)"
fi

echo "═══════════════════════════════════════════"
echo ""
