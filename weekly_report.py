"""
weekly_report.py
Εβδομαδιαία Αναφορά OSINT — Migration Intelligence Agent
Τρέξε: python weekly_report.py
Παράγει: reports/Weekly_OSINT_Report_YYYY-WXX.pdf
"""

import os
import sqlite3
import datetime
import unicodedata
from collections import defaultdict
from fpdf import FPDF
from google import genai
from dotenv import load_dotenv

load_dotenv()

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, "migration_data.db")
REPORTS_DIR  = os.path.join(BASE_DIR, "reports")
FONT_PATH    = os.path.join(BASE_DIR, "DejaVuSans.ttf")
FONT_BOLD    = os.path.join(BASE_DIR, "DejaVuSans-Bold.ttf")
LOGO_PATH    = os.path.join(BASE_DIR, "cypronetwork_logo.png")

# ── Χρώματα ──────────────────────────────────────────────────
RED   = (185, 28,  28)
AMBER = (161, 98,  7)
BLUE  = (37,  99,  235)
GREEN = (22,  101, 52)
NAVY  = (15,  23,  42)
GRAY  = (107, 114, 128)
LGRAY = (239, 246, 255)
WHITE = (255, 255, 255)
BLACK = (17,  24,  39)


def clean_for_pdf(text):
    """Ίδια συνάρτηση με το migration_agent_full.py"""
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                  "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρςστυφχψω"
                  "άέήίόύώΆΈΉΊΌΎΏϊϋΪΫΐΰ0123456789 .,!?:;'-()[]/%€\"'@#")
    cleaned = "".join(c for c in text if c in allowed)
    return " ".join(cleaned.split())


def get_week_range():
    today = datetime.date.today()
    start = today - datetime.timedelta(days=today.weekday() + 7)
    end   = start + datetime.timedelta(days=6)
    return start, end


def load_data(start, end):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT source, score, summary, date, link, country
        FROM signals
        WHERE date >= ? AND date <= ?
        ORDER BY score DESC, date DESC
    """, (start.isoformat(), end.isoformat()))
    rows = c.fetchall()
    conn.close()
    return rows


def gemini_executive_summary(rows, start, end):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Executive summary mh diathesimo."
    try:
        gc = genai.Client(api_key=api_key)
        top = [r for r in rows if r[1] >= 6][:25]
        signal_text = "\n".join(f"[Score {r[1]}] {r[0]}: {r[2]}" for r in top)
        prompt = f"""Eisai Intelligence Analyst sto Ypourgeio Metanastefsis Kyprou.
Analysise ta parakatw signals apo tis {start} eos {end} kai grapse ena EXECUTIVE SUMMARY sta ELLINIKA, 150-250 lexeis.
Periorise se: kyrious kindynous, taseis, systaseis. MHN xrhsimopoieis emojis.
Signals:\n{signal_text}\nGrapse MONO to summary, xwris titlo."""
        response = gc.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text.strip()
    except Exception as e:
        return f"Executive summary den paragmathike: {e}"


class WeeklyPDF(FPDF):
    def __init__(self, R, has_bold, start, end, week_num):
        super().__init__()
        self.R        = R
        self.has_bold = has_bold
        self.start    = start
        self.end      = end
        self.week_num = week_num

    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 34, 'F')
        if os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, x=8, y=2, h=30)
        self.set_text_color(*WHITE)
        self.set_font(self.R, "B" if self.has_bold else "", 12)
        self.set_xy(54, 7)
        self.cell(0, 6, "OSINT MIGRATION INTELLIGENCE", ln=True)
        self.set_font(self.R, "", 8)
        self.set_xy(54, 15)
        self.cell(0, 5, clean_for_pdf("Εβδομαδιαια Αναφορα Μεταναστευτικων Ροων"), ln=True)
        self.set_text_color(148, 163, 184)
        self.set_font(self.R, "", 7)
        self.set_xy(54, 22)
        period = f"{self.start.strftime('%d/%m/%Y')} - {self.end.strftime('%d/%m/%Y')}  |  Εβδομαδα {self.week_num}"
        self.cell(0, 5, clean_for_pdf(period), ln=True)
        self.set_fill_color(185, 28, 28)
        self.set_text_color(*WHITE)
        self.set_font(self.R, "B" if self.has_bold else "", 7)
        self.set_xy(140, 12)
        self.cell(62, 8, clean_for_pdf("ΠΕΡΙΟΡΙΣΜΕΝΗΣ ΚΥΚΛΟΦΟΡΙΑΣ"), align='C', fill=True)
        self.set_text_color(0, 0, 0)
        self.set_y(40)

    def footer(self):
        self.set_y(-13)
        self.set_draw_color(209, 213, 219)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)
        self.set_font(self.R, "", 7)
        self.set_text_color(156, 163, 175)
        self.cell(95, 5, "CyproNetwork Consultancy Group | OSINT Migration Intelligence")
        self.cell(95, 5,
            clean_for_pdf(f"Περιορισμενης Κυκλοφοριας | Εβδομαδα {self.week_num} | Σελιδα {self.page_no()}"),
            align='R')
        self.set_text_color(0, 0, 0)


def generate_weekly_report():
    start, end = get_week_range()
    week_num   = start.isocalendar()[1]
    os.makedirs(REPORTS_DIR, exist_ok=True)

    print(f"Φορτωση δεδομενων: {start} - {end}")
    rows = load_data(start, end)
    if not rows:
        print("Δεν βρεθηκαν δεδομενα για αυτη την εβδομαδα.")
        return

    alerts  = [r for r in rows if r[1] >= 8]
    borders = [r for r in rows if 6 <= r[1] <= 7]
    macros  = [r for r in rows if 1 <= r[1] <= 5]

    by_country = defaultdict(lambda: {"total": 0, "alerts": 0, "borders": 0, "total_score": 0})
    for r in rows:
        country = r[5] or "Other"
        by_country[country]["total"]       += 1
        by_country[country]["total_score"] += r[1]
        if r[1] >= 8:   by_country[country]["alerts"]  += 1
        elif r[1] >= 6: by_country[country]["borders"] += 1

    by_date = defaultdict(list)
    for r in rows:
        by_date[r[3]].append(r[1])

    # ── Fonts ────────────────────────────────────────────────
    has_font = os.path.exists(FONT_PATH)
    has_bold = os.path.exists(FONT_BOLD)
    R = "DV" if has_font else "Helvetica"

    print("Δημιουργια Executive Summary...")
    summary = gemini_executive_summary(rows, start, end)

    print("Δημιουργια PDF...")
    pdf = WeeklyPDF(R, has_bold, start, end, week_num)
    pdf.set_auto_page_break(auto=True, margin=18)
    if has_font:
        pdf.add_font("DV", "", FONT_PATH)
    if has_bold:
        pdf.add_font("DV", "B", FONT_BOLD)

    # ── Helpers ──────────────────────────────────────────────
    def section_header(title, r, g, b):
        pdf.set_fill_color(r, g, b)
        y = pdf.get_y()
        pdf.rect(10, y, 190, 8, 'F')
        pdf.set_font(R, "B" if has_bold else "", 8)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(13, y + 1.5)
        pdf.cell(0, 5, clean_for_pdf(title))
        pdf.set_text_color(0, 0, 0)
        pdf.set_y(y + 10)

    def signal_row(source, score, summary_text, country, link=""):
        if score >= 8:
            sr, sg, sb = 254, 226, 226
            tr, tg, tb = 153, 27,  27
        elif score >= 6:
            sr, sg, sb = 255, 251, 235
            tr, tg, tb = 120, 53,  15
        else:
            sr, sg, sb = 239, 246, 255
            tr, tg, tb = 29,  78,  216

        summary_clean = clean_for_pdf(summary_text or '')
        meta = clean_for_pdf(f"{country or ''} | {source or ''}")

        pdf.set_fill_color(sr, sg, sb)
        pdf.set_text_color(tr, tg, tb)
        pdf.set_font(R, "B" if has_bold else "", 10)
        pdf.cell(14, 6, str(score), align='C', fill=True)
        pdf.set_text_color(107, 114, 128)
        pdf.set_font(R, "", 7)
        pdf.cell(176, 6, meta, ln=True)

        pdf.set_text_color(*BLACK)
        pdf.set_font(R, "", 8)
        pdf.set_x(10)
        pdf.multi_cell(190, 4.5, summary_clean)

        if link and str(link).startswith("http"):
            pdf.set_text_color(29, 78, 216)
            pdf.set_font(R, "", 7)
            pdf.set_x(10)
            pdf.cell(190, 4, clean_for_pdf(link[:100]), ln=True)
            pdf.set_text_color(0, 0, 0)

        pdf.set_draw_color(229, 231, 235)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)
        pdf.set_text_color(0, 0, 0)

    def empty_msg(msg):
        pdf.set_x(13)
        pdf.set_font(R, "", 8)
        pdf.set_text_color(107, 114, 128)
        pdf.cell(0, 7, clean_for_pdf(msg), ln=True)
        pdf.set_text_color(0, 0, 0)

    # ══════════════════════════════════════════════════════════
    # ΣΕΛΙΔΑ 1: Cover + Executive Summary + KPIs
    # ══════════════════════════════════════════════════════════
    pdf.add_page()

    # KPI bar
    y0 = pdf.get_y()
    pdf.set_fill_color(239, 246, 255)
    pdf.set_draw_color(147, 197, 253)
    pdf.set_line_width(0.4)
    pdf.rect(10, y0, 190, 8, 'FD')
    pdf.set_font(R, "B" if has_bold else "", 8)
    pdf.set_text_color(29, 78, 216)
    pdf.set_xy(13, y0 + 1.5)
    pdf.cell(0, 5, clean_for_pdf(
        f"Συνολικα signals: {len(rows)}   |   Cyprus Alerts (8+): {len(alerts)}"
        f"   |   Border Info (6-7): {len(borders)}   |   Macro (1-5): {len(macros)}"
    ))
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + 10)
    pdf.ln(3)

    # Executive Summary
    section_header("ΕΚΤΕΛΕΣΤΙΚΗ ΠΕΡΙΛΗΨΗ", 15, 23, 42)
    pdf.set_font(R, "", 8)
    pdf.set_x(13)
    pdf.multi_cell(184, 4.5, clean_for_pdf(summary))
    pdf.ln(5)

    # ── Συνοψη ανα Χωρα ──────────────────────────────────────
    section_header("ΣΥΝΟΨΗ ΑΝΑ ΧΩΡΑ", 15, 23, 42)

    # Table header
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(*WHITE)
    pdf.set_font(R, "B" if has_bold else "", 8)
    for label, w in [("ΧΩΡΑ", 55), ("ΣΥΝΟΛΟ", 30), ("ALERTS 8+", 35), ("BORDER 6-7", 35), ("ΜΕΣΟ SCORE", 35)]:
        pdf.cell(w, 7, clean_for_pdf(label), fill=True, border=0, align="C", ln=0)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)

    for i, (country, stats) in enumerate(sorted(by_country.items(), key=lambda x: -x[1]["total"])):
        fill = i % 2 == 0
        pdf.set_fill_color(243, 244, 246) if fill else pdf.set_fill_color(*WHITE)
        pdf.set_font(R, "", 8)
        avg = stats["total_score"] / stats["total"] if stats["total"] else 0
        for val, w in [
            (clean_for_pdf(country[:28]), 55),
            (str(stats["total"]), 30),
            (str(stats["alerts"]), 35),
            (str(stats["borders"]), 35),
            (f"{avg:.1f}", 35),
        ]:
            pdf.cell(w, 6, val, fill=fill, border=0, align="C", ln=0)
        pdf.ln()
    pdf.ln(5)

    # ── Ημερησιο Risk Index ───────────────────────────────────
    section_header("ΗΜΕΡΗΣΙΟ RISK INDEX", 15, 23, 42)

    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(*WHITE)
    pdf.set_font(R, "B" if has_bold else "", 8)
    for label, w in [("ΗΜΕΡΟΜΗΝΙΑ", 50), ("SIGNALS", 30), ("MAX SCORE", 35), ("ΜΕΣΟ SCORE", 35), ("RISK", 40)]:
        pdf.cell(w, 7, clean_for_pdf(label), fill=True, border=0, align="C", ln=0)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)

    for i, (dt, scores) in enumerate(sorted(by_date.items())):
        fill = i % 2 == 0
        pdf.set_fill_color(243, 244, 246) if fill else pdf.set_fill_color(*WHITE)
        pdf.set_font(R, "", 8)
        avg   = sum(scores) / len(scores)
        max_s = max(scores)
        risk  = "ALERT" if max_s >= 8 else "ELEVATED" if max_s >= 6 else "NORMAL"
        risk_color = RED if max_s >= 8 else AMBER if max_s >= 6 else GREEN
        for val, w in [(str(dt), 50), (str(len(scores)), 30), (str(max_s), 35), (f"{avg:.1f}", 35)]:
            pdf.cell(w, 6, val, fill=fill, border=0, align="C", ln=0)
        pdf.set_text_color(*risk_color)
        pdf.cell(40, 6, risk, fill=fill, border=0, align="C", ln=1)
        pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # ══════════════════════════════════════════════════════════
    # ΣΕΛΙΔΑ 2+: Cyprus Alerts
    # ══════════════════════════════════════════════════════════
    pdf.add_page()
    section_header(f"ΚΡΙΣΙΜΕΣ ΕΙΔΗΣΕΙΣ — CYPRUS ALERTS  (Score 8-10) — {len(alerts)} signals", 185, 28, 28)
    if not alerts:
        empty_msg("Καμια κρισιμη ειδηση αυτη την εβδομαδα.")
    else:
        for r in alerts[:50]:
            signal_row(r[0], r[1], r[2], r[5] or "", r[4] or "")
    pdf.ln(4)

    # ── Border Info ───────────────────────────────────────────
    section_header(f"ΠΛΗΡΟΦΟΡΙΕΣ ΣΥΝΟΡΩΝ — BORDER INFO  (Score 6-7) — {len(borders)} signals", 161, 98, 7)
    if not borders:
        empty_msg("Καμια ειδηση border info αυτη την εβδομαδα.")
    else:
        for r in borders[:60]:
            signal_row(r[0], r[1], r[2], r[5] or "", r[4] or "")
    pdf.ln(4)

    # ── Macro Info ────────────────────────────────────────────
    pdf.add_page()
    section_header(f"ΓΕΝΙΚΟ ΥΠΟΒΑΘΡΟ — MACRO INFO  (Score 1-5) — top 30 apo {len(macros)}", 37, 99, 235)
    if not macros:
        empty_msg("Καμια macro ειδηση αυτη την εβδομαδα.")
    else:
        for r in sorted(macros, key=lambda x: -x[1])[:30]:
            signal_row(r[0], r[1], r[2], r[5] or "", r[4] or "")

    filename = os.path.join(REPORTS_DIR, f"Weekly_OSINT_Report_{start.isocalendar()[0]}-W{week_num:02d}.pdf")
    pdf.output(filename)
    print(f"\nDhmiourgithike: {filename}")
    print(f"  Synolo signals: {len(rows)}")
    print(f"  Cyprus Alerts:  {len(alerts)}")
    print(f"  Border Info:    {len(borders)}")
    print(f"  Macro Signals:  {len(macros)}")
    return filename


if __name__ == "__main__":
    generate_weekly_report()