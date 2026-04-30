#!/bin/bash
# Use curl directly to avoid Python SSL issues
FUNDS_FILE="data/funds_clean.json"
OID_FILE="data/fund_oid_map.json"
DONE_FILE="data/fund_oids_done.txt"

mkdir -p data

# Load funds and extract codes
python3 -c "
import json
with open('$FUNDS_FILE') as f:
    funds = json.load(f)
codes = [f['code'] for f in funds]
print('\n'.join(codes))
" > /tmp/fund_codes.txt

TOTAL=$(wc -l < /tmp/fund_codes.txt)
echo "Total funds: $TOTAL"

> "$OID_FILE"
> "$DONE_FILE"

while IFS= read -r code; do
  if grep -q "^${code}=" "$OID_FILE" 2>/dev/null; then
    echo "SKIP: $code"
    continue
  fi
  
  result=$(curl -sL -X POST "https://www.kap.org.tr/tr/api/search/combined" \
    -H "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)" \
    -H "Content-Type: application/json" \
    -d "{\"keyword\":\"$code\"}" \
    --max-time 15 2>/dev/null)
  
  oid=$(echo "$result" | python3 -c "
import json,sys
try:
    data = json.load(sys.stdin)
    for cat in data:
        if cat.get('category') == 'companyOrFunds':
            for r in cat.get('results', []):
                if r.get('searchType') == 'F' and r.get('cmpOrFundCode','').lower() == '$code'.lower():
                    print(r.get('memberOrFundOid',''))
                    break
except: pass
" 2>/dev/null)
  
  if [ -n "$oid" ]; then
    echo "${code}=${oid}" >> "$OID_FILE"
    echo "OK: $code -> $oid"
  else
    echo "MISS: $code"
  fi
  
  sleep 0.1
  COUNT=$(wc -l < "$DONE_FILE")
  if [ $((COUNT % 100)) -eq 0 ]; then
    echo "Progress: $COUNT/$TOTAL"
  fi
done < /tmp/fund_codes.txt

echo "Done! OIDs collected: $(wc -l < $OID_FILE)"
