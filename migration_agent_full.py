#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OSINT Migration Intelligence Agent
Σάρωση RSS feeds + Telegram για migration-related signals
Semantic deduplication με sentence-transformers
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
import hashlib

# Data processing
import pandas as pd
import feedparser
feedparser.USER_AGENT = "Mozilla/5.0"
from entity_extractor import extract_entities

# Embeddings
from sentence_transformers import SentenceTransformer
import math

# Gemini scoring
import google.generativeai as genai
from dotenv import load_dotenv

# ═══════════════════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════════════════

load_dotenv(os.path.expanduser('~/.env'))

PROJECT_DIR = Path(__file__).parent
DB_FILE = PROJECT_DIR / "migration_data.db"
CSV_FILE = PROJECT_DIR / "migration_data.csv"
LOG_FILE = PROJECT_DIR / "migration_agent.log"

# Initialize Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)
gemini_model = genai.GenerativeModel('models/gemini-2.5-flash')

# Load embedding model (cached after first run)
print("Loading embedding model...")
embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# ═══════════════════════════════════════════════════════════════════════════
# EMBEDDING & SIMILARITY
# ═══════════════════════════════════════════════════════════════════════════

def get_embedding(text):
    """Get embedding vector for text"""
    try:
        return embedding_model.encode(text, convert_to_tensor=False)
    except Exception as e:
        print(f"❌ Embedding error: {str(e)}")
        return None

def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors"""
    if vec1 is None or vec2 is None or len(vec1) == 0 or len(vec2) == 0:
        return 0
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a ** 2 for a in vec1))
    magnitude2 = math.sqrt(sum(b ** 2 for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0
    
    return dot_product / (magnitude1 * magnitude2)

def is_duplicate(new_summary, today_str):
    """
    Ελέγχει αν υπάρχει ήδη παρόμοιο signal σήμερα
    Χρησιμοποιεί semantic similarity (embeddings) με threshold 0.80
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        # Πάρε όλα τα summaries από σήμερα
        cursor.execute(
            "SELECT summary FROM signals WHERE date = ? LIMIT 100",
            (today_str,)
        )
        existing = cursor.fetchall()
        
        if not existing:
            return False
        
        # Compute embedding του νέου summary
        new_emb = get_embedding(new_summary)
        if new_emb is None:
            # Fallback σε word overlap αν το embedding αποτύχει
            new_words = set(new_summary.lower().split())
            for (ex_summary,) in existing:
                ex_words = set(ex_summary.lower().split())
                overlap = len(new_words & ex_words) / len(new_words | ex_words)
                if overlap > 0.65:
                    return True
            return False
        
        # Compare με όλα τα existing summaries
        for (ex_summary,) in existing:
            ex_emb = get_embedding(ex_summary)
            if ex_emb is None:
                continue
            
            similarity = cosine_similarity(new_emb, ex_emb)
            
            # Threshold: 0.80 (80% similarity = duplicate)
            if similarity >= 0.95:
                print(f"  [DUP] Similarity {similarity:.1%} > 80%")
                return True
        
        return False
    
    finally:
        conn.close()

# ═══════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════

def init_db():
    """Initialize database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            source TEXT,
            title TEXT,
            summary TEXT UNIQUE,
            score INTEGER,
            embedding BLOB,
            countries TEXT,
            people TEXT,
            organizations TEXT,
            locations TEXT,
            category TEXT,
            confidence REAL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

def save_signal(date, source, title, summary, score, embedding=None, entities=None):
    """Save signal to database"""
    import json
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        embedding_blob = embedding.tobytes() if embedding is not None else None
        
        countries = json.dumps(entities.get('countries', []), ensure_ascii=False) if entities else None
        people = json.dumps(entities.get('people', []), ensure_ascii=False) if entities else None
        organizations = json.dumps(entities.get('organizations', []), ensure_ascii=False) if entities else None
        locations = json.dumps(entities.get('locations', []), ensure_ascii=False) if entities else None
        category = entities.get('category', 'Other') if entities else None
        confidence = entities.get('confidence', 0.0) if entities else None
        
        cursor.execute("""
            INSERT OR IGNORE INTO signals 
            (date, source, title, summary, score, embedding,
             countries, people, organizations, locations, category, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date, source, title, summary, score, embedding_blob,
              countries, people, organizations, locations, category, confidence))
        
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# ═══════════════════════════════════════════════════════════════════════════
# RSS SCANNING
# ═══════════════════════════════════════════════════════════════════════════

RSS_FEEDS = []

import json as _json, socket as _socket
_socket.setdefaulttimeout(15)
try:
    _cfg = _json.load(open(PROJECT_DIR / "config.json", encoding="utf-8"))
    for _region, _feeds in _cfg.get("rss_feeds", {}).items():
        for _f in _feeds:
            _u = _f.get("url")
            if _u and _u not in RSS_FEEDS:
                RSS_FEEDS.append(_u)
    KEYWORDS = [str(k).lower() for k in _cfg.get("global_keywords", [])]
except Exception as _e:
    print("config.json load warning:", _e)
    KEYWORDS = []
# Cyprus/Levant-specific fallback keywords μόνο
KEYWORDS += ["migrant","smuggl","irregular","asylum seeker","coast guard","border crossing","deportat","detention"]
KEYWORDS = list(dict.fromkeys(KEYWORDS))
print(f"RSS feeds total: {len(RSS_FEEDS)} | keywords: {len(KEYWORDS)}")

def scan_rss():
    """Σάρωση RSS feeds για migration-related content"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    count = 0
    
    for feed_url in RSS_FEEDS:
        try:
            print(f"📡 Scanning {feed_url[:50]}...")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')[:500]
                
                # Filter 1 — migration-related keywords
                text_lower = (title + " " + summary).lower()
                if not any(kw.lower() in text_lower for kw in KEYWORDS):
                    continue

                # Filter 2 — geographic proximity (Levant/Cyprus corridor)
                GEO_TERMS = [
                    "cyprus", "κύπρος", "κυπρ",
                    "lebanon", "لبنان", "λίβανος",
                    "syria", "سوريا", "συρία",
                    "turkey", "türkiye", "τουρκία", "kıbrıs",
                    "egypt", "مصر", "αίγυπτος",
                    "mediterranean", "aegean", "eastern med",
                    "frontex", "unhcr", "iom",
                    "libya", "λιβύη",
                    "beirut", "damascus", "aleppo", "latakia", "tartus",
                    "iskenderun", "mersin", "bodrum", "izmir",
                    "nicosia", "limassol", "larnaca", "famagusta",
                    "lesbos", "dodecanese", "rhodes",
                    "migrant boat", "irregular crossing", "sea crossing",
                    "coast guard interception", "coastguard"
                ]
                if not any(gt in text_lower for gt in GEO_TERMS):
                    continue
                
                # Check for duplicates
                if is_duplicate(summary, today_str):
                    continue
                
                # Score με Gemini
                score = score_signal(title, summary)
                
                # Get embedding
                embedding = get_embedding(summary)
                
                # Extract entities
                entities = extract_entities(title, summary)
                print(f"  [CAT] {entities.get('category', 'Other')} | {entities.get('countries', [])}")
                
                # Save
                if save_signal(today_str, urlparse(feed_url).netloc, title, summary, score, embedding, entities):
                    count += 1
                    print(f"  ✅ Saved: {title[:60]}...")
        
        except Exception as e:
            print(f"  ❌ Error scanning {feed_url}: {str(e)}")
    
    return count

# ═══════════════════════════════════════════════════════════════════════════
# GEMINI SCORING
# ═══════════════════════════════════════════════════════════════════════════

def score_signal(title, summary):
    """Score signal από 1-10 χρησιμοποιώντας Gemini"""
    try:
        prompt = f"""
        Rate this migration-related signal from 1-10:
        Title: {title}
        Summary: {summary}
        
        Scoring: 1-3 (low impact), 4-6 (medium), 7-10 (high impact)
        Reply with ONLY a number.
        """
        
        response = gemini_model.generate_content(prompt)
        score_text = response.text.strip()
        return int(''.join(filter(str.isdigit, score_text[:2]))) or 5
    except:
        return 5

# ═══════════════════════════════════════════════════════════════════════════
# EXPORT & REPORT
# ═══════════════════════════════════════════════════════════════════════════

def export_csv():
    """Export database to CSV"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM signals ORDER BY score DESC, date DESC", conn)
    conn.close()
    
    df.to_csv(CSV_FILE, index=False)
    print(f"📊 Exported {len(df)} signals to {CSV_FILE}")

def main():
    print("╔════════════════════════════════════════════╗")
    print("║  OSINT Migration Intelligence Agent (Β.1) ║")
    print("║  Semantic Deduplication                   ║")
    print("╚════════════════════════════════════════════╝")
    
    init_db()
    
    print("\n🔍 Scanning RSS feeds...")
    count = scan_rss()
    
    print(f"\n✅ Added {count} new signals")
    
    print("\n📊 Exporting to CSV...")
    export_csv()
    
    print("\n✅ Done!")

if __name__ == "__main__":
    main()
