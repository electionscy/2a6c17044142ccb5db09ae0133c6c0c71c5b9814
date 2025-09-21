from pathlib import Path
import sqlite3

DB_PATH = Path(".state.sqlite")

def ensure():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
    CREATE TABLE IF NOT EXISTS seen (
      id INTEGER PRIMARY KEY,
      source TEXT NOT NULL,
      url TEXT UNIQUE NOT NULL,
      first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    con.close()

def seen(url: str) -> bool:
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT 1 FROM seen WHERE url=?", (url,)).fetchone()
    con.close()
    return row is not None

def mark(source: str, url: str):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT OR IGNORE INTO seen(source,url) VALUES(?,?)", (source, url))
    con.commit(); con.close()
