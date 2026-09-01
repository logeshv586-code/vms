from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import logging
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import glob
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the workspace root directory
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CAMERA_JSON_PATH = os.path.join(WORKSPACE_ROOT, "backend", "data", "camera_configuration.json")
RECORDINGS_PATH = os.path.join(WORKSPACE_ROOT, "backend", "recordings")
EVENTS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "events_configuration.json")
USERS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "backend", "data", "users_configuration.json")

# Create router
router = APIRouter(prefix="/api/dashboard", tags=["dashboard-analytics"])

# Define models
class SystemMetrics(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime: str

class CameraStats(BaseModel):
    total_cameras: int
    active_cameras: int
    inactive_cameras: int
    collections_count: int

class RecordingStats(BaseModel):
    total_recordings: int
    total_size_gb: float
    recordings_today: int
    recordings_this_week: int
    recordings_this_month: int
    storage_usage_by_camera: Dict[str, float]

class EventStats(BaseModel):
    total_events: int
    events_today: int
    events_this_week: int
    events_by_type: Dict[str, int]
    recent_events: List[Dict[str, Any]]

class UserStats(BaseModel):
    total_users: int
    active_sessions: int
    user_roles: Dict[str, int]

class DashboardAnalytics(BaseModel):
    system_metrics: SystemMetrics
    camera_stats: CameraStats
    recording_stats: RecordingStats
    event_stats: EventStats
    user_stats: UserStats
    last_updated: str

# Helper functions
def get_system_metrics() -> SystemMetrics:
    """Get current system performance metrics"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot_time = psutil.boot_time()
        uptime = str(timedelta(seconds=int(time.time() - boot_time)))
        
        return SystemMetrics(
            cpu_usage=round(cpu_percent, 1),
            memory_usage=round(memory.percent, 1),
            disk_usage=round(disk.percent, 1),
            uptime=uptime
        )
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return SystemMetrics(
            cpu_usage=0.0,
            memory_usage=0.0,
            disk_usage=0.0,
            uptime="Unknown"
        )

def get_camera_stats() -> CameraStats:
    """Get camera statistics from configuration"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return CameraStats(
                total_cameras=0,
                active_cameras=0,
                inactive_cameras=0,
                collections_count=0
            )
        
        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)
        
        total_cameras = 0
        collections_count = len(camera_data)
        
        for collection_name, cameras in camera_data.items():
            total_cameras += len(cameras)
        
        # For now, assume all cameras are active (in a real implementation, 
        # you would check actual stream status)
        active_cameras = total_cameras
        inactive_cameras = 0
        
        return CameraStats(
            total_cameras=total_cameras,
            active_cameras=active_cameras,
            inactive_cameras=inactive_cameras,
            collections_count=collections_count
        )
    except Exception as e:
        logger.error(f"Error getting camera stats: {e}")
        return CameraStats(
            total_cameras=0,
            active_cameras=0,
            inactive_cameras=0,
            collections_count=0
        )

def get_recording_stats() -> RecordingStats:
    """Get recording statistics from recordings directory"""
    try:
        if not os.path.exists(RECORDINGS_PATH):
            return RecordingStats(
                total_recordings=0,
                total_size_gb=0.0,
                recordings_today=0,
                recordings_this_week=0,
                recordings_this_month=0,
                storage_usage_by_camera={}
            )
        
        total_recordings = 0
        total_size_bytes = 0
        recordings_today = 0
        recordings_this_week = 0
        recordings_this_month = 0
        storage_usage_by_camera = {}
        
        now = datetime.now()
        today = now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Scan all recording directories
        for camera_dir in glob.glob(os.path.join(RECORDINGS_PATH, "*")):
            if os.path.isdir(camera_dir):
                camera_name = os.path.basename(camera_dir)
                camera_size = 0
                camera_recordings = 0
                
                # Scan all files in camera directory
                for file_path in glob.glob(os.path.join(camera_dir, "*")):
                    if os.path.isfile(file_path):
                        file_stat = os.stat(file_path)
                        file_size = file_stat.st_size
                        file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                        
                        total_recordings += 1
                        total_size_bytes += file_size
                        camera_size += file_size
                        camera_recordings += 1
                        
                        # Count recordings by time period
                        if file_mtime.date() == today:
                            recordings_today += 1
                        if file_mtime >= week_ago:
                            recordings_this_week += 1
                        if file_mtime >= month_ago:
                            recordings_this_month += 1
                
                storage_usage_by_camera[camera_name] = round(camera_size / (1024**3), 2)  # GB
        
        return RecordingStats(
            total_recordings=total_recordings,
            total_size_gb=round(total_size_bytes / (1024**3), 2),
            recordings_today=recordings_today,
            recordings_this_week=recordings_this_week,
            recordings_this_month=recordings_this_month,
            storage_usage_by_camera=storage_usage_by_camera
        )
    except Exception as e:
        logger.error(f"Error getting recording stats: {e}")
        return RecordingStats(
            total_recordings=0,
            total_size_gb=0.0,
            recordings_today=0,
            recordings_this_week=0,
            recordings_this_month=0,
            storage_usage_by_camera={}
        )

def get_event_stats() -> EventStats:
    """Get event statistics from events configuration"""
    try:
        if not os.path.exists(EVENTS_CONFIG_PATH):
            return EventStats(
                total_events=0,
                events_today=0,
                events_this_week=0,
                events_by_type={},
                recent_events=[]
            )
        
        with open(EVENTS_CONFIG_PATH, "r") as f:
            events_data = json.load(f)
        
        # For now, return mock data since we don't have actual event logs
        # In a real implementation, you would query an event database
        events_by_type = {}
        if "rules" in events_data:
            for rule in events_data["rules"]:
                if rule.get("enabled", False):
                    events_by_type[rule["name"]] = 0  # Would be actual count
        
        return EventStats(
            total_events=0,
            events_today=0,
            events_this_week=0,
            events_by_type=events_by_type,
            recent_events=[]
        )
    except Exception as e:
        logger.error(f"Error getting event stats: {e}")
        return EventStats(
            total_events=0,
            events_today=0,
            events_this_week=0,
            events_by_type={},
            recent_events=[]
        )

def get_user_stats() -> UserStats:
    """Get user statistics from users configuration"""
    try:
        if not os.path.exists(USERS_CONFIG_PATH):
            return UserStats(
                total_users=0,
                active_sessions=0,
                user_roles={}
            )

        with open(USERS_CONFIG_PATH, "r") as f:
            users_data = json.load(f)

        total_users = len(users_data.get("users", []))
        user_roles = {}

        for user in users_data.get("users", []):
            role = user.get("role", "Unknown")
            user_roles[role] = user_roles.get(role, 0) + 1

        return UserStats(
            total_users=total_users,
            active_sessions=1,  # Mock data - would track actual sessions
            user_roles=user_roles
        )
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return UserStats(
            total_users=0,
            active_sessions=0,
            user_roles={}
        )

# API Endpoints
@router.get("/analytics", response_model=DashboardAnalytics)
async def get_dashboard_analytics():
    """Get comprehensive dashboard analytics data"""
    try:
        analytics = DashboardAnalytics(
            system_metrics=get_system_metrics(),
            camera_stats=get_camera_stats(),
            recording_stats=get_recording_stats(),
            event_stats=get_event_stats(),
            user_stats=get_user_stats(),
            last_updated=datetime.now().isoformat()
        )
        return analytics
    except Exception as e:
        logger.error(f"Error getting dashboard analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system-metrics", response_model=SystemMetrics)
async def get_system_metrics_endpoint():
    """Get current system performance metrics"""
    try:
        return get_system_metrics()
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/camera-stats", response_model=CameraStats)
async def get_camera_stats_endpoint():
    """Get camera statistics"""
    try:
        return get_camera_stats()
    except Exception as e:
        logger.error(f"Error getting camera stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recording-stats", response_model=RecordingStats)
async def get_recording_stats_endpoint():
    """Get recording statistics"""
    try:
        return get_recording_stats()
    except Exception as e:
        logger.error(f"Error getting recording stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/event-stats", response_model=EventStats)
async def get_event_stats_endpoint():
    """Get event statistics"""
    try:
        return get_event_stats()
    except Exception as e:
        logger.error(f"Error getting event stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user-stats", response_model=UserStats)
async def get_user_stats_endpoint():
    """Get user statistics"""
    try:
        return get_user_stats()
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storage-usage")
async def get_storage_usage():
    """Get detailed storage usage information"""
    try:
        recording_stats = get_recording_stats()
        system_metrics = get_system_metrics()

        return {
            "total_storage_gb": recording_stats.total_size_gb,
            "disk_usage_percent": system_metrics.disk_usage,
            "storage_by_camera": recording_stats.storage_usage_by_camera,
            "recordings_count": recording_stats.total_recordings
        }
    except Exception as e:
        logger.error(f"Error getting storage usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/activity-summary")
async def get_activity_summary():
    """Get recent activity summary"""
    try:
        recording_stats = get_recording_stats()
        event_stats = get_event_stats()

        return {
            "recordings_today": recording_stats.recordings_today,
            "recordings_this_week": recording_stats.recordings_this_week,
            "events_today": event_stats.events_today,
            "events_this_week": event_stats.events_this_week,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting activity summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
