"""
alert_system.py
Αυτόματη αποστολή email όταν εντοπίζεται Cyprus Alert (score >= 8)
Καλείται από migration_agent_full.py και telegram_collector.py
"""

import os
import smtplib
import sqlite3
import datetime
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_PATH    = os.path.join(BASE_DIR, "migration_data.db")

SMTP_USER  = os.getenv("SMTP_USER", "")
SMTP_PASS  = os.getenv("SMTP_PASS", "")
RECIPIENTS = [
    "mixalispolidorou@gmail.com",
    "marketing@cypronetwork.com",
]

ALERT_THRESHOLD = 8  # Score >= 8 → email


def already_alerted(signal_id):
    """Ελέγχει αν έχει ήδη σταλεί alert για αυτό το signal."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            CREATE TABLE IF NOT EXISTS alert_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_source TEXT,
                signal_summary TEXT,
                signal_date TEXT,
                sent_at TEXT,
                UNIQUE(signal_source, signal_summary, signal_date)
            )
        """)
        conn.commit()
        c.execute("""
            SELECT id FROM alert_log
            WHERE signal_source = ? AND signal_summary = ? AND signal_date = ?
        """, (signal_id['source'], signal_id['summary'][:100], signal_id['date']))
        return c.fetchone() is not None
    finally:
        conn.close()


def mark_alerted(signal_id):
    """Καταγράφει ότι εστάλη alert για αυτό το signal."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR IGNORE INTO alert_log (signal_source, signal_summary, signal_date, sent_at)
            VALUES (?, ?, ?, ?)
        """, (
            signal_id['source'],
            signal_id['summary'][:100],
            signal_id['date'],
            datetime.datetime.now().isoformat()
        ))
        conn.commit()
    finally:
        conn.close()


def send_alert_email(signal):
    """
    Αποστολή email alert για Cyprus Alert signal.
    signal = {'score': 9, 'source': 'Al Jazeera', 'summary': '...', 'date': '2026-06-13', 'link': '...'}
    """
    if not SMTP_USER or not SMTP_PASS:
        logging.warning("Alert system: SMTP credentials missing in .env")
        return False

    if already_alerted(signal):
        logging.info(f"Alert already sent for: {signal['source']} — {signal['summary'][:50]}")
        return False

    score   = signal.get('score', 0)
    source  = signal.get('source', '—')
    summary = signal.get('summary', '')
    date    = signal.get('date', datetime.datetime.now().date().isoformat())
    link    = signal.get('link', '')

    subject = f"🚨 [CYPRUS ALERT] Score {score}/10 — {source}"

    # HTML email body
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background: #f8f9fb; margin: 0; padding: 20px;">
      <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">

        <!-- Header -->
        <div style="background: #0f172a; padding: 20px 24px;">
          <div style="color: #ffffff; font-size: 16px; font-weight: 600;">OSINT Migration Intelligence</div>
          <div style="color: #94a3b8; font-size: 12px; margin-top: 4px;">Υφυπουργείο Μετανάστευσης — Κυπριακή Δημοκρατία</div>
        </div>

        <!-- Alert Badge -->
        <div style="background: #fef2f2; border-left: 4px solid #dc2626; padding: 16px 24px; margin: 0;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span style="background: #dc2626; color: #ffffff; font-size: 20px; font-weight: 700; padding: 6px 14px; border-radius: 6px;">{score}</span>
            <div>
              <div style="color: #991b1b; font-size: 14px; font-weight: 600;">CYPRUS ALERT</div>
              <div style="color: #6b7280; font-size: 12px;">Εντοπίστηκε κρίσιμο signal — {date}</div>
            </div>
          </div>
        </div>

        <!-- Content -->
        <div style="padding: 20px 24px;">
          <div style="margin-bottom: 16px;">
            <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Πηγή</div>
            <div style="font-size: 14px; color: #111827; font-weight: 500;">{source}</div>
          </div>

          <div style="margin-bottom: 16px;">
            <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">Περίληψη</div>
            <div style="font-size: 14px; color: #1f2937; line-height: 1.6; background: #f9fafb; padding: 12px; border-radius: 6px; border: 1px solid #e5e7eb;">{summary}</div>
          </div>

          {f'<div style="margin-bottom: 16px;"><a href="{link}" style="color: #2563eb; font-size: 13px;">Πηγή →</a></div>' if link and link.startswith("http") else ''}
        </div>

        <!-- Footer -->
        <div style="background: #f3f4f6; padding: 12px 24px; border-top: 1px solid #e5e7eb;">
          <div style="font-size: 11px; color: #9ca3af;">
            Migration Intelligence System — Αυτόματη ειδοποίηση | Περιορισμένης Κυκλοφορίας
          </div>
        </div>

      </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f"Migration Intelligence <{SMTP_USER}>"
        msg['To']      = ", ".join(RECIPIENTS)

        # Plain text fallback
        text = f"CYPRUS ALERT — Score {score}/10\n\nΠηγή: {source}\nΗμερομηνία: {date}\n\n{summary}\n\nLink: {link}\n\n---\nMigration Intelligence System"
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, RECIPIENTS, msg.as_string())

        mark_alerted(signal)
        logging.warning(f"ALERT EMAIL SENT: score={score} source={source}")
        print(f"   📧 Alert email sent: score={score} — {source}")
        return True

    except Exception as e:
        logging.error(f"Alert email failed: {e}")
        print(f"   ❌ Alert email failed: {e}")
        return False


def check_and_send_alerts():
    """
    Ελέγχει τη βάση για σημερινά signals score >= 8
    και στέλνει email για όσα δεν έχουν ειδοποιηθεί ακόμα.
    Καλείται από auto_run.sh μετά από κάθε scan.
    """
    if not SMTP_USER or not SMTP_PASS:
        print("Alert system: SMTP credentials missing — skipping")
        return

    today_str = datetime.datetime.now().date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Δημιουργία alert_log αν δεν υπάρχει
    c.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_source TEXT,
            signal_summary TEXT,
            signal_date TEXT,
            sent_at TEXT,
            UNIQUE(signal_source, signal_summary, signal_date)
        )
    """)
    conn.commit()

    c.execute("""
        SELECT source, score, summary, date, link
        FROM signals
        WHERE date = ? AND score >= ?
        ORDER BY score DESC
    """, (today_str, ALERT_THRESHOLD))
    signals = c.fetchall()
    conn.close()

    if not signals:
        print(f"Alert check: Κανένα Cyprus Alert σήμερα (score >= {ALERT_THRESHOLD})")
        return

    print(f"Alert check: {len(signals)} Cyprus Alerts σήμερα — ελέγχω για νέα...")
    sent = 0
    for row in signals:
        signal = {
            'source':  row[0],
            'score':   row[1],
            'summary': row[2],
            'date':    row[3],
            'link':    row[4] or '',
        }
        if send_alert_email(signal):
            sent += 1

    print(f"Alert check: {sent} νέα emails εστάλησαν")


if __name__ == "__main__":
    print("Testing alert system...")
    check_and_send_alerts()
