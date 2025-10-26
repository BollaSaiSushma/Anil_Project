# migrate_db.py
import sqlite3
from pathlib import Path
from app.utils.config_loader import SETTINGS

DB = Path(SETTINGS.database_path)

# Columns your pipeline writes today (update if you add more later)
EXPECTED_COLUMNS = {
    "address": "TEXT",
    "city": "TEXT",
    "state": "TEXT",
    "price": "REAL",
    "beds": "INT",
    "baths": "INT",
    "lot_sqft": "REAL",
    "url": "TEXT",
    "development_score": "INT",
    "label": "TEXT",
    "explanation": "TEXT",
    "has_keywords": "INT",
    "opportunity_score": "REAL",
    "buildable_sf": "REAL",
    "lat": "REAL",
    "lon": "REAL",
    # NEW ROI fields
    "roi_percentage": "REAL",
    "roi_score": "INT",
}

def get_existing_columns(conn):
    cur = conn.execute("PRAGMA table_info(development_leads);")
    return {row[1] for row in cur.fetchall()}  # set of column names

def add_missing_columns(conn, missing):
    for col in missing:
        ddl = f"ALTER TABLE development_leads ADD COLUMN {col} {EXPECTED_COLUMNS[col]}"
        conn.execute(ddl)
        print("Added column:", ddl)

def main():
    if not DB.exists():
        print("DB not found at", DB, "— run init_db() or pipeline once.")
        return
    with sqlite3.connect(DB) as conn:
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS development_leads(
                id INTEGER PRIMARY KEY AUTOINCREMENT
            );
        """)
        existing = get_existing_columns(conn)
        needed = set(EXPECTED_COLUMNS) - existing
        if not needed:
            print("No migration needed. Columns already present ✓")
            return
        add_missing_columns(conn, needed)
        print("Migration complete. Added:", ", ".join(sorted(needed)))

if __name__ == "__main__":
    main()
