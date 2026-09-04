from fastapi import APIRouter, HTTPException, Body
import json
import os
import logging
import threading
from typing import Dict, Any, List

from services.yolo26_engine import yolo26_engine
from services.pattern_engine import pattern_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DATA_DIR = os.path.join(WORKSPACE_ROOT, "backend", "data")
CAMERA_ZONES_PATH = os.path.join(DATA_DIR, "camera_zones.json")
_ZONES_LOCK = threading.RLock()

router = APIRouter(prefix="/api/augment", tags=["camera_zones"])


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_zones() -> Dict[str, Any]:
    with _ZONES_LOCK:
        if not os.path.exists(CAMERA_ZONES_PATH):
            return {}
        try:
            with open(CAMERA_ZONES_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            logger.error("Error loading zones: %s", exc)
            return {}


def save_zones(zones_data: Dict[str, Any]):
    ensure_data_dir()
    temp_path = f"{CAMERA_ZONES_PATH}.tmp"
    try:
        with _ZONES_LOCK:
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(zones_data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, CAMERA_ZONES_PATH)
    except Exception as exc:
        logger.error("Error saving zones to %s: %s", CAMERA_ZONES_PATH, exc)
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to save zones: {exc}") from exc


@router.get("/camera-zones")
async def get_camera_zones():
    """Retrieve all camera zones configuration."""
    return {"success": True, "data": load_zones()}


@router.post("/camera-zones/{stream_id}")
async def update_camera_zones(stream_id: str, zones: List[Dict[str, Any]] = Body(...)):
    """Atomically update zones for a specific camera stream."""
    zones_data = load_zones()
    zones_data[stream_id] = {"zones": zones}
    save_zones(zones_data)

    yolo26_engine.reload_config()
    pattern_engine.reload_config()

    return {"success": True, "message": f"Zones updated for {stream_id}"}


@router.get("/camera-zones/{stream_id}")
async def get_camera_zones_for_stream(stream_id: str):
    """Retrieve zones for a specific camera stream."""
    zones_data = load_zones()
    return {"success": True, "data": zones_data.get(stream_id, {"zones": []})}
