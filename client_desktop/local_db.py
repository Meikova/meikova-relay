"""
Local SQLite Storage and Offline Cache for Meikova Relay Desktop Client.
Stores:
- User Preferences & Session Tokens
- Cached Device Fleet (accessible even when disconnected)
- Recent Quick Connect History
- Offline Sync Mutation Queue
"""

import os
import sys
import sqlite3
import json
import time
from pathlib import Path


def get_client_data_dir() -> Path:
    """Returns local app data directory for desktop client."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        data_dir = base / "MeikovaRelayClient"
    elif sys.platform == "darwin":
        data_dir = Path.home() / "Library" / "Application Support" / "MeikovaRelayClient"
    else:
        data_dir = Path.home() / ".local" / "share" / "meikova-relay-client"

    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


class ClientLocalDB:
    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            self.db_path = get_client_data_dir() / "client_cache.db"
        else:
            self.db_path = Path(db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS local_kv (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cached_devices (
                        id TEXT PRIMARY KEY,
                        device_name TEXT NOT NULL,
                        room_id TEXT NOT NULL,
                        pin TEXT,
                        os_info TEXT,
                        resolution TEXT,
                        is_favorite INTEGER DEFAULT 0,
                        last_seen REAL NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS quick_history (
                        room_id TEXT PRIMARY KEY,
                        device_name TEXT NOT NULL,
                        last_connected REAL NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS offline_sync_queue (
                        id TEXT PRIMARY KEY,
                        action TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        status TEXT DEFAULT 'pending'
                    );
                """)
                conn.commit()
        finally:
            conn.close()

    # --- Key-Value Store ---
    def set_kv(self, key: str, value: str | dict | list):
        val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
        now = time.time()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO local_kv (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                """, (key, val_str, now))
                conn.commit()
        finally:
            conn.close()

    def get_kv(self, key: str, default=None):
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM local_kv WHERE key = ?", (key,))
            row = cur.fetchone()
            if not row:
                return default
            val = row["value"]
            try:
                return json.loads(val)
            except Exception:
                return val
        finally:
            conn.close()

    # --- Cached Devices ---
    def cache_devices(self, devices: list[dict]):
        now = time.time()
        conn = self._get_connection()
        try:
            with conn:
                for d in devices:
                    conn.execute("""
                        INSERT INTO cached_devices (id, device_name, room_id, pin, os_info, resolution, last_seen)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            device_name = excluded.device_name,
                            room_id = excluded.room_id,
                            pin = COALESCE(excluded.pin, cached_devices.pin),
                            os_info = excluded.os_info,
                            resolution = excluded.resolution,
                            last_seen = excluded.last_seen
                    """, (
                        d.get("id"),
                        d.get("device_name", "Unknown"),
                        d.get("room_id", ""),
                        d.get("pin", ""),
                        d.get("os_info", "Windows"),
                        d.get("resolution", "1920x1080"),
                        now
                    ))
                conn.commit()
        finally:
            conn.close()

    def get_cached_devices(self) -> list[dict]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM cached_devices ORDER BY is_favorite DESC, last_seen DESC")
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    # --- Quick Connect History ---
    def record_connection(self, room_id: str, device_name: str = ""):
        now = time.time()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO quick_history (room_id, device_name, last_connected)
                    VALUES (?, ?, ?)
                    ON CONFLICT(room_id) DO UPDATE SET
                        device_name = excluded.device_name,
                        last_connected = excluded.last_connected
                """, (room_id, device_name or room_id, now))
                conn.commit()
        finally:
            conn.close()

    def get_recent_history(self, limit: int = 10) -> list[dict]:
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM quick_history ORDER BY last_connected DESC LIMIT ?", (limit,))
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
