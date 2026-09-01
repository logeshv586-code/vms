import asyncio
import json
import logging
import os
import uuid
from typing import Dict, List, Optional, Set

import socketio
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRelay

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create a Socket.IO server with improved CORS settings
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=logger,
    engineio_logger=True,  # Enable Engine.IO logging for better debugging
    ping_timeout=20,       # Increase ping timeout for better reliability
    ping_interval=25,      # Increase ping interval for better reliability
    max_http_buffer_size=1e8  # Increase buffer size for larger messages
)
# Create ASGI app with explicit path
socket_app = socketio.ASGIApp(sio, socketio_path='socket.io')

# Store active peer connections
peer_connections: Dict[str, RTCPeerConnection] = {}
# Store active rooms (camera streams)
rooms: Dict[str, Set[str]] = {}
# Media relay for sharing a single stream with multiple peers
relay = MediaRelay()

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    try:
        client_address = environ.get('REMOTE_ADDR', 'unknown')
        http_user_agent = environ.get('HTTP_USER_AGENT', 'unknown')

        logger.info(f"Client connected: {sid} from {client_address}")
        logger.debug(f"User agent: {http_user_agent}")

        # Log headers for debugging
        headers = {k: v for k, v in environ.items() if k.startswith('HTTP_')}
        logger.debug(f"Connection headers: {headers}")

        # Send success message to client
        await sio.emit('connection_success', {
            'message': 'Connected to signaling server',
            'sid': sid
        }, to=sid)
    except Exception as e:
        logger.error(f"Error in connect handler: {str(e)}")
        # Still try to send a success message
        await sio.emit('connection_success', {'message': 'Connected with warnings'}, to=sid)

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")

    # Clean up any peer connections for this client
    if sid in peer_connections:
        pc = peer_connections[sid]
        for sender in pc.getSenders():
            if sender.track:
                try:
                    sender.track.stop()
                    logger.info(f"Stopped track for client {sid}")
                except Exception as e:
                    logger.error(f"Error stopping track: {e}")
        try:
            await pc.close()
            logger.info(f"Closed peer connection for client {sid}")
        except Exception as e:
            logger.error(f"Error closing peer connection: {e}")
        del peer_connections[sid]

    # Remove client from any rooms and clean up rooms/peer connections if empty
    rooms_to_delete = []
    for room_id, clients in list(rooms.items()):
        if sid in clients:
            clients.remove(sid)
            # If room is empty, clean it up
            if not clients:
                rooms_to_delete.append(room_id)

    for room_id in rooms_to_delete:
        logger.info(f"Room {room_id} is empty after disconnect, cleaning up WebRTC resources")
        rooms.pop(room_id, None)
        if room_id in peer_connections:
            pc = peer_connections[room_id]
            for sender in pc.getSenders():
                if sender.track:
                    try:
                        sender.track.stop()
                        logger.info(f"Stopped track for room {room_id}")
                    except Exception as e:
                        logger.error(f"Error stopping track: {e}")
            try:
                await pc.close()
                logger.info(f"Closed peer connection for room {room_id}")
            except Exception as e:
                logger.error(f"Error closing peer connection: {e}")
            del peer_connections[room_id]

@sio.event
async def join_room(sid, data):
    """Handle client joining a camera stream room with WebRTC offer"""
    try:
        room_id = data.get('room')
        rtsp_url = data.get('rtspUrl')
        sdp_offer = data.get('sdp')
        
        if not room_id or not rtsp_url or not sdp_offer:
            await sio.emit('error', {'message': 'Room ID, RTSP URL, and SDP are required'}, to=sid)
            return

        logger.info(f"Client {sid} joining room {room_id} for RTSP: {rtsp_url}")

        # Create room if it doesn't exist
        if room_id not in rooms:
            rooms[room_id] = set()
            
            # Create a new peer connection for this room
            pc = RTCPeerConnection()
            peer_connections[room_id] = pc
            
            # Add video track from RTSP stream
            from .webrtc_stream import RTSPVideoStreamTrack
            video_track = RTSPVideoStreamTrack(rtsp_url)
            pc.addTrack(video_track)
            
            # Set up ICE candidate handling
            @pc.on("ice_candidate")
            async def on_ice_candidate(candidate):
                await sio.emit('ice_candidate', {
                    'candidate': candidate.to_json(),
                    'streamId': room_id
                }, room=room_id)
                
            # Set up connection state change handling
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                logger.info(f"Connection state changed to {pc.connectionState}")
                if pc.connectionState in ["failed", "closed"]:
                    logger.info(f"Cleaning up peer connection for room {room_id}")
                    for sender in pc.getSenders():
                        if sender.track:
                            try:
                                sender.track.stop()
                                logger.info(f"Stopped track in connectionstatechange for room {room_id}")
                            except Exception as e:
                                logger.error(f"Error stopping track: {e}")
                    try:
                        await pc.close()
                    except Exception as e:
                        logger.error(f"Error closing peer connection: {e}")
                    rooms.pop(room_id, None)
                    peer_connections.pop(room_id, None)
        
        # Add client to room
        rooms[room_id].add(sid)
        
        # If this is the first client, create and send answer
        if len(rooms[room_id]) == 1 and room_id in peer_connections:
            pc = peer_connections[room_id]
            await pc.setRemoteDescription(RTCSessionDescription(
                sdp=sdp_offer['sdp'],
                type=sdp_offer['type']
            ))
            
            # Create and send answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            await sio.emit('answer', {
                'sdp': pc.localDescription,
                'streamId': room_id
            }, room=room_id)
        
        # Notify client they've joined the room
        await sio.emit('room_joined', {'room': room_id}, to=sid)
        
    except Exception as e:
        logger.error(f"Error in join_room: {str(e)}")
        await sio.emit('error', {'message': str(e)}, to=sid)

@sio.event
async def leave_room(sid, data):
    """Handle client leaving a camera stream room"""
    room_id = data.get('room')
    if not room_id or room_id not in rooms:
        return

    logger.info(f"Client {sid} leaving room {room_id}")

    # Remove client from room
    if sid in rooms[room_id]:
        rooms[room_id].remove(sid)

    # If room is empty, clean it up
    if not rooms[room_id]:
        logger.info(f"Room {room_id} is empty after client left, cleaning up WebRTC resources")
        rooms.pop(room_id, None)
        if room_id in peer_connections:
            pc = peer_connections[room_id]
            for sender in pc.getSenders():
                if sender.track:
                    try:
                        sender.track.stop()
                        logger.info(f"Stopped track for room {room_id}")
                    except Exception as e:
                        logger.error(f"Error stopping track: {e}")
            try:
                await pc.close()
                logger.info(f"Closed peer connection for room {room_id}")
            except Exception as e:
                logger.error(f"Error closing peer connection: {e}")
            del peer_connections[room_id]

@sio.event
async def offer(sid, data):
    """Handle WebRTC offer from client"""
    room_id = data.get('room')
    sdp = data.get('sdp')

    if not room_id or not sdp:
        await sio.emit('error', {'message': 'Room ID and SDP are required'}, to=sid)
        return

    logger.info(f"Received offer from client {sid} for room {room_id}")

    # Create a new RTCPeerConnection
    pc = RTCPeerConnection()
    peer_connections[sid] = pc

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logger.info(f"Signaling peer connection state for {sid} changed to {pc.connectionState}")
        if pc.connectionState in ["failed", "closed"]:
            # Clean up tracks
            for sender in pc.getSenders():
                if sender.track:
                    try:
                        sender.track.stop()
                        logger.info(f"Stopped track for client {sid}")
                    except Exception as e:
                        logger.error(f"Error stopping track: {e}")
            try:
                await pc.close()
                logger.info(f"Closed peer connection for client {sid}")
            except Exception as e:
                logger.error(f"Error closing peer connection: {e}")
            peer_connections.pop(sid, None)

    # Set the remote description
    await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type='offer'))

    # Create an answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Send the answer back to the client
    await sio.emit('answer', {
        'sdp': pc.localDescription.sdp,
        'room': room_id
    }, to=sid)

@sio.event
async def answer(sid, data):
    """Handle WebRTC answer from client"""
    room_id = data.get('room')
    sdp = data.get('sdp')

    if not room_id or not sdp or sid not in peer_connections:
        return

    logger.info(f"Received answer from client {sid} for room {room_id}")

    # Get the peer connection
    pc = peer_connections[sid]

    # Set the remote description
    await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type='answer'))

@sio.event
async def ice_candidate(sid, data):
    """Handle ICE candidate from client"""
    if sid not in peer_connections:
        return

    candidate = data.get('candidate')
    sdp_mid = data.get('sdpMid')
    sdp_m_line_index = data.get('sdpMLineIndex')

    if not candidate or sdp_mid is None or sdp_m_line_index is None:
        return

    logger.info(f"Received ICE candidate from client {sid}")

    # Get the peer connection
    pc = peer_connections[sid]

    # Add the ICE candidate
    await pc.addIceCandidate({
        'candidate': candidate,
        'sdpMid': sdp_mid,
        'sdpMLineIndex': sdp_m_line_index
    })

# Function to add to a FastAPI app
def setup_socketio(app, path='/ws'):
    """
    Set up Socket.IO with a FastAPI app

    Args:
        app: The FastAPI app to mount Socket.IO on
        path: The path to mount Socket.IO on (default: '/ws')
              This should match the path used in the frontend

    Returns:
        The Socket.IO server instance
    """
    logger.info(f"Setting up Socket.IO server at path: {path}")
    app.mount(path, socket_app)

    # Log setup completion
    logger.info(f"Socket.IO server setup complete at path: {path}")

    return sio
