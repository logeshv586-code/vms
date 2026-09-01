from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import logging
from typing import List, Dict, Optional, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the workspace root directory
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
EVENTS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "events_configuration.json")

# Create router
router = APIRouter(prefix="/api/augment", tags=["events"])

# Define models
class EventRule(BaseModel):
    id: int
    name: str
    enabled: bool
    hotlisted: bool
    show_popup: bool
    play_audio: bool

class EventRuleSet(BaseModel):
    rules: List[EventRule]

class DetectionRuleToggle(BaseModel):
    event: str
    enabled: bool

class EventStatistic(BaseModel):
    event_id: int
    event_name: str
    count: int
    camera_id: Optional[str] = None
    timestamp: str

class EventStatisticsResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    error: Optional[str] = None

# Helper function to ensure the events configuration file exists
def ensure_events_config():
    if not os.path.exists(EVENTS_CONFIG_PATH):
        # Create default configuration with all event types
        default_events = {
            "rules": [
                {"id": 1, "name": "Appearance Search", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
                {"id": 2, "name": "Camera Tamper", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
                {"id": 3, "name": "Chain/Handbag Snatching", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": True},
                {"id": 4, "name": "Crowd Detection", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
                {"id": 5, "name": "Eve Teasing", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": True},
                {"id": 6, "name": "Face Capture", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": False},
                {"id": 7, "name": "Face Recognition", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
                {"id": 8, "name": "Gesture Detection", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
                {"id": 9, "name": "Graffiti and Vandalism Detection", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": False},
                {"id": 10, "name": "Intrusion Detection", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
                {"id": 11, "name": "Lakshmanrekha Crossing", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": False},
                {"id": 12, "name": "Loitering", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
                {"id": 13, "name": "Mobile Snatching", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": True},
                {"id": 14, "name": "Object Classification", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
                {"id": 15, "name": "People Fighting", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
                {"id": 16, "name": "Person Collapsing", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": True},
                {"id": 17, "name": "Strike / Morcha / Hartal / Procession", "enabled": True, "hotlisted": False, "show_popup": True, "play_audio": False},
                {"id": 18, "name": "Suspected Appearance", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
                {"id": 19, "name": "Unattended Object", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
                {"id": 20, "name": "Women Surrounded by Men", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
                {"id": 21, "name": "Women/Infant Abduction", "enabled": True, "hotlisted": True, "show_popup": True, "play_audio": True},
                {"id": 22, "name": "Vehicle Monitoring", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False},
                {"id": 23, "name": "Zone Monitoring", "enabled": True, "hotlisted": False, "show_popup": False, "play_audio": False}
            ],
            "statistics": []
        }

        with open(EVENTS_CONFIG_PATH, "w") as f:
            json.dump(default_events, f, indent=2)

        logger.info(f"Created default events configuration at {EVENTS_CONFIG_PATH}")

# Endpoint to get all event rules
@router.get("/events/rules")
async def get_event_rules():
    try:
        ensure_events_config()

        with open(EVENTS_CONFIG_PATH, "r") as f:
            events_data = json.load(f)

        return {
            "success": True,
            "data": {"rules": events_data["rules"]},
            "message": "Event rules retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting event rules: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Endpoint to update event rules
@router.post("/events/rules")
async def update_event_rules(rule_set: EventRuleSet):
    try:
        ensure_events_config()

        with open(EVENTS_CONFIG_PATH, "r") as f:
            events_data = json.load(f)

        # Update rules
        events_data["rules"] = [rule.dict() for rule in rule_set.rules]

        with open(EVENTS_CONFIG_PATH, "w") as f:
            json.dump(events_data, f, indent=2)

        return {
            "success": True,
            "message": "Event rules updated successfully"
        }
    except Exception as e:
        logger.error(f"Error updating event rules: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Endpoint to toggle a single detection rule
@router.post("/detection-rule")
async def toggle_detection_rule(rule_toggle: DetectionRuleToggle):
    try:
        ensure_events_config()

        with open(EVENTS_CONFIG_PATH, "r") as f:
            events_data = json.load(f)

        # Find the rule by name and update its enabled status
        rule_found = False
        for rule in events_data["rules"]:
            if rule["name"] == rule_toggle.event:
                rule["enabled"] = rule_toggle.enabled
                rule_found = True
                break

        if not rule_found:
            return {
                "success": False,
                "error": f"Rule '{rule_toggle.event}' not found"
            }

        # Save the updated configuration
        with open(EVENTS_CONFIG_PATH, "w") as f:
            json.dump(events_data, f, indent=2)

        return {
            "success": True,
            "message": f"Detection rule '{rule_toggle.event}' {'enabled' if rule_toggle.enabled else 'disabled'} successfully"
        }
    except Exception as e:
        logger.error(f"Error toggling detection rule: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# Endpoint to get event statistics
@router.get("/events/statistics")
async def get_event_statistics(camera_id: Optional[str] = None, event_id: Optional[int] = None):
    try:
        ensure_events_config()

        # In a real application, this would query a database for actual statistics
        # For this example, we'll generate some mock data
        mock_statistics = [
            {"event_id": 1, "event_name": "Appearance Search", "count": 15, "camera_id": "camera1", "timestamp": "2023-05-08T10:30:00Z"},
            {"event_id": 2, "event_name": "Camera Tamper", "count": 3, "camera_id": "camera2", "timestamp": "2023-05-08T11:15:00Z"},
            {"event_id": 6, "event_name": "Face Capture", "count": 42, "camera_id": "camera1", "timestamp": "2023-05-08T12:00:00Z"},
            {"event_id": 10, "event_name": "Intrusion Detection", "count": 7, "camera_id": "camera3", "timestamp": "2023-05-08T13:45:00Z"},
            {"event_id": 19, "event_name": "Unattended Object", "count": 2, "camera_id": "camera2", "timestamp": "2023-05-08T14:30:00Z"}
        ]

        # Filter statistics based on query parameters
        filtered_stats = mock_statistics
        if camera_id:
            filtered_stats = [stat for stat in filtered_stats if stat["camera_id"] == camera_id]
        if event_id:
            filtered_stats = [stat for stat in filtered_stats if stat["event_id"] == event_id]

        return {
            "success": True,
            "data": {"statistics": filtered_stats},
            "message": "Event statistics retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting event statistics: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

# --- Event Management API ---
EVENT_RECORDS_PATH = os.path.join(WORKSPACE_ROOT, "backend", "data", "event_records.json")

def get_event_records():
    if not os.path.exists(EVENT_RECORDS_PATH):
        return []
    try:
        with open(EVENT_RECORDS_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading event records: {e}")
        return []

def save_event_records(records):
    try:
        os.makedirs(os.path.dirname(EVENT_RECORDS_PATH), exist_ok=True)
        with open(EVENT_RECORDS_PATH, "w") as f:
            json.dump(records, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error writing event records: {e}")
        return False

@router.get("/events/current")
async def get_current_events():
    try:
        records = get_event_records()
        # Active events are those with status == "Active" or "Acknowledged"
        active_events = [e for e in records if e.get("status") in ["Active", "Acknowledged"]]
        # Sort by newest first
        active_events.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {
            "success": True,
            "data": active_events,
            "message": "Current events retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting current events: {e}")
        return {"success": False, "error": str(e)}

def rule_matches(filter_rule: str, event_rule: str) -> bool:
    if not filter_rule or filter_rule in ["all", "All Rules"]:
        return True
    if not event_rule:
        return False
    fr, er = filter_rule.lower().strip(), event_rule.lower().strip()
    if fr == er or fr in er or er in fr:
        return True
    clean_er = er.split("(")[0].strip()
    clean_fr = fr.split("(")[0].strip()
    return clean_er in clean_fr or clean_fr in clean_er

def category_matches(filter_cat: str, event_cat: str) -> bool:
    if not filter_cat or filter_cat in ["all", "All Categories"]:
        return True
    if not event_cat:
        return False
    fc, ec = filter_cat.lower().strip(), event_cat.lower().strip()
    return fc == ec or fc in ec or ec in fc

@router.get("/events/search")
async def search_events(
    category: Optional[str] = None,
    rule: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    camera: Optional[str] = None,
    location: Optional[str] = None,
    acknowledged: Optional[str] = None,
    dateRange: Optional[str] = None
):
    try:
        records = get_event_records()
        
        filtered = records
        if category and category not in ["all", "All Categories"]:
            filtered = [e for e in filtered if category_matches(category, e.get("category", ""))]
        if rule and rule not in ["all", "All Rules"]:
            filtered = [e for e in filtered if rule_matches(rule, e.get("rule_name", ""))]
        if priority and priority not in ["all", "All Priorities"]:
            filtered = [e for e in filtered if e.get("priority", "").lower() == priority.lower()]
        if status and status not in ["all", "All Statuses"]:
            filtered = [e for e in filtered if e.get("status", "").lower() == status.lower()]
        if camera and camera not in ["all", "All Cameras"]:
            clean_cam = camera.lower().replace(" (", "_").replace(")", "")
            filtered = [e for e in filtered if clean_cam in e.get("camera_name", "").lower() or clean_cam in e.get("camera_id", "").lower()]
        if location and location not in ["all", "All Locations"]:
            filtered = [e for e in filtered if location.lower() in e.get("location", "").lower()]
        if acknowledged and acknowledged not in ["all", "All Events"]:
            is_ack = acknowledged.lower() in ["acknowledged", "true"]
            filtered = [e for e in filtered if e.get("acknowledged") == is_ack]
            
        filtered.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return {
            "success": True,
            "data": filtered,
            "message": "Events searched successfully"
        }
    except Exception as e:
        logger.error(f"Error searching events: {e}")
        return {"success": False, "error": str(e)}

@router.post("/events/acknowledge/{event_id}")
async def acknowledge_event(event_id: str):
    try:
        records = get_event_records()
        found = False
        for e in records:
            if e.get("event_id") == event_id:
                e["acknowledged"] = True
                if e["status"] == "Active":
                    e["status"] = "Acknowledged"
                found = True
                break
        if not found:
            return {"success": False, "error": "Event not found"}
            
        save_event_records(records)
        return {"success": True, "message": "Event acknowledged"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/events/resolve/{event_id}")
async def resolve_event(event_id: str):
    try:
        records = get_event_records()
        found = False
        for e in records:
            if e.get("event_id") == event_id:
                e["status"] = "Resolved"
                from datetime import datetime
                e["resolved_at"] = datetime.now().isoformat()
                found = True
                break
        if not found:
            return {"success": False, "error": "Event not found"}
            
        save_event_records(records)
        return {"success": True, "message": "Event resolved"}
    except Exception as e:
        return {"success": False, "error": str(e)}

from fastapi.responses import FileResponse

@router.get("/events/proofs/{filename}")
async def get_video_proof(filename: str):
    file_path = os.path.join(PROOFS_DIR, filename)
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return FileResponse(file_path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video proof not found or empty")

