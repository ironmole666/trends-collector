import json
import hashlib
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trends (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    source      TEXT    NOT NULL,
                    title       TEXT    NOT NULL,
                    url         TEXT,
                    rank        INTEGER DEFAULT 0,
                    score       INTEGER DEFAULT 0,
                    comments    INTEGER DEFAULT 0,
                    author      TEXT DEFAULT '',
                    region      TEXT DEFAULT '',
                    created_at  TEXT DEFAULT '',
                    collected_at TEXT DEFAULT (datetime('now')),
                    ip          TEXT DEFAULT '',
                    content_hash TEXT UNIQUE,
                    raw_data    TEXT DEFAULT ''
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_collected ON trends(source, collected_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_collected ON trends(collected_at)")
            conn.commit()
        finally:
            conn.close()

    def _content_hash(self, source: str, title: str, url: str) -> str:
        raw = f"{source}:{title}:{url}"
        return hashlib.md5(raw.encode()).hexdigest()

    def save(self, source: str, title: str, url: str = "", rank: int = 0,
             score: int = 0, comments: int = 0, author: str = "",
             region: str = "", created_at: str = "", ip: str = "",
             raw_data: str = "") -> bool:
        conn = self._get_conn()
        try:
            ch = self._content_hash(source, title, url)
            conn.execute("""
                INSERT OR IGNORE INTO trends
                    (source, title, url, rank, score, comments,
                     author, region, created_at, ip, content_hash, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (source, title, url, rank, score, comments,
                  author, region, created_at, ip, ch, raw_data))
            conn.commit()
            return conn.total_changes > 0
        except sqlite3.Error as e:
            logger.error(f"DB save error: {e}")
            return False
        finally:
            conn.close()

    def batch_save(self, items: list) -> int:
        count = 0
        for item in items:
            if self.save(**item):
                count += 1
        return count

    def get_recent(self, source: str = None, limit: int = 50, hours: int = 24) -> list:
        conn = self._get_conn()
        try:
            if source:
                rows = conn.execute("""
                    SELECT * FROM trends
                    WHERE source = ? AND collected_at > datetime('now', ?)
                    ORDER BY score DESC, collected_at DESC LIMIT ?
                """, (source, f'-{hours} hours', limit))
            else:
                rows = conn.execute("""
                    SELECT * FROM trends
                    WHERE collected_at > datetime('now', ?)
                    ORDER BY score DESC, collected_at DESC LIMIT ?
                """, (f'-{hours} hours', limit))
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_stats(self, hours: int = 24) -> dict:
        conn = self._get_conn()
        try:
            by_source = conn.execute("""
                SELECT source, COUNT(*) as count
                FROM trends
                WHERE collected_at > datetime('now', ?)
                GROUP BY source ORDER BY count DESC
            """, (f'-{hours} hours',)).fetchall()
            total = conn.execute("""
                SELECT COUNT(*) as count
                FROM trends
                WHERE collected_at > datetime('now', ?)
            """, (f'-{hours} hours',)).fetchone()["count"]
            return {"total": total, "by_source": {r["source"]: r["count"] for r in by_source}}
        finally:
            conn.close()

    def get_top(self, hours: int = 24, limit: int = 20) -> list:
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT title, url, score, source, region
                FROM trends
                WHERE collected_at > datetime('now', ?)
                ORDER BY score DESC LIMIT ?
            """, (f'-{hours} hours', limit))
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def enforce_retention(self, days: int = 30):
        conn = self._get_conn()
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            conn.execute("DELETE FROM trends WHERE collected_at < ?", (cutoff,))
            conn.commit()
            logger.info(f"Retention: purged records before {cutoff}")
        finally:
            conn.close()

    def get_sources_summary(self) -> list:
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT source, COUNT(*) as total, MAX(collected_at) as last_seen
                FROM trends GROUP BY source ORDER BY total DESC
            """).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
