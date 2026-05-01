import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "wardrobe.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS clothes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            colors TEXT NOT NULL,
            description TEXT,
            tags TEXT,
            image_base64 TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS wear_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cloth_ids TEXT NOT NULL,
            outfit_description TEXT,
            worn_at TEXT DEFAULT (datetime('now')),
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS style_profile (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


# ── Clothes ───────────────────────────────────────────────────────────────────

def add_clothing_item(name, category, colors, description, tags, image_base64):
    conn = get_conn()
    conn.execute(
        "INSERT INTO clothes (name, category, colors, description, tags, image_base64) VALUES (?,?,?,?,?,?)",
        (name, category, json.dumps(colors), description, json.dumps(tags), image_base64),
    )
    conn.commit()
    conn.close()


def get_all_clothes():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM clothes ORDER BY category, name").fetchall()
    conn.close()
    items = []
    for r in rows:
        item = dict(r)
        item["colors"] = json.loads(item["colors"])
        item["tags"] = json.loads(item["tags"])
        items.append(item)
    return items


def get_clothing_item(item_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM clothes WHERE id=?", (item_id,)).fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    item["colors"] = json.loads(item["colors"])
    item["tags"] = json.loads(item["tags"])
    return item


def delete_clothing_item(item_id):
    conn = get_conn()
    conn.execute("DELETE FROM clothes WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


# ── Wear log ──────────────────────────────────────────────────────────────────

def log_outfit_worn(cloth_ids: list[int], outfit_description: str, notes: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO wear_log (cloth_ids, outfit_description, notes) VALUES (?,?,?)",
        (json.dumps(cloth_ids), outfit_description, notes),
    )
    conn.commit()
    conn.close()


def get_recent_wear_log(days: int = 7):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM wear_log WHERE worn_at >= datetime('now', ?) ORDER BY worn_at DESC",
        (f"-{days} days",),
    ).fetchall()
    conn.close()
    logs = []
    for r in rows:
        log = dict(r)
        log["cloth_ids"] = json.loads(log["cloth_ids"])
        logs.append(log)
    return logs


def get_all_wear_log():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM wear_log ORDER BY worn_at DESC").fetchall()
    conn.close()
    logs = []
    for r in rows:
        log = dict(r)
        log["cloth_ids"] = json.loads(log["cloth_ids"])
        logs.append(log)
    return logs


def get_recently_worn_ids(days: int = 3) -> set[int]:
    logs = get_recent_wear_log(days)
    ids = set()
    for log in logs:
        ids.update(log["cloth_ids"])
    return ids


# ── Style profile ─────────────────────────────────────────────────────────────

def set_profile_value(key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO style_profile (key, value, updated_at) VALUES (?,?,datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_profile_value(key: str, default: str = "") -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM style_profile WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def get_full_profile() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM style_profile").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}
