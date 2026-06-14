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
python telegram_collector.py >> "$LOG_FILE" 2>&1 || log "⚠️  Telegram scan had issues"

# Export CSV
log "Exporting CSV..."
python -c "import pandas as pd; df = pd.read_csv('migration_data.csv'); print(f'Exported {len(df)} records')" >> "$LOG_FILE" 2>&1

# Weekly Report (Sundays)
if [ "$(date +%w)" = "0" ]; then
    log "Running weekly report..."
    python weekly_report.py >> "$LOG_FILE" 2>&1
    log "✅ Weekly report complete"
fi

log "=== OSINT ENGINE END ==="

# Backup to B2
log "Backing up database to B2..."
python backup_to_b2.py >> "$LOG_FILE" 2>&1

# Push to GitHub
log "Pushing to GitHub..."
cd "$PROJECT_DIR"
git add -A
git commit -m "Auto-sync $(date +'%Y-%m-%d %H:%M:%S')" || true
git push origin master || log "⚠️  Git push had issues"

# Health Check - Success
HEALTHCHECK_URL="https://hc-ping.com/6bc3a8de-a710-4d69-9d7f-f0ceac254de7"
curl -m 10 "$HEALTHCHECK_URL" || true

log "✅ ALL TASKS COMPLETED"

