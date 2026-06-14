#!/bin/bash

# ══════════════════════════════════════════════════════════════════════════════
# OSINT Migration Intelligence Agent — Daily Automation Script
# Runs: RSS scan → Telegram scan → CSV export → Weekly report (Sundays) → Git push
# ══════════════════════════════════════════════════════════════════════════════

set -e  # Exit on any error
PROJECT_DIR="/Users/mixalispolidorou/migration_agent"
LOG_FILE="${PROJECT_DIR}/cron_log.txt"

# Function to log with timestamp
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

cd "$PROJECT_DIR" || { echo "❌ Cannot cd to $PROJECT_DIR"; exit 1; }
source .venv/bin/activate

log "════════════════════════════════════════════════════════════════"
log "🚀 OSINT Migration Agent — Daily Run Started"
log "════════════════════════════════════════════════════════════════"

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1: RSS Scan + AI Analysis + PDF Generation
# ──────────────────────────────────────────────────────────────────────────────
log ""
log "📰 STEP 1: RSS Scan + Migration Agent"
log "───────────────────────────────────────"

if python migration_agent_full.py >> "$LOG_FILE" 2>&1; then
    log "✅ RSS scan completed successfully"
    RSS_SUCCESS=1
else
    log "❌ RSS scan failed — check migration_agent_full.py"
    RSS_SUCCESS=0
fi

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2: Telegram Scan + AI Analysis
# ──────────────────────────────────────────────────────────────────────────────
log ""
log "📱 STEP 2: Telegram Collector"
log "────────────────────────────"

if python telegram_collector.py >> "$LOG_FILE" 2>&1; then
    log "✅ Telegram scan completed successfully"
    TG_SUCCESS=1
else
    log "❌ Telegram scan failed — check telegram_collector.py"
    TG_SUCCESS=0
fi

# ──────────────────────────────────────────────────────────────────────────────
# STEP 3: Re-export CSV (includes both RSS + TG signals)
# ──────────────────────────────────────────────────────────────────────────────
log ""
log "📊 STEP 3: CSV Export (refresh dashboard data)"
log "──────────────────────────────────────────────"

python3 << 'PYTHON_SCRIPT'
import sqlite3
import csv
import os

db_path = "migration_data.db"
csv_path = "migration_data.csv"

try:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        SELECT source, score, summary, date, link, country 
        FROM signals 
        ORDER BY date DESC, score DESC
    """)
    rows = c.fetchall()
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Source', 'Risk Score', 'Summary', 'Date', 'Link', 'Country'])
        writer.writerows(rows)
    
    conn.close()
    print(f"✅ CSV exported: {len(rows)} records")
except Exception as e:
    print(f"❌ CSV export failed: {e}")
    exit(1)
PYTHON_SCRIPT

if [ $? -eq 0 ]; then
    CSV_SUCCESS=1
else
    CSV_SUCCESS=0
fi

# ──────────────────────────────────────────────────────────────────────────────
# STEP 4: Alert Check — Email notifications for Cyprus Alerts (score >= 8)
# ──────────────────────────────────────────────────────────────────────────────
log ""
log "🚨 STEP 4: Alert Check (Cyprus Alerts email)"
log "────────────────────────────────────────────"

if python3 -c "from alert_system import check_and_send_alerts; check_and_send_alerts()" >> "$LOG_FILE" 2>&1; then
    log "✅ Alert check completed"
    ALERT_SUCCESS=1
else
    log "⚠️  Alert check failed (non-critical)"
    ALERT_SUCCESS=0
fi

# ──────────────────────────────────────────────────────────────────────────────
# STEP 5: Weekly Report (only on Sundays — day 7)
# ──────────────────────────────────────────────────────────────────────────────
DOW=$(date +%u)  # 1=Monday, 7=Sunday

log ""
log "📄 STEP 5: Weekly Report Generation"
log "──────────────────────────────────"

if [ "$DOW" = "7" ]; then
    log "ℹ️  Today is Sunday — generating weekly report"
    if python weekly_report.py >> "$LOG_FILE" 2>&1; then
        log "✅ Weekly report generated successfully"
        WEEKLY_SUCCESS=1
    else
        log "⚠️  Weekly report generation failed (non-critical)"
        WEEKLY_SUCCESS=0
    fi
else
    log "ℹ️  Today is not Sunday (day $DOW) — skipping weekly report"
    WEEKLY_SUCCESS=1  # Don't fail the whole run
fi

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6: Update Status File
# ──────────────────────────────────────────────────────────────────────────────
log ""
log "⏱️  STEP 6: Update Status"
log "──────────────────────"

python3 << 'PYTHON_SCRIPT'
import json
from datetime import datetime

status = {
    "last_scan": datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
    "date": datetime.now().strftime('%Y-%m-%d')
}

with open('status.json', 'w', encoding='utf-8') as f:
    json.dump(status, f, indent=2)

print(f"✅ Status updated: {status['last_scan']}")
PYTHON_SCRIPT

# ──────────────────────────────────────────────────────────────────────────────
# STEP 6: Git Commit & Push
# ──────────────────────────────────────────────────────────────────────────────
log ""
log "🔄 STEP 6: Git Synchronization"
log "────────────────────────────"

# Untrack and remove sensitive files from history if they exist
if [ -f "session.session" ]; then
    log "⚠️  Removing session.session (security)"
    git rm --cached session.session 2>/dev/null || true
    rm -f session.session
fi

if [ -f "export_csv.py" ]; then
    log "⚠️  Removing export_csv.py (deprecated)"
    git rm --cached export_csv.py 2>/dev/null || true
    rm -f export_csv.py
fi

if [ -f ".env" ]; then
    log "ℹ️  .env file will not be tracked (already in .gitignore)"
fi

# Update .gitignore to ensure safety
cat > .gitignore << 'GITIGNORE'
*.session
.env
__pycache__/
*.pyc
*.pyo
cron_log.txt
migration_data.db
.DS_Store
.streamlit/secrets.toml
GITIGNORE

log "✅ .gitignore updated"

# Stage and commit changes
git add migration_data.csv reports/ status.json .gitignore
git add -A  # Add any other modified tracked files

COMMIT_MSG="Auto-update: $(date +'%Y-%m-%d %H:%M') | RSS: $([ $RSS_SUCCESS -eq 1 ] && echo '✅' || echo '❌'), TG: $([ $TG_SUCCESS -eq 1 ] && echo '✅' || echo '❌'), CSV: $([ $CSV_SUCCESS -eq 1 ] && echo '✅' || echo '❌')"

if git commit -m "$COMMIT_MSG" >> "$LOG_FILE" 2>&1; then
    log "✅ Git commit created"
else
    log "ℹ️  No changes to commit (or commit failed)"
fi

if git push origin main >> "$LOG_FILE" 2>&1; then
    log "✅ Git push successful"
    GIT_SUCCESS=1
else
    log "⚠️  Git push failed (check network/credentials)"
    GIT_SUCCESS=0
fi

# ──────────────────────────────────────────────────────────────────────────────
# STEP 7: Summary
# ──────────────────────────────────────────────────────────────────────────────
log ""
log "════════════════════════════════════════════════════════════════"
log "📊 Execution Summary"
log "════════════════════════════════════════════════════════════════"
log "  RSS Scan:       $([ $RSS_SUCCESS -eq 1 ] && echo '✅ OK' || echo '❌ FAILED')"
log "  Telegram Scan:  $([ $TG_SUCCESS -eq 1 ] && echo '✅ OK' || echo '❌ FAILED')"
log "  CSV Export:     $([ $CSV_SUCCESS -eq 1 ] && echo '✅ OK' || echo '❌ FAILED')"
log "  Alert Check:    $([ $ALERT_SUCCESS -eq 1 ] && echo '✅ OK' || echo '⚠️  FAILED')"
log "  Weekly Report:  $([ $WEEKLY_SUCCESS -eq 1 ] && echo '✅ OK' || echo '⏭️  SKIPPED')"
log "  Git Push:       $([ $GIT_SUCCESS -eq 1 ] && echo '✅ OK' || echo '⚠️  FAILED')"
log "════════════════════════════════════════════════════════════════"

# Overall success check
if [ $RSS_SUCCESS -eq 1 ] && [ $TG_SUCCESS -eq 1 ] && [ $CSV_SUCCESS -eq 1 ]; then
    log "✅ Daily run completed successfully!"
    exit 0
else
    log "⚠️  Daily run completed with errors — check log above"
    exit 1
fi
