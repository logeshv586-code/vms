"""PTZ configuration and ONVIF controller endpoints.

The controller is intentionally fail-closed: PTZ is reported as ready only after an
actual ONVIF connection succeeds. Credentials are resolved from the server-side camera
configuration and are never returned by this API.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlsplit

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

try:
    from onvif import ONVIFCamera
    _ONVIF_AVAILABLE = True
except Exception as exc:  # optional hardware dependency
    ONVIFCamera = None
    _ONVIF_AVAILABLE = False
    logger.warning("ONVIF PTZ support unavailable: %s", exc)

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAMERA_CONFIG_PATH = os.path.join(BACKEND_DIR, "data", "camera_configuration.json")
PTZ_CONFIG_PATH = os.path.join(BACKEND_DIR, "data", "ptz_configuration.json")

router = APIRouter(prefix="/ptz", tags=["ptz"])
_CONFIG_LOCK = threading.RLock()
_RUNTIME_LOCK = threading.RLock()
_TOUR_WORKERS: Dict[str, Tuple[threading.Thread, threading.Event]] = {}
_TRACK_ACTIVE: Dict[str, bool] = {}


class TourPreset(BaseModel):
    token: str
    name: str = "Preset"
    dwell_seconds: float = Field(default=5.0, ge=1.0, le=300.0)


class TourConfig(BaseModel):
    enabled: bool = False
    onvif_port: int = Field(default=80, ge=1, le=65535)
    presets: List[TourPreset] = []
    loop: bool = True
    return_to_first: bool = True


class TrackConfig(BaseModel):
    enabled: bool = False
    onvif_port: int = Field(default=80, ge=1, le=65535)
    target_class: str = "person"
    confidence: float = Field(default=0.5, ge=0.05, le=0.99)
    dead_zone_percent: float = Field(default=12.0, ge=2.0, le=45.0)
    pan_speed: float = Field(default=0.35, ge=0.05, le=1.0)
    tilt_speed: float = Field(default=0.30, ge=0.05, le=1.0)
    lost_target_seconds: float = Field(default=3.0, ge=0.5, le=60.0)
    return_preset: Optional[str] = None


class TargetUpdate(BaseModel):
    center_x: float = Field(ge=0.0, le=1.0)
    center_y: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    target_class: str = "person"


def _atomic_write(payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(PTZ_CONFIG_PATH), exist_ok=True)
    temporary = f"{PTZ_CONFIG_PATH}.tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, PTZ_CONFIG_PATH)


def _load_ptz_config() -> Dict[str, Any]:
    with _CONFIG_LOCK:
        if not os.path.exists(PTZ_CONFIG_PATH):
            data = {"cameras": {}}
            _atomic_write(data)
            return data
        try:
            with open(PTZ_CONFIG_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                data = {"cameras": {}}
            data.setdefault("cameras", {})
            return data
        except Exception as exc:
            logger.error("Unable to read PTZ configuration: %s", exc)
            return {"cameras": {}}


def _save_camera_config(camera_id: str, section: str, value: Dict[str, Any]) -> None:
    with _CONFIG_LOCK:
        data = _load_ptz_config()
        camera = data["cameras"].setdefault(camera_id, {})
        camera[section] = value
        _atomic_write(data)


def _default_tour() -> Dict[str, Any]:
    return TourConfig().model_dump()


def _default_track() -> Dict[str, Any]:
    return TrackConfig().model_dump()


def _camera_ptz_config(camera_id: str) -> Dict[str, Any]:
    data = _load_ptz_config().get("cameras", {}).get(camera_id, {})
    return {
        "tour": {**_default_tour(), **(data.get("tour") or {})},
        "track": {**_default_track(), **(data.get("track") or {})},
    }


def _normalize(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"^camera[-_]", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def _camera_candidates(collection: str, ip: str) -> List[str]:
    slug = re.sub(r"[^a-z0-9]+", "-", collection.lower()).strip("-")
    dashed_ip = ip.replace(".", "-")
    return [
        f"{collection}_{ip}",
        f"{collection} ({ip})",
        f"camera-{slug}-{dashed_ip}",
        ip,
    ]


def _resolve_camera(camera_id: str) -> Dict[str, str]:
    if not os.path.isfile(CAMERA_CONFIG_PATH):
        raise RuntimeError("Camera configuration file is not available")
    with open(CAMERA_CONFIG_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    wanted = _normalize(camera_id)
    if not isinstance(data, dict):
        raise RuntimeError("Camera configuration is invalid")

    for collection, cameras in data.items():
        if not isinstance(cameras, dict):
            continue
        for ip, stream_url in cameras.items():
            if wanted not in {_normalize(item) for item in _camera_candidates(str(collection), str(ip))}:
                continue
            parts = urlsplit(str(stream_url))
            username = unquote(parts.username or "")
            password = unquote(parts.password or "")
            host = parts.hostname or str(ip)
            return {
                "camera_id": camera_id,
                "collection": str(collection),
                "ip": str(ip),
                "host": host,
                "username": username,
                "password": password,
            }
    raise RuntimeError("Camera not found in the server camera configuration")


def _safe_error(exc: Exception) -> str:
    text = str(exc) or exc.__class__.__name__
    # Do not allow credential-bearing URLs/user-info to escape into API responses.
    text = re.sub(r"(?i)(https?|rtsp|rtsps)://[^@\s]+@", r"\1://***:***@", text)
    return text[:300]


def _connect(camera_id: str, port: int):
    if not _ONVIF_AVAILABLE or ONVIFCamera is None:
        raise RuntimeError("ONVIF support is not installed. Install backend requirements first.")
    camera_meta = _resolve_camera(camera_id)
    camera = ONVIFCamera(
        camera_meta["host"],
        int(port),
        camera_meta["username"],
        camera_meta["password"],
    )
    media = camera.create_media_service()
    ptz = camera.create_ptz_service()
    profiles = media.GetProfiles()
    if not profiles:
        raise RuntimeError("Camera returned no ONVIF media profiles")
    profile = next((item for item in profiles if getattr(item, "PTZConfiguration", None)), profiles[0])
    profile_token = getattr(profile, "token", None) or getattr(profile, "_token", None)
    if not profile_token:
        raise RuntimeError("ONVIF profile has no token")
    return camera_meta, ptz, str(profile_token)


def _read_presets(ptz, profile_token: str) -> List[Dict[str, str]]:
    try:
        presets = ptz.GetPresets({"ProfileToken": profile_token}) or []
    except Exception:
        presets = []
    result: List[Dict[str, str]] = []
    for index, preset in enumerate(presets):
        token = getattr(preset, "token", None) or getattr(preset, "_token", None)
        if not token:
            continue
        name = getattr(preset, "Name", None) or f"Preset {index + 1}"
        result.append({"token": str(token), "name": str(name)})
    return result


def _stop_motion(ptz, profile_token: str) -> None:
    try:
        ptz.Stop({"ProfileToken": profile_token, "PanTilt": True, "Zoom": True})
    except Exception:
        try:
            ptz.Stop({"ProfileToken": profile_token})
        except Exception:
            pass


def _goto_preset(ptz, profile_token: str, preset_token: str) -> None:
    ptz.GotoPreset({"ProfileToken": profile_token, "PresetToken": preset_token})


def _tour_loop(camera_id: str, config: Dict[str, Any], stop_event: threading.Event) -> None:
    try:
        _, ptz, profile_token = _connect(camera_id, int(config.get("onvif_port", 80)))
        presets = list(config.get("presets") or [])
        if not presets:
            return
        while not stop_event.is_set():
            for preset in presets:
                if stop_event.is_set():
                    break
                _goto_preset(ptz, profile_token, str(preset.get("token")))
                stop_event.wait(max(1.0, float(preset.get("dwell_seconds", 5))))
            if not config.get("loop", True):
                break
        if config.get("return_to_first") and presets and not stop_event.is_set():
            _goto_preset(ptz, profile_token, str(presets[0].get("token")))
        _stop_motion(ptz, profile_token)
    except Exception as exc:
        logger.error("PTZ tour stopped for %s: %s", camera_id, _safe_error(exc))
    finally:
        with _RUNTIME_LOCK:
            _TOUR_WORKERS.pop(camera_id, None)


def _tour_running(camera_id: str) -> bool:
    with _RUNTIME_LOCK:
        item = _TOUR_WORKERS.get(camera_id)
        return bool(item and item[0].is_alive())


@router.get("/config/{camera_id}")
async def get_ptz_config(camera_id: str):
    config = _camera_ptz_config(camera_id)
    return {
        "success": True,
        "data": {
            **config,
            "runtime": {
                "tour_running": _tour_running(camera_id),
                "track_active": bool(_TRACK_ACTIVE.get(camera_id, False)),
            },
        },
    }


@router.get("/capabilities/{camera_id}")
async def get_ptz_capabilities(camera_id: str, port: int = 80):
    if not _ONVIF_AVAILABLE:
        return {
            "success": True,
            "data": {
                "supported": False,
                "verified": False,
                "reason": "ONVIF Python package is not available",
                "presets": [],
            },
        }
    try:
        meta, ptz, profile_token = _connect(camera_id, port)
        presets = _read_presets(ptz, profile_token)
        return {
            "success": True,
            "data": {
                "supported": True,
                "verified": True,
                "camera_ip": meta["ip"],
                "profile_token": profile_token,
                "presets": presets,
                "can_pan_tilt": True,
                "can_tour": bool(presets),
                "message": "ONVIF PTZ connection verified",
            },
        }
    except Exception as exc:
        return {
            "success": True,
            "data": {
                "supported": False,
                "verified": False,
                "reason": _safe_error(exc),
                "presets": [],
            },
        }


@router.put("/tour/{camera_id}")
async def save_tour_config(camera_id: str, config: TourConfig):
    _resolve_camera(camera_id)
    _save_camera_config(camera_id, "tour", config.model_dump())
    return {"success": True, "data": config.model_dump(), "message": "PTZ tour configuration saved"}


@router.post("/tour/{camera_id}/start")
async def start_tour(camera_id: str):
    config = _camera_ptz_config(camera_id)["tour"]
    if not config.get("enabled"):
        return {"success": False, "error": "Enable Auto Tour and save the configuration first"}
    if not config.get("presets"):
        return {"success": False, "error": "Select at least one ONVIF preset for the tour"}
    # Verify hardware before starting the worker.
    try:
        _connect(camera_id, int(config.get("onvif_port", 80)))
    except Exception as exc:
        return {"success": False, "error": _safe_error(exc)}

    with _RUNTIME_LOCK:
        existing = _TOUR_WORKERS.get(camera_id)
        if existing and existing[0].is_alive():
            return {"success": True, "message": "PTZ Auto Tour is already running"}
        stop_event = threading.Event()
        worker = threading.Thread(target=_tour_loop, args=(camera_id, config, stop_event), daemon=True)
        _TOUR_WORKERS[camera_id] = (worker, stop_event)
        worker.start()
    return {"success": True, "message": "PTZ Auto Tour started"}


@router.post("/tour/{camera_id}/stop")
async def stop_tour(camera_id: str):
    with _RUNTIME_LOCK:
        item = _TOUR_WORKERS.get(camera_id)
        if item:
            item[1].set()
    return {"success": True, "message": "PTZ Auto Tour stop requested"}


@router.put("/track/{camera_id}")
async def save_track_config(camera_id: str, config: TrackConfig):
    _resolve_camera(camera_id)
    _save_camera_config(camera_id, "track", config.model_dump())
    if not config.enabled:
        with _RUNTIME_LOCK:
            _TRACK_ACTIVE[camera_id] = False
    return {"success": True, "data": config.model_dump(), "message": "PTZ Auto Track configuration saved"}


@router.post("/track/{camera_id}/start")
async def start_track(camera_id: str):
    config = _camera_ptz_config(camera_id)["track"]
    if not config.get("enabled"):
        return {"success": False, "error": "Enable Auto Track and save the configuration first"}
    try:
        _connect(camera_id, int(config.get("onvif_port", 80)))
    except Exception as exc:
        return {"success": False, "error": _safe_error(exc)}
    with _RUNTIME_LOCK:
        _TRACK_ACTIVE[camera_id] = True
    return {
        "success": True,
        "message": "PTZ Auto Track controller armed. It moves only when the AI pipeline sends a target center.",
        "data": {"active": True, "target_handoff_required": True},
    }


@router.post("/track/{camera_id}/stop")
async def stop_track(camera_id: str):
    with _RUNTIME_LOCK:
        _TRACK_ACTIVE[camera_id] = False
    config = _camera_ptz_config(camera_id)["track"]
    try:
        _, ptz, profile_token = _connect(camera_id, int(config.get("onvif_port", 80)))
        _stop_motion(ptz, profile_token)
    except Exception:
        pass
    return {"success": True, "message": "PTZ Auto Track disarmed"}


@router.post("/track/{camera_id}/target")
async def update_track_target(camera_id: str, target: TargetUpdate):
    """Move toward a normalized target center supplied by the AI tracking pipeline.

    This endpoint makes the PTZ controller testable without claiming that every
    camera feed already supplies a target handoff. The UI reports that distinction.
    """
    if not _TRACK_ACTIVE.get(camera_id, False):
        return {"success": False, "error": "PTZ Auto Track is not armed"}
    config = _camera_ptz_config(camera_id)["track"]
    if target.target_class != config.get("target_class") or target.confidence < float(config.get("confidence", 0.5)):
        return {"success": True, "data": {"moved": False, "reason": "target does not meet tracking policy"}}

    dead_zone = float(config.get("dead_zone_percent", 12)) / 200.0
    dx = float(target.center_x) - 0.5
    dy = float(target.center_y) - 0.5
    try:
        _, ptz, profile_token = _connect(camera_id, int(config.get("onvif_port", 80)))
        if abs(dx) <= dead_zone and abs(dy) <= dead_zone:
            _stop_motion(ptz, profile_token)
            return {"success": True, "data": {"moved": False, "centered": True}}

        pan = 0.0 if abs(dx) <= dead_zone else (1.0 if dx > 0 else -1.0) * float(config.get("pan_speed", 0.35))
        # Image Y increases downward; invert it for conventional camera tilt direction.
        tilt = 0.0 if abs(dy) <= dead_zone else (-1.0 if dy > 0 else 1.0) * float(config.get("tilt_speed", 0.30))
        request = {
            "ProfileToken": profile_token,
            "Velocity": {"PanTilt": {"x": pan, "y": tilt}},
        }
        ptz.ContinuousMove(request)
        return {"success": True, "data": {"moved": True, "pan": pan, "tilt": tilt}}
    except Exception as exc:
        return {"success": False, "error": _safe_error(exc)}
