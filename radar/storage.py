from __future__ import annotations
import hashlib
import sqlite3
from datetime import datetime, timezone
from .config import DATA_DIR

DB_PATH = DATA_DIR / "radar.sqlite3"


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_signals (
            key TEXT PRIMARY KEY,
            url TEXT,
            title TEXT,
            channel TEXT,
            first_seen TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            key TEXT PRIMARY KEY,
            payload TEXT,
            updated_at TEXT
        )
        """)


def signal_key(channel: str, url: str, title: str) -> str:
    base = (url or title or "").strip().lower()
    return hashlib.sha256(f"{channel}|{base}".encode("utf-8")).hexdigest()


def is_new_and_mark(channel: str, url: str, title: str) -> bool:
    key = signal_key(channel, url, title)
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("SELECT 1 FROM seen_signals WHERE key=?", (key,))
        if cur.fetchone():
            return False
        conn.execute("INSERT INTO seen_signals(key,url,title,channel,first_seen) VALUES (?,?,?,?,?)", (key, url, title, channel, now))
        return True
