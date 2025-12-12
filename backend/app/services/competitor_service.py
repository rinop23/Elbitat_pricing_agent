import sqlite3
import os
from typing import List, Optional, Dict

# Get the absolute path to store the database in the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "pricing_agent.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS competitors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        website TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        lighthouse_hotel_id TEXT
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        dry_run INTEGER NOT NULL,
        occupancy INTEGER NOT NULL,
        status TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        run_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        recommended_rate REAL NOT NULL,
        lowest_competitor REAL NOT NULL
    )
    """)

    conn.commit()
    conn.close()


def add_competitor(name: str, website: Optional[str], active: bool) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO competitors (name, website, active) VALUES (?, ?, ?)",
        (name, website, 1 if active else 0)
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def list_competitors() -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, website, active FROM competitors ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "website": r[2], "active": bool(r[3])}
        for r in rows
    ]


def delete_competitor(cid: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM competitors WHERE id=?", (cid,))
    conn.commit()
    conn.close()

def update_competitor_db(cid: int, fields: Dict):
    if not fields:
        return None

    conn = get_conn()
    cur = conn.cursor()

    cols = []
    vals = []
    for k, v in fields.items():
        if k == "active":
            v = 1 if v else 0
        cols.append(f"{k}=?")
        vals.append(v)

    vals.append(cid)

    cur.execute(
        f"UPDATE competitors SET {', '.join(cols)} WHERE id=?",
        tuple(vals)
    )
    conn.commit()

    cur.execute("SELECT id, name, website, active, lighthouse_hotel_id FROM competitors WHERE id=?", (cid,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "id": row[0],
        "name": row[1],
        "website": row[2],
        "active": bool(row[3]),
        "lighthouse_hotel_id": row[4]
    }
