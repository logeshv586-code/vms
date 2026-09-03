from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import logging
import threading
from typing import List, Dict, Optional, Any

from services.pattern_engine import pattern_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
EVENTS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "events_configuration.json")
CAMERA_RULES_PATH = os.path.join(WORKSPACE_ROOT, "camera_rules.json")

router = APIRouter(prefix="/api/augment", tags=["camera_rules"])
_CAMERA_RULES_LOCK = threading.RLock()


class CameraRuleRequest(BaseModel):
    cameraIds: List[str]
    ruleIds: List[int]


class CameraRuleResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None


def _atomic_write(path: str, payload: Dict[str, Any]) -> None:
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def ensure_camera_rules_config():
    with _CAMERA_RULES_LOCK:
        if not os.path.exists(CAMERA_RULES_PATH):
            _atomic_write(CAMERA_RULES_PATH, {"camera_rules": {}})
            logger.info("Created default camera rules configuration at %s", CAMERA_RULES_PATH)


def ensure_events_config():
    if not os.path.exists(EVENTS_CONFIG_PATH):
        logger.error("Events configuration file not found at %s", EVENTS_CONFIG_PATH)
        raise HTTPException(status_code=500, detail="Events configuration file not found")


def _load_camera_rules() -> Dict[str, Any]:
    ensure_camera_rules_config()
    with _CAMERA_RULES_LOCK:
        with open(CAMERA_RULES_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    if not isinstance(data, dict):
        data = {"camera_rules": {}}
    data.setdefault("camera_rules", {})
    return data


def _enabled_rule_ids() -> set:
    ensure_events_config()
    with open(EVENTS_CONFIG_PATH, "r", encoding="utf-8") as handle:
        events_data = json.load(handle)
    return {
        int(rule["id"])
        for rule in events_data.get("rules", [])
        if isinstance(rule, dict) and rule.get("enabled", False) and rule.get("id") is not None
    }


@router.get("/camera-rules")
async def get_camera_rules():
    try:
        camera_rules_data = _load_camera_rules()
        enabled_ids = sorted(_enabled_rule_ids()) if os.path.exists(EVENTS_CONFIG_PATH) else []
        return {
            "success": True,
            "data": {
                "cameraRules": camera_rules_data.get("camera_rules", {}),
                "globalEnabledRuleIds": enabled_ids,
            },
            "message": "Camera rules retrieved successfully",
        }
    except Exception as exc:
        logger.error("Error getting camera rules: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post("/apply-camera-rules")
async def apply_camera_rules(request: CameraRuleRequest):
    try:
        enabled_rule_ids = _enabled_rule_ids()
        requested_rule_ids = []
        for rule_id in request.ruleIds:
            value = int(rule_id)
            if value not in requested_rule_ids:
                requested_rule_ids.append(value)

        invalid_rules = [rule_id for rule_id in requested_rule_ids if rule_id not in enabled_rule_ids]
        if invalid_rules:
            return {
                "success": False,
                "error": f"The following rules are not globally enabled: {invalid_rules}",
            }

        camera_ids = [str(camera_id).strip() for camera_id in request.cameraIds if str(camera_id).strip()]
        if not camera_ids:
            return {"success": False, "error": "Select at least one camera"}

        with _CAMERA_RULES_LOCK:
            camera_rules_data = _load_camera_rules()
            camera_rules = camera_rules_data.get("camera_rules", {})
            for camera_id in camera_ids:
                # Empty list intentionally means all detection is OFF for this camera.
                camera_rules[camera_id] = requested_rule_ids
            camera_rules_data["camera_rules"] = camera_rules
            _atomic_write(CAMERA_RULES_PATH, camera_rules_data)

        pattern_engine.reload_config()

        return {
            "success": True,
            "data": {
                "cameraRules": camera_rules,
                "globalEnabledRuleIds": sorted(enabled_rule_ids),
            },
            "message": f"Rules applied successfully to {len(camera_ids)} cameras",
        }
    except Exception as exc:
        logger.error("Error applying camera rules: %s", exc)
        return {"success": False, "error": str(exc)}


# PTZ lives under /api/augment/ptz. Including the sub-router here keeps the main
# application registration simple because camera_rules.router is already mounted.
from .ptz import router as ptz_router  # noqa: E402
router.include_router(ptz_router)
