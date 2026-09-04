import copy
import json
import logging
import os
import threading
from pathlib import Path
from typing import Dict

from services.security_service import encrypt_credential, decrypt_credential

logger = logging.getLogger(__name__)

CAMERA_SETTINGS_PATH = Path(__file__).parent.parent / "data" / "camera_settings.json"
_SETTINGS_LOCK = threading.RLock()


def ensure_camera_settings_file():
    """Ensure camera settings file exists using an atomic initial write."""
    CAMERA_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _SETTINGS_LOCK:
        if not CAMERA_SETTINGS_PATH.exists():
            _atomic_write({})


def _atomic_write(payload: Dict):
    CAMERA_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = CAMERA_SETTINGS_PATH.with_suffix(CAMERA_SETTINGS_PATH.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, CAMERA_SETTINGS_PATH)


def load_camera_settings() -> Dict:
    """Load camera settings with decrypted credentials for runtime use."""
    ensure_camera_settings_file()
    try:
        with _SETTINGS_LOCK:
            with open(CAMERA_SETTINGS_PATH, "r", encoding="utf-8") as handle:
                data = json.load(handle)

        if not isinstance(data, dict):
            return {}
        data = copy.deepcopy(data)
        for _, config in data.items():
            if isinstance(config, dict) and "onvif_credentials" in config:
                creds = config["onvif_credentials"]
                if isinstance(creds, dict) and "password" in creds:
                    creds["password"] = decrypt_credential(creds["password"])
        return data
    except Exception as exc:
        logger.error("Error loading camera settings: %s", exc)
        return {}


def save_camera_settings(settings: Dict):
    """Save camera settings atomically with AES-256-GCM encrypted credentials."""
    ensure_camera_settings_file()
    try:
        data_to_save = copy.deepcopy(settings if isinstance(settings, dict) else {})
        for _, config in data_to_save.items():
            if isinstance(config, dict) and "onvif_credentials" in config:
                creds = config["onvif_credentials"]
                if isinstance(creds, dict) and "password" in creds:
                    creds["password"] = encrypt_credential(creds["password"])

        with _SETTINGS_LOCK:
            _atomic_write(data_to_save)
    except Exception as exc:
        logger.error("Error saving camera settings: %s", exc)
        raise
