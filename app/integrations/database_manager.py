# app/integrations/database_manager.py
import sqlite3
from typing import Iterable
import pandas as pd
import numpy as np
from app.utils.config_loader import SETTINGS

# ---------- helpers ----------

def _sqlite_type_for(s: pd.Series) -> str:
    """Map pandas dtype to a reasonable SQLite type."""
    try:
        if pd.api.types.is_integer_dtype(s):
            return "INTEGER"
        if pd.api.types.is_bool_dtype(s):
            return "INTEGER"  # store booleans as 0/1
        if pd.api.types.is_float_dtype(s):
            return "REAL"
    except Exception:
        pass
    return "TEXT"

def _ensure_table_exists(conn: sqlite3.Connection, table: str = "development_leads") -> None:
    """
    Create a minimal table if it doesn't exist yet.
    We'll add columns on demand later.
    """
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id   INTEGER PRIMARY KEY,
            url  TEXT
        )
    """)
    conn.commit()

def _ensure_table_columns(conn: sqlite3.Connection, table: str, df: pd.DataFrame) -> None:
    """
    Make sure every column in df exists in the SQLite table; add missing ones.
    """
    _ensure_table_exists(conn, table)
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}  # set of column names

    for col in df.columns:
        if col not in existing:
            sqltype = _sqlite_type_for(df[col])
            cur.execute(f'ALTER TABLE {table} ADD COLUMN "{col}" {sqltype}')
    conn.commit()

# ---------- public API ----------

def init_db() -> None:
    """
    Initialize the SQLite database so the pipeline can write immediately.
    Safe to call multiple times.
    """
    db = SETTINGS.database_path
    with sqlite3.connect(db) as conn:
        _ensure_table_exists(conn, "development_leads")

def upsert_leads(df: pd.DataFrame) -> int:
    """
    Insert (append) leads into SQLite.
    - Auto-creates table if missing
    - Auto-adds any new columns to the table before inserting
    - Sanitizes NaN/Inf to None (NULL)
    Returns the number of rows written.
    """
    if df is None or df.empty:
        return 0

    # sanitize for SQLite
    df = df.replace([pd.NA, np.nan, np.inf, -np.inf], None)

    # optional: de-dup within this batch by URL if present
    if "url" in df.columns:
        df = df.drop_duplicates(subset=["url"])

    db = SETTINGS.database_path
    with sqlite3.connect(db) as conn:
        _ensure_table_columns(conn, "development_leads", df)
        df.to_sql("development_leads", conn, if_exists="append", index=False)
        return len(df)
