#!/bin/bash
# Bulk download + parse KAP portfolio PDFs
# Args: $1 = JSON file with download list, $2 = output directory

LIST_FILE="$1"
OUT_DIR="$2"
PARSE_SCRIPT="$(dirname "$0")/parse_pdf.mjs"

mkdir -p "$OUT_DIR"

# Read each entry from JSON and process
python3 -c "
import json, sys
with open('$LIST_FILE') as f:
    data = json.load(f)
for item in data:
    b = item['disclosureBasic']
    print(f\"{b['stockCode']}|{b['disclosureIndex']}\")
" | while IFS='|' read -r code idx; do
    text_file="$OUT_DIR/${code}_text.txt"
    pdf_file="$OUT_DIR/${code}.pdf"
    
    # Skip if already done
    [ -f "$text_file" ] && [ $(wc -c < "$text_file") -gt 100 ] && continue
    
    # Get PDF UUID
    uuid=$(curl -s -L --max-time 10 "https://www.kap.org.tr/tr/Bildirim/$idx" | grep -oE 'file/download/[a-f0-9]{32}' | head -1 | sed 's|file/download/||')
    
    if [ -z "$uuid" ]; then
        echo "NO_UUID: $code"
        continue
    fi
    
    # Download PDF
    curl -s -L --max-time 15 -o "$pdf_file" -H 'User-Agent: Mozilla/5.0' "https://www.kap.org.tr/tr/api/file/download/$uuid"
    
    if [ ! -f "$pdf_file" ] || [ $(wc -c < "$pdf_file") -lt 1000 ]; then
        echo "DL_FAIL: $code"
        continue
    fi
    
    # Parse PDF
    cd ~/Desktop/projects/fon-app
    node parse_pdf.mjs "$pdf_file" > "$text_file" 2>/dev/null
    
    size=$(wc -c < "$text_file" 2>/dev/null || echo 0)
    echo "OK: $code ($(echo $size | tr -d ' ') bytes)"
    
    sleep 0.1
done
