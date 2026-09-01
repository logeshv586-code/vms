import json
import logging
from pathlib import Path
from typing import Dict

from services.security_service import encrypt_credential, decrypt_credential

logger = logging.getLogger(__name__)

# Configuration file path
CAMERA_SETTINGS_PATH = Path(__file__).parent.parent / "data" / "camera_settings.json"

def ensure_camera_settings_file():
    """Ensure camera settings file exists"""
    CAMERA_SETTINGS_PATH.parent.mkdir(exist_ok=True)
    if not CAMERA_SETTINGS_PATH.exists():
        with open(CAMERA_SETTINGS_PATH, 'w') as f:
            json.dump({}, f, indent=2)

def load_camera_settings() -> Dict:
    """Load camera settings from file with decrypted credentials"""
    ensure_camera_settings_file()
    try:
        with open(CAMERA_SETTINGS_PATH, 'r') as f:
            data = json.load(f)
            
        # Transparently decrypt credentials for runtime use
        for ip, config in data.items():
            if isinstance(config, dict) and "onvif_credentials" in config:
                creds = config["onvif_credentials"]
                if isinstance(creds, dict) and "password" in creds:
                    creds["password"] = decrypt_credential(creds["password"])
        return data
    except Exception as e:
        logger.error(f"Error loading camera settings: {e}")
        return {}

def save_camera_settings(settings: Dict):
    """Save camera settings to file with AES-256-GCM encrypted credentials"""
    ensure_camera_settings_file()
    try:
        # Create deep copy for saving to avoid mutating in-memory runtime objects
        import copy
        data_to_save = copy.deepcopy(settings)

        for ip, config in data_to_save.items():
            if isinstance(config, dict) and "onvif_credentials" in config:
                creds = config["onvif_credentials"]
                if isinstance(creds, dict) and "password" in creds:
                    creds["password"] = encrypt_credential(creds["password"])

        with open(CAMERA_SETTINGS_PATH, 'w') as f:
            json.dump(data_to_save, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving camera settings: {e}")
        raise e
