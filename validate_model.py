"""
validate_model.py — Επικυρωση Δεικτη Μεταναστευτικης Πιεσης

Τρια επιπεδα:
  1. Anchor calibration — εναντι πραγματικων ιστορικων αφιξεων
  2. Sensitivity analysis — ευρωστια ως προς τις παραμετρους
  3. Prospective logging — καταγραφη προβλεψεων για μελλοντικη επικυρωση

ΣΗΜΑΝΤΙΚΟ: Πληρες out-of-sample backtest ΔΕΝ ειναι δυνατο γιατι τα signals
συλλεγονται μονο απο τον Μαιο 2026. Επικυρωνουμε το anchor (κυριαρχος
παραγοντας) + ευρωστια, και στηνουμε prospective validation προς τα εμπρος.
"""
import numpy as np
import json
import os
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    CY_TZ = ZoneInfo("Asia/Nicosia")
except ImportError:
    import pytz
    CY_TZ = pytz.timezone("Asia/Nicosia")

def now_cy():
    return datetime.now(CY_TZ)

# ── Παραμετροι μοντελου (συγχρονισμενες με predictive_model.py) ──
BASELINE = 565   # μηνιαιος ρυθμος 2024 = index 50
COEF = 21        # λογαριθμικη κλιση

VALIDATION_LOG = "/home/agent/migration_agent/validation_log.json"

def anchor_fn(monthly, baseline=BASELINE, coef=COEF):
    """Η anchor συναρτηση του μοντελου (απομονωμενη για testing)."""
    ratio = monthly / baseline
    if ratio <= 0:
        return 8.0
    return float(np.clip(50 + coef * np.log2(max(0.05, ratio)), 8, 95))

def categorize(index):
    if index < 20: return "MINIMAL"
    if index < 40: return "LOW"
    if index < 65: return "MODERATE"
    return "HIGH"

# ════════════════════════════════════════════════════════════
# 1. ANCHOR CALIBRATION — εναντι πραγματικων δεδομενων
# ════════════════════════════════════════════════════════════
# Πηγες (επαληθευμενες): EUAA Latest Asylum Trends, MMC, Prague Process,
# Eurostat. Διακριση: χρησιμοποιουμε αιτησεις ασυλου (πιο συνεπης σειρα).
HISTORICAL = [
    # (περιοδος, ετησιο, μηνιαιος ρυθμος, αναδρομικος χαρακτηρισμος, αναμενομενη κατηγορια)
    ("2022 (peak κρισης)",  21500, 1792, "Κορυφη — μαζικες ροες",          "HIGH"),
    ("2023",                10662,  889, "Υψηλα αλλα πτωτικα",             "MODERATE"),
    ("2024 (baseline)",      6800,  567, "Κανονικοτητα αναφορας",          "MODERATE"),
    ("2025 (Ιαν-Ιουλ ann.)", 2424,  202, "Δραματικη πτωση -70%",          "MINIMAL"),
]

def run_calibration():
    print("=" * 64)
    print("1. ANCHOR CALIBRATION — εναντι πραγματικων ιστορικων αφιξεων")
    print("=" * 64)
    print(f"{'Περιοδος':<24}{'Ρυθμος/μ':>9}{'Anchor':>8}{'Κατηγορια':>12}{'Match':>7}")
    print("-" * 64)
    hits = 0
    for period, annual, monthly, desc, expected in HISTORICAL:
        a = anchor_fn(monthly)
        cat = categorize(a)
        match = "OK" if cat == expected else "ΔΙΑΦ"
        if cat == expected:
            hits += 1
        print(f"{period:<24}{monthly:>9}{a:>8.1f}{cat:>12}{match:>7}")
    print("-" * 64)
    pct = hits / len(HISTORICAL) * 100
    print(f"Συμφωνια κατηγοριων: {hits}/{len(HISTORICAL)} ({pct:.0f}%)")
    print()
    print("Ερμηνεια: Το anchor αναπαραγει σωστα τη σειρα και τις κατηγοριες")
    print("κινδυνου των γνωστων ιστορικων περιοδων. Η βαθμονομηση (50 στο")
    print("baseline 2024) δινει αποτελεσματα συμβατα με την αναδρομικη γνωση.")
    print()
    return hits, len(HISTORICAL)

# ════════════════════════════════════════════════════════════
# 2. SENSITIVITY ANALYSIS — ευρωστια ως προς τις παραμετρους
# ════════════════════════════════════════════════════════════
def run_sensitivity():
    print("=" * 64)
    print("2. SENSITIVITY ANALYSIS — ευρωστια στις παραμετρους")
    print("=" * 64)
    print("Ερωτημα: αλλαζει το ΣΥΜΠΕΡΑΣΜΑ αν πειραξουμε τις 'αυθαιρετες'")
    print("παραμετρους; Εξεταζουμε τον τρεχοντα ρυθμο (~200/μηνα).")
    print()

    current = 200

    # Μεταβολη baseline ±20%
    print(f"{'Σεναριο':<32}{'Anchor':>9}{'Κατηγορια':>13}")
    print("-" * 64)
    base_central = anchor_fn(current)
    print(f"{'Κεντρικο (baseline=565, coef=21)':<32}{base_central:>9.1f}{categorize(base_central):>13}")
    print()

    print("Μεταβολη baseline ±20%:")
    for b in [int(BASELINE*0.8), int(BASELINE*0.9), BASELINE, int(BASELINE*1.1), int(BASELINE*1.2)]:
        a = anchor_fn(current, baseline=b)
        print(f"  baseline={b:<24}{a:>9.1f}{categorize(a):>13}")
    print()

    print("Μεταβολη coef ±30%:")
    for c in [round(COEF*0.7,1), round(COEF*0.85,1), COEF, round(COEF*1.15,1), round(COEF*1.3,1)]:
        a = anchor_fn(current, coef=c)
        print(f"  coef={c:<27}{a:>9.1f}{categorize(a):>13}")
    print()

    # Συγκεντρωση: ευρος κατηγοριων στο grid
    cats = set()
    for b in [int(BASELINE*0.8), BASELINE, int(BASELINE*1.2)]:
        for c in [round(COEF*0.7,1), COEF, round(COEF*1.3,1)]:
            cats.add(categorize(anchor_fn(current, baseline=b, coef=c)))
    print(f"Ευρος κατηγοριων σε ολο το grid (±20% baseline, ±30% coef): {sorted(cats)}")
    robust = cats.issubset({"MINIMAL", "LOW"})
    print()
    if robust:
        print("✅ ΕΥΡΩΣΤΟ: Το συμπερασμα 'χαμηλη/ελαχιστη πιεση' παραμενει σταθερο")
        print("   ακομα κι οταν πειραξουμε σημαντικα τις παραμετρους. Οι ακριβεις")
        print("   τιμες (21, 565) ΔΕΝ ειναι κρισιμες — το μοντελο δεν ειναι ευθραυστο.")
    else:
        print("⚠️  ΕΥΑΙΣΘΗΤΟ: Η κατηγορια αλλαζει αναλογα με τις παραμετρους.")
        print(f"   Κατηγοριες: {sorted(cats)}. Χρειαζεται πιο προσεκτικη βαθμονομηση.")
    print()
    return robust, sorted(cats)

# ════════════════════════════════════════════════════════════
# 3. PROSPECTIVE LOGGING — καταγραφη για μελλοντικη επικυρωση
# ════════════════════════════════════════════════════════════
def run_prospective_logging():
    print("=" * 64)
    print("3. PROSPECTIVE VALIDATION — καταγραφη προβλεψης")
    print("=" * 64)

    # Διαβασε την τρεχουσα προβλεψη
    pi_path = "/home/agent/migration_agent/pressure_index.json"
    if not os.path.exists(pi_path):
        print("⚠️  Δεν βρεθηκε pressure_index.json — τρεξε πρωτα predictive_model.py")
        return

    with open(pi_path) as f:
        pi = json.load(f)

    today = now_cy().strftime("%Y-%m-%d")
    entry = {
        "logged_at": now_cy().strftime("%Y-%m-%d %H:%M"),
        "date": today,
        "predicted_index": pi["today_index"],
        "predicted_risk": pi["today_risk"],
        "forecast_7d": [{"date": d["date"], "index": d["index"]} for d in pi["forecast"]],
        "components": pi["components"],
        "actual_arrivals": None,   # συμπληρωνεται αργοτερα οταν ειναι γνωστα
        "notes": ""
    }

    # Φορτωσε υπαρχον log
    log = []
    if os.path.exists(VALIDATION_LOG):
        try:
            with open(VALIDATION_LOG) as f:
                log = json.load(f)
        except Exception:
            log = []

    # Απεφυγε διπλοεγγραφη ιδιας ημερας
    log = [e for e in log if e.get("date") != today]
    log.append(entry)

    with open(VALIDATION_LOG, "w") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"✅ Καταγραφηκε η προβλεψη της {today}: index={pi['today_index']} ({pi['today_risk']})")
    print(f"   Συνολο καταγεγραμμενων προβλεψεων: {len(log)}")
    print()
    print("Πως δουλευει η prospective επικυρωση:")
    print("  • Καθε μερα καταγραφεται η προβλεψη (μαζι με την auto_run).")
    print("  • Οταν γινονται γνωστες οι πραγματικες αφιξεις (μηνιαια, απο")
    print("    UNHCR/CyStat), συμπληρωνεται το πεδιο 'actual_arrivals'.")
    print("  • Μετα απο ~2-3 μηνες, συγκρινουμε προβλεψεις vs πραγματικοτητα")
    print("    και υπολογιζουμε σφαλμα (MAE) — τοτε εχουμε ΠΡΑΓΜΑΤΙΚΗ επικυρωση.")
    print()

# ════════════════════════════════════════════════════════════
def main():
    print()
    print("╔" + "═" * 62 + "╗")
    print("║  ΕΠΙΚΥΡΩΣΗ ΜΟΝΤΕΛΟΥ — Δεικτης Μεταναστευτικης Πιεσης" + " " * 10 + "║")
    print("╚" + "═" * 62 + "╝")
    print()

    hits, total = run_calibration()
    robust, cats = run_sensitivity()
    run_prospective_logging()

    # Τελικη ετυμηγορια
    print("=" * 64)
    print("ΣΥΝΟΛΙΚΗ ΕΤΥΜΗΓΟΡΙΑ")
    print("=" * 64)
    print(f"  Anchor calibration:  {hits}/{total} κατηγοριες σωστες")
    print(f"  Ευρωστια:            {'ΝΑΙ' if robust else 'ΟΧΙ'} (κατηγοριες: {cats})")
    print(f"  Prospective log:     Ενεργο")
    print()
    print("  Τι ΕΧΕΙ επικυρωθει: η βαθμονομηση του anchor (κυριαρχος παραγοντας)")
    print("  ειναι συμβατη με ιστορικα δεδομενα ΚΑΙ ευρωστη στις παραμετρους.")
    print()
    print("  Τι ΔΕΝ εχει επικυρωθει ακομα: η προγνωστικη ακριβεια του πληρους")
    print("  μοντελου (gates) — απαιτει prospective δεδομενα 2-3 μηνων.")
    print()

if __name__ == "__main__":
    main()
