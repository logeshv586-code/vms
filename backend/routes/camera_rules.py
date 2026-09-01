from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import logging
from typing import List, Dict, Optional, Any

from services.pattern_engine import pattern_engine

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the workspace root directory
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
EVENTS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "events_configuration.json")
CAMERA_RULES_PATH = os.path.join(WORKSPACE_ROOT, "camera_rules.json")

# Create router
router = APIRouter(prefix="/api/augment", tags=["camera_rules"])

# Define models
class CameraRuleRequest(BaseModel):
    cameraIds: List[str]
    ruleIds: List[int]

class CameraRuleResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None

# Helper function to ensure the camera rules configuration file exists
def ensure_camera_rules_config():
    if not os.path.exists(CAMERA_RULES_PATH):
        # Create default configuration with empty camera rules
        default_camera_rules = {
            "camera_rules": {}
        }

        with open(CAMERA_RULES_PATH, "w") as f:
            json.dump(default_camera_rules, f, indent=2)

        logger.info(f"Created default camera rules configuration at {CAMERA_RULES_PATH}")

# Helper function to ensure the events configuration file exists
def ensure_events_config():
    if not os.path.exists(EVENTS_CONFIG_PATH):
        logger.error(f"Events configuration file not found at {EVENTS_CONFIG_PATH}")
        raise HTTPException(status_code=500, detail="Events configuration file not found")

# Endpoint to get camera rules
@router.get("/camera-rules")
async def get_camera_rules():
    try:
        ensure_camera_rules_config()

        with open(CAMERA_RULES_PATH, "r") as f:
            camera_rules_data = json.load(f)

        return {
            "success": True,
            "data": {"cameraRules": camera_rules_data.get("camera_rules", {})},
            "message": "Camera rules retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting camera rules: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Endpoint to apply rules to cameras
@router.post("/apply-camera-rules")
async def apply_camera_rules(request: CameraRuleRequest):
    try:
        ensure_camera_rules_config()
        ensure_events_config()

        # Validate that all rule IDs are valid and enabled
        with open(EVENTS_CONFIG_PATH, "r") as f:
            events_data = json.load(f)
            
        # Get all enabled rule IDs
        enabled_rule_ids = [rule["id"] for rule in events_data.get("rules", []) if rule.get("enabled", False)]
        
        # Check if all requested rule IDs are enabled
        invalid_rules = [rule_id for rule_id in request.ruleIds if rule_id not in enabled_rule_ids]
        if invalid_rules:
            return {
                "success": False,
                "error": f"The following rules are not enabled: {invalid_rules}"
            }

        # Load current camera rules
        with open(CAMERA_RULES_PATH, "r") as f:
            camera_rules_data = json.load(f)
        
        camera_rules = camera_rules_data.get("camera_rules", {})
        
        # Update camera rules
        for camera_id in request.cameraIds:
            camera_rules[camera_id] = request.ruleIds
        
        # Save updated camera rules
        camera_rules_data["camera_rules"] = camera_rules
        with open(CAMERA_RULES_PATH, "w") as f:
            json.dump(camera_rules_data, f, indent=2)

        # Notify engine to reload rules
        pattern_engine.reload_config()

        return {
            "success": True,
            "data": {"cameraRules": camera_rules},
            "message": f"Rules applied successfully to {len(request.cameraIds)} cameras"
        }
    except Exception as e:
        logger.error(f"Error applying camera rules: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }
