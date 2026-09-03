from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ANALYTICS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "analytics_configuration.json")
_CONFIG_LOCK = threading.RLock()
router = APIRouter(prefix="/api/augment", tags=["analytics"])


class AnalyticsServer(BaseModel):
    id: Optional[int] = None
    ip: str
    name: str


class AnalyticsResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    message: Optional[str] = None
    error: Optional[str] = None


def _atomic_save(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=directory, encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = handle.name
    os.replace(temporary, path)


def load_analytics_config() -> Dict[str, Any]:
    with _CONFIG_LOCK:
        try:
            if not os.path.exists(ANALYTICS_CONFIG_PATH):
                default_config = {"servers": []}
                _atomic_save(ANALYTICS_CONFIG_PATH, default_config)
                return default_config
            with open(ANALYTICS_CONFIG_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError("analytics configuration must be a JSON object")
            data.setdefault("servers", [])
            return data
        except Exception as exc:
            logger.error("Error loading analytics configuration: %s", exc)
            return {"servers": []}


def save_analytics_config(config: Dict[str, Any]) -> bool:
    with _CONFIG_LOCK:
        try:
            _atomic_save(ANALYTICS_CONFIG_PATH, config)
            return True
        except Exception as exc:
            logger.error("Error saving analytics configuration: %s", exc)
            return False


@router.get("/servers")
async def get_servers():
    config = load_analytics_config()
    return {"success": True, "data": config["servers"], "message": "Servers retrieved successfully"}


@router.post("/servers")
async def add_server(server: AnalyticsServer):
    config = load_analytics_config()
    servers = config["servers"]
    new_id = max((int(item.get("id", 0)) for item in servers if isinstance(item, dict)), default=0) + 1
    new_server = {"id": new_id, "ip": server.ip, "name": server.name}
    servers.append(new_server)
    if not save_analytics_config(config):
        raise HTTPException(status_code=500, detail="Failed to save analytics configuration")
    return {"success": True, "data": new_server, "message": "Server added successfully"}


@router.put("/servers/{server_id}")
async def update_server(server_id: int, server: AnalyticsServer):
    config = load_analytics_config()
    servers = config["servers"]
    index = next((idx for idx, item in enumerate(servers) if item.get("id") == server_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail=f"Server with ID {server_id} not found")
    servers[index] = {"id": server_id, "ip": server.ip, "name": server.name}
    if not save_analytics_config(config):
        raise HTTPException(status_code=500, detail="Failed to save analytics configuration")
    return {"success": True, "data": servers[index], "message": "Server updated successfully"}


@router.delete("/servers/{server_id}")
async def delete_server(server_id: int):
    config = load_analytics_config()
    servers = config["servers"]
    index = next((idx for idx, item in enumerate(servers) if item.get("id") == server_id), None)
    if index is None:
        raise HTTPException(status_code=404, detail=f"Server with ID {server_id} not found")
    deleted = servers.pop(index)
    if not save_analytics_config(config):
        raise HTTPException(status_code=500, detail="Failed to save analytics configuration")
    return {"success": True, "data": deleted, "message": "Server deleted successfully"}


def _safe_status(name: str, callback) -> Dict[str, Any]:
    try:
        value = callback()
        return value if isinstance(value, dict) else {"available": True, "value": value}
    except Exception as exc:
        logger.exception("AI health probe failed for %s", name)
        return {"available": False, "status": "error", "error": str(exc)}


@router.get("/ai-health")
async def get_ai_health():
    """Return truthful runtime capability state for operator/diagnostics screens."""
    from detections import get_detector_health
    from services.gemma_engine import gemma_engine
    from services.gemma_onnx_engine import gemma_onnx_engine
    from services.yolo26_engine import yolo26_engine

    detectors = _safe_status("detectors", get_detector_health)
    yolo = _safe_status("yolo", yolo26_engine.get_status)
    gemma = _safe_status("gemma", gemma_engine.get_status)
    paligemma = _safe_status("paligemma", gemma_onnx_engine.get_status)

    detector_values = list(detectors.values()) if isinstance(detectors, dict) else []
    missing_required = [
        item.get("key")
        for item in detector_values
        if isinstance(item, dict) and item.get("required") and not item.get("available")
    ]
    degraded = bool(missing_required) or not bool(yolo.get("available", False))
    if not gemma.get("available", False):
        degraded = True

    return {
        "success": True,
        "data": {
            "overall": "degraded" if degraded else "healthy",
            "required_detectors_missing": missing_required,
            "detectors": detectors,
            "yolo": yolo,
            "gemma4": gemma,
            "paligemma_onnx": paligemma,
            "notes": {
                "paligemma_optional": True,
                "identity_matching_requires_embedding_backend": True,
                "fallback_gesture_backend_is_analytics_only": True,
            },
        },
        "message": "AI capability health retrieved successfully",
    }
