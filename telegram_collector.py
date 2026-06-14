import os
import json
import sqlite3
import datetime
import asyncio
import logging
from collections import defaultdict
from telethon import TelegramClient
from telethon.tl.types import Channel, Chat, PeerChannel, PeerUser
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "migration_data.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
SESSION_PATH = os.path.join(BASE_DIR, "migration_agent_session")
DISCOVERED_PATH = os.path.join(BASE_DIR, "discovered_channels.json")

API_ID   = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE    = os.getenv("TELEGRAM_PHONE", "")

# ── 2.5: Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=os.path.join(BASE_DIR, 'migration_agent.log'),
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

# Map Telegram regions to consistent country names (matching RSS country names)
REGION_MAP = {
    "Cyprus_Direct": "Cross_Regional",
    "Lebanon_Local": "Lebanon",
    "Syria_Coast":   "Syria",
    "Turkiye":       "Turkiye",
    "OSINT_Regional":"Cross_Regional"
}


# ── 3.1: Semantic Deduplication (shared με migration_agent_full.py) ────────────
def is_duplicate_tg(new_summary, today_str):
    """Ελέγχει αν υπάρχει ήδη παρόμοιο signal σήμερα."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT summary FROM signals WHERE date = ?", (today_str,))
        existing = [r[0] for r in c.fetchall() if r[0]]
        conn.close()
        if not existing:
            return False
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
        logging.warning(f"TG deduplication check failed: {e}")
        return False


def init_db_telegram():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telegram_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            channel TEXT,
            channel_handle TEXT,
            message_id INTEGER,
            text TEXT,
            score INTEGER,
            summary TEXT,
            link TEXT,
            UNIQUE(channel_handle, message_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS discovered_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id TEXT,
            channel_title TEXT,
            channel_username TEXT,
            forward_count INTEGER DEFAULT 1,
            max_score INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            status TEXT DEFAULT "pending",
            UNIQUE(channel_id)
        )
    ''')
    conn.commit()
    conn.close()


def get_telegram_channels():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    channels = []
    for region, handles in config.get("telegram_channels", {}).items():
        for handle in handles:
            channels.append({"handle": handle, "region": region})
    return channels


def save_telegram_signal(channel_name, handle, msg_id, text, score, summary, date_str, link):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO telegram_signals
            (date, channel, channel_handle, message_id, text, score, summary, link)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_str, channel_name, handle, msg_id, text[:500], score, summary, link))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def save_to_main_signals(channel_name, score, summary, date_str, link, country="Telegram"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        title = summary[:250] if summary else channel_name
        cursor.execute("""
            INSERT OR IGNORE INTO signals (date, country, source, title, score, summary, link)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (date_str, country, channel_name, title, score, summary, link))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def save_discovered_channel(channel_id, title, username, score):
    today_str = datetime.datetime.now().date().isoformat()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Αν υπάρχει ήδη → αυξάνουμε counter και ενημερώνουμε max score
        cursor.execute("""
            INSERT INTO discovered_channels (channel_id, channel_title, channel_username, forward_count, max_score, first_seen, last_seen)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                forward_count = forward_count + 1,
                max_score = MAX(max_score, ?),
                last_seen = ?,
                channel_username = COALESCE(NULLIF(?, ''), channel_username),
                channel_title = COALESCE(NULLIF(?, ''), channel_title)
        """, (
            str(channel_id), title, username or '', score, today_str, today_str,
            score, today_str, username or '', title or ''
        ))
        conn.commit()
    except Exception as e:
        pass
    finally:
        conn.close()


def get_top_discovered():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT channel_title, channel_username, forward_count, max_score, first_seen
        FROM discovered_channels
        WHERE status = 'pending'
        ORDER BY (forward_count * max_score) DESC
        LIMIT 20
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


async def analyze_message(text, gemini_client):
    if not text or len(text.strip()) < 20:
        return None

    prompt = """
    Είσαι ένας αυστηρός Intelligence Analyst για το Υφυπουργείο Μετανάστευσης της Κυπριακής Δημοκρατίας.
    Αξιολόγησε το μήνυμα ΑΠΟΚΛΕΙΣΤΙΚΑ με βάση τον κίνδυνο δημιουργίας μεταναστευτικών/προσφυγικών ροών ΠΡΟΣ ΤΗΝ ΚΥΠΡΟ ή τον κίνδυνο για κυκλώματα διακίνησης που στοχεύουν Κύπρο/Ανατολική Μεσόγειο.
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

    ΜΟΡΦΗ ΑΠΑΝΤΗΣΗΣ (ΑΥΣΤΗΡΑ — τίποτα άλλο):
    SCORE: [ΑΡΙΘΜΟΣ] | SUMMARY: [ΕΤΙΚΕΤΑ] [Περίληψη 1-2 προτάσεις στα Ελληνικά — ΜΟΝΟ τα γεγονότα, χωρίς υποθετικές συνέπειες]

    ΜΗΝΥΜΑ: """ + text[:1500]

    try:
        response = gemini_client.models.generate_content(
            model='gemini-2.5-flash', contents=prompt
        )
        res_text = response.text.strip()
        if "IGNORE" in res_text or not res_text:
            return None
        return res_text
    except Exception:
        return None


async def collect_telegram(gemini_client):
    if not API_ID or not API_HASH or not PHONE:
        print("TELEGRAM: Λείπουν credentials στο .env")
        return

    channels = get_telegram_channels()
    if not channels:
        print("TELEGRAM: Δεν βρέθηκαν κανάλια στο config.json")
        return

    today_str = datetime.datetime.now().date().isoformat()
    cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)

    # Tracker για forward chains
    forward_tracker = defaultdict(lambda: {"count": 0, "max_score": 0, "title": "", "username": ""})

    print(f"--- TELEGRAM COLLECTOR START: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    async with TelegramClient(SESSION_PATH, API_ID, API_HASH) as client:
        await client.start(phone=PHONE)
        print(f"Συνδέθηκε ως: {(await client.get_me()).first_name}")

        for ch in channels:
            handle = ch["handle"]
            region = ch["region"]
            # Map region to country using REGION_MAP
            country = REGION_MAP.get(region, region)
            print(f"Ελέγχεται: @{handle} ({region} → {country})...")

            try:
                entity = await client.get_entity(handle)
                channel_name = getattr(entity, 'title', handle)

                count = 0
                channel_high_score_count = 0  # deduplication counter per channel/day

                async for message in client.iter_messages(entity, limit=30):
                    if not message.text:
                        continue
                    if message.date.replace(tzinfo=None) < cutoff:
                        break

                    # ── FORWARD CHAIN TRACKING ──────────────────
                    if message.forward:
                        fwd = message.forward
                        fwd_id = None
                        fwd_title = ""
                        fwd_username = ""

                        try:
                            if hasattr(fwd, 'chat') and fwd.chat:
                                fwd_id = fwd.chat.id
                                fwd_title = getattr(fwd.chat, 'title', '')
                                fwd_username = getattr(fwd.chat, 'username', '') or ''
                            elif hasattr(fwd, 'from_id') and fwd.from_id:
                                fwd_id = getattr(fwd.from_id, 'channel_id', None) or \
                                         getattr(fwd.from_id, 'user_id', None)
                        except Exception:
                            pass

                        if fwd_id:
                            # Αποθηκεύουμε προσωρινά — score θα ενημερωθεί μετά την ανάλυση
                            forward_tracker[fwd_id]["count"] += 1
                            forward_tracker[fwd_id]["title"] = fwd_title
                            forward_tracker[fwd_id]["username"] = fwd_username

                    # ── AI ANALYSIS ─────────────────────────────
                    analysis = await analyze_message(message.text, gemini_client)
                    if not analysis or '|' not in analysis:
                        continue

                    try:
                        score = int(analysis.split('|')[0].replace('SCORE:', '').strip())
                        summary = analysis.split('|')[1].replace('SUMMARY:', '').strip()
                        msg_link = f"https://t.me/{handle}/{message.id}"

                        # 3.1: Score validation
                        if not (1 <= score <= 10):
                            logging.warning(f"TG invalid score {score} from @{handle}, skipping")
                            continue

                        # 3.1: Semantic deduplication
                        if score >= 4 and is_duplicate_tg(summary, today_str):
                            logging.info(f"TG duplicate skipped from @{handle}")
                            continue

                        # Ενημέρωση forward tracker με score
                        if message.forward and fwd_id:
                            forward_tracker[fwd_id]["max_score"] = max(
                                forward_tracker[fwd_id]["max_score"], score
                            )

                        save_telegram_signal(
                            channel_name, handle, message.id,
                            message.text, score, summary, today_str, msg_link
                        )

                        if score >= 3:
                            # Deduplication: score>=6 μέγιστο 3 ανά κανάλι/ημέρα
                            if score >= 6:
                                if channel_high_score_count >= 3:
                                    continue
                                channel_high_score_count += 1

                            save_to_main_signals(
                                f"TG: {channel_name}", score, summary, today_str, msg_link, country
                            )
                            count += 1

                            if score >= 8:
                                logging.warning(f"TG CYPRUS ALERT score={score}: @{handle} — {summary[:80]}")

                    except (ValueError, IndexError) as e:
                        logging.error(f"TG parse error @{handle}: {e}")
                        continue

                if count > 0:
                    print(f"   Βρέθηκαν {count} signals")

            except Exception as e:
                print(f"   Σφάλμα για @{handle}: {e}")
                continue

        # ── ΑΠΟΘΗΚΕΥΣΗ DISCOVERED CHANNELS ──────────────────────
        print("\n--- FORWARD CHAIN ANALYSIS ---")
        known_handles = {ch["handle"].lower() for ch in channels}

        new_discoveries = 0
        for ch_id, info in forward_tracker.items():
            username = info["username"].lower()
            # Αγνόησε γνωστά κανάλια
            if username and username in known_handles:
                continue
            save_discovered_channel(ch_id, info["title"], info["username"], info["max_score"])
            new_discoveries += 1

        print(f"Νέες πηγές που εντοπίστηκαν μέσω forwards: {new_discoveries}")

    # ── ΕΚΤΥΠΩΣΗ TOP ΠΡΟΤΑΣΕΩΝ ───────────────────────────────
    top = get_top_discovered()
    if top:
        print("\n╔══════════════════════════════════════════════════════════╗")
        print("║         ΠΡΟΤΕΙΝΟΜΕΝΑ ΝΕΑ ΚΑΝΑΛΙΑ (via Forward Chain)    ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"{'Τίτλος':<30} {'Username':<20} {'Forwards':<10} {'Max Score'}")
        print("─" * 62)
        for row in top:
            title, username, fwd_count, max_score, first_seen = row
            uname = f"@{username}" if username else "—"
            print(f"{str(title)[:28]:<30} {uname:<20} {fwd_count:<10} {max_score}")
        print("╚══════════════════════════════════════════════════════════╝")
        print("\nΓια να προσθέσεις κανάλι: πρόσθεσε το username στο config.json")

    print("\n--- TELEGRAM COLLECTOR COMPLETE ---")


def run_telegram_collector(gemini_client):
    asyncio.run(collect_telegram(gemini_client))


if __name__ == "__main__":
    import google.generativeai as genai
    load_dotenv()
    gc = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    init_db_telegram()
    asyncio.run(collect_telegram(gc))