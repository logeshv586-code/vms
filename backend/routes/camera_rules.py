from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import logging
import re
import threading
from typing import List, Dict, Optional, Any

from services.pattern_engine import pattern_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
EVENTS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "events_configuration.json")
CAMERA_RULES_PATH = os.path.join(WORKSPACE_ROOT, "camera_rules.json")
CAMERA_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "backend", "data", "camera_configuration.json")

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


def _normalize_camera_id(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"^camera[-_]", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def _camera_aliases_from_config() -> Dict[str, set]:
    """Map normalized physical-camera identity to all UI/runtime aliases."""
    output: Dict[str, set] = {}
    if not os.path.isfile(CAMERA_CONFIG_PATH):
        return output
    try:
        with open(CAMERA_CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return output
        for collection, cameras in data.items():
            if not isinstance(cameras, dict):
                continue
            for ip in cameras:
                slug = re.sub(r"[^a-z0-9]+", "-", str(collection).lower()).strip("-")
                frontend_id = f"camera-{slug}-{str(ip).replace('.', '-')}"
                stream_id = f"{collection}_{ip}"
                display_name = f"{collection} ({ip})"
                aliases = {frontend_id, stream_id, display_name, str(ip)}
                key = _normalize_camera_id(stream_id)
                output[key] = aliases
    except Exception as exc:
        logger.warning("Unable to expand camera aliases: %s", exc)
    return output


def _expanded_camera_rules(camera_rules: Dict[str, Any]) -> Dict[str, List[int]]:
    """Return compatibility aliases without changing the persisted canonical data."""
    expanded: Dict[str, List[int]] = {}
    physical_aliases = _camera_aliases_from_config()
    for stored_id, rule_ids in (camera_rules or {}).items():
        ids = [int(value) for value in (rule_ids or [])]
        expanded[str(stored_id)] = ids
        normalized = _normalize_camera_id(stored_id)
        aliases = physical_aliases.get(normalized)
        if aliases:
            for alias in aliases:
                expanded[alias] = ids
    return expanded


@router.get("/camera-rules")
async def get_camera_rules():
    try:
        camera_rules_data = _load_camera_rules()
        enabled_ids = sorted(_enabled_rule_ids()) if os.path.exists(EVENTS_CONFIG_PATH) else []
        raw_rules = camera_rules_data.get("camera_rules", {})
        return {
            "success": True,
            "data": {
                "cameraRules": _expanded_camera_rules(raw_rules),
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
                camera_rules[camera_id] = requested_rule_ids
            camera_rules_data["camera_rules"] = camera_rules
            _atomic_write(CAMERA_RULES_PATH, camera_rules_data)

        pattern_engine.reload_config()

        return {
            "success": True,
            "data": {
                "cameraRules": _expanded_camera_rules(camera_rules),
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
