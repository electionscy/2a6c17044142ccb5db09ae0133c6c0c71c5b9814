#!/bin/bash

# ══════════════════════════════════════════════════════════════════════════════
# OSINT Migration Intelligence Agent — Daily Automation Script
# Runs: RSS scan → Telegram scan → CSV export → Weekly report (Sundays) → Git push
# ══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on any error
PROJECT_DIR="/home/agent/migration_agent"
LOG_FILE="${PROJECT_DIR}/cron_log.txt"

# Function to log with timestamp
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Health Check - Start
HEALTHCHECK_START="https://hc-ping.com/6bc3a8de-a710-4d69-9d7f-f0ceac254de7/start"
curl -m 10 "$HEALTHCHECK_START" || true

cd "$PROJECT_DIR" || { echo "❌ Cannot cd to $PROJECT_DIR"; exit 1; }
source .venv/bin/activate

log "=== OSINT ENGINE START ==="

# RSS Scan
log "Starting RSS scan..."
python migration_agent_full.py >> "$LOG_FILE" 2>&1
log "✅ RSS scan complete"

# Telegram Scan
log "Starting Telegram scan..."
timeout 300 python telegram_collector.py >> "$LOG_FILE" 2>&1 || log "⚠️  Telegram scan had issues"

# Entity extraction & Gemini enrichment
log "Running entity extraction & Gemini enrichment..."
python - >> "$LOG_FILE" 2>&1 << 'PYEOF'
import sqlite3, json, sys, os
sys.path.insert(0, "/home/agent/migration_agent")
os.chdir("/home/agent/migration_agent")
from entity_extractor import extract_entities

conn = sqlite3.connect("migration_data.db")
cur = conn.cursor()

# Επεξεργασία signals χωρίς enrichment (country IS NULL)
cur.execute("""
    SELECT id, title, summary FROM signals
    WHERE country IS NULL OR country = ''
    ORDER BY id DESC LIMIT 50
""")
rows = cur.fetchall()
print(f"Enriching {len(rows)} signals...")

for sid, title, summary in rows:
    result = extract_entities(title, summary)
    cur.execute("""
        UPDATE signals SET
            country = ?,
            countries = ?,
            people = ?,
            organizations = ?,
            locations = ?,
            category = ?,
            confidence = ?,
            summary = CASE WHEN ? != '' THEN ? ELSE summary END
        WHERE id = ?
    """, (
        result["primary_country"],
        json.dumps(result["countries"], ensure_ascii=False),
        json.dumps(result["people"], ensure_ascii=False),
        json.dumps(result["organizations"], ensure_ascii=False),
        json.dumps(result["locations"], ensure_ascii=False),
        result["category"],
        result["confidence"],
        result["summary_el"], result["summary_el"],
        sid
    ))

conn.commit()
conn.close()
print(f"✅ Enriched {len(rows)} signals")
PYEOF
log "✅ Entity extraction complete"

# Export CSV
log "Exporting CSV..."
python -c "
import sqlite3, pandas as pd
conn = sqlite3.connect('migration_data.db')
df = pd.read_sql_query(\"SELECT * FROM signals ORDER BY date DESC, score DESC\", conn)
conn.close()
df.to_csv('migration_data.csv', index=False)
print(f'Exported {len(df)} records to CSV')
" >> "$LOG_FILE" 2>&1

# Weekly Report (Sundays)
if [ "$(date +%w)" = "0" ]; then
    log "Running weekly report..."
    python weekly_report.py >> "$LOG_FILE" 2>&1
    log "✅ Weekly report complete"
fi

# Predictive Model — Migration Pressure Index
log "Generating Migration Pressure Index..."
python predictive_model.py >> "$LOG_FILE" 2>&1
log "✅ Pressure Index complete"

# Validation logging — καταγραφη προβλεψης για prospective επικυρωση
log "Logging prediction for validation..."
python validate_model.py >> "$LOG_FILE" 2>&1
log "✅ Validation log updated"

# Daily PDF Report
log "Generating daily PDF report..."
python daily_report.py >> "$LOG_FILE" 2>&1
log "✅ Daily report complete"

# Email Alerts — Cyprus Alerts (score >= 8) + Pressure Index (>= 50)
log "Checking email alerts..."
python email_alerts.py >> "$LOG_FILE" 2>&1
log "✅ Email alerts complete"

log "=== OSINT ENGINE END ==="

# Backup to B2
log "Backing up database to B2..."
python backup_to_b2.py >> "$LOG_FILE" 2>&1

# Push to GitHub
log "Pushing to GitHub..."
cd "$PROJECT_DIR"
git add -A
git commit -m "Auto-sync $(date +'%Y-%m-%d %H:%M:%S')" || true
git push origin master || log "⚠️  Origin push had issues"
git push dashboard master:main --force || log "⚠️  Dashboard push had issues"

# Health Check - Success
HEALTHCHECK_URL="https://hc-ping.com/6bc3a8de-a710-4d69-9d7f-f0ceac254de7"
curl -m 10 "$HEALTHCHECK_URL" || true

log "✅ ALL TASKS COMPLETED"

