#!/bin/bash
# TEFAS scraper health monitor — runs at 11:00 TR weekdays
# Checks if yesterday's scrape was successful and writes report

PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
export PATH

cd ~/Desktop/projects/fon-app

# Run the monitor check (writes to logs/monitor_latest.txt and logs/monitor_alerts.txt)
python3.11 -c "
import requests
import json
from datetime import date, datetime, timedelta

HEADERS = {'apikey': 'sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi', 'Authorization': 'Bearer sb_secret_PkAEAOU2YO4YS-ELYpwS5w_SsVg2kqi'}

report = []
status = 'OK'
report.append(f'TEFAS Monitor — {datetime.utcnow().isoformat()} UTC')
report.append('=' * 50)

# 1. Check system_status
r = requests.get('https://oqkobptbvcazifpvjwfz.supabase.co/rest/v1/system_status?key=eq.last_tefas_fetch', headers=HEADERS, timeout=15)
if r.status_code == 200:
    data = r.json()
    if data:
        ts = data[0].get('value', 'N/A')
        report.append(f'last_tefas_fetch: {ts}')
        # Check if it's today (TR time)
        today_tr = (datetime.utcnow() - timedelta(hours=3)).date().isoformat()
        fetch_date = ts[:10] if ts else None
        if fetch_date != today_tr:
            status = 'PROBLEM'
            report.append(f'  ⚠️ Son scrape BUGÜN DEĞİL! (beklenen: {today_tr})')
    else:
        status = 'PROBLEM'
        report.append('  ⚠️ system_status tablosunda kayıt yok!')
else:
    status = 'PROBLEM'
    report.append(f'  ⚠️ system_status sorgu hatası: {r.status_code}')

# 2. Check sample funds
sample_codes = ['VEV', 'GES', 'GRL', 'TIP', 'PAF']
r2 = requests.get(f'https://oqkobptbvcazifpvjwfz.supabase.co/rest/v1/funds?code=in.({chr(44).join(sample_codes)})&select=code,price,daily_change,price_history,last_tefas_fetch', headers=HEADERS, timeout=15)
if r2.status_code == 200:
    funds = r2.json()
    for f in funds:
        ph = f.get('price_history', [])
        ph_len = len(ph) if isinstance(ph, list) else 0
        ph_last = ph[-1]['date'] if ph else 'N/A'
        price = f.get('price', 'N/A')
        dc = f.get('daily_change', 0)
        report.append(f'  {f[\"code\"]}: price={price}, change={dc:+.2f}%, history={ph_len} pts, last={ph_last}')
else:
    status = 'PROBLEM'
    report.append(f'  ⚠️ Örnek fon sorgu hatası: {r2.status_code}')

# 3. Overall status
report.append('')
report.append(f'Overall status: {status}')

report_text = '\n'.join(report)
print(report_text)

# Write to monitor_latest.txt
with open('logs/monitor_latest.txt', 'w') as f:
    f.write(report_text + '\n')

# Write to monitor_report.json
with open('logs/monitor_report.json', 'w') as f:
    json.dump({
        'checked_at': datetime.utcnow().isoformat(),
        'status': status,
        'report': report_text,
    }, f, indent=2)

# If PROBLEM, append to alerts
if status == 'PROBLEM':
    alert_line = f'[{datetime.utcnow().isoformat()}] {status}'
    with open('logs/monitor_alerts.txt', 'a') as f:
        f.write(alert_line + '\n')

print(f'Report written. Status: {status}')
"
