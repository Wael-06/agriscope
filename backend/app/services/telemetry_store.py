import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from pydantic import ValidationError

from app.schemas.telemetry import TelemetryReading
from app.services.cache import DB_PATH


def _open_connection() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS device_telemetry (
            device_id TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            soil_moisture_top REAL,
            temp_c REAL,
            humidity_pct REAL,
            source TEXT,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS device_commands (
            device_id TEXT PRIMARY KEY,
            irrigate INTEGER,
            duration_sec INTEGER,
            consumed INTEGER DEFAULT 0,
            last_auto_triggered_at TIMESTAMP
        )
        """
    )
    command_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(device_commands)")
    }
    if "last_auto_triggered_at" not in command_columns:
        conn.execute(
            "ALTER TABLE device_commands ADD COLUMN last_auto_triggered_at TIMESTAMP"
        )
    return conn


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    conn = _open_connection()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _as_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fresh_reading(row: sqlite3.Row | None, max_age_seconds: int) -> TelemetryReading | None:
    if row is None:
        return None
    received_at = _as_datetime(row["received_at"])
    if received_at is None:
        return None
    age_seconds = (datetime.now(timezone.utc) - received_at).total_seconds()
    if age_seconds < 0 or age_seconds > max_age_seconds:
        return None

    try:
        return TelemetryReading.model_validate(
            {key: row[key] for key in (
                "device_id", "lat", "lon", "soil_moisture_top",
                "temp_c", "humidity_pct", "source",
            )}
        )
    except (ValidationError, TypeError, ValueError):
        return None


def upsert_telemetry(reading: TelemetryReading) -> None:
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO device_telemetry (
                device_id, lat, lon, soil_moisture_top, temp_c, humidity_pct, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                lat = excluded.lat,
                lon = excluded.lon,
                soil_moisture_top = excluded.soil_moisture_top,
                temp_c = excluded.temp_c,
                humidity_pct = excluded.humidity_pct,
                source = excluded.source,
                received_at = CURRENT_TIMESTAMP
            """,
            (
                reading.device_id,
                reading.lat,
                reading.lon,
                reading.soil_moisture_top,
                reading.temp_c,
                reading.humidity_pct,
                reading.source,
            ),
        )


def get_fresh_telemetry(
    device_id: str, max_age_seconds: int = 900
) -> TelemetryReading | None:
    try:
        with _connection() as conn:
            row = conn.execute(
                "SELECT * FROM device_telemetry WHERE device_id = ?", (device_id,)
            ).fetchone()
        return _fresh_reading(row, max_age_seconds)
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return None


def get_telemetry_status(device_id: str, max_age_seconds: int = 900) -> dict:
    try:
        with _connection() as conn:
            row = conn.execute(
                "SELECT * FROM device_telemetry WHERE device_id = ?", (device_id,)
            ).fetchone()
        received_at = _as_datetime(row["received_at"]) if row else None
        reading = _fresh_reading(row, max_age_seconds)
        return {
            "online": reading is not None,
            "last_seen": received_at.isoformat() if received_at else None,
            "reading": reading.model_dump() if reading else None,
        }
    except (sqlite3.Error, OSError, TypeError, ValueError):
        return {"online": False, "last_seen": None, "reading": None}


def set_command(
    device_id: str,
    irrigate: bool,
    duration_sec: int = 5,
    *,
    auto: bool = False,
) -> bool:
    with _connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if auto:
            cursor = conn.execute(
                """
                INSERT INTO device_commands (
                    device_id, irrigate, duration_sec, consumed, last_auto_triggered_at
                ) VALUES (?, ?, ?, 0, CURRENT_TIMESTAMP)
                ON CONFLICT(device_id) DO UPDATE SET
                    irrigate = excluded.irrigate,
                    duration_sec = excluded.duration_sec,
                    consumed = 0,
                    last_auto_triggered_at = CURRENT_TIMESTAMP
                WHERE device_commands.last_auto_triggered_at IS NULL
                   OR device_commands.last_auto_triggered_at
                      < datetime('now', '-10 minutes')
                """,
                (device_id, int(irrigate), duration_sec),
            )
            return cursor.rowcount == 1

        conn.execute(
            """
            INSERT INTO device_commands (device_id, irrigate, duration_sec, consumed)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(device_id) DO UPDATE SET
                irrigate = excluded.irrigate,
                duration_sec = excluded.duration_sec,
                consumed = 0
            """,
            (device_id, int(irrigate), duration_sec),
        )
        return True


def consume_command(device_id: str) -> dict[str, int | bool]:
    with _connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT irrigate, duration_sec, consumed
            FROM device_commands WHERE device_id = ?
            """,
            (device_id,),
        ).fetchone()
        if row and row["irrigate"] and not row["consumed"]:
            conn.execute(
                "UPDATE device_commands SET consumed = 1 WHERE device_id = ?",
                (device_id,),
            )
            return {"irrigate": True, "duration_sec": row["duration_sec"]}
    return {"irrigate": False, "duration_sec": 0}
