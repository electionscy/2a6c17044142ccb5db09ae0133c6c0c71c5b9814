"""
Φάση Γ — Migration Pressure Index & 7-day Forecast (v2 — baseline-anchored)

Λογική: Ο δείκτης είναι αγκυρωμένος στην ΠΡΑΓΜΑΤΙΚΗ τάση αφίξεων προς Κύπρο,
όχι στην ένταση ειδήσεων. Conflict/καιρός είναι modifiers, όχι κύρια συνιστώσα.
Gating: χωρίς ένδειξη πραγματικών ροών, ο δείκτης καπάρεται σε LOW.

Σημεία αναφοράς (UNHCR/EUAA/MMC):
  2022 ~21.500 αιτήσεις (peak) | 2023: 10.662 | 2024: 6.800 (-44%)
  2025 Ιαν-Ιουλ: 1.414 (-70% vs 2024) → ~200/μήνα
  Baseline (index=50) = ρυθμός 2024 (~565/μήνα)
"""
import sqlite3
import pandas as pd
import numpy as np
import json
import requests
from datetime import datetime, timedelta
try:
    from zoneinfo import ZoneInfo
    CY_TZ = ZoneInfo("Asia/Nicosia")
except ImportError:
    import pytz
    CY_TZ = pytz.timezone("Asia/Nicosia")

def now_cy():
    return datetime.now(CY_TZ)

DB_PATH = "/home/agent/migration_agent/migration_data.db"
OUTPUT_PATH = "/home/agent/migration_agent/pressure_index.json"

# ── Σημεία αναφοράς αφίξεων (μηνιαίος ρυθμός) ──
BASELINE_2024_MONTHLY = 565      # index ~50 (κανονικότητα 2024)
CURRENT_2025_MONTHLY  = 200      # τρέχων ρυθμός (-70%)
PEAK_2022_MONTHLY     = 1800     # index ~95 (κρίση 2022)

def arrivals_anchor():
    """
    Βασικός δείκτης (0-100) από την πραγματική τάση αφίξεων.
    Χρησιμοποιεί UNHCR live data + γνωστή πτωτική τάση.
    Αυτός είναι ο ΚΥΡΙΑΡΧΟΣ παράγοντας (anchor).
    """
    try:
        url = "https://api.unhcr.org/population/v1/asylum-applications/"
        params = {"yearFrom": 2024, "yearTo": 2026, "coa": "CYP",
                  "coo_all": "true", "limit": 500}
        r = requests.get(url, params=params, timeout=12)
        if r.status_code == 200:
            items = r.json().get("items", [])
            by_year = {}
            for i in items:
                yr = i.get("year")
                by_year[yr] = by_year.get(yr, 0) + int(i.get("applied", 0) or 0)
            # Προτίμηση πιο πρόσφατου έτους. Αν είναι τρέχον (μερικό), annualize
            latest_yr = max(by_year.keys()) if by_year else 2025
            latest_annual = by_year.get(latest_yr, 2400)
            cur_year = now_cy().year
            if latest_yr >= cur_year:
                # Μερικό έτος — annualize βάσει μήνα
                months_elapsed = max(1, now_cy().month)
                latest_monthly = latest_annual / months_elapsed
            else:
                latest_monthly = latest_annual / 12
            # Αν το τελευταίο πλήρες έτος είναι >1 χρόνο πίσω, εφάρμοσε
            # τη γνωστή πτωτική τάση (-70% το 2025)
            # Αν το πιο πρόσφατο δεδομένο είναι το προηγούμενο έτος ή παλιότερο,
            # τα φετινά στοιχεία δεν είναι ακόμα στο API. Εφάρμοσε τη γνωστή
            # πτωτική τάση (MMC/EUAA: 2025 -70% vs 2024) για ρεαλιστικό ρυθμό.
            if latest_yr <= cur_year - 1:
                latest_monthly = CURRENT_2025_MONTHLY
        else:
            latest_monthly = CURRENT_2025_MONTHLY
    except Exception:
        latest_monthly = CURRENT_2025_MONTHLY

    # Λογαριθμική κλίμακα: current/baseline → index
    # ρυθμός = baseline (565) → 50, peak (1800) → 95, ~0 → 5
    ratio = latest_monthly / BASELINE_2024_MONTHLY
    if ratio <= 0:
        anchor = 5
    else:
        # Καλιμπραρισμένο: ratio 0.35→25, 1.0→50, 3.2→90
        # Ηπιότερη λογαριθμική κλίση (×18 αντί ×32) + offset
        anchor = 50 + 21 * np.log2(max(0.05, ratio))
    return float(np.clip(anchor, 8, 95)), latest_monthly

def load_signal_history():
    """Ιστορικά signals — ΜΟΝΟ ως modifier, όχι anchor."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("""
        SELECT date,
               COUNT(*) as signals,
               AVG(score) as avg_score,
               SUM(CASE WHEN score >= 8 THEN 1 ELSE 0 END) as high_alerts
        FROM signals
        WHERE date >= date('now', '-30 days')
        GROUP BY date ORDER BY date ASC
    """, conn)
    conn.close()
    df['date'] = pd.to_datetime(df['date'])
    return df

def flow_signal_gate(df):
    """
    GATING: Ψάχνει signals που αναφέρουν ΠΡΑΓΜΑΤΙΚΕΣ ροές προς Κύπρο
    (όχι γενικό conflict). Χωρίς τέτοια, ο δείκτης καπάρεται.
    Επιστρέφει multiplier 0.5-1.3.
    """
    conn = sqlite3.connect(DB_PATH)
    # Ψάχνει keywords ροών προς Κύπρο στα summaries των τελευταίων 14 ημερών
    flow_kw = pd.read_sql("""
        SELECT COUNT(*) as n FROM signals
        WHERE date >= date('now', '-14 days')
        AND (
            lower(summary) LIKE '%boat%cyprus%' OR
            lower(summary) LIKE '%cyprus%arriv%' OR
            lower(summary) LIKE '%αφίξ%κύπρο%' OR
            lower(summary) LIKE '%βάρκα%κύπρο%' OR
            lower(summary) LIKE '%μετανάστ%κύπρο%' OR
            lower(summary) LIKE '%πουρνάρα%' OR
            lower(summary) LIKE '%pournara%' OR
            (lower(summary) LIKE '%cyprus%' AND lower(summary) LIKE '%migrant%')
        )
    """, conn)
    conn.close()
    flow_mentions = int(flow_kw['n'].iloc[0])
    # 0 αναφορές → 0.5 (καπάρει), 5+ → 1.3 (ενισχύει)
    if flow_mentions == 0:
        return 0.5, flow_mentions
    elif flow_mentions <= 2:
        return 0.8, flow_mentions
    elif flow_mentions <= 5:
        return 1.0, flow_mentions
    else:
        return 1.3, flow_mentions

def transit_staging_gate():
    """
    EARLY WARNING: Πιάνει upstream signals — κινητικότητα/συγκεντρώσεις σε
    χώρες & λιμάνια διέλευσης (Τουρκία, Λίβανος, Συρία) που προηγούνται
    αφίξεων στην Κύπρο. Lagged predictor (Nature/EUAA methodology).

    Διαφορά από flow_signal_gate: αυτό πιάνει ΠΡΟΘΕΣΗ/ΠΡΟΕΤΟΙΜΑΣΙΑ, όχι άφιξη.
    Επιστρέφει early-warning bump (0-22) + αριθμό αναφορών.
    """
    conn = sqlite3.connect(DB_PATH)
    transit = pd.read_sql("""
        SELECT COUNT(*) as n FROM signals
        WHERE date >= date('now', '-14 days')
        AND (
            -- Λιμάνια/ακτές εκκίνησης προς Κύπρο
            lower(summary) LIKE '%mersin%' OR
            lower(summary) LIKE '%μερσίν%' OR
            lower(summary) LIKE '%latakia%' OR
            lower(summary) LIKE '%λατάκ%' OR
            lower(summary) LIKE '%tartus%' OR
            lower(summary) LIKE '%tripoli%lebanon%' OR
            lower(summary) LIKE '%τρίπολ%λίβαν%' OR
            -- Προετοιμασία/πρόθεση διέλευσης προς Ευρώπη
            (lower(summary) LIKE '%smuggl%' AND (lower(summary) LIKE '%syria%' OR lower(summary) LIKE '%lebanon%' OR lower(summary) LIKE '%turkey%' OR lower(summary) LIKE '%turkiye%')) OR
            (lower(summary) LIKE '%boat%' AND lower(summary) LIKE '%depart%') OR
            (lower(summary) LIKE '%europe-bound%') OR
            (lower(summary) LIKE '%ready%cross%') OR
            (lower(summary) LIKE '%gather%coast%') OR
            -- Μετακινήσεις Σύρων/προσφύγων προς χώρες διέλευσης
            (lower(summary) LIKE '%syrian%' AND lower(summary) LIKE '%move%' AND (lower(summary) LIKE '%coast%' OR lower(summary) LIKE '%turkey%' OR lower(summary) LIKE '%lebanon%')) OR
            (lower(summary) LIKE '%σύριοι%' AND (lower(summary) LIKE '%ακτ%' OR lower(summary) LIKE '%παράλια%' OR lower(summary) LIKE '%ευρώπη%')) OR
            (lower(summary) LIKE '%πρόσφυγ%' AND lower(summary) LIKE '%ευρώπη%')
        )
    """, conn)
    conn.close()
    n = int(transit['n'].iloc[0])
    # Early-warning bump: κάθε transit signal δίνει μικρή ώθηση, με ανώτατο
    if n == 0:
        return 0.0, 0
    elif n <= 2:
        return 6.0, n      # ασθενές σήμα
    elif n <= 5:
        return 12.0, n     # μέτριο σήμα
    elif n <= 10:
        return 18.0, n     # ισχυρό σήμα
    else:
        return 22.0, n     # έντονη upstream κινητικότητα

def conflict_modifier(df):
    """Conflict intensity ως ΜΙΚΡΟΣ modifier (±8 max)."""
    if df.empty:
        return 0
    last7 = df[df['date'] >= df['date'].max() - timedelta(days=7)]
    high = last7['high_alerts'].sum() if not last7.empty else 0
    # Πολλά high alerts → μικρή ανοδική ώθηση (lagged pressure)
    return float(np.clip(high * 0.8, 0, 8))

def get_sea_forecast():
    try:
        url = ("https://marine-api.open-meteo.com/v1/marine"
               "?latitude=34.97&longitude=34.08"
               "&daily=wave_height_max&forecast_days=7")
        r = requests.get(url, timeout=8)
        return r.json().get('daily', {}).get('wave_height_max', [0.5]*7)
    except Exception:
        return [0.5]*7

def seasonal_modifier(date):
    """Εποχικότητα ως ΜΙΚΡΟΣ modifier (±6)."""
    m = date.month
    summer = {5:2, 6:4, 7:6, 8:6, 9:3}  # ώθηση καλοκαίρι
    winter = {11:-3, 12:-5, 1:-5, 2:-4} # μείωση χειμώνα
    return summer.get(m, 0) + winter.get(m, 0)

def sea_modifier(wave_h):
    """Καιρός ως ΜΙΚΡΟΣ modifier (±5). Ήρεμη=+, τρικυμία=-."""
    if wave_h < 0.5:   return 5
    if wave_h < 1.25:  return 2
    if wave_h < 2.5:   return -2
    return -5

def generate_forecast():
    df = load_signal_history()
    sea = get_sea_forecast()
    anchor, latest_monthly = arrivals_anchor()
    gate, flow_mentions = flow_signal_gate(df)
    transit_bump, transit_mentions = transit_staging_gate()
    conflict_mod = conflict_modifier(df)

    today = now_cy().date()
    forecast = []

    for i in range(7):
        target = today + timedelta(days=i)
        wave_h = sea[i] if i < len(sea) else 0.5

        # ── Σύνθεση δείκτη ──
        # Βάση = anchor (πραγματικές αφίξεις) × gate (ύπαρξη ροών Κύπρου)
        base = anchor * gate
        # Conflict/seasonal/sea × gate (χωρίς ροές, ο πόλεμος δεν φουσκώνει)
        modifiers = (conflict_mod + seasonal_modifier(target) + sea_modifier(wave_h))
        base += modifiers * gate
        # EARLY WARNING: transit/staging signals προστίθενται ΑΝΕΞΑΡΤΗΤΑ.
        # Αυτά είναι lagged predictors — upstream κινητικότητα πριν τις αφίξεις.
        # Φθίνει με τον χρόνο πρόβλεψης (πιο αβέβαιο όσο πάμε μπροστά).
        base += transit_bump * max(0.6, 1.0 - i * 0.05)

        index = float(np.clip(base, 0, 100))
        confidence = max(0.4, 1.0 - i * 0.09)

        if index >= 65:
            risk, color = "HIGH", "#dc2626"
        elif index >= 40:
            risk, color = "MODERATE", "#d97706"
        elif index >= 20:
            risk, color = "LOW", "#16a34a"
        else:
            risk, color = "MINIMAL", "#0891b2"

        forecast.append({
            "date": target.strftime("%Y-%m-%d"),
            "day": ["Κυρ","Δευ","Τρι","Τετ","Πεμ","Παρ","Σαβ"][target.weekday()],
            "index": round(index, 1),
            "risk": risk,
            "risk_color": color,
            "confidence": round(confidence, 2),
            "wave_height": round(wave_h, 2),
        })

    output = {
        "generated_at": now_cy().strftime("%Y-%m-%d %H:%M"),
        "today_index": forecast[0]["index"],
        "today_risk": forecast[0]["risk"],
        "today_risk_color": forecast[0]["risk_color"],
        "forecast": forecast,
        "components": {
            "arrivals_anchor": round(anchor, 1),
            "flow_gate": gate,
            "flow_mentions_14d": flow_mentions,
            "transit_bump": round(transit_bump, 1),
            "transit_mentions_14d": transit_mentions,
            "conflict_modifier": round(conflict_mod, 1),
            "latest_monthly_rate": round(latest_monthly, 0),
            "baseline_monthly": BASELINE_2024_MONTHLY,
        },
        "interpretation": _interpret(forecast[0]["index"], flow_mentions, latest_monthly, transit_mentions)
    }

    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Pressure Index v2: {output['today_index']} ({output['today_risk']})")
    print(f"   Anchor (αφίξεις): {anchor:.1f} | Gate (ροές): {gate} | Conflict: +{conflict_mod:.1f}")
    print(f"   Ρυθμός: ~{latest_monthly:.0f}/μήνα vs baseline {BASELINE_2024_MONTHLY}/μήνα")
    print(f"   Αναφορές άμεσων ροών (14δ): {flow_mentions}")
    print(f"   Transit/staging signals (14δ): {transit_mentions} → bump +{transit_bump:.0f}")
    print(f"\n   7-day forecast:")
    for d in forecast:
        bar = "█" * int(d['index'] / 10)
        print(f"   {d['day']} {d['date']} | {bar:<10} {d['index']:5.1f} | {d['risk']}")
    return output

def _interpret(index, flow_mentions, monthly, transit_mentions=0):
    transit_note = ""
    if transit_mentions > 0:
        transit_note = (f" ⚠️ Early warning: {transit_mentions} αναφορές upstream "
                        f"κινητικότητας σε χώρες/λιμάνια διέλευσης (Τουρκία/Λίβανος/Συρία).")
    if index < 20:
        return (f"Ελάχιστη πίεση. Οι αφίξεις (~{monthly:.0f}/μήνα) παραμένουν δραματικά "
                f"μειωμένες έναντι του baseline 2024. {flow_mentions} αναφορές άμεσων ροών το 14ήμερο.{transit_note}")
    elif index < 40:
        return (f"Χαμηλή πίεση. Ρυθμός ~{monthly:.0f}/μήνα. Παρακολούθηση χωρίς ανησυχία.{transit_note}")
    elif index < 65:
        return (f"Μέτρια πίεση. Ενδείξεις αύξησης ({flow_mentions} άμεσες, {transit_mentions} upstream αναφορές).{transit_note}")
    else:
        return (f"Υψηλή πίεση. Σημαντική αύξηση δραστηριότητας — απαιτείται επαγρύπνηση.{transit_note}")

if __name__ == "__main__":
    generate_forecast()
