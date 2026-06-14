#!/usr/bin/env python3
"""
Batch categorization of existing signals using Gemini API
"""

import sqlite3
import time
import sys
from entity_extractor import extract_entities

DB_FILE = "/home/agent/migration_agent/migration_data.db"

def batch_categorize():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Πάρε όλα τα records χωρίς category
    cursor.execute("""
        SELECT id, title, summary 
        FROM signals 
        WHERE category IS NULL
        ORDER BY id DESC
    """)
    records = cursor.fetchall()
    
    total = len(records)
    print(f"📊 Total records to categorize: {total}")
    
    success = 0
    errors = 0
    
    for i, (record_id, title, summary) in enumerate(records):
        try:
            # Progress
            if i % 10 == 0:
                pct = (i / total) * 100
                print(f"[{i}/{total}] {pct:.1f}% — Processing ID {record_id}...")
                sys.stdout.flush()
            
            # Skip αν δεν υπάρχει summary
            if not title and not summary:
                continue
            
            # Extract entities
            entities = extract_entities(
                title or '',
                summary or ''
            )
            
            # Update database
            import json
            cursor.execute("""
                UPDATE signals SET
                    countries     = ?,
                    people        = ?,
                    organizations = ?,
                    locations     = ?,
                    category      = ?,
                    confidence    = ?
                WHERE id = ?
            """, (
                json.dumps(entities.get('countries', []), ensure_ascii=False),
                json.dumps(entities.get('people', []), ensure_ascii=False),
                json.dumps(entities.get('organizations', []), ensure_ascii=False),
                json.dumps(entities.get('locations', []), ensure_ascii=False),
                entities.get('category', 'Other'),
                entities.get('confidence', 0.0),
                record_id
            ))
            
            # Commit κάθε 50 records
            if i % 50 == 0:
                conn.commit()
            
            success += 1
            
            # Rate limiting — 1 δευτερόλεπτο μεταξύ calls
            time.sleep(1)
        
        except Exception as e:
            errors += 1
            print(f"  ❌ Error on ID {record_id}: {str(e)}")
            time.sleep(2)  # Αναμονή αν υπάρχει error
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Done!")
    print(f"  Success: {success}")
    print(f"  Errors:  {errors}")

if __name__ == "__main__":
    batch_categorize()
