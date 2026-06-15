"""
daily_report.py
Ημερήσια Αναφορά OSINT — Migration Intelligence Agent
Παράγει: reports/OSINT_Report_YYYY-MM-DD.pdf
"""
import os, sqlite3, datetime, unicodedata, json
from fpdf import FPDF
from dotenv import load_dotenv

load_dotenv()

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, "migration_data.db")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
FONT_PATH   = os.path.join(BASE_DIR, "DejaVuSans.ttf")
FONT_BOLD   = os.path.join(BASE_DIR, "DejaVuSans-Bold.ttf")
PI_PATH     = os.path.join(BASE_DIR, "pressure_index.json")

RED   = (185, 28,  28)
AMBER = (161, 98,  7)
BLUE  = (37,  99,  235)
GREEN = (22,  101, 52)
NAVY  = (15,  23,  42)
GRAY  = (107, 114, 128)
LGRAY = (239, 246, 255)
WHITE = (255, 255, 255)
BLACK = (17,  24,  39)

def clean(text):
    if not text: return ""
    text = unicodedata.normalize('NFKC', str(text))
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                  "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρςστυφχψω"
                  "άέήίόύώΆΈΉΊΌΎΏϊϋΪΫΐΰ0123456789 .,!?:;'-()[]/%€\"'@#")
    return " ".join("".join(c for c in text if c in allowed).split())

class DailyPDF(FPDF):
    def __init__(self, report_date):
        super().__init__()
        self.report_date = report_date
        self.add_font("Regular", "", FONT_PATH)
        self.add_font("Regular", "B", FONT_BOLD)
        self.set_font("Regular", "", 10)

    def header(self):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 18, 'F')
        self.set_font("Regular", "B", 11)
        self.set_text_color(*WHITE)
        self.set_xy(8, 4)
        self.cell(0, 10, "OSINT MIGRATION INTELLIGENCE — CYPRUS", ln=False)
        self.set_font("Regular", "", 8)
        self.set_xy(0, 4)
        self.cell(200, 10, f"Hmerisia Anafora: {self.report_date}", align="R")
        self.set_text_color(*BLACK)
        self.ln(14)

    def footer(self):
        self.set_y(-12)
        self.set_font("Regular", "", 7)
        self.set_text_color(*GRAY)
        self.cell(0, 5, f"Cypronetwork Consultancy Group | Periorizomenis Kykloforias | Selida {self.page_no()}", align="C")

    def section_title(self, title, color=NAVY):
        self.set_font("Regular", "B", 10)
        self.set_text_color(*color)
        self.set_fill_color(*LGRAY)
        self.cell(0, 7, clean(title), ln=True, fill=True)
        self.set_text_color(*BLACK)
        self.ln(1)

    def kpi_row(self, items):
        w = 190 / len(items)
        x0 = self.get_x()
        for label, value, color in items:
            self.set_fill_color(*LGRAY)
            self.rect(self.get_x(), self.get_y(), w-2, 16, 'F')
            self.set_font("Regular", "", 7)
            self.set_text_color(*GRAY)
            self.set_xy(self.get_x(), self.get_y()+1)
            self.cell(w-2, 4, clean(label), ln=False, align="C")
            self.set_xy(self.get_x()-w+2, self.get_y()+4)
            self.set_font("Regular", "B", 14)
            self.set_text_color(*color)
            self.cell(w-2, 8, str(value), ln=False, align="C")
            self.set_xy(self.get_x(), self.get_y()-4)
        self.ln(20)
        self.set_text_color(*BLACK)

def get_data(target_date):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    date_str = target_date.strftime("%Y-%m-%d")
    c.execute("""
        SELECT source, score, summary, link, country, category
        FROM signals WHERE date = ?
        ORDER BY score DESC
    """, (date_str,))
    rows = c.fetchall()
    conn.close()
    return rows

def generate_daily_report(target_date=None):
    if target_date is None:
        target_date = datetime.date.today()

    os.makedirs(REPORTS_DIR, exist_ok=True)
    date_str = target_date.strftime("%Y-%m-%d")
    output   = os.path.join(REPORTS_DIR, f"OSINT_Report_{date_str}.pdf")

    rows = get_data(target_date)
    if not rows:
        print(f"  Δεν υπάρχουν δεδομένα για {date_str}")
        return None

    # Στατιστικά
    total   = len(rows)
    high    = sum(1 for r in rows if r[1] >= 8)
    border  = sum(1 for r in rows if r[1] >= 4 and r[1] <= 7)
    macro   = sum(1 for r in rows if r[1] <= 3)
    alerts  = [r for r in rows if r[1] >= 8]
    top10   = rows[:10]

    # Pressure Index
    pi_index, pi_risk = "—", "—"
    if os.path.exists(PI_PATH):
        try:
            pi = json.load(open(PI_PATH))
            pi_index = f"{pi['today_index']:.0f}/100"
            risk_map = {"MINIMAL":"Elaxisti", "LOW":"Xamili", "MODERATE":"Metria", "HIGH":"Ipsili"}
            pi_risk  = risk_map.get(pi['today_risk'], pi['today_risk'])
        except Exception:
            pass

    # Κατανομή κατηγοριών
    from collections import Counter
    cats = Counter(r[5] for r in rows if r[5])

    pdf = DailyPDF(date_str)
    pdf.add_page()

    # ── Τίτλος ──
    pdf.set_font("Regular", "B", 13)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 8, f"Hmerisia Anafora Metanasteutikis Epilirosis", ln=True, align="C")
    pdf.set_font("Regular", "", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5, f"Periodo: {date_str} | Paragogi: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
    pdf.ln(4)

    # ── KPIs ──
    pdf.section_title("SINOPTIKA STOIXEIA")
    pdf.kpi_row([
        ("Sinolo Signals", total, BLUE),
        ("Cyprus Alerts (≥8)", high, RED),
        ("Border Info (4-7)", border, AMBER),
        ("Macro (1-3)", macro, GREEN),
    ])

    # ── Pressure Index ──
    pdf.section_title("DEIKTIS METANASTEUTIKIS PIESIS")
    pdf.set_font("Regular", "", 9)
    pdf.cell(95, 7, f"Deiktis simeras: {pi_index}", ln=False)
    pdf.cell(95, 7, f"Kategorias: {pi_risk}", ln=True)
    pdf.ln(3)

    # ── Cyprus Alerts ──
    if alerts:
        pdf.section_title(f"CYPRUS ALERTS — SCORE >= 8 ({len(alerts)} signals)", RED)
        for src, score, summ, link, country, cat in alerts:
            pdf.set_fill_color(*RED)
            pdf.set_text_color(*WHITE)
            pdf.set_font("Regular", "B", 8)
            pdf.cell(15, 5, f"  {score}/10", fill=True, ln=False)
            pdf.set_fill_color(*LGRAY)
            pdf.set_text_color(*BLACK)
            pdf.cell(175, 5, clean(src) + (f" | {clean(country)}" if country else ""), fill=True, ln=True)
            pdf.set_font("Regular", "", 8)
            pdf.multi_cell(0, 4, clean(summ)[:300])
            pdf.ln(2)

    # ── Top 10 Signals ──
    pdf.section_title("TOP 10 SIGNALS IMERINAS")
    pdf.set_font("Regular", "B", 7)
    pdf.set_fill_color(*NAVY)
    pdf.set_text_color(*WHITE)
    pdf.cell(12, 5, "Score", fill=True, ln=False, align="C")
    pdf.cell(40, 5, "Pigi", fill=True, ln=False)
    pdf.cell(18, 5, "Xora", fill=True, ln=False)
    pdf.cell(120, 5, "Perilepsi", fill=True, ln=True)
    pdf.set_text_color(*BLACK)

    for i, (src, score, summ, link, country, cat) in enumerate(top10):
        fill = i % 2 == 0
        pdf.set_fill_color(*(LGRAY if fill else WHITE))
        pdf.set_font("Regular", "B" if score >= 8 else "", 7)
        color = RED if score >= 8 else (AMBER if score >= 5 else BLACK)
        pdf.set_text_color(*color)
        pdf.cell(12, 5, str(score), fill=fill, ln=False, align="C")
        pdf.set_text_color(*BLACK)
        pdf.set_font("Regular", "", 7)
        pdf.cell(40, 5, clean(src)[:25], fill=fill, ln=False)
        pdf.cell(18, 5, clean(country or "")[:12], fill=fill, ln=False)
        pdf.cell(120, 5, clean(summ)[:80], fill=fill, ln=True)

    pdf.ln(4)

    # ── Κατανομή κατηγοριών ──
    pdf.section_title("KATANOMI KATHGORION")
    pdf.set_font("Regular", "", 8)
    for cat, cnt in cats.most_common():
        pct = cnt / total * 100
        pdf.cell(60, 5, clean(cat), ln=False)
        pdf.cell(20, 5, f"{cnt} signals", ln=False)
        pdf.cell(110, 5, f"({pct:.0f}%)", ln=True)

    pdf.output(output)
    print(f"✅ PDF: {output} ({total} signals)")
    return output

if __name__ == "__main__":
    generate_daily_report()
