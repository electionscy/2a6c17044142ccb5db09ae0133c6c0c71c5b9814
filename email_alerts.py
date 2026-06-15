"""
Φάση Δ — Email Alert System
Δύο τύποι ειδοποίησης:
  1. ALERT: signals με score ≥ 8 (κρίσιμες ειδήσεις)
  2. PRESSURE: Δεικτης Πίεσης ≥ 50 (MODERATE/HIGH)
"""
import sqlite3
import smtplib
import json
import os
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
try:
    from zoneinfo import ZoneInfo
    CY_TZ = ZoneInfo("Asia/Nicosia")
except ImportError:
    import pytz
    CY_TZ = pytz.timezone("Asia/Nicosia")

def now_cy():
    return datetime.now(CY_TZ)

# ── Config ──
SMTP_USER = os.getenv("SMTP_USER", "mixalispolidorou@gmail.com")
SMTP_PASS = os.getenv("SMTP_PASS", "pqli xfmi aglt ithc")
RECIPIENT  = "mixalispolidorou@gmail.com"
DB_PATH    = "/home/agent/migration_agent/migration_data.db"
PI_PATH    = "/home/agent/migration_agent/pressure_index.json"
SENT_LOG   = "/home/agent/migration_agent/alerts_sent.json"

ALERT_THRESHOLD    = 8    # score ≥ 8 → alert email
PRESSURE_THRESHOLD = 50   # index ≥ 50 → pressure email

logging.basicConfig(filename="/home/agent/migration_agent/dashboard.log",
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def load_sent_log():
    if os.path.exists(SENT_LOG):
        try:
            with open(SENT_LOG) as f:
                return json.load(f)
        except Exception:
            pass
    return {"alert_ids": [], "pressure_dates": []}

def save_sent_log(log):
    with open(SENT_LOG, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def send_email(subject, html_body):
    """Αποστολή email μέσω Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = RECIPIENT
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, RECIPIENT, msg.as_string())
        logging.info(f"Email sent: {subject}")
        return True
    except Exception as e:
        logging.error(f"Email failed: {e}")
        return False

def check_high_alerts():
    """Ελεγχος για signals score ≥ 8 που δεν εχουν σταλει."""
    sent = load_sent_log()
    already_sent = set(sent.get("alert_ids", []))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = now_cy().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT rowid, source, score, summary, link, country, category, date
        FROM signals
        WHERE score >= ? AND date = ?
        ORDER BY score DESC
    """, (ALERT_THRESHOLD, today))
    rows = cursor.fetchall()
    conn.close()

    new_alerts = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7])
                  for r in rows if r[0] not in already_sent]

    if not new_alerts:
        print(f"  Κανένα νέο high alert σήμερα ({today}).")
        return False

    print(f"  Βρέθηκαν {len(new_alerts)} νέα high alerts — αποστολή email...")

    # Δόμηση HTML
    rows_html = ""
    for rid, src, score, summ, link, country, cat, date in new_alerts:
        score_color = "#dc2626" if score >= 9 else "#d97706"
        link_html = f'<a href="{link}" style="color:#2563eb">Πηγή →</a>' if link and link.startswith("http") else ""
        rows_html += f"""
        <div style="background:#fff;border:1px solid #e2e8f0;border-left:4px solid {score_color};
                    border-radius:8px;padding:14px 16px;margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;margin-bottom:6px">
            <span style="font-size:11px;font-weight:600;color:#374151">{src}</span>
            <span style="background:{score_color};color:#fff;font-size:12px;font-weight:700;
                         padding:2px 10px;border-radius:12px">Score {score}</span>
          </div>
          <div style="font-size:13px;color:#1f2937;line-height:1.6;margin-bottom:6px">{summ}</div>
          <div style="font-size:11px;color:#94a3b8">{cat or ''} · {country or ''} · {date} &nbsp; {link_html}</div>
        </div>"""

    now_str = now_cy().strftime("%d/%m/%Y %H:%M")
    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f1f5f9;padding:20px;margin:0">
    <div style="max-width:640px;margin:0 auto">
      <div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:12px;
                  padding:20px 24px;margin-bottom:20px">
        <div style="color:#fff;font-size:18px;font-weight:700">Migration Intelligence — Cyprus</div>
        <div style="color:rgba(255,255,255,0.7);font-size:12px;margin-top:4px">
          Ειδοποίηση Υψηλής Προτεραιότητας · {now_str}</div>
      </div>
      <div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;
                  padding:12px 16px;margin-bottom:16px">
        <div style="color:#991b1b;font-size:13px;font-weight:600">
          {len(new_alerts)} νέο{'ι' if len(new_alerts)>1 else ''} alert{'s' if len(new_alerts)>1 else ''}
          score ≥ {ALERT_THRESHOLD} εντοπίστηκε{'αν' if len(new_alerts)>1 else ''} σήμερα</div>
      </div>
      {rows_html}
      <div style="text-align:center;padding:16px;font-size:11px;color:#94a3b8">
        Cypronetwork Consultancy Group · OSINT Migration Intelligence Agent<br>
        Περιορισμένης Κυκλοφορίας
      </div>
    </div></body></html>"""

    subject = f"[Migration Alert] {len(new_alerts)} High-Priority Signal{'s' if len(new_alerts)>1 else ''} — {today}"
    ok = send_email(subject, html)
    if ok:
        sent["alert_ids"] = list(already_sent | {r[0] for r in new_alerts})
        # Κρατα μονο τελευταίες 500 εγγραφές
        sent["alert_ids"] = sent["alert_ids"][-500:]
        save_sent_log(sent)
    return ok

def check_pressure_alert():
    """Ελεγχος αν ο Δεικτης Πίεσης >= 50 και δεν εχει σταλει σήμερα."""
    if not os.path.exists(PI_PATH):
        print("  Δεν βρέθηκε pressure_index.json.")
        return False

    with open(PI_PATH) as f:
        pi = json.load(f)

    index = pi.get("today_index", 0)
    risk  = pi.get("today_risk", "")
    color = pi.get("today_risk_color", "#2563eb")

    if index < PRESSURE_THRESHOLD:
        print(f"  Δεικτης {index:.1f} < {PRESSURE_THRESHOLD} — δεν απαιτείται ειδοποίηση.")
        return False

    sent = load_sent_log()
    today = now_cy().strftime("%Y-%m-%d")
    if today in sent.get("pressure_dates", []):
        print(f"  Pressure alert ήδη εστάλη σήμερα ({today}).")
        return False

    print(f"  Δεικτης {index:.1f} ({risk}) ≥ {PRESSURE_THRESHOLD} — αποστολή pressure alert...")

    comp = pi.get("components", {})
    forecast = pi.get("forecast", [])
    interp = pi.get("interpretation", "")
    now_str = now_cy().strftime("%d/%m/%Y %H:%M")

    risk_labels = {"MINIMAL":"Ελάχιστη","LOW":"Χαμηλή","MODERATE":"Μέτρια","HIGH":"Υψηλή"}

    # 7-day forecast rows
    fc_html = ""
    for d in forecast[:7]:
        fc_color = d.get("risk_color","#64748b")
        fc_html += f"""
        <tr>
          <td style="padding:6px 10px;font-size:12px;color:#374151">{d['day']} {d['date'][5:]}</td>
          <td style="padding:6px 10px;text-align:center;font-weight:700;color:{fc_color}">{d['index']:.0f}</td>
          <td style="padding:6px 10px;text-align:center;font-size:11px;color:{fc_color};font-weight:600">{d['risk']}</td>
        </tr>"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f1f5f9;padding:20px;margin:0">
    <div style="max-width:640px;margin:0 auto">
      <div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);border-radius:12px;
                  padding:20px 24px;margin-bottom:20px">
        <div style="color:#fff;font-size:18px;font-weight:700">Migration Intelligence — Cyprus</div>
        <div style="color:rgba(255,255,255,0.7);font-size:12px;margin-top:4px">
          Ειδοποίηση Μεταναστευτικής Πίεσης · {now_str}</div>
      </div>

      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;
                  padding:20px;margin-bottom:16px;text-align:center">
        <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.8px;margin-bottom:8px">Δεικτης Μεταναστευτικης Πιεσης</div>
        <div style="font-size:52px;font-weight:700;color:{color};line-height:1">{index:.0f}</div>
        <div style="margin-top:8px">
          <span style="background:{color}20;color:{color};border:1px solid {color}40;
                       font-size:13px;font-weight:600;padding:4px 16px;border-radius:20px">
            {risk_labels.get(risk,risk)} Πίεση</span>
        </div>
      </div>

      <div style="background:#eff6ff;border-left:4px solid #2563eb;border-radius:6px;
                  padding:12px 16px;margin-bottom:16px;font-size:13px;color:#1e3a5f;line-height:1.7">
        <b>Ανάλυση:</b> {interp}
      </div>

      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;
                  padding:16px;margin-bottom:16px">
        <div style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.8px;margin-bottom:12px">Συνιστωσες Μοντελου</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <div style="background:#f8fafc;border-radius:6px;padding:10px;border-left:3px solid #2563eb">
            <div style="font-size:10px;color:#94a3b8">Anchor αφίξεων</div>
            <div style="font-size:18px;font-weight:700;color:#2563eb">{comp.get('arrivals_anchor',0):.0f}/100</div>
          </div>
          <div style="background:#f8fafc;border-radius:6px;padding:10px;border-left:3px solid #16a34a">
            <div style="font-size:10px;color:#94a3b8">Flow gate</div>
            <div style="font-size:18px;font-weight:700;color:#16a34a">×{comp.get('flow_gate',0)}</div>
          </div>
          <div style="background:#f8fafc;border-radius:6px;padding:10px;border-left:3px solid #d97706">
            <div style="font-size:10px;color:#94a3b8">Transit bump</div>
            <div style="font-size:18px;font-weight:700;color:#d97706">+{comp.get('transit_bump',0):.0f}</div>
          </div>
          <div style="background:#f8fafc;border-radius:6px;padding:10px;border-left:3px solid #dc2626">
            <div style="font-size:10px;color:#94a3b8">Conflict modifier</div>
            <div style="font-size:18px;font-weight:700;color:#dc2626">+{comp.get('conflict_modifier',0):.0f}</div>
          </div>
        </div>
      </div>

      <div style="background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:16px;margin-bottom:16px">
        <div style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                    letter-spacing:0.8px;margin-bottom:12px">Προβλεψη 7 Ημερων</div>
        <table style="width:100%;border-collapse:collapse">
          <tr style="background:#f8fafc">
            <th style="padding:6px 10px;text-align:left;font-size:11px;color:#6b7280">Ημέρα</th>
            <th style="padding:6px 10px;text-align:center;font-size:11px;color:#6b7280">Δείκτης</th>
            <th style="padding:6px 10px;text-align:center;font-size:11px;color:#6b7280">Κατηγορία</th>
          </tr>
          {fc_html}
        </table>
      </div>

      <div style="text-align:center;padding:16px;font-size:11px;color:#94a3b8">
        Cypronetwork Consultancy Group · OSINT Migration Intelligence Agent<br>
        Περιορισμένης Κυκλοφορίας
      </div>
    </div></body></html>"""

    subject = f"[Migration Pressure] Δεικτης {index:.0f}/100 — {risk_labels.get(risk,risk)} Πίεση · {today}"
    ok = send_email(subject, html)
    if ok:
        sent.setdefault("pressure_dates", []).append(today)
        sent["pressure_dates"] = sent["pressure_dates"][-90:]
        save_sent_log(sent)
    return ok

def main():
    # Φόρτωση .env
    env_path = "/home/agent/migration_agent/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

    global SMTP_USER, SMTP_PASS
    SMTP_USER = os.getenv("SMTP_USER", SMTP_USER)
    SMTP_PASS = os.getenv("SMTP_PASS", SMTP_PASS)

    print("\n── Φάση Δ: Email Alert System ──")
    print(f"  Ώρα Κύπρου: {now_cy().strftime('%d/%m/%Y %H:%M')}")
    print()

    print("1. Ελεγχος high alerts (score ≥ 8)...")
    check_high_alerts()

    print()
    print("2. Ελεγχος pressure index (≥ 50)...")
    check_pressure_alert()

    print("\n✅ Email alerts complete.")

if __name__ == "__main__":
    main()
