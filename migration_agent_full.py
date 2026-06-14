import os
import json
import sqlite3
import datetime
import csv
import socket
import logging
import urllib.request
import unicodedata
from google import genai
import feedparser
from dotenv import load_dotenv
from fpdf import FPDF

socket.setdefaulttimeout(15)
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "migration_data.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
CSV_PATH = os.path.join(BASE_DIR, "migration_data.csv")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
FONT_PATH = os.path.join(BASE_DIR, "DejaVuSans.ttf")
FONT_BOLD_PATH = os.path.join(BASE_DIR, "DejaVuSans-Bold.ttf")
LOGO_PATH = os.path.join(BASE_DIR, "cypronetwork_logo.png")

# ── 2.5: Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=os.path.join(BASE_DIR, 'migration_agent.log'),
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ── 3.1: Semantic Deduplication ───────────────────────────────────────────────
def is_duplicate(new_summary, today_str):
    """Ελέγχει αν υπάρχει ήδη παρόμοιο signal σήμερα (TF-IDF similarity)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT summary FROM signals WHERE date = ?", (today_str,))
        existing = [r[0] for r in c.fetchall() if r[0]]
        conn.close()
        if not existing:
            return False

        # Απλό word overlap (χωρίς sklearn dependency)
        new_words = set(new_summary.lower().split())
        for ex in existing:
            ex_words = set(ex.lower().split())
            if not new_words or not ex_words:
                continue
            overlap = len(new_words & ex_words) / len(new_words | ex_words)
            if overlap > 0.65:
                return True
        return False
    except Exception as e:
        logging.warning(f"Deduplication check failed: {e}")
        return False


# ── 3.4: Named Entity Recognition (NER) ──────────────────────────────────────
def extract_locations(summary):
    """Εξάγει τοποθεσίες από summary για το geospatial map."""
    LOCATION_KEYWORDS = {
        'Λίβανος': 'Lebanon', 'Λιβάνου': 'Lebanon', 'Βηρυτός': 'Lebanon',
        'Τύρος': 'Lebanon', 'Τρίπολη': 'Lebanon', 'Σιδώνα': 'Lebanon',
        'Συρία': 'Syria', 'Συρίας': 'Syria', 'Δαμασκός': 'Syria',
        'Λατάκεια': 'Syria', 'Χαλέπι': 'Syria', 'Ντέιρ': 'Syria',
        'Τουρκία': 'Turkiye', 'Τουρκίας': 'Turkiye', 'Μερσίνη': 'Turkiye',
        'Αίγυπτος': 'Egypt', 'Αλεξάνδρεια': 'Egypt', 'Κάιρο': 'Egypt',
        'Γάζα': 'Cross_Regional', 'Ισραήλ': 'Cross_Regional',
        'Κύπρος': 'Cyprus', 'Κύπρου': 'Cyprus',
        'Lebanon': 'Lebanon', 'Syria': 'Syria', 'Turkey': 'Turkiye',
        'Egypt': 'Egypt', 'Gaza': 'Cross_Regional', 'Israel': 'Cross_Regional',
    }
    found = set()
    if not summary:
        return list(found)
    for keyword, country in LOCATION_KEYWORDS.items():
        if keyword.lower() in summary.lower():
            found.add(country)
    return list(found)


# ── 3.5: Anomaly Detection ────────────────────────────────────────────────────
def check_anomaly():
    """Ελέγχει αν υπάρχει ασυνήθιστη αύξηση signals σήμερα."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        today_str = datetime.datetime.now().date().isoformat()

        # Signals σήμερα
        c.execute("SELECT COUNT(*) FROM signals WHERE date = ?", (today_str,))
        today_count = c.fetchone()[0]

        # Μέσος όρος τελευταίων 14 ημερών (εκτός σήμερα)
        c.execute("""
            SELECT date, COUNT(*) as cnt FROM signals
            WHERE date < ?
            GROUP BY date
            ORDER BY date DESC
            LIMIT 14
        """, (today_str,))
        history = [r[1] for r in c.fetchall()]
        conn.close()

        if len(history) < 3:
            return None

        avg = sum(history) / len(history)
        std = (sum((x - avg) ** 2 for x in history) / len(history)) ** 0.5

        if today_count > avg + 2 * std and std > 0:
            pct = round((today_count - avg) / avg * 100)
            msg = f"ANOMALY: {today_count} signals σήμερα (+{pct}% vs 14-day avg {avg:.0f})"
            logging.warning(msg)
            print(f"⚠️  {msg}")
            return msg
        return None
    except Exception as e:
        logging.error(f"Anomaly detection failed: {e}")
        return None

if not os.path.exists(FONT_PATH):
    for url in [
        "https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf",
        "https://raw.githubusercontent.com/fpdf2/fpdf2/master/test/fonts/DejaVuSans.ttf"
    ]:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as r, open(FONT_PATH, 'wb') as f:
                f.write(r.read())
            break
        except Exception:
            continue

if not os.path.exists(FONT_BOLD_PATH):
    for url in [
        "https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf",
        "https://raw.githubusercontent.com/fpdf2/fpdf2/master/test/fonts/DejaVuSans-Bold.ttf"
    ]:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as r, open(FONT_BOLD_PATH, 'wb') as f:
                f.write(r.read())
            break
        except Exception:
            continue

if not os.path.exists(REPORTS_DIR):
    os.makedirs(REPORTS_DIR)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, country TEXT, source TEXT,
            title TEXT, score INTEGER, summary TEXT, link TEXT,
            UNIQUE(title, date)
        )
    ''')
    try:
        cursor.execute("ALTER TABLE signals ADD COLUMN link TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


def get_ai_analysis(text):
    prompt = """
    Είσαι ένας αυστηρός Intelligence Analyst για το Υφυπουργείο Μετανάστευσης της Κυπριακής Δημοκρατίας.
    Αξιολόγησε την είδηση ΑΠΟΚΛΕΙΣΤΙΚΑ με βάση τον κίνδυνο δημιουργίας μεταναστευτικών/προσφυγικών ροών ΠΡΟΣ ΤΗΝ ΚΥΠΡΟ ή τον κίνδυνο για κυκλώματα διακίνησης που στοχεύουν Κύπρο/Ανατολική Μεσόγειο.
    ΜΗΝ χρησιμοποιείς emojis.

    SCORE 9-10 | [CYPRUS ALERT]
    - Αναχώρηση πλοιαρίων/βαρκών με προορισμό Κύπρο
    - Σύλληψη διακινητών στον άξονα Λίβανος/Συρία/Τουρκία → Κύπρο
    - Επιχείρηση ακτοφυλακής Κύπρου
    - Τουρκική παρενόχληση κυπριακών συνόρων/EEZ

    SCORE 6-8 | [BORDER INFO]
    - Εντολές εκκένωσης Νότιου Λιβάνου, βομβαρδισμοί (score 7-8)
    - Κλείσιμο συνόρων Συρία-Λίβανος ή Τουρκία-Συρία (score 6-7)
    - Μαζικοί εκτοπισμοί σε Συρία, Λίβανο (score 6)
    - Αλλαγές πολιτικής ασύλου Αίγυπτος/Τουρκία (score 6)

    SCORE 3-5 | [MACRO INFO]
    - Βομβαρδισμοί σε Ισραήλ, Ιράν, Υεμένη (score 3-4)
    - Οικονομική κρίση Λίβανος, Συρία, Τουρκία (score 3-4)
    - Ναυτιλιακά περιστατικά Ερυθρά/Ορμούζ (score 4-5)

    SCORE 1-2 | [MACRO INFO]
    - Γενική γεωπολιτική χωρίς επιχειρησιακό περιεχόμενο

    IGNORE: Αθλητικά, lifestyle, τεχνολογία, γεγονότα εκτός περιοχής.

    ΕΙΔΙΚΟΙ ΚΑΝΟΝΕΣ:
    - Αναφορά σε Κύπρο με μεταναστευτικό/επιχειρησιακό περιεχόμενο = score 7+
    - Απλή αναφορά στη λέξη "Κύπρος" χωρίς μεταναστευτικό περιεχόμενο = score <= 3
    - Γενική βία/πόλεμος χωρίς εκτοπισμό πληθυσμών = score <= 4
    - ΜΗΝ αναφέρεις "κίνδυνο για Κύπρο" στο summary αν δεν υπάρχει ρητή σύνδεση στο κείμενο

    ΜΟΡΦΗ ΑΠΑΝΤΗΣΗΣ (ΑΥΣΤΗΡΑ):
    SCORE: [ΑΡΙΘΜΟΣ] | SUMMARY: [ΕΤΙΚΕΤΑ] [Περίληψη 1-2 προτάσεις στα Ελληνικά — ΜΟΝΟ τα γεγονότα, χωρίς υποθετικές συνέπειες]
    """ + text[:2000]

    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        res_text = response.text.strip()
        if "IGNORE" in res_text or not res_text:
            return None
        return res_text
    except Exception:
        return None


def scan_rss():
    print(f"--- OSINT ENGINE START: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
    logging.info("RSS scan started")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today_str = datetime.datetime.now().date().isoformat()
    total_saved = 0

    for country, feeds in config.get("rss_feeds", {}).items():
        for feed_info in feeds:
            print(f"Ελέγχεται: {feed_info['name']}...")
            try:
                feed = feedparser.parse(feed_info['url'])
                if not getattr(feed, 'entries', None):
                    continue
                for entry in feed.entries[:5]:
                    analysis = get_ai_analysis(entry.title + " " + getattr(entry, 'description', ''))
                    if analysis and '|' in analysis:
                        try:
                            score_raw = int(analysis.split('|')[0].replace('SCORE:', '').strip())
                            summary = analysis.split('|')[1].replace('SUMMARY:', '').strip()

                            # 3.1: Score validation — αποδεκτό μόνο 1-10
                            if not (1 <= score_raw <= 10):
                                logging.warning(f"Invalid score {score_raw} from {feed_info['name']}, skipping")
                                continue

                            # 3.1: Semantic deduplication
                            if is_duplicate(summary, today_str):
                                logging.info(f"Duplicate skipped: {entry.title[:60]}")
                                continue

                            # 3.4: NER — εξαγωγή χώρας από summary αν δεν ταιριάζει
                            detected = extract_locations(summary)
                            final_country = country
                            if detected and country == 'Cross_Regional' and len(detected) == 1:
                                final_country = detected[0]

                            link = getattr(entry, 'link', '') or ''
                            cursor.execute("""
                                INSERT OR IGNORE INTO signals (date, country, source, title, score, summary, link)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                today_str,
                                final_country, feed_info['name'],
                                entry.title[:250], score_raw, summary, link[:500]
                            ))
                            if cursor.rowcount > 0:
                                total_saved += 1
                                if score_raw >= 8:
                                    logging.warning(f"CYPRUS ALERT score={score_raw}: {feed_info['name']} — {summary[:80]}")
                        except (ValueError, IndexError) as e:
                            logging.error(f"Parse error for {feed_info['name']}: {e}")
                            continue
                conn.commit()
            except socket.timeout:
                print(f"   Timeout: Προσπέραση...")
                logging.warning(f"Timeout: {feed_info['name']}")
            except Exception as e:
                logging.error(f"Feed error {feed_info['name']}: {e}")
                pass

    conn.close()
    logging.info(f"RSS scan complete: {total_saved} new signals saved")

    # 3.5: Anomaly detection
    anomaly = check_anomaly()
    if anomaly:
        print(f"⚠️  {anomaly}")


def export_csv():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT date, country, source, title, score, summary, link FROM signals ORDER BY date DESC, score DESC")
    rows = cursor.fetchall()
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Country', 'Source', 'Title', 'Risk Score', 'Summary', 'Link'])
        writer.writerows(rows)
    conn.close()
    print("Εξαγωγή CSV: Επιτυχής")


def clean_for_pdf(text):
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
                  "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩαβγδεζηθικλμνξοπρςστυφχψω"
                  "άέήίόύώΆΈΉΊΌΎΏϊϋΪΫΐΰ0123456789 .,!?:;'-()[]/%€\"'")
    cleaned = "".join(c for c in text if c in allowed)
    return " ".join(cleaned.split())


class OsintPDF(FPDF):
    def __init__(self, R, has_bold, logo_path, today_display):
        super().__init__()
        self.R = R
        self.has_bold = has_bold
        self.logo_path = logo_path
        self.today_display = today_display

    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 34, 'F')
        if os.path.exists(self.logo_path):
            self.image(self.logo_path, x=8, y=2, h=30)
        self.set_text_color(255, 255, 255)
        self.set_font(self.R, "B" if self.has_bold else "", 12)
        self.set_xy(54, 7)
        self.cell(0, 6, "OSINT MIGRATION INTELLIGENCE", ln=True)
        self.set_font(self.R, "", 8)
        self.set_xy(54, 15)
        self.cell(0, 5, "Ημερησια Αναφορα Μεταναστευτικων Ροων", ln=True)
        self.set_text_color(148, 163, 184)
        self.set_font(self.R, "", 7)
        self.set_xy(54, 22)
        self.cell(0, 5, f"Ημερομηνια: {self.today_display}", ln=True)
        self.set_fill_color(185, 28, 28)
        self.set_text_color(255, 255, 255)
        self.set_font(self.R, "B" if self.has_bold else "", 7)
        self.set_xy(140, 12)
        self.cell(62, 8, "ΠΕΡΙΟΡΙΣΜΕΝΗΣ ΚΥΚΛΟΦΟΡΙΑΣ", align='C', fill=True)
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
            f"Περιορισμενης Κυκλοφοριας | {self.today_display} | Σελιδα {self.page_no()}",
            align='R')
        self.set_text_color(0, 0, 0)


def generate_daily_pdf():
    today_str = datetime.datetime.now().date().isoformat()
    today_display = datetime.datetime.now().strftime('%d/%m/%Y')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT source, score, summary, country FROM signals WHERE date = ? ORDER BY score DESC",
        (today_str,)
    )
    rows = cursor.fetchall()
    conn.close()

    alerts  = [r for r in rows if r[1] >= 8]
    borders = [r for r in rows if 4 <= r[1] < 8]
    macros  = [r for r in rows if r[1] < 4]

    has_font = os.path.exists(FONT_PATH)
    has_bold = os.path.exists(FONT_BOLD_PATH)
    R = "DV" if has_font else "Helvetica"

    pdf = OsintPDF(R, has_bold, LOGO_PATH, today_display)
    pdf.set_auto_page_break(auto=True, margin=18)
    if has_font:
        pdf.add_font("DV", "", FONT_PATH)
    if has_bold:
        pdf.add_font("DV", "B", FONT_BOLD_PATH)
    pdf.add_page()

    # ── EXECUTIVE SUMMARY ─────────────────────────────────────
    y0 = pdf.get_y()
    pdf.set_fill_color(239, 246, 255)
    pdf.set_draw_color(147, 197, 253)
    pdf.set_line_width(0.4)
    pdf.rect(10, y0, 190, 8, 'FD')
    pdf.set_font(R, "B" if has_bold else "", 8)
    pdf.set_text_color(29, 78, 216)
    pdf.set_xy(13, y0 + 1.5)
    pdf.cell(0, 5, "ΕΚΤΕΛΕΣΤΙΚΗ ΠΕΡΙΛΗΨΗ")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(y0 + 10)
    pdf.set_font(R, "", 8)
    pdf.set_x(13)
    pdf.cell(0, 5, clean_for_pdf(
        f"Συνολικα signals: {len(rows)}   |   Cyprus Alerts (8+): {len(alerts)}"
        f"   |   Border Info (4-7): {len(borders)}   |   Macro (1-3): {len(macros)}"
    ), ln=True)
    pdf.set_x(13)
    if alerts:
        pdf.set_text_color(185, 28, 28)
        pdf.set_font(R, "B" if has_bold else "", 8)
        pdf.cell(0, 5, clean_for_pdf(
            "ΠΡΟΕΙΔΟΠΟΙΗΣΗ: Εντοπιστηκαν κρισιμες ειδησεις που απαιτουν αμεση προσοχη."
        ), ln=True)
    else:
        pdf.set_text_color(22, 101, 52)
        pdf.cell(0, 5, clean_for_pdf(
            "Καμια κρισιμη ειδηση για Κυπρο σημερα. Παρακολουθηση συνεχιζεται."
        ), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)

    # ── HELPERS ───────────────────────────────────────────────
    def section_header(title, r, g, b):
        pdf.set_fill_color(r, g, b)
        y = pdf.get_y()
        pdf.rect(10, y, 190, 8, 'F')
        pdf.set_font(R, "B" if has_bold else "", 8)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(13, y + 1.5)
        pdf.cell(0, 5, clean_for_pdf(title))
        pdf.set_text_color(0, 0, 0)
        pdf.set_y(y + 10)

    def signal_row(source, score, summary, country):
        # Score badge color
        if score >= 8:
            sr, sg, sb = 254, 226, 226
            tr, tg, tb = 153, 27, 27
        elif score >= 4:
            sr, sg, sb = 255, 251, 235
            tr, tg, tb = 120, 53, 15
        else:
            sr, sg, sb = 239, 246, 255
            tr, tg, tb = 29, 78, 216

        summary_clean = clean_for_pdf(summary or '')
        meta = clean_for_pdf(f"{country or ''} | {source or ''}")

        # Γραμμή 1: score badge + meta label
        pdf.set_fill_color(sr, sg, sb)
        pdf.set_text_color(tr, tg, tb)
        pdf.set_font(R, "B" if has_bold else "", 10)
        pdf.cell(14, 6, str(score), align='C', fill=True)
        pdf.set_text_color(107, 114, 128)
        pdf.set_font(R, "", 7)
        pdf.cell(176, 6, meta, ln=True)

        # Γραμμή 2: summary (full width, με indent)
        pdf.set_text_color(17, 24, 39)
        pdf.set_font(R, "", 8)
        pdf.set_x(10)
        pdf.multi_cell(190, 4.5, summary_clean)

        # Separator
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

    # ── CYPRUS ALERTS ─────────────────────────────────────────
    section_header("ΚΡΙΣΙΜΕΣ ΕΙΔΗΣΕΙΣ — CYPRUS ALERTS  (Score 8-10)", 185, 28, 28)
    if not alerts:
        empty_msg("Καμια κρισιμη ειδηση σημερα.")
    else:
        for r in alerts:
            signal_row(r[0], r[1], r[2], r[3])
    pdf.ln(4)

    # ── BORDER INFO ───────────────────────────────────────────
    section_header("ΠΛΗΡΟΦΟΡΙΕΣ ΣΥΝΟΡΩΝ — BORDER INFO  (Score 4-7)", 161, 98, 7)
    if not borders:
        empty_msg("Καμια ειδηση border info σημερα.")
    else:
        for r in borders:
            signal_row(r[0], r[1], r[2], r[3])
    pdf.ln(4)

    # ── MACRO INFO ────────────────────────────────────────────
    section_header("ΓΕΝΙΚΟ ΥΠΟΒΑΘΡΟ — MACRO INFO  (Score 1-3)", 37, 99, 235)
    if not macros:
        empty_msg("Καμια macro ειδηση σημερα.")
    else:
        for r in macros:
            signal_row(r[0], r[1], r[2], r[3])

    pdf_filename = os.path.join(REPORTS_DIR, f"OSINT_Report_{today_str}.pdf")
    pdf.output(pdf_filename)
    print(f"Δημιουργηθηκε το PDF: {pdf_filename}")


if __name__ == "__main__":
    init_db()
    scan_rss()
    export_csv()
    generate_daily_pdf()