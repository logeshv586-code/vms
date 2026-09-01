"""
Gesture Analytics API Routes
=============================
REST endpoints for:
  - Gesture detection event log (per camera, category, time range)
  - Gesture vocabulary definitions
  - Summary statistics
  - Gesture configuration (sensitivity, vocabulary override)
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/gestures", tags=["gesture-analytics"])

# ── Service singletons ────────────────────────────────────────────────────────
try:
    from services.face_db_service import face_db_service as _db
    _DB_AVAILABLE = True
except Exception as e:
    _DB_AVAILABLE = False
    _db = None
    logger.error("FaceDBService unavailable for gesture analytics: %s", e)

try:
    from detections.hand_gesture_classifier import GESTURE_VOCABULARY
    _VOCAB_AVAILABLE = True
except Exception as e:
    GESTURE_VOCABULARY = {}
    _VOCAB_AVAILABLE = False


# ── Pydantic models ───────────────────────────────────────────────────────────
class GestureConfig(BaseModel):
    sos_wave_threshold: Optional[int] = None
    sos_wave_window: Optional[int] = None
    min_detection_confidence: Optional[float] = None
    alert_categories: Optional[list] = None


# ── Health ────────────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {
        "status": "ok" if _DB_AVAILABLE else "db_unavailable",
        "vocabulary_loaded": _VOCAB_AVAILABLE,
        "gesture_count": len(GESTURE_VOCABULARY),
    }


# ── Gesture log ───────────────────────────────────────────────────────────────
@router.get("/log")
async def get_gesture_log(
    stream_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None, description="help | threat | asl | accessibility | neutral"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    since_hours: Optional[float] = Query(None),
):
    """
    Return gesture detection history.

    Filter by stream, category (help/threat/asl/accessibility), or time window.
    """
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Gesture database not available.")

    # Time filtering is done at the DB level
    gestures = _db.list_gestures(
        stream_id=stream_id,
        category=category,
        limit=limit,
        offset=offset,
    )

    # Apply since_hours filter (in-memory for simplicity)
    if since_hours is not None:
        cutoff = time.time() - since_hours * 3600
        gestures = [g for g in gestures if g.get("timestamp", 0) >= cutoff]

    return {"success": True, "count": len(gestures), "gestures": gestures}


@router.get("/log/sos")
async def get_sos_events(
    stream_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Return only SOS / help gesture events (high priority feed)."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Gesture database not available.")
    gestures = _db.list_gestures(stream_id=stream_id, category="help", limit=limit)
    return {"success": True, "count": len(gestures), "sos_events": gestures}


@router.get("/log/threats")
async def get_threat_events(
    stream_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Return only criminal / threat gesture events."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Gesture database not available.")
    gestures = _db.list_gestures(stream_id=stream_id, category="threat", limit=limit)
    return {"success": True, "count": len(gestures), "threat_events": gestures}


@router.get("/log/asl")
async def get_asl_events(
    stream_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
):
    """Return ASL letter / word detection events (deaf-community communication)."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Gesture database not available.")
    gestures = _db.list_gestures(stream_id=stream_id, category="asl", limit=limit)
    # Build a word/sentence from sequential ASL letters
    asl_letters = [
        g.get("asl_letter") for g in gestures if g.get("asl_letter")
    ]
    return {
        "success": True,
        "count": len(gestures),
        "asl_events": gestures,
        "asl_sequence": "".join(asl_letters[-50:]),  # Last 50 letters as sequence
    }


# ── Vocabulary ────────────────────────────────────────────────────────────────
@router.get("/vocabulary")
async def get_gesture_vocabulary(
    category: Optional[str] = Query(None, description="Filter by category"),
):
    """
    Return the full gesture vocabulary with descriptions and categories.

    This defines every gesture the system can detect:
    help, threat, asl (letters A-Z, digits 0-9), accessibility signs, neutral.
    """
    vocab = GESTURE_VOCABULARY
    if category:
        vocab = {
            k: v for k, v in vocab.items()
            if v.get("category", "").lower() == category.lower()
        }
    return {
        "success": True,
        "total_gestures": len(vocab),
        "vocabulary": vocab,
        "categories": list({v.get("category") for v in GESTURE_VOCABULARY.values()}),
    }


# ── Analytics summary ─────────────────────────────────────────────────────────
@router.get("/analytics")
async def get_gesture_analytics(
    stream_id: Optional[str] = Query(None),
):
    """Return aggregate gesture statistics for the analytics dashboard."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Gesture database not available.")
    summary = _db.get_gesture_summary(stream_id=stream_id)
    return {"success": True, "summary": summary}


@router.get("/analytics/per-camera")
async def get_per_camera_analytics():
    """Return gesture statistics broken down by camera / stream."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Gesture database not available.")
    with _db._conn() as conn:
        rows = conn.execute(
            """
            SELECT stream_id,
                   COUNT(*) AS total,
                   SUM(CASE WHEN category='help'   THEN 1 ELSE 0 END) AS help,
                   SUM(CASE WHEN category='threat' THEN 1 ELSE 0 END) AS threat,
                   SUM(CASE WHEN category='asl'    THEN 1 ELSE 0 END) AS asl
            FROM gesture_log
            GROUP BY stream_id
            ORDER BY total DESC
            """
        ).fetchall()
    return {
        "success": True,
        "cameras": [dict(r) for r in rows],
    }


# ── Configuration ─────────────────────────────────────────────────────────────
# In-memory config store (would be persisted to gesture_db/gesture_config.json
# in a full production system)
_gesture_config: dict = {}


@router.get("/config")
async def get_gesture_config():
    """Return current gesture detection configuration."""
    return {"success": True, "config": _gesture_config}


@router.post("/config")
async def update_gesture_config(config: GestureConfig):
    """
    Update gesture detection configuration (sensitivity, alert categories).

    Changes take effect on the next detector initialisation.
    """
    global _gesture_config
    updates = config.dict(exclude_none=True)
    _gesture_config.update(updates)

    # Persist to disk
    import json, os
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "gesture_db", "gesture_config.json"
    )
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    try:
        with open(config_path, "w") as fh:
            json.dump(_gesture_config, fh, indent=2)
    except Exception as e:
        logger.error("Failed to persist gesture config: %s", e)

    return {"success": True, "config": _gesture_config, "message": "Gesture config updated."}
