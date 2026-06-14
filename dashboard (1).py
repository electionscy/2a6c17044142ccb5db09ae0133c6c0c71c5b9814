import streamlit as st
import pandas as pd
import os
import json
import logging
import sqlite3
import requests
from datetime import datetime, date, timedelta
import plotly.graph_objects as go

# ── 2.5: Logging System ──────────────────────────────────────────────────────
logging.basicConfig(
    filename='dashboard.log',
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)

st.set_page_config(
    page_title="Migration Intelligence — Cyprus",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: #f8f9fb !important;
    color: #1a1d23;
    font-family: 'Inter', sans-serif;
}
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e5e7eb;
}
[data-testid="stSidebar"] * { font-size: 13px; }

.top-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 0 20px 0;
    border-bottom: 1px solid #e5e7eb;
    margin-bottom: 24px;
}
.top-title { font-size: 15px; font-weight: 600; color: #111827; letter-spacing: -0.2px; }
.top-sub { font-size: 12px; color: #6b7280; margin-top: 2px; }
.top-right { text-align: right; }
.status-pill {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 11px; font-weight: 500; color: #15803d;
    background: #f0fdf4; border: 1px solid #bbf7d0;
    padding: 3px 10px; border-radius: 20px;
}
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #16a34a; }
.scan-info { font-size: 11px; color: #9ca3af; margin-top: 4px; font-family: 'JetBrains Mono', monospace; }

.kpi-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 24px; }
.kpi {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 16px 18px;
}
.kpi-label { font-size: 11px; font-weight: 500; color: #6b7280; letter-spacing: 0.3px; margin-bottom: 8px; text-transform: uppercase; }
.kpi-value { font-size: 30px; font-weight: 600; line-height: 1; color: #111827; }
.kpi-value.danger { color: #dc2626; }
.kpi-value.warning { color: #d97706; }
.kpi-value.info { color: #2563eb; }
.kpi-value.success { color: #16a34a; }
.kpi-delta { font-size: 11px; color: #9ca3af; margin-top: 5px; font-family: 'JetBrains Mono', monospace; }

.section-label {
    font-size: 11px; font-weight: 600; color: #6b7280;
    letter-spacing: 0.8px; text-transform: uppercase;
    margin-bottom: 12px; margin-top: 8px;
    padding-bottom: 8px; border-bottom: 1px solid #e5e7eb;
}

.alert-card {
    background: #fff;
    border: 1px solid #fca5a5;
    border-left: 3px solid #dc2626;
    border-radius: 6px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.alert-card-header {
    display: flex; align-items: center; gap: 8px;
    margin-bottom: 6px;
}
.score-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; font-weight: 500;
    padding: 2px 8px; border-radius: 4px;
    min-width: 32px; text-align: center;
}
.badge-danger { background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; }
.badge-warning { background: #fffbeb; color: #92400e; border: 1px solid #fcd34d; }
.badge-neutral { background: #f9fafb; color: #374151; border: 1px solid #e5e7eb; }
.alert-source { font-size: 11px; font-weight: 500; color: #6b7280; }
.alert-summary { font-size: 13px; color: #1f2937; line-height: 1.5; margin-bottom: 4px; }
.alert-link a {
    font-size: 11px; color: #2563eb; text-decoration: none;
    font-family: 'JetBrains Mono', monospace;
}
.alert-link a:hover { text-decoration: underline; }
.alert-meta { font-size: 11px; color: #9ca3af; margin-top: 4px; }

.signal-row {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 6px;
    display: flex; gap: 12px; align-items: flex-start;
}
.signal-body { flex: 1; min-width: 0; }
.signal-title { font-size: 12px; color: #1f2937; line-height: 1.45; margin-bottom: 3px; }
.signal-meta { font-size: 11px; color: #9ca3af; }
.signal-link a { font-size: 11px; color: #2563eb; text-decoration: none; font-family: 'JetBrains Mono', monospace; }
.signal-link a:hover { text-decoration: underline; }

.tag {
    display: inline-block; font-size: 10px;
    background: #f3f4f6; color: #374151;
    border: 1px solid #e5e7eb;
    padding: 1px 6px; border-radius: 3px;
    margin-right: 4px;
}

.empty-state {
    text-align: center; padding: 32px;
    background: #fff; border: 1px solid #e5e7eb;
    border-radius: 8px; color: #6b7280; font-size: 13px;
}

/* Sidebar: ευανάγνωστες ετικέτες & captions (όχι τα colored pills) */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] *,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
    color: #1a1d23 !important;
    font-weight: 600;
}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] * {
    color: #4b5563 !important;
    font-weight: 400;
}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=300)
def load_data():
    # 2.1: Direct DB read — πάντα fresh data, CSV ως fallback
    db_path = "migration_data.db"
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            df = pd.read_sql_query("""
                SELECT source   AS Source,
                       score    AS "Risk Score",
                       summary  AS Summary,
                       date     AS Date,
                       link     AS Link,
                       country  AS Country
                FROM signals
                ORDER BY date DESC, score DESC
            """, conn)
            conn.close()
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            df['Link'] = df['Link'].fillna('')
            logging.info(f"DB load OK: {len(df)} records")
            return df
        except Exception as e:
            logging.error(f"DB load failed, falling back to CSV: {e}")

    # Fallback σε CSV (Streamlit Cloud όταν δεν ανεβαίνει η βάση)
    csv_path = "migration_data.csv"
    if not os.path.exists(csv_path):
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    if 'Link' not in df.columns:
        df['Link'] = ''
    df['Link'] = df['Link'].fillna('')
    return df


# ── 2.3: Real-time Sea State (Open-Meteo Marine API) ─────────────────────────
@st.cache_data(ttl=1800)  # Cache 30 λεπτά
def get_sea_state():
    try:
        url = (
            "https://marine-api.open-meteo.com/v1/marine"
            "?latitude=34.97&longitude=34.08"   # Cape Greco
            "&current=wave_height,wave_period,wind_wave_height,wave_direction"
            "&wind_speed_unit=kn"
        )
        r = requests.get(url, timeout=5)
        data = r.json().get('current', {})
        wh   = data.get('wave_height', None)
        wp   = data.get('wave_period', None)
        wd   = data.get('wave_direction', None)
        wwh  = data.get('wind_wave_height', None)

        def beaufort(h):
            if h is None: return "—"
            if h < 0.1: return "Calm"
            if h < 0.5: return "Slight"
            if h < 1.25: return "Moderate"
            if h < 2.5: return "Rough"
            return "Very Rough"

        def direction(deg):
            if deg is None: return "—"
            dirs = ["N","NE","E","SE","S","SW","W","NW"]
            return dirs[round(deg / 45) % 8]

        return {
            "Τοποθεσία":     "Cape Greco / FAM",
            "Ύψος κύματος":  f"{wh:.1f}m — {beaufort(wh)}" if wh else "—",
            "Περίοδος":      f"{wp:.0f}s" if wp else "—",
            "Κατεύθυνση":    direction(wd),
            "Άνεμος (κύμα)": f"{wwh:.1f}m" if wwh else "—",
            "Ενημέρωση":     datetime.now().strftime("%H:%M"),
        }
    except Exception as e:
        logging.warning(f"Sea state API failed: {e}")
        return {
            "Τοποθεσία":    "Cape Greco / FAM",
            "Ύψος κύματος": "N/A",
            "Περίοδος":     "N/A",
            "Κατεύθυνση":   "N/A",
            "Άνεμος (κύμα)":"N/A",
            "Ενημέρωση":    "API unavailable",
        }


# ── 2.4: Source Credibility Weights ──────────────────────────────────────────
SOURCE_CREDIBILITY = {
    "BBC Arabic":          0.95,
    "Al Jazeera":          0.92,
    "Middle East Eye":     0.88,
    "Al Monitor":          0.85,
    "The New Humanitarian":0.90,
    "InfoMigrants English":0.88,
    "Mada Masr English":   0.82,
    "Syria Direct":        0.80,
    "Daraj":               0.78,
    "Enab Baladi":         0.75,
    "North Press Agency":  0.72,
    "Syrian Observatory":  0.65,
    "ARIJ Network":        0.80,
    "Egyptian Streets":    0.70,
    "Turkish Minute":      0.72,
    "Evrensel":            0.68,
    "Daily Sabah":         0.60,
}


# ── 3.2: Triangulation / Confidence ──────────────────────────────────────────
def get_triangulation(df_today):
    """
    Εντοπίζει signals που αναφέρουν το ίδιο γεγονός από πολλαπλές πηγές.
    Επιστρέφει dict: summary_key -> {'count': N, 'sources': [...], 'max_score': N, 'confidence': 'HIGH/MEDIUM'}
    """
    if df_today.empty or 'Summary' not in df_today.columns:
        return {}

    clusters = {}
    summaries = df_today['Summary'].fillna('').tolist()
    sources   = df_today['Source'].fillna('').tolist()
    scores    = df_today['Risk Score'].tolist()

    used = set()
    for i, (s1, src1, sc1) in enumerate(zip(summaries, sources, scores)):
        if i in used or not s1:
            continue
        words1 = set(s1.lower().split())
        group_sources = [src1]
        group_scores  = [sc1]
        group_summaries = [s1]

        for j, (s2, src2, sc2) in enumerate(zip(summaries, sources, scores)):
            if j <= i or j in used or not s2:
                continue
            words2 = set(s2.lower().split())
            if not words1 or not words2:
                continue
            overlap = len(words1 & words2) / len(words1 | words2)
            if overlap > 0.45:  # Χαμηλότερο threshold για triangulation
                group_sources.append(src2)
                group_scores.append(sc2)
                group_summaries.append(s2)
                used.add(j)

        if len(group_sources) >= 2:
            used.add(i)
            key = s1[:80]
            confidence = "HIGH" if len(group_sources) >= 3 else "MEDIUM"
            clusters[key] = {
                'count':      len(group_sources),
                'sources':    group_sources,
                'max_score':  max(group_scores),
                'confidence': confidence,
                'summary':    s1,
            }

    return clusters

@st.cache_data(ttl=60)
def load_status():
    # Η ώρα του τελευταίου scan βγαίνει από το πότε γράφτηκε πραγματικά
    # το migration_data.csv — έτσι δεν μπορεί να μείνει stale / λάθος.
    csv_path = "migration_data.csv"
    if os.path.exists(csv_path):
        ts = datetime.fromtimestamp(os.path.getmtime(csv_path))
        return {"last_scan": ts.strftime("%d/%m/%Y %H:%M:%S")}
    if os.path.exists("status.json"):
        with open("status.json") as f:
            return json.load(f)
    return {"last_scan": "—"}

df = load_data()
status = load_status()

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("**Φίλτρα**")
    st.markdown("---")

    if not df.empty:
        min_date = df['Date'].min()
        max_date = df['Date'].max()
        date_range = st.date_input(
            "Εύρος ημερομηνιών",
            value=(max_date - timedelta(days=7), max_date),
            min_value=min_date, max_value=max_date
        )
        all_countries = sorted(df['Country'].dropna().unique().tolist()) if 'Country' in df.columns else []
        selected_countries = st.multiselect("Χώρες", all_countries, default=all_countries)
        min_score = st.slider("Ελάχιστο score", 1, 10, 1)

        st.markdown("---")
        st.markdown("**Σύστημα**")
        st.caption(f"Τελευταίο scan: {status.get('last_scan','—')}")
        st.caption(f"Συνολικά records: {len(df):,}")
        if st.button("Ανανέωση"):
            st.cache_data.clear()
            st.rerun()
    else:
        date_range = (date.today() - timedelta(days=7), date.today())
        selected_countries = []
        min_score = 1

# ── Filter ───────────────────────────────────────────────────
if not df.empty:
    if isinstance(date_range, tuple) and len(date_range) == 2:
        df_f = df[(df['Date'] >= date_range[0]) & (df['Date'] <= date_range[1])]
    else:
        df_f = df.copy()
    if selected_countries and 'Country' in df_f.columns:
        df_f = df_f[df_f['Country'].isin(selected_countries)]
    if 'Risk Score' in df_f.columns:
        df_f = df_f[df_f['Risk Score'] >= min_score]
    sc = 'Risk Score'
else:
    df_f = pd.DataFrame()
    sc = 'Risk Score'

today_dt = df_f['Date'].max() if not df_f.empty else date.today()
yest_dt = today_dt - timedelta(days=1)
df_today = df_f[df_f['Date'] == today_dt] if not df_f.empty else pd.DataFrame()
df_yest  = df_f[df_f['Date'] == yest_dt]  if not df_f.empty else pd.DataFrame()

def cnt(d, lo, hi):
    if d.empty or sc not in d.columns: return 0
    return int(((d[sc] >= lo) & (d[sc] <= hi)).sum())

at = cnt(df_today, 8, 10); ay = cnt(df_yest, 8, 10)
bt = cnt(df_today, 4, 7);  by_ = cnt(df_yest, 4, 7)
mt = cnt(df_today, 1, 3)
tt = len(df_today)

def delta(a, b):
    diff = a - b
    sym = "+" if diff > 0 else ""
    return f"{sym}{diff} vs χθες"

# ── Top bar ───────────────────────────────────────────────────
now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
st.markdown(f"""
<div class="top-bar">
  <div>
    <div class="top-title">Migration Intelligence — Cyprus</div>
    <div class="top-sub">Υφυπουργείο Μετανάστευσης &amp; Διεθνούς Προστασίας</div>
  </div>
  <div class="top-right">
    <div class="status-pill"><span class="status-dot"></span>Σύστημα σε λειτουργία</div>
    <div class="scan-info">Τελευταίο scan: {status.get('last_scan','—')}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── KPIs ─────────────────────────────────────────────────────
# Χρώμα ανάλογα με την τιμή: κόκκινο ΜΟΝΟ όταν υπάρχουν πραγματικά alerts.
alert_cls  = "danger" if at > 0 else "success"
border_cls = "warning" if bt > 0 else ""
st.markdown(f"""
<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-label">Cyprus Alerts</div>
    <div class="kpi-value {alert_cls}">{at}</div>
    <div class="kpi-delta">{delta(at, ay)}</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Border Info</div>
    <div class="kpi-value {border_cls}">{bt}</div>
    <div class="kpi-delta">{delta(bt, by_)}</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Macro Signals</div>
    <div class="kpi-value info">{mt}</div>
    <div class="kpi-delta">score 1–3</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Σύνολο σήμερα</div>
    <div class="kpi-value success">{tt}</div>
    <div class="kpi-delta">{today_dt}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Cyprus Alerts",
    "Intelligence Feed",
    "Trend Analysis",
    "Geospatial",
    "Αρχείο PDF"
])

def render_link(link):
    if link and str(link).startswith('http'):
        return f'<div class="alert-link"><a href="{link}" target="_blank">Πηγή →</a></div>'
    return ''

def credibility_badge(source):
    """2.4: Source credibility indicator"""
    score = SOURCE_CREDIBILITY.get(source, None)
    # Ψάχνει και για TG sources (partial match)
    if score is None:
        for k, v in SOURCE_CREDIBILITY.items():
            if k.lower() in str(source).lower():
                score = v
                break
    if score is None:
        return ''
    if score >= 0.85:
        color, label = "#16a34a", f"★ {int(score*100)}%"
    elif score >= 0.70:
        color, label = "#d97706", f"◆ {int(score*100)}%"
    else:
        color, label = "#9ca3af", f"◇ {int(score*100)}%"
    return f'<span style="font-size:10px;color:{color};font-weight:500;margin-left:4px">{label}</span>'

# ── TAB 1: Cyprus Alerts ─────────────────────────────────────
with tab1:

    # ── 3.2: Triangulation Panel ─────────────────────────────
    if not df_today.empty:
        clusters = get_triangulation(df_today)
        high_conf = {k: v for k, v in clusters.items() if v['max_score'] >= 6}
        if high_conf:
            st.markdown('<div class="section-label" style="background:#1e3a5f;color:white;padding:6px 10px;border-radius:4px;margin-bottom:12px">🔗 CONFIRMED EVENTS — Επιβεβαιωμένα από πολλαπλές πηγές</div>', unsafe_allow_html=True)
            for key, cl in sorted(high_conf.items(), key=lambda x: -x[1]['max_score'])[:5]:
                conf_color = "#16a34a" if cl['confidence'] == "HIGH" else "#d97706"
                conf_label = f"{'★' * cl['count']} {cl['confidence']} ({cl['count']} πηγές)"
                sources_str = " · ".join(cl['sources'][:4])
                st.markdown(f"""
                <div style="background:#fff;border:1px solid #e5e7eb;border-left:3px solid {conf_color};border-radius:6px;padding:12px 16px;margin-bottom:8px;">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-size:11px;font-weight:600;color:{conf_color}">{conf_label}</span>
                    <span style="background:#f3f4f6;color:#374151;font-size:10px;padding:2px 8px;border-radius:3px;font-family:monospace">score {cl['max_score']}</span>
                  </div>
                  <div style="font-size:13px;color:#1f2937;line-height:1.5;margin-bottom:6px">{cl['summary'][:200]}</div>
                  <div style="font-size:11px;color:#9ca3af">{sources_str}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown("---")

    st.markdown('<div class="section-label">Cyprus Alerts — Score 8–10</div>', unsafe_allow_html=True)
    if df_today.empty or sc not in df_today.columns:
        st.markdown('<div class="empty-state">Δεν βρέθηκαν δεδομένα για σήμερα.</div>', unsafe_allow_html=True)
    else:
        alerts_df = df_today[df_today[sc] >= 8].sort_values(sc, ascending=False)
        if alerts_df.empty:
            st.markdown("""
            <div class="empty-state">
              Καμία κρίσιμη ειδοποίηση τις τελευταίες 24 ώρες.<br>
              <span style="font-size:11px;color:#d1d5db;margin-top:4px;display:block">Το σύστημα παρακολουθεί ενεργά.</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            for _, row in alerts_df.iterrows():
                score = int(row[sc])
                summary = row.get('Summary', '') or row.get('Title', '')
                source = row.get('Source', '—')
                country = row.get('Country', '')
                link = render_link(row.get('Link', ''))
                cred = credibility_badge(source)
                st.markdown(f"""
                <div class="alert-card">
                  <div class="alert-card-header">
                    <span class="score-badge badge-danger">{score}</span>
                    <span class="alert-source">{source}</span>{cred}
                    <span class="tag">{country}</span>
                  </div>
                  <div class="alert-summary">{summary}</div>
                  {link}
                </div>
                """, unsafe_allow_html=True)

        st.markdown('<div class="section-label" style="margin-top:20px">Border Info — Score 6–7</div>', unsafe_allow_html=True)
        border_df = df_today[(df_today[sc] >= 6) & (df_today[sc] < 8)].sort_values(sc, ascending=False)
        if border_df.empty:
            st.markdown('<div class="empty-state">Καμία είδηση border info σήμερα.</div>', unsafe_allow_html=True)
        else:
            for _, row in border_df.iterrows():
                score = int(row[sc])
                summary = row.get('Summary', '') or row.get('Title', '')
                source = row.get('Source', '—')
                country = row.get('Country', '')
                link = render_link(row.get('Link', ''))
                cred = credibility_badge(source)
                st.markdown(f"""
                <div class="signal-row">
                  <span class="score-badge badge-warning">{score}</span>
                  <div class="signal-body">
                    <div class="signal-title">{summary}</div>
                    <div class="signal-meta"><span class="tag">{country}</span><span class="tag">{source}</span>{cred}</div>
                    {link.replace('alert-link','signal-link')}
                  </div>
                </div>
                """, unsafe_allow_html=True)

# ── TAB 2: Intelligence Feed ─────────────────────────────────
with tab2:
    if df_f.empty or sc not in df_f.columns:
        st.markdown('<div class="empty-state">Δεν βρέθηκαν δεδομένα.</div>', unsafe_allow_html=True)
    else:
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            score_range = st.select_slider("Score", options=list(range(1,11)), value=(4, 10))
        with col2:
            countries_feed = st.multiselect("Χώρα", sorted(df_f['Country'].dropna().unique().tolist()), key="feed_country")
        with col3:
            sort_opt = st.selectbox("Ταξινόμηση", ["Score", "Ημερομηνία"])

        feed = df_f[(df_f[sc] >= score_range[0]) & (df_f[sc] <= score_range[1])].copy()
        if countries_feed:
            feed = feed[feed['Country'].isin(countries_feed)]
        if sort_opt == "Score":
            feed = feed.sort_values([sc, 'Date'], ascending=[False, False])
        else:
            feed = feed.sort_values(['Date', sc], ascending=[False, False])

        st.markdown(f'<div class="section-label">{len(feed)} signals</div>', unsafe_allow_html=True)

        for _, row in feed.head(80).iterrows():
            score = int(row[sc])
            summary = row.get('Summary', '') or row.get('Title', '')
            source = row.get('Source', '—')
            country = row.get('Country', '')
            dt = str(row.get('Date', ''))
            link = render_link(row.get('Link', ''))
            badge = 'badge-danger' if score >= 8 else 'badge-warning' if score >= 4 else 'badge-neutral'
            cred = credibility_badge(source)
            st.markdown(f"""
            <div class="signal-row">
              <span class="score-badge {badge}">{score}</span>
              <div class="signal-body">
                <div class="signal-title">{summary}</div>
                <div class="signal-meta"><span class="tag">{country}</span><span class="tag">{source}</span>{cred} {dt}</div>
                {link.replace('alert-link','signal-link')}
              </div>
            </div>
            """, unsafe_allow_html=True)

# ── TAB 3: Trend Analysis ─────────────────────────────────────
with tab3:
    if df_f.empty or sc not in df_f.columns:
        st.markdown('<div class="empty-state">Δεν βρέθηκαν δεδομένα για ανάλυση.</div>', unsafe_allow_html=True)
    else:
        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown('<div class="section-label">Ημερήσιο Risk Trend</div>', unsafe_allow_html=True)
            daily = df_f.groupby('Date').agg(
                alerts=(sc, lambda x: (x >= 8).sum()),
                border=(sc, lambda x: ((x >= 4) & (x < 8)).sum()),
                avg=(sc, 'mean')
            ).reset_index().sort_values('Date')

            fig1 = go.Figure()
            fig1.add_trace(go.Bar(x=daily['Date'], y=daily['border'], name='Border Info',
                marker_color='rgba(217,119,6,0.5)', marker_line_color='#d97706', marker_line_width=0.5))
            fig1.add_trace(go.Bar(x=daily['Date'], y=daily['alerts'], name='Cyprus Alert',
                marker_color='rgba(220,38,38,0.6)', marker_line_color='#dc2626', marker_line_width=0.5))
            fig1.add_trace(go.Scatter(x=daily['Date'], y=daily['avg'], name='Avg Score',
                line=dict(color='#2563eb', width=1.5, dash='dot'), yaxis='y2'))
            fig1.update_layout(
                paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
                font=dict(family='Inter', size=11, color='#6b7280'),
                barmode='stack', height=260,
                margin=dict(l=0, r=0, t=10, b=0),
                legend=dict(font=dict(size=10), bgcolor='rgba(0,0,0,0)', x=0, y=1.1, orientation='h'),
                xaxis=dict(gridcolor='#f3f4f6', tickfont=dict(size=10), linecolor='#e5e7eb'),
                yaxis=dict(gridcolor='#f3f4f6', tickfont=dict(size=10), linecolor='#e5e7eb'),
                yaxis2=dict(overlaying='y', side='right', range=[0,10],
                            tickfont=dict(size=10), gridcolor='rgba(0,0,0,0)', linecolor='rgba(0,0,0,0)'),
            )
            st.plotly_chart(fig1, use_container_width=True)

        with col_b:
            st.markdown('<div class="section-label">Signals ανά Χώρα</div>', unsafe_allow_html=True)
            if 'Country' in df_f.columns:
                cs = df_f.groupby('Country').agg(
                    total=(sc, 'count'),
                    high=(sc, lambda x: (x >= 6).sum())
                ).reset_index().sort_values('high', ascending=True)

                fig2 = go.Figure()
                fig2.add_trace(go.Bar(y=cs['Country'], x=cs['high'], orientation='h',
                    name='Score 6+', marker_color='rgba(217,119,6,0.55)',
                    marker_line_color='#d97706', marker_line_width=0.5))
                fig2.add_trace(go.Bar(y=cs['Country'], x=cs['total']-cs['high'], orientation='h',
                    name='Score <6', marker_color='rgba(37,99,235,0.2)',
                    marker_line_color='#2563eb', marker_line_width=0.5))
                fig2.update_layout(
                    paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
                    font=dict(family='Inter', size=11, color='#6b7280'),
                    barmode='stack', height=260,
                    margin=dict(l=0, r=0, t=10, b=0),
                    legend=dict(font=dict(size=10), bgcolor='rgba(0,0,0,0)', x=0, y=1.1, orientation='h'),
                    xaxis=dict(gridcolor='#f3f4f6', tickfont=dict(size=10), linecolor='#e5e7eb'),
                    yaxis=dict(gridcolor='rgba(0,0,0,0)', tickfont=dict(size=11, color='#374151'), linecolor='rgba(0,0,0,0)'),
                )
                st.plotly_chart(fig2, use_container_width=True)

        st.markdown('<div class="section-label" style="margin-top:8px">Top Πηγές — Score 6+</div>', unsafe_allow_html=True)
        if 'Source' in df_f.columns:
            ts = df_f[df_f[sc] >= 6].groupby('Source').size().reset_index(name='n').sort_values('n', ascending=False).head(12)
            fig3 = go.Figure(go.Bar(
                x=ts['n'], y=ts['Source'], orientation='h',
                marker_color='rgba(37,99,235,0.45)',
                marker_line_color='#2563eb', marker_line_width=0.5,
                text=ts['n'], textposition='outside',
                textfont=dict(size=10, color='#6b7280')
            ))
            fig3.update_layout(
                paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
                font=dict(family='Inter', size=11, color='#6b7280'),
                height=280, margin=dict(l=0, r=30, t=10, b=0),
                xaxis=dict(gridcolor='#f3f4f6', tickfont=dict(size=10), linecolor='#e5e7eb'),
                yaxis=dict(gridcolor='rgba(0,0,0,0)', tickfont=dict(size=11, color='#374151'), linecolor='rgba(0,0,0,0)'),
            )
            st.plotly_chart(fig3, use_container_width=True)

# ── TAB 4: Geospatial ────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-label">Geospatial Intelligence — Eastern Mediterranean</div>', unsafe_allow_html=True)
    col_m, col_i = st.columns([2, 1])

    with col_m:
        nodes = {
            'Cyprus':         {'lat': 35.1264, 'lon': 33.4299, 'risk': 5,  'color': '#16a34a'},
            'Beirut':         {'lat': 33.8938, 'lon': 35.5018, 'risk': 9,  'color': '#dc2626'},
            'Tripoli (LB)':   {'lat': 34.4367, 'lon': 35.8497, 'risk': 8,  'color': '#dc2626'},
            'Tyre':           {'lat': 33.2705, 'lon': 35.2038, 'risk': 9,  'color': '#dc2626'},
            'Latakia':        {'lat': 35.5236, 'lon': 35.7913, 'risk': 6,  'color': '#d97706'},
            'Tartus':         {'lat': 34.8888, 'lon': 35.8866, 'risk': 5,  'color': '#d97706'},
            'Damascus':       {'lat': 33.5138, 'lon': 36.2765, 'risk': 5,  'color': '#d97706'},
            'Mersin (TR)':    {'lat': 36.8121, 'lon': 34.6415, 'risk': 7,  'color': '#d97706'},
            'Alexandria':     {'lat': 31.2001, 'lon': 29.9187, 'risk': 4,  'color': '#2563eb'},
            'Gaza':           {'lat': 31.5017, 'lon': 34.4668, 'risk': 8,  'color': '#dc2626'},
        }
        if not df_today.empty and sc in df_today.columns:
            cr = df_today.groupby('Country')[sc].max().to_dict()
            if 'Lebanon' in cr:
                nodes['Beirut']['risk'] = min(10, int(cr['Lebanon']))
            if 'Syria' in cr:
                nodes['Latakia']['risk'] = min(10, int(cr['Syria']))

        fig_map = go.Figure(go.Scattermapbox(
            lat=[v['lat'] for v in nodes.values()],
            lon=[v['lon'] for v in nodes.values()],
            mode='markers+text',
            marker=dict(size=[v['risk']*4+8 for v in nodes.values()],
                        color=[v['color'] for v in nodes.values()], opacity=0.85),
            text=list(nodes.keys()),
            textposition='top right',
            textfont=dict(size=10, color='#374151'),
            customdata=[v['risk'] for v in nodes.values()],
            hovertemplate='<b>%{text}</b><br>Risk: %{customdata}/10<extra></extra>'
        ))
        fig_map.update_layout(
            mapbox=dict(style='carto-positron', center=dict(lat=34.5, lon=35.0), zoom=5.5),
            margin=dict(l=0, r=0, t=0, b=0),
            height=420, paper_bgcolor='#f8f9fb',
        )
        st.plotly_chart(fig_map, use_container_width=True)

    with col_i:
        st.markdown('<div class="section-label">Sea State — Real-time</div>', unsafe_allow_html=True)
        sea = get_sea_state()
        for label, val in sea.items():
            color = "#6b7280"
            if label == "Ύψος κύματος":
                if "Very Rough" in val or "Rough" in val:
                    color = "#dc2626"
                elif "Moderate" in val:
                    color = "#d97706"
                else:
                    color = "#16a34a"
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid #f3f4f6;font-size:12px;">
              <span style="color:#6b7280">{label}</span>
              <span style="color:{color};font-weight:500">{val}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<div class="section-label" style="margin-top:16px">Υπόμνημα</div>', unsafe_allow_html=True)
        for lbl, col, desc in [("9–10","#dc2626","Cyprus Alert"),("6–8","#d97706","Border Info"),
                                ("3–5","#2563eb","Macro Signal"),("HQ","#16a34a","Cyprus Base")]:
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:8px;padding:5px 0;font-size:12px;">
              <span style="width:10px;height:10px;border-radius:50%;background:{col};display:inline-block;flex-shrink:0"></span>
              <span style="color:#6b7280;min-width:36px">{lbl}</span>
              <span style="color:#374151">{desc}</span>
            </div>
            """, unsafe_allow_html=True)

# ── TAB 5: Archive ───────────────────────────────────────────
with tab5:
    st.markdown('<div class="section-label">Αρχείο Ημερήσιων Αναφορών</div>', unsafe_allow_html=True)
    reports_dir = "reports"
    if os.path.exists(reports_dir):
        pdfs = sorted([f for f in os.listdir(reports_dir) if f.endswith('.pdf')], reverse=True)
        if pdfs:
            for pdf_file in pdfs:
                date_str = pdf_file.replace('OSINT_Report_', '').replace('.pdf', '')
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"""
                    <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #f3f4f6;font-size:13px;">
                      <span style="color:#6b7280;font-size:11px">PDF</span>
                      <span style="color:#374151">Ημερήσια Αναφορά</span>
                      <span style="color:#111827;font-weight:500;font-family:'JetBrains Mono',monospace;font-size:12px">{date_str}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with c2:
                    with open(os.path.join(reports_dir, pdf_file), "rb") as f:
                        st.download_button("Λήψη", data=f, file_name=pdf_file,
                            mime="application/pdf", key=f"dl_{pdf_file}")
        else:
            st.markdown('<div class="empty-state">Δεν βρέθηκαν αρχεία.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">Ο φάκελος reports δεν έχει δημιουργηθεί.</div>', unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center;padding:32px 0 8px;font-size:11px;color:#d1d5db;">
  Υφυπουργείο Μετανάστευσης &amp; Διεθνούς Προστασίας — Κυπριακή Δημοκρατία — Περιορισμένης Κυκλοφορίας
</div>
""", unsafe_allow_html=True)