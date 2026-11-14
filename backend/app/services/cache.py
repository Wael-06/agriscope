import os
import shutil
import sqlite3
import json
from pathlib import Path
from typing import Optional, Any

BUNDLED_DB = Path(__file__).resolve().parents[2] / "farm_cache.db"
RUNTIME_DB = Path(os.getenv("CACHE_DB_PATH", "/tmp/farm_cache.db"))

def _ensure_db() -> Path:
    if not RUNTIME_DB.exists() and BUNDLED_DB.exists():
        RUNTIME_DB.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BUNDLED_DB, RUNTIME_DB)
    return RUNTIME_DB

def _get_conn() -> sqlite3.Connection:
    db_path = _ensure_db()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_cache (
            cache_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn

def get_cached(key: str) -> Optional[Any]:
    with _get_conn() as conn:
        row = conn.execute("SELECT payload FROM api_cache WHERE cache_key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

def set_cached(key: str, data: Any) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO api_cache (cache_key, payload) VALUES (?, ?)",
            (key, json.dumps(data))
        )
