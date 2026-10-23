import sqlite3
import time

from .config import ROOT

DB_PATH = ROOT / "data" / "factory.db"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS used (
               url TEXT PRIMARY KEY, title TEXT, format TEXT,
               folder TEXT, video_id TEXT, created_at REAL)"""
    )
    return con


def is_used(con, url: str) -> bool:
    return con.execute("SELECT 1 FROM used WHERE url=?", (url,)).fetchone() is not None


def mark_used(con, url: str, title: str, fmt: str, folder: str, video_id: str | None = None):
    con.execute(
        "INSERT OR REPLACE INTO used VALUES (?,?,?,?,?,?)",
        (url, title, fmt, folder, video_id, time.time()),
    )
    con.commit()


def set_video_id(con, folder: str, video_id: str):
    con.execute("UPDATE used SET video_id=? WHERE folder=?", (video_id, folder))
    con.commit()
