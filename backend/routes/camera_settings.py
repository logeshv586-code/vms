"""
Camera Settings API Routes
Handles camera configuration and ONVIF settings management.
"""

import logging
from typing import Dict, Optional, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from services.onvif_service import onvif_service
from services.camera_settings import load_camera_settings, save_camera_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["camera_settings"])

# Data models
class CameraCredentials(BaseModel):
    ip: str
    username: str
    password: str
    port: int = 80

class ResolutionRequest(BaseModel):
    ip: str
    username: str
    password: str
    width: int
    height: int
    port: int = 80
    frame_rate: int = 15
    bitrate: int = 1024

class StreamSettingsRequest(BaseModel):
    ip: str
    username: str
    password: str
    port: int = 80
    frameRate: Optional[int] = None
    maxBitrate: Optional[int] = None
    videoEncoding: Optional[str] = None
    streamType: Optional[str] = None
    videoType: Optional[str] = None
    bitrateType: Optional[str] = None
    videoQuality: Optional[str] = None
    profile: Optional[str] = None
    iFrameInterval: Optional[int] = None

class CameraSettingsUpdate(BaseModel):
    ip: str
    resolution: Optional[Dict[str, int]] = None
    onvif_credentials: Optional[Dict[str, Any]] = None

@router.get("/camera-settings")
async def get_camera_settings():
    """Get all camera settings"""
    try:
        settings = load_camera_settings()
        return {"success": True, "data": settings}
    except Exception as e:
        logger.error(f"Error getting camera settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/camera-settings/{camera_ip}")
async def update_camera_settings(camera_ip: str, settings: CameraSettingsUpdate):
    """Update settings for a specific camera"""
    try:
        all_settings = load_camera_settings()

        if camera_ip not in all_settings:
            all_settings[camera_ip] = {}

        # Update resolution if provided
        if settings.resolution:
            all_settings[camera_ip]["resolution"] = settings.resolution

        # Update ONVIF credentials if provided
        if settings.onvif_credentials:
            all_settings[camera_ip]["onvif_credentials"] = settings.onvif_credentials

        save_camera_settings(all_settings)

        return {"success": True, "message": f"Settings updated for camera {camera_ip}"}
    except Exception as e:
        logger.error(f"Error updating camera settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/test-onvif-connection")
async def test_onvif_connection(credentials: CameraCredentials):
    """Test ONVIF connection to camera"""
    try:
        # Try the specified port first
        cam = await onvif_service.connect_camera(
            credentials.ip,
            credentials.username,
            credentials.password,
            credentials.port
        )

        if cam:
            return {
                "success": True,
                "message": f"Successfully connected to camera {credentials.ip} on port {credentials.port}",
                "port_used": credentials.port
            }

        # If specified port fails, try common ONVIF ports
        common_ports = [80, 8080, 8000, 8899, 554]
        if credentials.port not in common_ports:
            common_ports.insert(0, credentials.port)

        for port in common_ports:
            if port == credentials.port:
                continue  # Already tried this port

            try:
                cam = await onvif_service.connect_camera(
                    credentials.ip,
                    credentials.username,
                    credentials.password,
                    port
                )

                if cam:
                    return {
                        "success": True,
                        "message": f"Successfully connected to camera {credentials.ip} on port {port} (auto-detected)",
                        "port_used": port
                    }
            except Exception:
                continue  # Try next port

        return {
            "success": False,
            "message": f"Failed to connect to camera {credentials.ip} on any common ONVIF ports (tried: {common_ports})"
        }

    except Exception as e:
        logger.error(f"Error testing ONVIF connection: {e}")
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}"
        }

@router.get("/camera/{camera_ip}/profiles")
async def get_camera_profiles(camera_ip: str, username: str, password: str, port: int = 80):
    """Get video profiles from camera"""
    try:
        profiles = await onvif_service.get_video_profiles(camera_ip, username, password, port)
        return {"success": True, "data": profiles}
    except Exception as e:
        logger.error(f"Error getting camera profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/camera/{camera_ip}/current-resolution")
async def get_current_resolution(camera_ip: str, username: str, password: str, port: int = 80):
    """Get current resolution of camera"""
    try:
        resolution = await onvif_service.get_current_resolution(camera_ip, username, password, port)
        if resolution:
            return {
                "success": True,
                "data": {
                    "width": resolution[0],
                    "height": resolution[1]
                }
            }
        else:
            return {
                "success": False,
                "message": "Could not retrieve current resolution"
            }
    except Exception as e:
        logger.error(f"Error getting current resolution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/camera/{camera_ip}/supported-resolutions")
async def get_supported_resolutions(camera_ip: str, username: str, password: str, port: int = 80):
    """Get supported resolutions from camera"""
    try:
        resolutions = await onvif_service.get_supported_resolutions(camera_ip, username, password, port)
        resolution_list = [{"width": w, "height": h, "label": f"{w}x{h}"} for w, h in resolutions]
        return {"success": True, "data": resolution_list}
    except Exception as e:
        logger.error(f"Error getting supported resolutions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/camera/set-resolution")
async def set_camera_resolution(request: ResolutionRequest):
    """Set camera resolution via ONVIF"""
    try:
        success = await onvif_service.set_camera_resolution(
            request.ip,
            request.username,
            request.password,
            request.width,
            request.height,
            request.port,
            frame_rate=request.frame_rate,
            bitrate=request.bitrate
        )

        if success:
            # Update stored settings
            all_settings = load_camera_settings()
            if request.ip not in all_settings:
                all_settings[request.ip] = {}

            all_settings[request.ip]["resolution"] = {
                "width": request.width,
                "height": request.height
            }
            all_settings[request.ip]["onvif_credentials"] = {
                "username": request.username,
                "password": request.password,
                "port": request.port
            }

            save_camera_settings(all_settings)

            return {
                "success": True,
                "message": f"Resolution successfully changed to {request.width}x{request.height} for camera {request.ip}"
            }
        else:
            # Provide more helpful error message
            error_msg = f"Failed to set resolution {request.width}x{request.height} for camera {request.ip}. "
            error_msg += "This resolution may not be supported by the camera. "
            error_msg += "Try a different resolution or check camera capabilities."

            return {
                "success": False,
                "message": error_msg
            }
    except Exception as e:
        logger.error(f"Error setting camera resolution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete("/camera/{camera_ip}/disconnect")
async def disconnect_camera(camera_ip: str, port: int = 80):
    """Disconnect camera and clear cache"""
    try:
        onvif_service.disconnect_camera(camera_ip, port)
        return {"success": True, "message": f"Disconnected camera {camera_ip}"}
    except Exception as e:
        logger.error(f"Error disconnecting camera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/camera/{camera_ip}/debug-info")
async def get_camera_debug_info(camera_ip: str, username: str, password: str, port: int = 80):
    """Get detailed camera information for debugging"""
    try:
        profiles = await onvif_service.get_video_profiles(camera_ip, username, password, port)
        supported_resolutions = await onvif_service.get_supported_resolutions(camera_ip, username, password, port)
        current_resolution = await onvif_service.get_current_resolution(camera_ip, username, password, port)

        debug_info = {
            "camera_ip": camera_ip,
            "profiles": profiles,
            "supported_resolutions": [{"width": w, "height": h} for w, h in supported_resolutions],
            "current_resolution": {"width": current_resolution[0], "height": current_resolution[1]} if current_resolution else None,
            "profile_count": len(profiles),
            "onvif_port": port
        }

        return {"success": True, "data": debug_info}
    except Exception as e:
        logger.error(f"Error getting debug info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/common-resolutions")
async def get_common_resolutions():
    """Get list of common camera resolutions"""
    common_resolutions = [
        {"width": 1920, "height": 1080, "label": "1080p (1920x1080)"},
        {"width": 1280, "height": 720, "label": "720p (1280x720)"},
        {"width": 800, "height": 600, "label": "SVGA (800x600)"},
        {"width": 640, "height": 480, "label": "VGA (640x480)"},
        {"width": 320, "height": 240, "label": "QVGA (320x240)"},
    ]
    return {"success": True, "data": common_resolutions}

@router.get("/camera/{camera_ip}/current-stream-settings")
async def get_current_stream_settings(camera_ip: str, username: str, password: str, port: int = 80):
    """Get current stream settings from camera"""
    try:
        stream_settings = await onvif_service.get_current_stream_settings(camera_ip, username, password, port)
        if stream_settings:
            return {
                "success": True,
                "data": stream_settings
            }
        else:
            return {
                "success": False,
                "message": "Could not retrieve current stream settings"
            }
    except Exception as e:
        logger.error(f"Error getting current stream settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/camera/{camera_ip}/supported-stream-settings")
async def get_supported_stream_settings(camera_ip: str, username: str, password: str, port: int = 80):
    """Get supported stream settings from camera"""
    try:
        supported_settings = await onvif_service.get_supported_stream_settings(camera_ip, username, password, port)
        return {"success": True, "data": supported_settings}
    except Exception as e:
        logger.error(f"Error getting supported stream settings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post("/camera/set-stream-settings")
async def set_camera_stream_settings(request: StreamSettingsRequest):
    """Set camera stream settings via ONVIF"""
    try:
        result = await onvif_service.set_camera_stream_settings(
            request.ip,
            request.username,
            request.password,
            request.port,
            stream_type=request.streamType,
            video_type=request.videoType,
            bitrate_type=request.bitrateType,
            video_quality=request.videoQuality,
            frame_rate=request.frameRate,
            max_bitrate=request.maxBitrate,
            video_encoding=request.videoEncoding,
            profile=request.profile,
            i_frame_interval=request.iFrameInterval
        )

        logger.info(f"ONVIF service result for {request.ip}: {result}")

        # Check if result is a dictionary with expected keys
        if not isinstance(result, dict):
            logger.error(f"ONVIF service returned unexpected result type: {type(result)}")
            result = {
                "success": False,
                "message": f"ONVIF service returned unexpected result: {result}",
                "settings_applied": {},
                "settings_failed": {},
                "total_attempted": 0,
                "total_succeeded": 0,
                "total_failed": 0
            }

        # Always update stored settings with what was requested (for tracking purposes)
        all_settings = load_camera_settings()
        if request.ip not in all_settings:
            all_settings[request.ip] = {}

        # Store the original request settings
        all_settings[request.ip]["stream_settings"] = {
            "streamType": request.streamType,
            "videoType": request.videoType,
            "bitrateType": request.bitrateType,
            "videoQuality": request.videoQuality,
            "frameRate": request.frameRate,
            "maxBitrate": request.maxBitrate,
            "videoEncoding": request.videoEncoding,
            "profile": request.profile,
            "iFrameInterval": request.iFrameInterval
        }

        # Store what was actually applied successfully
        if result.get("settings_applied"):
            all_settings[request.ip]["applied_settings"] = result["settings_applied"]

        # Store what failed to apply
        if result.get("settings_failed"):
            all_settings[request.ip]["failed_settings"] = result["settings_failed"]

        all_settings[request.ip]["onvif_credentials"] = {
            "username": request.username,
            "password": request.password,
            "port": request.port
        }

        save_camera_settings(all_settings)

        # Return detailed result
        return {
            "success": result.get("success", False),
            "message": result.get("message", "Unknown error occurred"),
            "details": {
                "total_attempted": result.get("total_attempted", 0),
                "total_succeeded": result.get("total_succeeded", 0),
                "total_failed": result.get("total_failed", 0),
                "settings_applied": result.get("settings_applied", {}),
                "settings_failed": result.get("settings_failed", {})
            }
        }

    except Exception as e:
        logger.error(f"Error setting camera stream settings: {e}")
        logger.error(f"Exception type: {type(e)}")
        logger.error(f"Exception details: {str(e)}")

        # Return a detailed error response instead of throwing HTTP exception
        return {
            "success": False,
            "message": f"API error: {str(e)}",
            "details": {
                "total_attempted": 0,
                "total_succeeded": 0,
                "total_failed": 1,
                "settings_applied": {},
                "settings_failed": {"api_error": str(e)}
            }
        }
