from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import logging
import json
import uuid
import os
import socket
from typing import Dict, List

from services.webrtc_stream import RTSPVideoStreamTrack, get_webrtc_stream, create_webrtc_stream

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/webrtc", tags=["webrtc"])

# Store active peer connections
peer_connections: Dict[str, RTCPeerConnection] = {}

# Get local IP address for ICE configuration
def get_local_ip():
    try:
        # Create a socket to determine the outgoing IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google's DNS server
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.warning(f"Could not determine local IP: {e}")
        return None

# Configure ICE servers and options
def get_rtc_configuration():
    # Get host override from environment or use detected local IP
    host_override = os.environ.get("ICE_HOST_OVERRIDE", get_local_ip())
    
    # Set the ICE_HOST_OVERRIDE environment variable if we have a valid IP
    if host_override:
        logger.info(f"Using ICE host override: {host_override}")
        os.environ["ICE_HOST_OVERRIDE"] = host_override
    
    # Configure multiple STUN servers for better NAT traversal
    ice_servers = [
        # Public STUN servers with TCP support
        {"urls": ["stun:stun.l.google.com:19302"]},
        {"urls": ["stun:stun1.l.google.com:19302"]},
        {"urls": ["stun:stun2.l.google.com:19302"]},
        
        # Add TURN server if available (uncomment and fill in your TURN server details)
        # {
        #     "urls": ["turn:your-turn-server.com:3478"],
        #     "username": "username",
        #     "credential": "password",
        #     "credentialType": "password"
        # }
    ]
    
    # If we have a local IP, add it as a STUN server for local network access
    if host_override and not any(ip in host_override for ip in ['127.0.0.1', 'localhost']):
        ice_servers.append({"urls": [f"stun:{host_override}:3478"]})
    
    # Create RTC configuration with ICE servers
    config = RTCConfiguration(iceServers=ice_servers)
    
    # Set ICE transport policy
    config.iceTransportPolicy = 'all'  # Try all available candidates
    
    # Enable other WebRTC features
    config.bundlePolicy = 'max-bundle'
    config.rtcpMuxPolicy = 'require'
    
    return config

@router.post("/offer")
async def handle_offer(request: Request):
    """
    Handle WebRTC offer from client
    """
    try:
        body = await request.json()
        offer = RTCSessionDescription(sdp=body["sdp"], type=body["type"])

        # Get RTSP URL from request if provided
        rtsp_url = body.get("rtspUrl")

        # Create a new RTCPeerConnection with our configuration
        pc = RTCPeerConnection(configuration=get_rtc_configuration())
        pc_id = str(uuid.uuid4())
        peer_connections[pc_id] = pc

        video = None
        # If RTSP URL is provided, create a video track
        if rtsp_url:
            logger.info(f"Creating video track for RTSP URL: {rtsp_url}")
            video = RTSPVideoStreamTrack(rtsp_url)
            pc.addTrack(video)

        # Add cleanup callback
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state changed to: {pc.connectionState}")
            if pc.connectionState in ["failed", "closed"]:
                logger.info(f"Cleaning up peer connection {pc_id}")
                if video:
                    try:
                        video.stop()
                        logger.info(f"Stopped video track for peer connection {pc_id}")
                    except Exception as e:
                        logger.error(f"Error stopping video track: {e}")
                try:
                    await pc.close()
                    logger.info(f"Closed peer connection {pc_id}")
                except Exception as e:
                    logger.error(f"Error closing peer connection: {e}")
                if pc_id in peer_connections:
                    del peer_connections[pc_id]

        # Log ICE connection state changes
        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logger.info(f"ICE connection state changed to: {pc.iceConnectionState}")
            if pc.iceConnectionState == "completed":
                logger.info("ICE completed")

        # Set remote description
        await pc.setRemoteDescription(offer)

        # Create answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return JSONResponse({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
    except Exception as e:
        logger.error(f"Error handling offer: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/direct-offer")
async def handle_direct_offer(request: Request):
    """
    Handle WebRTC offer from client with direct RTSP URL
    """
    try:
        body = await request.json()
        offer = RTCSessionDescription(sdp=body["sdp"], type=body["type"])
        rtsp_url = body["rtspUrl"]

        if not rtsp_url:
            return JSONResponse({"error": "RTSP URL is required"}, status_code=400)

        logger.info(f"Received direct offer for RTSP URL: {rtsp_url}")

        # Create a new RTCPeerConnection with our configuration
        pc = RTCPeerConnection(configuration=get_rtc_configuration())
        pc_id = str(uuid.uuid4())
        peer_connections[pc_id] = pc

        # Create a video track from the RTSP URL
        logger.info(f"Creating video track for RTSP URL: {rtsp_url}")
        video = RTSPVideoStreamTrack(rtsp_url)
        pc.addTrack(video)

        # Add cleanup callback
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state changed to: {pc.connectionState}")
            if pc.connectionState in ["failed", "closed"]:
                logger.info(f"Cleaning up peer connection {pc_id}")
                try:
                    video.stop()
                    logger.info(f"Stopped video track for peer connection {pc_id}")
                except Exception as e:
                    logger.error(f"Error stopping video track: {e}")
                try:
                    await pc.close()
                    logger.info(f"Closed peer connection {pc_id}")
                except Exception as e:
                    logger.error(f"Error closing peer connection: {e}")
                if pc_id in peer_connections:
                    del peer_connections[pc_id]

        # Log ICE connection state changes
        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logger.info(f"ICE connection state changed to: {pc.iceConnectionState}")
            if pc.iceConnectionState == "completed":
                logger.info("ICE completed")

        # Set remote description
        await pc.setRemoteDescription(offer)

        # Create answer
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        logger.info("Created answer, sending back to client")
        return JSONResponse({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
    except Exception as e:
        logger.error(f"Error handling direct offer: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)
