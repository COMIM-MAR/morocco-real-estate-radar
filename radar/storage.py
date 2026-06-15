from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from .config import DB_PATH, DATA_DIR


def init_db(db_path: Path = DB_PATH) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS seen (
                key TEXT PRIMARY KEY,
                url TEXT,
                title TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def make_key(source: str, title: str, url: str) -> str:
    raw = f"{source}|{title}|{url}".lower().strip().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def is_new_and_mark(source: str, title: str, url: str, db_path: Path = DB_PATH) -> bool:
    init_db(db_path)
    key = make_key(source, title, url)
    with sqlite3.connect(db_path) as con:
        cur = con.execute("SELECT 1 FROM seen WHERE key=?", (key,))
        if cur.fetchone():
            return False
        con.execute("INSERT INTO seen(key,url,title) VALUES(?,?,?)", (key, url, title))
        return True
