"""
SQLite cache backend for local development.

Stores cache entries (JSON data + binary artifacts) in a single SQLite DB.
Auto-purges expired entries on every read operation.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

from .base import CacheBackend

logger = logging.getLogger(__name__)

# Default DB path: MarginCall/cache/MarginCall_cache.db
_DEFAULT_DB_DIR = (
    Path(os.path.dirname(os.path.abspath(__file__))).parent.parent / "cache"
)
_DEFAULT_DB_PATH = _DEFAULT_DB_DIR / "MarginCall_cache.db"

# Auto-purge at most once every 5 minutes to avoid overhead
_PURGE_INTERVAL_SECONDS = 300

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cache (
    cache_key    TEXT PRIMARY KEY,
    data         BLOB NOT NULL,
    mime_type    TEXT DEFAULT 'application/json',
    ttl_seconds  INTEGER NOT NULL,
    created_at   REAL NOT NULL,
    expires_at   REAL NOT NULL,
    ticker       TEXT DEFAULT '',
    data_type    TEXT DEFAULT ''
);
"""

_CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at);",
    "CREATE INDEX IF NOT EXISTS idx_cache_ticker ON cache(ticker);",
    "CREATE INDEX IF NOT EXISTS idx_cache_ticker_type ON cache(ticker, data_type);",
]


class SQLiteCacheBackend(CacheBackend):
    """SQLite-based cache with auto-purge of expired entries."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_purge_time: float = 0
        self._init_db()

    def _init_db(self) -> None:
        """Create tables and indexes if they don't exist."""
        with self._get_conn() as conn:
            conn.execute(_CREATE_TABLE_SQL)
            for idx_sql in _CREATE_INDEXES_SQL:
                conn.execute(idx_sql)
            conn.commit()
        logger.info("Cache DB initialized at %s", self._db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new connection (SQLite is thread-safe with separate connections)."""
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read/write
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _maybe_auto_purge(self) -> None:
        """Run purge if enough time has passed since last purge."""
        now = time.time()
        if now - self._last_purge_time > _PURGE_INTERVAL_SECONDS:
            self._last_purge_time = now
            try:
                with self._get_conn() as conn:
                    cursor = conn.execute(
                        "DELETE FROM cache WHERE expires_at < ?", (now,)
                    )
                    deleted = cursor.rowcount
                    conn.commit()
                    if deleted > 0:
                        logger.info("Auto-purged %d expired cache entries", deleted)
            except Exception as e:
                logger.warning("Auto-purge failed: %s", e)

    # ── CacheBackend interface ──────────────────────────────────────────

    async def get(self, key: str) -> bytes | None:
        """Retrieve cached data. Returns None if missing or expired."""
        self._maybe_auto_purge()
        now = time.time()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT data FROM cache WHERE cache_key = ? AND expires_at > ?",
                (key, now),
            ).fetchone()
        if row is None:
            logger.debug("Cache MISS: %s", key)
            return None
        logger.info("Cache HIT: %s", key)
        return row[0]

    async def put(
        self,
        key: str,
        data: bytes,
        ttl_seconds: int,
        ticker: str = "",
        data_type: str = "",
        mime_type: str = "application/json",
    ) -> None:
        """Store data with TTL. Overwrites existing entry."""
        now = time.time()
        expires_at = now + ttl_seconds
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO cache (cache_key, data, mime_type, ttl_seconds,
                                   created_at, expires_at, ticker, data_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    data = excluded.data,
                    mime_type = excluded.mime_type,
                    ttl_seconds = excluded.ttl_seconds,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at
                """,
                (
                    key,
                    data,
                    mime_type,
                    ttl_seconds,
                    now,
                    expires_at,
                    ticker.upper(),
                    data_type,
                ),
            )
            conn.commit()
        logger.info("Cache PUT: %s (TTL=%ds)", key, ttl_seconds)

    async def delete(self, key: str) -> None:
        """Delete a single cache entry."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
            conn.commit()
        logger.debug("Cache DELETE: %s", key)

    async def exists(self, key: str) -> bool:
        """Check if a valid (non-expired) entry exists."""
        now = time.time()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM cache WHERE cache_key = ? AND expires_at > ?",
                (key, now),
            ).fetchone()
        return row is not None

    async def invalidate_ticker(self, ticker: str) -> int:
        """Delete ALL cache entries for a ticker (used for real-time refresh)."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "DELETE FROM cache WHERE ticker = ?", (ticker.upper(),)
            )
            deleted = cursor.rowcount
            conn.commit()
        logger.info("Cache INVALIDATE ticker=%s, deleted=%d entries", ticker, deleted)
        return deleted

    async def purge_expired(self) -> int:
        """Delete all expired entries."""
        now = time.time()
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
            deleted = cursor.rowcount
            conn.commit()
        if deleted > 0:
            logger.info("Cache PURGE: removed %d expired entries", deleted)
        self._last_purge_time = now
        return deleted

    async def close(self) -> None:
        """No persistent connection to close (we use per-call connections)."""
        pass

    async def get_stats(self) -> dict:
        """Return distinct ticker count, total entries, and list of tickers (non-expired only)."""
        now = time.time()
        with self._get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM cache WHERE expires_at > ?", (now,)
            ).fetchone()[0]
            tickers_row = conn.execute(
                "SELECT DISTINCT ticker FROM cache WHERE expires_at > ? AND ticker != '' ORDER BY ticker",
                (now,),
            ).fetchall()
        tickers = [r[0] for r in tickers_row]
        return {
            "distinct_stocks": len(tickers),
            "total_entries": total,
            "tickers": tickers,
        }

    # ── JSON convenience methods ────────────────────────────────────────

    async def get_json(self, key: str) -> dict | None:
        """Retrieve and deserialize JSON data from cache."""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Cache entry %s is not valid JSON, deleting", key)
            await self.delete(key)
            return None

    async def put_json(
        self,
        key: str,
        data: dict,
        ttl_seconds: int,
        ticker: str = "",
        data_type: str = "",
    ) -> None:
        """Serialize dict to JSON and store in cache."""
        raw = json.dumps(data, default=str).encode("utf-8")
        await self.put(
            key,
            raw,
            ttl_seconds,
            ticker=ticker,
            data_type=data_type,
            mime_type="application/json",
        )
