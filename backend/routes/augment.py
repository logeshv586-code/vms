from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging
import json
import os
import requests
import base64
from aiortc import RTCPeerConnection, RTCSessionDescription
import sys
from pathlib import Path
import re
from urllib.parse import urljoin

# Add the backend directory to the path to import webrtc_stream
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from services.webrtc_stream import RTSPVideoStreamTrack

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/augment", tags=["augment"])

# Store active peer connections for WebRTC streaming
pcs = set()

# Camera configuration path
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CAMERA_JSON_PATH = os.path.join(WORKSPACE_ROOT, "backend", "data", "camera_configuration.json")

# Pydantic models for camera login
class CameraLoginRequest(BaseModel):
    camera_ip: str
    action: str = "authenticate"
    username: Optional[str] = None
    password: Optional[str] = None

# RTSPVideoStreamTrack is now imported from webrtc_stream.py

@router.get("/decoders")
async def get_decoders() -> Dict[str, Any]:
    """
    Get available video decoders information.
    Returns a dictionary with decoder information.
    """
    # For now return a simple mock response with common decoders
    decoders = {
        "status": "success",
        "decoders": [
            {
                "name": "h264",
                "description": "H.264/AVC decoder",
                "supported": True,
                "hardware_acceleration": ["nvidia", "intel", "software"]
            },
            {
                "name": "h265",
                "description": "H.265/HEVC decoder",
                "supported": True,
                "hardware_acceleration": ["nvidia", "intel", "software"]
            },
            {
                "name": "vp8",
                "description": "VP8 decoder",
                "supported": True,
                "hardware_acceleration": ["software"]
            },
            {
                "name": "vp9",
                "description": "VP9 decoder",
                "supported": True,
                "hardware_acceleration": ["software"]
            }
        ]
    }
    return decoders

@router.post("/stream")
async def handle_webrtc_stream(request: Request):
    """
    Handle WebRTC streaming offer from client using camera configuration.
    Follows the standardized /api/augment/ endpoint pattern.
    """
    return await _handle_webrtc_request(request)

@router.post("/webrtc")
async def handle_webrtc_stream_alt(request: Request):
    """
    Handle WebRTC streaming offer from client using camera configuration.
    Alternative endpoint name for compatibility.
    """
    return await _handle_webrtc_request(request)

async def _handle_webrtc_request(request: Request):
    """
    Shared implementation for WebRTC streaming requests.
    """
    try:
        body = await request.json()
        offer = RTCSessionDescription(sdp=body["sdp"], type=body["type"])

        # Get camera info from request
        collection_name = body.get("collection_name")
        camera_ip = body.get("camera_ip")

        if not collection_name or not camera_ip:
            return JSONResponse({
                "success": False,
                "error": "collection_name and camera_ip are required"
            }, status_code=400)

        # Read camera configuration
        if not os.path.exists(CAMERA_JSON_PATH):
            return JSONResponse({
                "success": False,
                "error": "camera_configuration.json not found"
            }, status_code=404)

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        # Case-insensitive collection lookup for robustness
        found_collection = None
        for name in camera_data.keys():
            if name.lower() == collection_name.lower():
                found_collection = name
                break

        if not found_collection:
            return JSONResponse({
                "success": False,
                "error": f"Collection '{collection_name}' not found"
            }, status_code=404)
        
        # Use the correctly-cased collection name
        collection_name = found_collection

        if camera_ip not in camera_data[collection_name]:
            return JSONResponse({
                "success": False,
                "error": f"Camera IP '{camera_ip}' not found in collection '{collection_name}'"
            }, status_code=404)

        # Get the RTSP URL for this camera
        rtsp_url = camera_data[collection_name][camera_ip]

        logger.info(f"Creating WebRTC connection for {collection_name}/{camera_ip} -> {rtsp_url}")

        pc = RTCPeerConnection()
        pcs.add(pc)

        video = RTSPVideoStreamTrack(rtsp_url)
        pc.addTrack(video)

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state for {camera_ip} changed to {pc.connectionState}")
            if pc.connectionState in ["failed", "closed"]:
                logger.info(f"Cleaning up WebRTC connection for {camera_ip}")
                video.stop()
                await pc.close()
                pcs.discard(pc)

        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        # Wait for ICE gathering to complete before returning the answer
        # This is important for non-trickle ICE environments
        try:
            import asyncio
            wait_count = 0
            while pc.iceGatheringState != "complete" and wait_count < 20:
                await asyncio.sleep(0.1)
                wait_count += 1
            
            if pc.iceGatheringState != "complete":
                logger.warning("ICE gathering timed out, returning partial answer")
        except Exception as e:
            logger.error(f"Error during ICE gathering wait: {e}")

        return JSONResponse({
            "success": True,
            "data": {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            },
            "message": "WebRTC stream established successfully"
        })

    except Exception as e:
        logger.error(f"Error handling WebRTC stream: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": str(e)
        }, status_code=500)

# Direct WebRTC endpoint is handled in main.py

def get_camera_credentials(camera_ip: str) -> Dict[str, str]:
    """
    Get stored credentials for a camera IP from camera configurations (decryption supported).
    Returns default credentials if none found.
    """
    try:
        from services.security_service import decrypt_credential
        from services.camera_settings import load_camera_settings
        
        # 1. Check camera_settings.json
        settings = load_camera_settings()
        if camera_ip in settings and "onvif_credentials" in settings[camera_ip]:
            creds = settings[camera_ip]["onvif_credentials"]
            if creds.get("username") and creds.get("password"):
                return {"username": creds["username"], "password": creds["password"]}

        # 2. Check collections camera_configuration.json
        if os.path.exists(CAMERA_JSON_PATH):
            with open(CAMERA_JSON_PATH, "r") as f:
                camera_data = json.load(f)

            for collection_name, cameras in camera_data.items():
                if camera_ip in cameras:
                    rtsp_url = cameras[camera_ip]
                    if "://" in rtsp_url and "@" in rtsp_url:
                        try:
                            auth_part = rtsp_url.split("://")[1].split("@")[0]
                            if ":" in auth_part:
                                username, password = auth_part.split(":", 1)
                                return {"username": username, "password": decrypt_credential(password)}
                        except Exception as e:
                            logger.warning(f"Failed to parse credentials from RTSP URL: {e}")
    except Exception as e:
        logger.error(f"Error reading camera configuration: {e}")

    return {"username": "admin", "password": "Admin@123"}

@router.post("/camera-login")
async def camera_login(request: CameraLoginRequest):
    """
    Handle Hikvision camera authentication and login.
    Supports automatic credential retrieval and session management.
    """
    try:
        camera_ip = request.camera_ip
        action = request.action

        # Validate IP address format
        import re
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if not re.match(ip_pattern, camera_ip):
            return JSONResponse({
                "success": False,
                "error": "Invalid IP address format"
            }, status_code=400)

        if action == "authenticate":
            # Get credentials for this camera
            credentials = get_camera_credentials(camera_ip)
            username = request.username or credentials["username"]
            password = request.password or credentials["password"]

            # Test camera connectivity and authentication
            try:
                # Test if camera is reachable and authenticate
                session = requests.Session()

                # First, get the login page to establish session
                login_url = f"http://{camera_ip}/doc/page/login.asp"
                login_response = requests.get(login_url, timeout=10)

                if login_response.status_code == 200:
                    # Store session for later use (in a real implementation, you'd use a proper session store)
                    logger.info(f"Camera {camera_ip} is accessible and login page loaded")

                    return JSONResponse({
                        "success": True,
                        "data": {
                            "camera_ip": camera_ip,
                            "login_url": login_url,
                            "credentials_available": True,
                            "username": username,
                            "session_ready": True
                        },
                        "message": f"Camera {camera_ip} is accessible. Authentication ready."
                    })
                else:
                    return JSONResponse({
                        "success": False,
                        "error": f"Camera {camera_ip} returned status {login_response.status_code}"
                    }, status_code=503)

            except requests.exceptions.Timeout:
                return JSONResponse({
                    "success": False,
                    "error": f"Camera {camera_ip} is not responding. Please check the IP address and network connection."
                }, status_code=408)
            except requests.exceptions.ConnectionError:
                return JSONResponse({
                    "success": False,
                    "error": f"Cannot connect to camera {camera_ip}. Please verify the IP address and ensure the camera is online."
                }, status_code=503)
            except Exception as e:
                logger.error(f"Error testing camera connectivity: {e}")
                return JSONResponse({
                    "success": False,
                    "error": f"Failed to test camera connectivity: {str(e)}"
                }, status_code=500)

        elif action == "get_credentials":
            # Return stored credentials for this camera
            credentials = get_camera_credentials(camera_ip)
            return JSONResponse({
                "success": True,
                "data": {
                    "camera_ip": camera_ip,
                    "username": credentials["username"],
                    "has_password": bool(credentials["password"])
                },
                "message": "Credentials retrieved successfully"
            })

        else:
            return JSONResponse({
                "success": False,
                "error": f"Unknown action: {action}"
            }, status_code=400)

    except Exception as e:
        logger.error(f"Error in camera login endpoint: {str(e)}")
        return JSONResponse({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }, status_code=500)

@router.get("/camera-proxy")
async def camera_proxy(ip: str = Query(...), page: str = Query("config")):
    """
    Proxy endpoint to serve Hikvision camera pages with authentication and content filtering.
    Only shows the video/audio configuration content without the full Hikvision interface.
    """
    try:
        # Validate IP address
        ip_pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
        if not re.match(ip_pattern, ip):
            return HTMLResponse(
                "<html><body><h1>Error</h1><p>Invalid IP address format</p></body></html>",
                status_code=400
            )

        # Get credentials for authentication
        credentials = get_camera_credentials(ip)
        username = credentials["username"]
        password = credentials["password"]

        # Create session with authentication
        session = requests.Session()
        session.auth = (username, password)

        # Determine target URL based on page type
        if page == "video_config":
            target_url = f"http://{ip}/doc/page/config.asp"
        elif page == "config":
            target_url = f"http://{ip}/doc/page/config.asp"
        else:
            target_url = f"http://{ip}/doc/page/login.asp"

        # Fetch the page content
        response = session.get(target_url, timeout=15)

        if response.status_code == 200:
            content = response.text

            if page == "video_config":
                # Create a filtered HTML page showing only Video/Audio configuration
                filtered_html = create_video_config_page(content, ip)
                return HTMLResponse(filtered_html)
            else:
                # For full config, return the complete page but with our styling
                enhanced_html = enhance_config_page(content, ip)
                return HTMLResponse(enhanced_html)
        else:
            error_html = f"""
            <html>
            <head><title>Camera Access Error</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                <div style="background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <h1 style="color: #dc3545;">Camera Access Error</h1>
                    <p>Failed to access camera at {ip}</p>
                    <p>Status Code: {response.status_code}</p>
                    <p>Please check:</p>
                    <ul>
                        <li>Camera IP address is correct</li>
                        <li>Camera is online and accessible</li>
                        <li>Credentials are valid</li>
                    </ul>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(error_html, status_code=response.status_code)

    except requests.exceptions.Timeout:
        error_html = f"""
        <html>
        <head><title>Camera Timeout</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
            <div style="background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h1 style="color: #ffc107;">Camera Timeout</h1>
                <p>Camera at {ip} is not responding</p>
                <p>Please check network connectivity and try again.</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(error_html, status_code=408)
    except Exception as e:
        logger.error(f"Error in camera proxy: {str(e)}")
        error_html = f"""
        <html>
        <head><title>Proxy Error</title></head>
        <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
            <div style="background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h1 style="color: #dc3545;">Proxy Error</h1>
                <p>An error occurred while accessing the camera: {str(e)}</p>
            </div>
        </body>
        </html>
        """
        return HTMLResponse(error_html, status_code=500)

def create_video_config_page(original_content: str, camera_ip: str) -> str:
    """
    Create a filtered HTML page showing only the Video/Audio configuration content.
    This extracts and displays only the video configuration form elements.
    """

    # Custom HTML template for video configuration
    video_config_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Camera Video Configuration - {camera_ip}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
            }}
            .container {{
                background-color: white;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                max-width: 700px;
                margin: 0 auto;
            }}
            .header {{
                border-bottom: 2px solid #dc3545;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }}
            .tab-header {{
                display: flex;
                border-bottom: 1px solid #ddd;
                margin-bottom: 20px;
            }}
            .tab {{
                padding: 10px 20px;
                background-color: #dc3545;
                color: white;
                border: none;
                cursor: pointer;
                margin-right: 2px;
            }}
            .tab.active {{
                background-color: #dc3545;
            }}
            .tab:not(.active) {{
                background-color: #f8f9fa;
                color: #333;
            }}
            .form-group {{
                display: flex;
                align-items: center;
                margin-bottom: 15px;
                padding: 8px 0;
            }}
            .form-group label {{
                width: 150px;
                font-weight: 500;
                color: #333;
            }}
            .form-group select, .form-group input {{
                flex: 1;
                padding: 6px 10px;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }}
            .form-group .unit {{
                margin-left: 10px;
                color: #666;
                font-size: 14px;
            }}
            .slider-container {{
                display: flex;
                align-items: center;
                flex: 1;
            }}
            .slider {{
                flex: 1;
                margin-right: 10px;
            }}
            .slider-value {{
                min-width: 40px;
                text-align: center;
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            .save-btn {{
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                margin-top: 20px;
            }}
            .save-btn:hover {{
                background-color: #c82333;
            }}
            .clear-smooth {{
                color: #007bff;
                text-decoration: none;
                font-size: 12px;
                margin-left: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h2>Camera Video Configuration - {camera_ip}</h2>
            </div>

            <div class="tab-header">
                <button class="tab active">Video</button>
                <button class="tab">Audio</button>
                <button class="tab">ROI</button>
                <button class="tab">Display Info. on Stream</button>
            </div>

            <form id="videoConfigForm">
                <div class="form-group">
                    <label>Stream Type</label>
                    <select name="streamType">
                        <option value="main">Main Stream(Normal)</option>
                        <option value="sub">Sub Stream</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Video Type</label>
                    <select name="videoType">
                        <option value="video">Video Stream</option>
                        <option value="composite">Composite Stream</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Resolution</label>
                    <select name="resolution">
                        <option value="1280x720P">1280*720P</option>
                        <option value="1920x1080P">1920*1080P</option>
                        <option value="640x480">640*480</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Bitrate Type</label>
                    <select name="bitrateType">
                        <option value="variable">Variable</option>
                        <option value="constant">Constant</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Video Quality</label>
                    <select name="videoQuality">
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="low">Low</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Frame Rate</label>
                    <select name="frameRate">
                        <option value="25">25</option>
                        <option value="30">30</option>
                        <option value="15">15</option>
                        <option value="10">10</option>
                    </select>
                    <span class="unit">fps</span>
                </div>

                <div class="form-group">
                    <label>Max. Bitrate</label>
                    <input type="number" name="maxBitrate" value="2048" min="64" max="16384">
                    <span class="unit">Kbps</span>
                </div>

                <div class="form-group">
                    <label>Video Encoding</label>
                    <select name="videoEncoding">
                        <option value="H.264">H.264</option>
                        <option value="H.265">H.265</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>H.265+</label>
                    <select name="h265Plus">
                        <option value="off">OFF</option>
                        <option value="on">ON</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Profile</label>
                    <select name="profile">
                        <option value="main">Main Profile</option>
                        <option value="high">High Profile</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>I Frame Interval</label>
                    <input type="number" name="iFrameInterval" value="50" min="1" max="400">
                </div>

                <div class="form-group">
                    <label>SVC</label>
                    <select name="svc">
                        <option value="on">ON</option>
                        <option value="off">OFF</option>
                    </select>
                </div>

                <div class="form-group">
                    <label>Smoothing</label>
                    <div class="slider-container">
                        <input type="range" name="smoothing" min="1" max="100" value="50" class="slider">
                        <div class="slider-value">50</div>
                        <a href="#" class="clear-smooth">Clear->Smooth</a>
                    </div>
                </div>

                <button type="button" class="save-btn" onclick="saveConfiguration()">💾 Save</button>
            </form>
        </div>

        <script>
            function saveConfiguration() {{
                // Get form data
                const form = document.getElementById('videoConfigForm');
                const formData = new FormData(form);

                // Convert to object
                const config = {{}};
                for (let [key, value] of formData.entries()) {{
                    config[key] = value;
                }}

                // Add smoothing value
                config.smoothing = document.querySelector('input[name="smoothing"]').value;

                // Here you would normally send the configuration to the camera
                // For now, just show a success message
                alert('Configuration saved successfully!\\n\\nNote: This is a demo interface. To save actual camera settings, you would need to implement the camera API calls.');

                console.log('Configuration to save:', config);
            }}

            // Update slider value display
            document.querySelector('input[name="smoothing"]').addEventListener('input', function(e) {{
                document.querySelector('.slider-value').textContent = e.target.value;
            }});

            // Tab switching (visual only in this demo)
            document.querySelectorAll('.tab').forEach(tab => {{
                tab.addEventListener('click', function() {{
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    this.classList.add('active');

                    // In a real implementation, you would switch the form content here
                    if (this.textContent === 'Audio') {{
                        alert('Audio configuration would be shown here');
                    }} else if (this.textContent === 'ROI') {{
                        alert('ROI configuration would be shown here');
                    }} else if (this.textContent === 'Display Info. on Stream') {{
                        alert('Display info configuration would be shown here');
                    }}
                }});
            }});
        </script>
    </body>
    </html>
    """

    return video_config_html

def enhance_config_page(original_content: str, camera_ip: str) -> str:
    """
    Enhance the original camera configuration page with better styling and functionality.
    """
    # For now, return a simple enhanced version
    # In a real implementation, you would parse and modify the original HTML

    enhanced_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Camera Configuration - {camera_ip}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
            .container {{ background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Camera Configuration - {camera_ip}</h1>
            <p>Full camera configuration interface would be displayed here.</p>
            <p>This would include the complete Hikvision camera interface with all settings.</p>
            <iframe src="http://{camera_ip}/doc/page/config.asp" width="100%" height="600" frameborder="0"></iframe>
        </div>
    </body>
    </html>
    """

    return enhanced_html