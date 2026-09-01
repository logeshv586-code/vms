from fastapi import APIRouter, HTTPException, Body
import json
import os
import logging
from typing import Dict, Any, List

from services.yolo26_engine import yolo26_engine
from services.pattern_engine import pattern_engine

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the workspace root directory
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
DATA_DIR = os.path.join(WORKSPACE_ROOT, "backend", "data")
CAMERA_ZONES_PATH = os.path.join(DATA_DIR, "camera_zones.json")

# Create router
router = APIRouter(prefix="/api/augment", tags=["camera_zones"])

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_zones() -> Dict[str, Any]:
    if not os.path.exists(CAMERA_ZONES_PATH):
        return {}
    try:
        with open(CAMERA_ZONES_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading zones: {e}")
        return {}

def save_zones(zones_data: Dict[str, Any]):
    ensure_data_dir()
    try:
        with open(CAMERA_ZONES_PATH, "w") as f:
            json.dump(zones_data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving zones to {CAMERA_ZONES_PATH}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save zones: {str(e)}")

@router.get("/camera-zones")
async def get_camera_zones():
    """Retrieve all camera zones configuration"""
    zones = load_zones()
    return {"success": True, "data": zones}

@router.post("/camera-zones/{stream_id}")
async def update_camera_zones(stream_id: str, zones: List[Dict[str, Any]] = Body(...)):
    """Update zones for a specific camera stream"""
    zones_data = load_zones()
    zones_data[stream_id] = {"zones": zones}
    save_zones(zones_data)
    
    # Notify engines to reload
    yolo26_engine.reload_config()
    pattern_engine.reload_config()
    
    return {"success": True, "message": f"Zones updated for {stream_id}"}

@router.get("/camera-zones/{stream_id}")
async def get_camera_zones_for_stream(stream_id: str):
    """Retrieve zones for a specific camera stream"""
    zones_data = load_zones()
    return {"success": True, "data": zones_data.get(stream_id, {"zones": []})}
