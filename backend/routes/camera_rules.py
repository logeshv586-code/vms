from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import logging
import threading
from typing import List, Dict, Optional, Any

from services.pattern_engine import pattern_engine
from services.camera_ai_preferences import set_camera_ai_enabled

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
EVENTS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "events_configuration.json")
CAMERA_RULES_PATH = os.path.join(WORKSPACE_ROOT, "camera_rules.json")
_CONFIG_LOCK = threading.RLock()

router = APIRouter(prefix="/api/augment", tags=["camera_rules"])


class CameraRuleRequest(BaseModel):
    cameraIds: List[str]
    ruleIds: List[int]


class CameraRuleResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None


def _atomic_json_write(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


def ensure_camera_rules_config():
    with _CONFIG_LOCK:
        if not os.path.exists(CAMERA_RULES_PATH):
            _atomic_json_write(CAMERA_RULES_PATH, {"camera_rules": {}})
            logger.info("Created default camera rules configuration at %s", CAMERA_RULES_PATH)


def ensure_events_config():
    if not os.path.exists(EVENTS_CONFIG_PATH):
        logger.error("Events configuration file not found at %s", EVENTS_CONFIG_PATH)
        raise HTTPException(status_code=500, detail="Events configuration file not found")


def _load_camera_rules() -> Dict[str, Any]:
    ensure_camera_rules_config()
    with _CONFIG_LOCK:
        with open(CAMERA_RULES_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    return data if isinstance(data, dict) else {"camera_rules": {}}


@router.get("/camera-rules")
async def get_camera_rules():
    try:
        camera_rules_data = _load_camera_rules()
        return {
            "success": True,
            "data": {"cameraRules": camera_rules_data.get("camera_rules", {})},
            "message": "Camera rules retrieved successfully",
        }
    except Exception as exc:
        logger.error("Error getting camera rules: %s", exc)
        return {"success": False, "error": str(exc)}


@router.post("/apply-camera-rules")
async def apply_camera_rules(request: CameraRuleRequest):
    try:
        ensure_camera_rules_config()
        ensure_events_config()

        with open(EVENTS_CONFIG_PATH, "r", encoding="utf-8") as handle:
            events_data = json.load(handle)

        enabled_rule_ids = {
            int(rule["id"])
            for rule in events_data.get("rules", [])
            if isinstance(rule, dict) and rule.get("enabled", False) and rule.get("id") is not None
        }
        requested_rule_ids = []
        for rule_id in request.ruleIds:
            value = int(rule_id)
            if value not in requested_rule_ids:
                requested_rule_ids.append(value)

        invalid_rules = [rule_id for rule_id in requested_rule_ids if rule_id not in enabled_rule_ids]
        if invalid_rules:
            return {"success": False, "error": f"The following rules are not enabled: {invalid_rules}"}

        camera_ids = [str(camera_id).strip() for camera_id in request.cameraIds if str(camera_id).strip()]
        if not camera_ids:
            return {"success": False, "error": "At least one camera is required"}

        with _CONFIG_LOCK:
            with open(CAMERA_RULES_PATH, "r", encoding="utf-8") as handle:
                camera_rules_data = json.load(handle)
            if not isinstance(camera_rules_data, dict):
                camera_rules_data = {"camera_rules": {}}
            camera_rules = camera_rules_data.get("camera_rules", {})
            if not isinstance(camera_rules, dict):
                camera_rules = {}

            for camera_id in camera_ids:
                camera_rules[camera_id] = requested_rule_ids

            camera_rules_data["camera_rules"] = camera_rules
            _atomic_json_write(CAMERA_RULES_PATH, camera_rules_data)

        # Selected rules are the persisted 24x7 monitoring preference.  Turning
        # all rules off disables AI for that camera; selecting any rule enables
        # it again, even after application restart.
        for camera_id in camera_ids:
            try:
                set_camera_ai_enabled(camera_id, bool(requested_rule_ids))
            except Exception as pref_exc:
                logger.warning("Could not update AI enabled preference for %s: %s", camera_id, pref_exc)

        pattern_engine.reload_config()

        return {
            "success": True,
            "data": {"cameraRules": camera_rules},
            "message": f"Rules applied successfully to {len(camera_ids)} cameras",
        }
    except Exception as exc:
        logger.error("Error applying camera rules: %s", exc)
        return {"success": False, "error": str(exc)}
