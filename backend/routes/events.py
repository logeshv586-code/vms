"""Event configuration, persistence and query API.

Runtime event records are stored in SQLite/WAL instead of a shared JSON file.
The legacy ``get_event_records`` / ``save_event_records`` functions are kept so
PatternEngine and older callers remain compatible; ``save_event_records`` uses
UPSERT semantics and therefore does not erase events written concurrently by
another camera thread.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
EVENTS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "events_configuration.json")
DATA_DIR = os.path.join(WORKSPACE_ROOT, "backend", "data")
EVENTS_DB_PATH = os.getenv("VMS_EVENTS_DB_PATH", os.path.join(DATA_DIR, "events.db"))
LEGACY_EVENT_RECORDS_PATH = os.path.join(DATA_DIR, "event_records.json")
PROOFS_DIR = os.path.join(DATA_DIR, "proofs")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PROOFS_DIR, exist_ok=True)

router = APIRouter(prefix="/api/augment", tags=["events"])
_CONFIG_LOCK = threading.RLock()
_DB_INIT_LOCK = threading.Lock()
_DB_INITIALIZED = False


DEFAULT_RULES = [
    {"id": 1, "name": "Appearance Search", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
    {"id": 2, "name": "Camera Tamper", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
    {"id": 3, "name": "Chain/Handbag Snatching", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": True},
    {"id": 4, "name": "Crowd Detection", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
    {"id": 5, "name": "Eve Teasing", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": True},
    {"id": 6, "name": "Face Capture", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": False},
    {"id": 7, "name": "Face Recognition", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
    {"id": 8, "name": "Gesture Detection", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
    {"id": 9, "name": "Graffiti and Vandalism Detection", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": False},
    {"id": 10, "name": "Intrusion Detection", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
    {"id": 11, "name": "Lakshmanrekha Crossing", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": False},
    {"id": 12, "name": "Loitering", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
    {"id": 13, "name": "Mobile Snatching", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": True},
    {"id": 14, "name": "Object Classification", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
    {"id": 15, "name": "People Fighting", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
    {"id": 16, "name": "Person Collapsing", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": True},
    {"id": 17, "name": "Strike / Morcha / Hartal / Procession", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": False},
    {"id": 18, "name": "Suspected Appearance", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
    {"id": 19, "name": "Unattended Object", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
    {"id": 20, "name": "Women Surrounded by Men", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
    {"id": 21, "name": "Women/Infant Abduction", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
    {"id": 22, "name": "Vehicle Monitoring", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
    {"id": 23, "name": "Zone Monitoring", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
]


class EventRule(BaseModel):
    id: int
    name: str
    enabled: bool
    hotlisted: bool
    show_popup: bool
    play_audio: bool


class EventRuleSet(BaseModel):
    rules: List[EventRule]


class DetectionRuleToggle(BaseModel):
    event: str
    enabled: bool


class EventStatistic(BaseModel):
    event_id: int
    event_name: str
    count: int
    camera_id: Optional[str] = None
    timestamp: str


class EventStatisticsResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None


def _atomic_json_write(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def ensure_events_config() -> None:
    with _CONFIG_LOCK:
        if not os.path.exists(EVENTS_CONFIG_PATH):
            _atomic_json_write(EVENTS_CONFIG_PATH, {"rules": DEFAULT_RULES, "statistics": []})
            logger.info("Created default event configuration at %s", EVENTS_CONFIG_PATH)


def _read_event_config() -> Dict[str, Any]:
    ensure_events_config()
    with _CONFIG_LOCK:
        with open(EVENTS_CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("events_configuration.json must contain an object")
    data.setdefault("rules", [])
    return data


@contextmanager
def _db():
    _ensure_db()
    connection = sqlite3.connect(EVENTS_DB_PATH, timeout=15, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=15000")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _ensure_db() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    with _DB_INIT_LOCK:
        if _DB_INITIALIZED:
            return
        os.makedirs(os.path.dirname(EVENTS_DB_PATH), exist_ok=True)
        connection = sqlite3.connect(EVENTS_DB_PATH, timeout=15, check_same_thread=False)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    rule_name TEXT,
                    camera_name TEXT,
                    camera_id TEXT,
                    location TEXT,
                    priority TEXT,
                    duration REAL,
                    status TEXT,
                    category TEXT,
                    confidence REAL,
                    confidence_source TEXT,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    message TEXT,
                    video_proof_url TEXT,
                    resolved_at TEXT,
                    record_json TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_events_rule_camera ON events(rule_name, camera_id)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_events_status ON events(status)")
            connection.commit()
        finally:
            connection.close()
        _DB_INITIALIZED = True
        _migrate_legacy_json_once()


def _normalise_record(record: Dict[str, Any]) -> Dict[str, Any]:
    value = dict(record or {})
    value["event_id"] = str(value.get("event_id") or "").strip()
    if not value["event_id"]:
        raise ValueError("event_id is required")
    value.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    value.setdefault("status", "Active")
    value.setdefault("acknowledged", False)
    return value


def _upsert_record(connection: sqlite3.Connection, record: Dict[str, Any]) -> None:
    record = _normalise_record(record)
    connection.execute(
        """
        INSERT INTO events (
            event_id, created_at, rule_name, camera_name, camera_id, location,
            priority, duration, status, category, confidence, confidence_source,
            acknowledged, message, video_proof_url, resolved_at, record_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(event_id) DO UPDATE SET
            created_at=excluded.created_at,
            rule_name=excluded.rule_name,
            camera_name=excluded.camera_name,
            camera_id=excluded.camera_id,
            location=excluded.location,
            priority=excluded.priority,
            duration=excluded.duration,
            status=excluded.status,
            category=excluded.category,
            confidence=excluded.confidence,
            confidence_source=excluded.confidence_source,
            acknowledged=excluded.acknowledged,
            message=excluded.message,
            video_proof_url=excluded.video_proof_url,
            resolved_at=excluded.resolved_at,
            record_json=excluded.record_json
        """,
        (
            record["event_id"],
            str(record.get("created_at") or ""),
            record.get("rule_name"),
            record.get("camera_name"),
            record.get("camera_id"),
            record.get("location"),
            record.get("priority"),
            record.get("duration"),
            record.get("status"),
            record.get("category"),
            record.get("confidence"),
            record.get("confidence_source"),
            1 if record.get("acknowledged") else 0,
            record.get("message"),
            record.get("video_proof_url"),
            record.get("resolved_at"),
            json.dumps(record, ensure_ascii=False, separators=(",", ":")),
        ),
    )


def _migrate_legacy_json_once() -> None:
    if not os.path.isfile(LEGACY_EVENT_RECORDS_PATH):
        return
    try:
        connection = sqlite3.connect(EVENTS_DB_PATH, timeout=15, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            if connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] != 0:
                return
            with open(LEGACY_EVENT_RECORDS_PATH, "r", encoding="utf-8") as handle:
                records = json.load(handle)
            if isinstance(records, list):
                for record in records:
                    if isinstance(record, dict) and record.get("event_id"):
                        _upsert_record(connection, record)
                connection.commit()
                logger.info("Migrated %d legacy VMS events to SQLite", len(records))
        finally:
            connection.close()
    except Exception as exc:
        logger.warning("Legacy event migration skipped: %s", exc)


def get_event_records() -> List[Dict[str, Any]]:
    try:
        with _db() as connection:
            rows = connection.execute("SELECT record_json FROM events ORDER BY created_at DESC").fetchall()
        output: List[Dict[str, Any]] = []
        for row in rows:
            try:
                output.append(json.loads(row["record_json"]))
            except Exception:
                logger.warning("Skipping corrupt event row")
        return output
    except Exception as exc:
        logger.error("Error reading event records: %s", exc)
        return []


def save_event_records(records: List[Dict[str, Any]]) -> bool:
    """Compatibility writer using atomic per-event UPSERTs.

    Existing callers may pass a stale snapshot plus one changed/new event.  We
    intentionally do not delete rows missing from that snapshot, so concurrent
    camera writers cannot erase one another's newly-created events.
    """
    try:
        with _db() as connection:
            for record in records or []:
                if isinstance(record, dict) and record.get("event_id"):
                    _upsert_record(connection, record)
        return True
    except Exception as exc:
        logger.error("Error writing event records: %s", exc)
        return False


def update_event_record(event_id: str, updates: Dict[str, Any]) -> bool:
    with _db() as connection:
        row = connection.execute("SELECT record_json FROM events WHERE event_id=?", (event_id,)).fetchone()
        if row is None:
            return False
        record = json.loads(row["record_json"])
        record.update(updates)
        _upsert_record(connection, record)
    return True


def find_recent_event(rule_name: str, camera_id: str, within_seconds: int = 300) -> Optional[Dict[str, Any]]:
    """Return newest matching event inside a deduplication window."""
    with _db() as connection:
        rows = connection.execute(
            "SELECT record_json, created_at FROM events WHERE rule_name=? AND camera_id=? ORDER BY created_at DESC LIMIT 5",
            (rule_name, camera_id),
        ).fetchall()
    now = datetime.now(timezone.utc)
    for row in rows:
        try:
            created = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if (now - created).total_seconds() <= within_seconds:
                return json.loads(row["record_json"])
        except Exception:
            continue
    return None


@router.get("/events/rules")
async def get_event_rules():
    try:
        data = _read_event_config()
        return {"success": True, "data": {"rules": data["rules"]}, "message": "Event rules retrieved successfully"}
    except Exception as exc:
        logger.exception("Error getting event rules")
        return {"success": False, "error": str(exc)}


@router.post("/events/rules")
async def update_event_rules(rule_set: EventRuleSet):
    try:
        data = _read_event_config()
        data["rules"] = [rule.model_dump() if hasattr(rule, "model_dump") else rule.dict() for rule in rule_set.rules]
        with _CONFIG_LOCK:
            _atomic_json_write(EVENTS_CONFIG_PATH, data)
        return {"success": True, "message": "Event rules updated successfully"}
    except Exception as exc:
        logger.exception("Error updating event rules")
        return {"success": False, "error": str(exc)}


@router.post("/detection-rule")
async def toggle_detection_rule(rule_toggle: DetectionRuleToggle):
    try:
        data = _read_event_config()
        for rule in data["rules"]:
            if rule.get("name") == rule_toggle.event:
                rule["enabled"] = bool(rule_toggle.enabled)
                with _CONFIG_LOCK:
                    _atomic_json_write(EVENTS_CONFIG_PATH, data)
                return {
                    "success": True,
                    "message": f"Detection rule '{rule_toggle.event}' {'enabled' if rule_toggle.enabled else 'disabled'} successfully",
                }
        return {"success": False, "error": f"Rule '{rule_toggle.event}' not found"}
    except Exception as exc:
        logger.exception("Error toggling event rule")
        return {"success": False, "error": str(exc)}


@router.get("/events/statistics")
async def get_event_statistics(camera_id: Optional[str] = None, event_id: Optional[int] = None):
    """Return statistics calculated from persisted events, never mock data."""
    try:
        config = _read_event_config()
        rule_ids = {str(rule.get("name")): int(rule.get("id")) for rule in config.get("rules", []) if rule.get("id") is not None}
        clauses: List[str] = []
        params: List[Any] = []
        if camera_id:
            clauses.append("camera_id=?")
            params.append(camera_id)
        if event_id:
            names = [name for name, rid in rule_ids.items() if rid == int(event_id)]
            if not names:
                return {"success": True, "data": {"statistics": []}, "message": "Event statistics retrieved successfully"}
            clauses.append("rule_name=?")
            params.append(names[0])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with _db() as connection:
            rows = connection.execute(
                f"""
                SELECT rule_name, camera_id, COUNT(*) AS count, MAX(created_at) AS latest
                FROM events {where}
                GROUP BY rule_name, camera_id
                ORDER BY count DESC, latest DESC
                """,
                params,
            ).fetchall()
        statistics = [
            {
                "event_id": rule_ids.get(row["rule_name"], 0),
                "event_name": row["rule_name"] or "Unknown Event",
                "count": int(row["count"]),
                "camera_id": row["camera_id"],
                "timestamp": row["latest"],
            }
            for row in rows
        ]
        return {"success": True, "data": {"statistics": statistics}, "message": "Event statistics retrieved successfully"}
    except Exception as exc:
        logger.exception("Error getting event statistics")
        return {"success": False, "error": str(exc)}


@router.get("/events/current")
async def get_current_events():
    records = [record for record in get_event_records() if record.get("status") in {"Active", "Acknowledged"}]
    records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"success": True, "data": records, "message": "Current events retrieved successfully"}


def rule_matches(filter_rule: str, event_rule: str) -> bool:
    if not filter_rule or filter_rule in {"all", "All Rules"}:
        return True
    if not event_rule:
        return False
    left, right = filter_rule.lower().strip(), event_rule.lower().strip()
    if left == right or left in right or right in left:
        return True
    return left.split("(")[0].strip() in right.split("(")[0].strip() or right.split("(")[0].strip() in left.split("(")[0].strip()


def category_matches(filter_cat: str, event_cat: str) -> bool:
    if not filter_cat or filter_cat in {"all", "All Categories"}:
        return True
    if not event_cat:
        return False
    left, right = filter_cat.lower().strip(), event_cat.lower().strip()
    return left == right or left in right or right in left


@router.get("/events/search")
async def search_events(
    category: Optional[str] = None,
    rule: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    camera: Optional[str] = None,
    location: Optional[str] = None,
    acknowledged: Optional[str] = None,
    dateRange: Optional[str] = None,
):
    try:
        filtered = get_event_records()
        if category and category not in {"all", "All Categories"}:
            filtered = [item for item in filtered if category_matches(category, item.get("category", ""))]
        if rule and rule not in {"all", "All Rules"}:
            filtered = [item for item in filtered if rule_matches(rule, item.get("rule_name", ""))]
        if priority and priority not in {"all", "All Priorities"}:
            filtered = [item for item in filtered if str(item.get("priority", "")).lower() == priority.lower()]
        if status and status not in {"all", "All Statuses"}:
            filtered = [item for item in filtered if str(item.get("status", "")).lower() == status.lower()]
        if camera and camera not in {"all", "All Cameras"}:
            query = camera.lower().replace(" (", "_").replace(")", "")
            filtered = [item for item in filtered if query in str(item.get("camera_name", "")).lower() or query in str(item.get("camera_id", "")).lower()]
        if location and location not in {"all", "All Locations"}:
            filtered = [item for item in filtered if location.lower() in str(item.get("location", "")).lower()]
        if acknowledged and acknowledged not in {"all", "All Events"}:
            expected = acknowledged.lower() in {"acknowledged", "true"}
            filtered = [item for item in filtered if bool(item.get("acknowledged")) == expected]
        filtered.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return {"success": True, "data": filtered, "message": "Events searched successfully"}
    except Exception as exc:
        logger.exception("Error searching events")
        return {"success": False, "error": str(exc)}


@router.post("/events/acknowledge/{event_id}")
async def acknowledge_event(event_id: str):
    try:
        records = get_event_records()
        current = next((item for item in records if item.get("event_id") == event_id), None)
        if current is None:
            return {"success": False, "error": "Event not found"}
        updates = {"acknowledged": True}
        if current.get("status") == "Active":
            updates["status"] = "Acknowledged"
        update_event_record(event_id, updates)
        return {"success": True, "message": "Event acknowledged"}
    except Exception as exc:
        logger.exception("Error acknowledging event")
        return {"success": False, "error": str(exc)}


@router.post("/events/resolve/{event_id}")
async def resolve_event(event_id: str):
    try:
        if not update_event_record(
            event_id,
            {"status": "Resolved", "resolved_at": datetime.now(timezone.utc).isoformat()},
        ):
            return {"success": False, "error": "Event not found"}
        return {"success": True, "message": "Event resolved"}
    except Exception as exc:
        logger.exception("Error resolving event")
        return {"success": False, "error": str(exc)}


@router.get("/events/proofs/{filename}")
async def get_video_proof(filename: str):
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Invalid proof filename")
    proof_root = Path(PROOFS_DIR).resolve()
    file_path = (proof_root / safe_name).resolve()
    if proof_root not in file_path.parents:
        raise HTTPException(status_code=400, detail="Invalid proof path")
    if file_path.exists() and file_path.is_file() and file_path.stat().st_size > 0:
        return FileResponse(str(file_path), media_type="video/mp4", filename=safe_name)
    raise HTTPException(status_code=404, detail="Video proof not found or empty")
