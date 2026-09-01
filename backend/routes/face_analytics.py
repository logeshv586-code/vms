"""
Face Analytics API Routes
==========================
REST endpoints for:
  - Face capture gallery management
  - Face recognition event log
  - Criminal / suspect watchlist management
  - Face registration from uploaded images
  - Summary statistics for the analytics dashboard
"""

import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/face", tags=["face-analytics"])

# ── Service singletons ────────────────────────────────────────────────────────
try:
    from services.face_db_service import face_db_service as _db
    _DB_AVAILABLE = True
except Exception as e:
    _DB_AVAILABLE = False
    _db = None
    logger.error("FaceDBService unavailable: %s", e)

# Face recognition detector (for live registration)
try:
    import sys, os as _os
    sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
    from detections.face_recognition import FaceRecognitionDetector
    _face_rec_detector = FaceRecognitionDetector()
    _FACE_REC_AVAILABLE = True
except Exception as e:
    _face_rec_detector = None
    _FACE_REC_AVAILABLE = False
    logger.error("FaceRecognitionDetector unavailable: %s", e)


# ── Pydantic models ───────────────────────────────────────────────────────────
class WatchlistEntry(BaseModel):
    name: str
    alias: Optional[str] = None
    category: str = "suspect"   # "suspect" | "criminal" | "person" | "staff"
    notes: Optional[str] = None


class TagRequest(BaseModel):
    capture_id: str
    identity: str


# ── Health ────────────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {
        "status": "ok" if _DB_AVAILABLE else "db_unavailable",
        "face_recognition": _FACE_REC_AVAILABLE,
        "db": _DB_AVAILABLE,
    }


# ── Capture gallery ───────────────────────────────────────────────────────────
@router.get("/captures")
async def list_captures(
    stream_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    since_hours: Optional[float] = Query(None),
):
    """List all face capture events, optionally filtered by stream / time."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    since = time.time() - since_hours * 3600 if since_hours else None
    captures = _db.list_captures(stream_id=stream_id, limit=limit, offset=offset, since=since)
    return {"success": True, "count": len(captures), "captures": captures}


@router.get("/captures/image/{capture_id}")
async def get_capture_image(capture_id: str):
    """Serve a face capture image by its DB record ID."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    captures = _db.list_captures(limit=1)
    # Lookup by id
    with _db._conn() as conn:
        row = conn.execute(
            "SELECT image_path FROM face_captures WHERE id=?", (capture_id,)
        ).fetchone()
    if not row or not row["image_path"]:
        raise HTTPException(status_code=404, detail="Capture not found.")
    if not os.path.isfile(row["image_path"]):
        raise HTTPException(status_code=404, detail="Image file not found on disk.")
    return FileResponse(row["image_path"], media_type="image/jpeg")


@router.post("/captures/tag")
async def tag_capture(request: TagRequest):
    """Tag an unknown face capture with an identity name."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    success = _db.tag_capture(request.capture_id, request.identity)
    if not success:
        raise HTTPException(status_code=404, detail="Capture record not found.")
    return {"success": True, "message": f"Capture tagged as '{request.identity}'."}


@router.delete("/captures/{capture_id}")
async def delete_capture(capture_id: str):
    """Delete a face capture record (and optionally the image file)."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    # Get image path first
    with _db._conn() as conn:
        row = conn.execute(
            "SELECT image_path FROM face_captures WHERE id=?", (capture_id,)
        ).fetchone()
    success = _db.delete_capture(capture_id)
    if not success:
        raise HTTPException(status_code=404, detail="Capture not found.")
    # Remove image from disk if it exists
    if row and row["image_path"] and os.path.isfile(row["image_path"]):
        try:
            os.remove(row["image_path"])
        except OSError:
            pass
    return {"success": True, "message": "Capture deleted."}


# ── Recognition log ───────────────────────────────────────────────────────────
@router.get("/recognitions")
async def list_recognitions(
    stream_id: Optional[str] = Query(None),
    identity: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Return face recognition match history."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    records = _db.list_recognitions(
        stream_id=stream_id, identity=identity, limit=limit, offset=offset
    )
    return {"success": True, "count": len(records), "recognitions": records}


@router.get("/analytics/summary")
async def analytics_summary():
    """Return aggregate face analytics statistics."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    summary = _db.get_recognition_summary()
    identities = (
        _face_rec_detector.list_identities()
        if _FACE_REC_AVAILABLE and _face_rec_detector
        else []
    )
    return {
        "success": True,
        "summary": summary,
        "registered_identities": len(identities),
        "identities": identities,
    }


# ── Face registration ─────────────────────────────────────────────────────────
@router.post("/register")
async def register_face(
    name: str = Form(...),
    category: str = Form("person"),
    file: UploadFile = File(...),
):
    """
    Register a face from an uploaded image into the recognition database.

    This seeds the recognition gallery (Option A — no model training needed).
    """
    if not _FACE_REC_AVAILABLE or _face_rec_detector is None:
        raise HTTPException(status_code=503, detail="Face recognition detector not available.")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    import cv2
    import numpy as np

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB).")

    nparr = np.frombuffer(content, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode image.")

    result = _face_rec_detector.register_face(name, frame, category=category)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return {"success": True, "message": result["message"], "name": name, "category": category}


@router.post("/seed-directory")
async def seed_from_directory(
    directory: str = Form(...),
    category: str = Form("person"),
):
    """
    Bulk-register faces from a LFW-format directory (Kaggle dataset).
    Each subdirectory name becomes an identity; first valid image is used.
    """
    if not _FACE_REC_AVAILABLE or _face_rec_detector is None:
        raise HTTPException(status_code=503, detail="Face recognition detector not available.")
    result = _face_rec_detector.seed_from_directory(directory, category=category)
    return result


@router.get("/identities")
async def list_identities():
    """List all registered identity names and their categories."""
    if not _FACE_REC_AVAILABLE or _face_rec_detector is None:
        raise HTTPException(status_code=503, detail="Face recognition detector not available.")
    return {"success": True, "identities": _face_rec_detector.list_identities()}


@router.delete("/identities/{name}")
async def unregister_identity(name: str):
    """Remove a registered identity from the recognition database."""
    if not _FACE_REC_AVAILABLE or _face_rec_detector is None:
        raise HTTPException(status_code=503, detail="Face recognition detector not available.")
    result = _face_rec_detector.unregister_face(name)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["message"])
    return result


# ── Watchlist ─────────────────────────────────────────────────────────────────
@router.get("/watchlist")
async def get_watchlist():
    """Return the active criminal / suspect watchlist."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    entries = _db.get_watchlist(active_only=True)
    return {"success": True, "count": len(entries), "watchlist": entries}


@router.post("/watchlist")
async def add_to_watchlist(entry: WatchlistEntry):
    """Add a person to the criminal / suspect watchlist."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    record_id = _db.add_to_watchlist(
        name=entry.name,
        alias=entry.alias,
        category=entry.category,
        notes=entry.notes,
    )
    return {
        "success": True,
        "id": record_id,
        "message": f"'{entry.name}' added to watchlist as '{entry.category}'.",
    }


@router.delete("/watchlist/{watchlist_id}")
async def remove_from_watchlist(watchlist_id: str):
    """Remove (deactivate) a watchlist entry."""
    if not _DB_AVAILABLE:
        raise HTTPException(status_code=503, detail="Face database not available.")
    success = _db.remove_from_watchlist(watchlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Watchlist entry not found.")
    return {"success": True, "message": "Entry removed from watchlist."}
