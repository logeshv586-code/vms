"""Per-camera AI runtime preferences.

This module is intentionally English-only and keeps camera-specific detector
settings in one atomic JSON store.  Missing values fall back to the global VMS
runtime defaults, so existing installations keep their current behaviour.
"""

from __future__ import annotations

import json
import os
import re
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PREFERENCES_PATH = DATA_DIR / "camera_ai_preferences.json"
_LOCK = threading.RLock()

DEFAULT_PREFERENCES: Dict[str, Any] = {
    "enabled": True,
    "confidence": None,
    "iou": None,
    "tracker": None,
    "skip_frames": None,
    "ai_fps": 4.0,
    "evidence_pre_seconds": 10.0,
    "evidence_post_seconds": 20.0,
}


def normalize_camera_id(value: str) -> str:
    """Return a stable comparison key for camera IDs used by UI and streams."""
    if not value:
        return ""
    clean = str(value).lower().replace("camera-", "").replace("camera_", "")
    return re.sub(r"[^a-z0-9]", "", clean)


def _atomic_write(payload: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = PREFERENCES_PATH.with_suffix(PREFERENCES_PATH.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, PREFERENCES_PATH)


def _read_unlocked() -> Dict[str, Any]:
    if not PREFERENCES_PATH.exists():
        return {}
    try:
        with open(PREFERENCES_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_all_preferences() -> Dict[str, Any]:
    with _LOCK:
        return deepcopy(_read_unlocked())


def get_camera_ai_preferences(camera_id: str) -> Dict[str, Any]:
    """Return validated preferences merged with safe defaults."""
    wanted = normalize_camera_id(camera_id)
    with _LOCK:
        data = _read_unlocked()
        selected: Dict[str, Any] = {}
        for key, value in data.items():
            if normalize_camera_id(key) == wanted and isinstance(value, dict):
                selected = value
                break

    merged = deepcopy(DEFAULT_PREFERENCES)
    merged.update({key: value for key, value in selected.items() if key in DEFAULT_PREFERENCES})
    return _validate_preferences(merged, partial=False)


def set_camera_ai_preferences(camera_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically update one camera's AI preferences and return the saved values."""
    if not camera_id or not str(camera_id).strip():
        raise ValueError("camera_id is required")
    if not isinstance(updates, dict):
        raise ValueError("updates must be an object")

    cleaned_updates = _validate_preferences(updates, partial=True)
    wanted = normalize_camera_id(camera_id)

    with _LOCK:
        data = _read_unlocked()
        existing_key = next((key for key in data if normalize_camera_id(key) == wanted), str(camera_id))
        current = data.get(existing_key, {}) if isinstance(data.get(existing_key), dict) else {}
        current = {key: value for key, value in current.items() if key in DEFAULT_PREFERENCES}
        current.update(cleaned_updates)
        data[existing_key] = current
        _atomic_write(data)

    return get_camera_ai_preferences(camera_id)


def set_camera_ai_enabled(camera_id: str, enabled: bool) -> Dict[str, Any]:
    return set_camera_ai_preferences(camera_id, {"enabled": bool(enabled)})


def _validate_preferences(values: Dict[str, Any], partial: bool) -> Dict[str, Any]:
    allowed = set(DEFAULT_PREFERENCES)
    output: Dict[str, Any] = {}

    for key, value in values.items():
        if key not in allowed:
            if partial:
                continue
            raise ValueError(f"Unsupported AI preference: {key}")

        if key == "enabled":
            if not isinstance(value, bool):
                raise ValueError("enabled must be true or false")
            output[key] = value
        elif key in {"confidence", "iou"}:
            if value is None:
                output[key] = None
            else:
                number = float(value)
                if not 0.01 <= number <= 0.99:
                    raise ValueError(f"{key} must be between 0.01 and 0.99")
                output[key] = number
        elif key == "tracker":
            if value in {None, ""}:
                output[key] = None
            elif str(value) not in {"bytetrack.yaml", "botsort.yaml"}:
                raise ValueError("tracker must be bytetrack.yaml or botsort.yaml")
            else:
                output[key] = str(value)
        elif key == "skip_frames":
            if value is None:
                output[key] = None
            else:
                number = int(value)
                if not 0 <= number <= 30:
                    raise ValueError("skip_frames must be between 0 and 30")
                output[key] = number
        elif key == "ai_fps":
            number = float(value)
            if not 0.5 <= number <= 30.0:
                raise ValueError("ai_fps must be between 0.5 and 30")
            output[key] = number
        elif key == "evidence_pre_seconds":
            number = float(value)
            if not 0.0 <= number <= 30.0:
                raise ValueError("evidence_pre_seconds must be between 0 and 30")
            output[key] = number
        elif key == "evidence_post_seconds":
            number = float(value)
            if not 1.0 <= number <= 120.0:
                raise ValueError("evidence_post_seconds must be between 1 and 120")
            output[key] = number

    if not partial:
        complete = deepcopy(DEFAULT_PREFERENCES)
        complete.update(output)
        return complete
    return output
