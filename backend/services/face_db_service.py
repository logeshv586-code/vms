"""
Face Database Service
=====================
Manages SQLite storage for:
  - Face capture events (image path, quality, stream, timestamp)
  - Recognition match events (identity, confidence, timestamp)
  - Criminal / suspect watchlist entries
  - Unknown face gallery for manual tagging

All tables are created on first import; callers never need to run migrations.
"""

import json
import logging
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Default DB path ──────────────────────────────────────────────────────────
_DEFAULT_DB_DIR = os.path.join(os.path.dirname(__file__), "..", "face_db")
_DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "face_captures.db")


class FaceDBService:
    """
    Thread-safe SQLite service for face capture & recognition persistence.

    Usage:
        from services.face_db_service import face_db_service
        face_db_service.insert_capture(...)
    """

    # ── DDL ─────────────────────────────────────────────────────────────────

    _CREATE_CAPTURES = """
    CREATE TABLE IF NOT EXISTS face_captures (
        id          TEXT PRIMARY KEY,
        stream_id   TEXT NOT NULL,
        camera_id   TEXT,
        timestamp   REAL NOT NULL,
        image_path  TEXT,
        blur_score  REAL,
        face_width  INTEGER,
        face_height INTEGER,
        confidence  REAL,
        bbox_x1     INTEGER,
        bbox_y1     INTEGER,
        bbox_x2     INTEGER,
        bbox_y2     INTEGER,
        tagged_as   TEXT DEFAULT NULL,
        created_at  REAL NOT NULL
    );
    """

    _CREATE_RECOGNITION_LOG = """
    CREATE TABLE IF NOT EXISTS recognition_log (
        id              TEXT PRIMARY KEY,
        capture_id      TEXT,
        stream_id       TEXT NOT NULL,
        identity        TEXT NOT NULL,
        category        TEXT DEFAULT 'unknown',
        confidence      REAL,
        distance        REAL,
        timestamp       REAL NOT NULL,
        is_watchlisted  INTEGER DEFAULT 0,
        created_at      REAL NOT NULL,
        FOREIGN KEY (capture_id) REFERENCES face_captures(id)
    );
    """

    _CREATE_WATCHLIST = """
    CREATE TABLE IF NOT EXISTS watchlist (
        id            TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        alias         TEXT,
        category      TEXT DEFAULT 'suspect',
        notes         TEXT,
        encoding_path TEXT,
        image_path    TEXT,
        added_at      REAL NOT NULL,
        is_active     INTEGER DEFAULT 1
    );
    """

    _CREATE_GESTURE_LOG = """
    CREATE TABLE IF NOT EXISTS gesture_log (
        id          TEXT PRIMARY KEY,
        stream_id   TEXT NOT NULL,
        timestamp   REAL NOT NULL,
        gesture     TEXT NOT NULL,
        category    TEXT NOT NULL,
        confidence  REAL,
        bbox        TEXT,
        fingers_up  TEXT,
        asl_letter  TEXT,
        created_at  REAL NOT NULL
    );
    """

    def __init__(self, db_path: str = _DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialise()

    # ── Context manager ─────────────────────────────────────────────────────

    @contextmanager
    def _conn(self):
        """Yield a thread-local connection with WAL mode for concurrency."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialise(self) -> None:
        """Create all tables if they don't already exist."""
        with self._conn() as conn:
            conn.execute(self._CREATE_CAPTURES)
            conn.execute(self._CREATE_RECOGNITION_LOG)
            conn.execute(self._CREATE_WATCHLIST)
            conn.execute(self._CREATE_GESTURE_LOG)
        logger.info("FaceDBService initialised at %s", self.db_path)

    # ── Face captures ────────────────────────────────────────────────────────

    def insert_capture(
        self,
        stream_id: str,
        image_path: str,
        confidence: float,
        bbox: List[int],
        quality: Dict[str, Any],
        camera_id: str = None,
        timestamp: float = None,
    ) -> str:
        """Persist a face capture event. Returns the new record ID."""
        record_id = uuid.uuid4().hex
        now = time.time()
        ts = timestamp or now
        x1, y1, x2, y2 = (bbox + [0, 0, 0, 0])[:4]

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO face_captures
                    (id, stream_id, camera_id, timestamp, image_path,
                     blur_score, face_width, face_height, confidence,
                     bbox_x1, bbox_y1, bbox_x2, bbox_y2, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record_id,
                    stream_id,
                    camera_id,
                    ts,
                    image_path,
                    quality.get("blur_score"),
                    quality.get("face_width"),
                    quality.get("face_height"),
                    confidence,
                    x1, y1, x2, y2,
                    now,
                ),
            )
        logger.debug("Inserted face capture %s for stream %s", record_id, stream_id)
        return record_id

    def list_captures(
        self,
        stream_id: str = None,
        limit: int = 100,
        offset: int = 0,
        since: float = None,
    ) -> List[Dict[str, Any]]:
        """Return face captures, optionally filtered by stream and time."""
        clauses = []
        params: List[Any] = []

        if stream_id:
            clauses.append("stream_id = ?")
            params.append(stream_id)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params += [limit, offset]

        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM face_captures {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def tag_capture(self, capture_id: str, identity: str) -> bool:
        """Tag a previously unknown capture with an identity name."""
        with self._conn() as conn:
            result = conn.execute(
                "UPDATE face_captures SET tagged_as = ? WHERE id = ?",
                (identity, capture_id),
            )
        return result.rowcount > 0

    def delete_capture(self, capture_id: str) -> bool:
        """Delete a capture record (image file cleanup is caller's responsibility)."""
        with self._conn() as conn:
            result = conn.execute(
                "DELETE FROM face_captures WHERE id = ?", (capture_id,)
            )
        return result.rowcount > 0

    # ── Recognition log ──────────────────────────────────────────────────────

    def insert_recognition(
        self,
        stream_id: str,
        identity: str,
        confidence: float,
        distance: float = None,
        category: str = "person",
        capture_id: str = None,
        is_watchlisted: bool = False,
        timestamp: float = None,
    ) -> str:
        """Log a face recognition match event."""
        record_id = uuid.uuid4().hex
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO recognition_log
                    (id, capture_id, stream_id, identity, category,
                     confidence, distance, timestamp, is_watchlisted, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record_id,
                    capture_id,
                    stream_id,
                    identity,
                    category,
                    confidence,
                    distance,
                    timestamp or now,
                    1 if is_watchlisted else 0,
                    now,
                ),
            )
        return record_id

    def list_recognitions(
        self,
        stream_id: str = None,
        identity: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if stream_id:
            clauses.append("stream_id = ?")
            params.append(stream_id)
        if identity:
            clauses.append("identity = ?")
            params.append(identity)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params += [limit, offset]

        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM recognition_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recognition_summary(self) -> Dict[str, Any]:
        """Return aggregate statistics for the recognition dashboard."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM recognition_log").fetchone()[0]
            watchlisted = conn.execute(
                "SELECT COUNT(*) FROM recognition_log WHERE is_watchlisted=1"
            ).fetchone()[0]
            unknowns = conn.execute(
                "SELECT COUNT(*) FROM face_captures WHERE tagged_as IS NULL"
            ).fetchone()[0]
            captures_total = conn.execute(
                "SELECT COUNT(*) FROM face_captures"
            ).fetchone()[0]
        return {
            "total_recognitions": total,
            "watchlisted_detections": watchlisted,
            "unknown_faces": unknowns,
            "total_captures": captures_total,
        }

    # ── Watchlist ────────────────────────────────────────────────────────────

    def add_to_watchlist(
        self,
        name: str,
        alias: str = None,
        category: str = "suspect",
        notes: str = None,
        encoding_path: str = None,
        image_path: str = None,
    ) -> str:
        """Add a person to the criminal / suspect watchlist."""
        record_id = uuid.uuid4().hex
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO watchlist
                    (id, name, alias, category, notes, encoding_path, image_path, added_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (record_id, name, alias, category, notes, encoding_path, image_path, time.time()),
            )
        logger.info("Added '%s' to watchlist (category: %s)", name, category)
        return record_id

    def get_watchlist(self, active_only: bool = True) -> List[Dict[str, Any]]:
        where = "WHERE is_active=1" if active_only else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM watchlist {where} ORDER BY added_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def remove_from_watchlist(self, watchlist_id: str) -> bool:
        with self._conn() as conn:
            result = conn.execute(
                "UPDATE watchlist SET is_active=0 WHERE id=?", (watchlist_id,)
            )
        return result.rowcount > 0

    def is_watchlisted(self, name: str) -> bool:
        """Check if a recognised identity name is on the active watchlist."""
        with self._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM watchlist WHERE name=? AND is_active=1", (name,)
            ).fetchone()[0]
        return count > 0

    # ── Gesture log ──────────────────────────────────────────────────────────

    def insert_gesture(
        self,
        stream_id: str,
        gesture: str,
        category: str,
        confidence: float,
        bbox: List[int] = None,
        fingers_up: List[bool] = None,
        asl_letter: str = None,
        timestamp: float = None,
    ) -> str:
        """Log a detected hand gesture event."""
        record_id = uuid.uuid4().hex
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO gesture_log
                    (id, stream_id, timestamp, gesture, category, confidence,
                     bbox, fingers_up, asl_letter, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record_id,
                    stream_id,
                    timestamp or now,
                    gesture,
                    category,
                    confidence,
                    json.dumps(bbox) if bbox else None,
                    json.dumps(fingers_up) if fingers_up is not None else None,
                    asl_letter,
                    now,
                ),
            )
        return record_id

    def list_gestures(
        self,
        stream_id: str = None,
        category: str = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if stream_id:
            clauses.append("stream_id = ?")
            params.append(stream_id)
        if category:
            clauses.append("category = ?")
            params.append(category)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params += [limit, offset]

        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM gesture_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            if d.get("bbox"):
                try:
                    d["bbox"] = json.loads(d["bbox"])
                except Exception:
                    pass
            if d.get("fingers_up"):
                try:
                    d["fingers_up"] = json.loads(d["fingers_up"])
                except Exception:
                    pass
            result.append(d)
        return result

    def get_gesture_summary(self, stream_id: str = None) -> Dict[str, Any]:
        where = f"WHERE stream_id='{stream_id}'" if stream_id else ""
        with self._conn() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM gesture_log {where}"
            ).fetchone()[0]
            sos = conn.execute(
                f"SELECT COUNT(*) FROM gesture_log {where} {'AND' if where else 'WHERE'} category='help'"
            ).fetchone()[0]
            threat = conn.execute(
                f"SELECT COUNT(*) FROM gesture_log {where} {'AND' if where else 'WHERE'} category='threat'"
            ).fetchone()[0]
            asl = conn.execute(
                f"SELECT COUNT(*) FROM gesture_log {where} {'AND' if where else 'WHERE'} asl_letter IS NOT NULL"
            ).fetchone()[0]
        return {
            "total_gestures": total,
            "sos_help_signals": sos,
            "threat_signals": threat,
            "asl_events": asl,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
face_db_service = FaceDBService()
