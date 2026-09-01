import asyncio
import fractions
import json
import logging
import os
import re
import subprocess
import time
import urllib.parse
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from aiortc import MediaStreamTrack, RTCPeerConnection
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants for RTSP connection - Improved for better stability
DEFAULT_RTSP_TRANSPORT = os.environ.get("RTSP_TRANSPORT", "tcp")  # Use TCP by default for more reliability
DEFAULT_RTSP_TIMEOUT = int(os.environ.get("RTSP_TIMEOUT", "90"))  # Increased from 30 to 90 seconds
RTSP_RECONNECT_DELAY = 2  # Initial delay for reconnection attempts in seconds
MAX_RECONNECT_ATTEMPTS = 10  # Increased from 5 to 10 attempts
MAX_QUEUE_SIZE = 50  # Increased from 30 to 50 frames for better buffering
FRAME_TIMEOUT = 15.0  # Increased from 5.0 to 15.0 seconds
CONNECTION_HEALTH_CHECK_INTERVAL = 60  # Check connection health every 60 seconds
KEEPALIVE_INTERVAL = 30  # Send keepalive every 30 seconds

# Dictionary to store active WebRTC streams
webrtc_streams = {}

class RTSPVideoStreamTrack(MediaStreamTrack):
    """
    A video stream track that reads from an RTSP stream.
    """
    kind = "video"

    def __init__(self, rtsp_url):
        super().__init__()
        self.rtsp_url = rtsp_url
        self._task = None
        self._queue = asyncio.Queue(maxsize=MAX_QUEUE_SIZE)
        self._timestamp = 0
        self._start_time = time.time()
        self._frame_time = 1 / 24  # Default to 24 FPS
        self._last_frame_time = 0
        self._frame_count = 0
        self._error_count = 0
        self._reconnect_attempts = 0
        self._cap = None
        self._running = True
        self._start()

    def _start(self):
        """Start capturing from the RTSP stream"""
        self._task = asyncio.ensure_future(self._run_capture())

    def _prepare_rtsp_url(self, url):
        """Prepare the RTSP URL with proper transport parameters and authentication."""
        if not url:
            return url

        # If URL already has transport parameter, don't modify it
        if "rtsp_transport=" in url:
            return url

        # Handle URLs with special characters in passwords
        url = self._fix_url_encoding(url)

        # Parse the URL
        parsed = urllib.parse.urlparse(url)

        # If it's not an RTSP URL or it's a test URL (port 0), return as is
        if parsed.scheme != "rtsp" or parsed.port == 0:
            return url

        # Add transport parameter
        transport = DEFAULT_RTSP_TRANSPORT

        # Rebuild the URL with proper parameters
        query = f"rtsp_transport={transport}"
        if parsed.query:
            query = f"{parsed.query}&{query}"

        # Reconstruct the URL with the new query
        return urllib.parse.urlunparse(parsed._replace(query=query))

    def _fix_url_encoding(self, url):
        """Fix URL encoding for passwords with special characters."""
        if not url or "://" not in url:
            return url

        try:
            # Parse the URL first to handle any existing encoding
            parsed = urllib.parse.urlparse(url)
            if not parsed.username or not parsed.password:
                return url

            # Re-encode the password to ensure special characters are properly handled
            # Keep @ safe because OpenCV/FFmpeg cannot parse percent-encoded RTSP URLs
            encoded_password = urllib.parse.quote(urllib.parse.unquote(parsed.password), safe="$-_.+!*'(),")

            # Reconstruct the URL with properly encoded password
            netloc = f"{parsed.username}:{encoded_password}@{parsed.hostname}"
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"

            # Rebuild the URL preserving all components
            fixed_url = urllib.parse.urlunparse((
                parsed.scheme,
                netloc,
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            return fixed_url

        except Exception as e:
            logger.warning(f"Error fixing URL encoding: {e}, using original URL")

        return url

    def _mask_credentials(self, url):
        """Mask credentials in URL for logging purposes."""
        if not url:
            return url

        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.username and parsed.password:
                # Replace password with asterisks
                masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
                if parsed.port:
                    masked_netloc += f":{parsed.port}"
                return urllib.parse.urlunparse(parsed._replace(netloc=masked_netloc))
        except Exception:
            pass
        return url

    def _validate_rtsp_url(self, url):
        """Validate RTSP URL format and check for common issues."""
        if not url:
            return False, "Empty URL"

        try:
            # First try to fix URL encoding issues
            fixed_url = self._fix_url_encoding(url)
            parsed = urllib.parse.urlparse(fixed_url)

            # Check scheme
            if parsed.scheme != "rtsp":
                return False, f"Invalid scheme '{parsed.scheme}', expected 'rtsp'"

            # Check hostname
            if not parsed.hostname:
                return False, "Missing hostname"

            # Check port
            if parsed.port and (parsed.port < 1 or parsed.port > 65535):
                return False, f"Invalid port {parsed.port}"

            return True, "Valid URL"

        except Exception as e:
            return False, f"URL parsing error: {str(e)}"

    async def _connect_rtsp(self, rtsp_url, use_tcp=True):
        """Establish RTSP connection with the given URL and transport protocol."""
        # Prepare the URL with transport protocol
        if use_tcp:
            rtsp_url = self._prepare_rtsp_url(rtsp_url)
        else:
            # Force UDP transport
            if "rtsp_transport=tcp" in rtsp_url:
                rtsp_url = rtsp_url.replace("rtsp_transport=tcp", "rtsp_transport=udp")
            elif "?" in rtsp_url:
                rtsp_url = f"{rtsp_url}&rtsp_transport=udp"
            else:
                rtsp_url = f"{rtsp_url}?rtsp_transport=udp"

        # Log connection attempt (mask credentials for security)
        masked_url = self._mask_credentials(rtsp_url)
        logger.info(f"Connecting to RTSP stream: {masked_url}")

        # Set OpenCV parameters for better RTSP handling
        cap = cv2.VideoCapture(rtsp_url)

        # Configure capture parameters for better performance and reliability
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # Increased buffer for stability
        cap.set(cv2.CAP_PROP_FPS, 24)  # Set to 24 FPS for display

        # Set timeouts (in milliseconds) - Using improved timeout values
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, DEFAULT_RTSP_TIMEOUT * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, DEFAULT_RTSP_TIMEOUT * 1000)

        # Additional stability settings
        try:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('H', '2', '6', '4'))
        except:
            pass  # Ignore if not supported

        # Try to open the stream
        if not cap.isOpened():
            logger.warning(f"Failed to open RTSP stream with {'TCP' if use_tcp else 'UDP'}")
            return None

        # Get stream information
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        logger.info(f"Stream opened successfully: {width}x{height} @ {fps}fps")

        return cap

    async def _run_capture(self):
        """Main capture loop for the RTSP stream."""
        # Validate URL before attempting connection
        is_valid, validation_msg = self._validate_rtsp_url(self.rtsp_url)
        if not is_valid:
            logger.error(f"Invalid RTSP URL: {validation_msg}")
            logger.error(f"URL: {self._mask_credentials(self.rtsp_url)}")
            self._running = False
            return

        rtsp_url = self.rtsp_url
        cap = None

        try:
            while self._running and self._reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                try:
                    # Try to connect with TCP first (more reliable)
                    cap = await self._connect_rtsp(rtsp_url, use_tcp=True)

                    # If TCP fails, try UDP
                    if not cap and DEFAULT_RTSP_TRANSPORT == "tcp":
                        logger.warning("TCP connection failed, trying UDP...")
                        cap = await self._connect_rtsp(rtsp_url, use_tcp=False)

                    if not cap:
                        raise RuntimeError(f"Failed to connect to RTSP stream: {rtsp_url}")

                    # Connection successful, reset reconnection attempts
                    self._reconnect_attempts = 0
                    self._cap = cap

                    # Get the actual frame rate from the camera if available
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    if fps > 0:
                        self._frame_time = 1 / fps
                        logger.info(f"Camera reports {fps:.2f} FPS, frame time: {self._frame_time:.3f}s")
                    else:
                        logger.warning(f"Could not determine camera FPS, using default of {1/self._frame_time:.1f} FPS")

                    # Main frame capture loop
                    await self._capture_frames(cap)

                except Exception as e:
                    error_msg = str(e)

                    # Check for specific authentication errors
                    if "401 Unauthorized" in error_msg:
                        logger.error(f"RTSP authentication failed: Invalid credentials for {self._mask_credentials(rtsp_url)}")
                        logger.error("Please check the username and password in the camera configuration")
                    elif "403 Forbidden" in error_msg:
                        logger.error(f"RTSP access forbidden: User may not have sufficient permissions for {self._mask_credentials(rtsp_url)}")
                    elif "404 Not Found" in error_msg:
                        logger.error(f"RTSP stream not found: Check the camera IP and stream path for {self._mask_credentials(rtsp_url)}")
                    elif "Connection refused" in error_msg:
                        logger.error(f"RTSP connection refused: Camera may be offline or port blocked for {self._mask_credentials(rtsp_url)}")
                    elif "timeout" in error_msg.lower():
                        logger.error(f"RTSP connection timeout: Camera may be unreachable for {self._mask_credentials(rtsp_url)}")
                    else:
                        logger.error(f"RTSP stream error: {error_msg}")

                    self._error_count += 1
                    self._reconnect_attempts += 1

                    # Clean up the capture object
                    if cap:
                        try:
                            cap.release()
                        except:
                            pass
                        cap = None

                    # For authentication errors, don't retry as credentials won't change
                    if "401 Unauthorized" in error_msg or "403 Forbidden" in error_msg:
                        logger.error("Authentication error detected - stopping reconnection attempts")
                        break

                    if self._running and self._reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                        # Exponential backoff for reconnection
                        delay = min(RTSP_RECONNECT_DELAY * (2 ** (self._reconnect_attempts - 1)), 30)
                        logger.warning(f"Reconnecting attempt {self._reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS} in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Max reconnection attempts ({MAX_RECONNECT_ATTEMPTS}) reached")
                        break
        finally:
            logger.info("Cleaning up RTSP capture resources in _run_capture finally block")
            if cap:
                try:
                    cap.release()
                    logger.info("Successfully released RTSP VideoCapture in finally block")
                except Exception as release_error:
                    logger.error(f"Error releasing RTSP VideoCapture: {release_error}")
            self._cap = None

    async def _capture_frames(self, cap):
        """Capture frames from an open capture device."""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while self._running:
            try:
                # Read a frame with timeout
                def _grab_and_retrieve():
                    if not cap.grab():
                        return False, None
                    return cap.retrieve()

                read_success, frame = await asyncio.get_event_loop().run_in_executor(
                    None,
                    _grab_and_retrieve
                )

                if not read_success or frame is None:
                    consecutive_errors += 1
                    logger.warning(f"Failed to read frame (attempt {consecutive_errors}/{max_consecutive_errors})")

                    if consecutive_errors >= max_consecutive_errors:
                        raise RuntimeError("Too many consecutive frame read errors")

                    await asyncio.sleep(0.1)
                    continue

                # Reset error counter on successful frame read
                consecutive_errors = 0

                # Update frame statistics
                now = time.time()
                if self._last_frame_time > 0:
                    frame_interval = now - self._last_frame_time
                    if self._frame_count % 100 == 0:  # Log every 100 frames
                        logger.debug(f"Frame interval: {frame_interval*1000:.1f}ms ({1/max(0.001, frame_interval):.1f} FPS)")

                self._last_frame_time = now
                self._frame_count += 1

                # Convert to RGB for WebRTC
                try:
                    # Resize frame if too large to improve performance
                    height, width = frame.shape[:2]
                    max_dimension = 1280  # Maximum dimension for performance

                    if width > max_dimension or height > max_dimension:
                        # Calculate new dimensions maintaining aspect ratio
                        if width > height:
                            new_width = max_dimension
                            new_height = int(height * (max_dimension / width))
                        else:
                            new_height = max_dimension
                            new_width = int(width * (max_dimension / height))

                        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

                    # Convert to RGB
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                except Exception as e:
                    logger.error(f"Error converting frame: {str(e)}")
                    continue

                # Put frame in queue (non-blocking)
                try:
                    self._queue.put_nowait(frame)
                except asyncio.QueueFull:
                    # If queue is full, discard the oldest frame and add the new one
                    try:
                        self._queue.get_nowait()
                        self._queue.put_nowait(frame)
                    except:
                        pass

                # Small sleep to prevent CPU overload
                await asyncio.sleep(0.001)

            except Exception as e:
                logger.error(f"Error in frame capture loop: {str(e)}")
                self._error_count += 1
                break  # Exit the capture loop to trigger reconnection

    async def next_timestamp(self):
        """
        Calculate the next timestamp for the video frame.
        Returns pts (presentation timestamp) and time_base.
        """
        # Calculate pts based on elapsed time since start
        self._timestamp += 1
        pts = int(self._timestamp * 90000 * self._frame_time)  # 90000 Hz is common for video
        time_base = fractions.Fraction(1, 90000)  # Standard time base for video
        return pts, time_base

    async def recv(self):
        """Get the next frame from the queue"""
        from aiortc.mediastreams import MediaStreamError

        if self.readyState != "live":
            raise MediaStreamError

        # Check if we have a valid capture device
        if not hasattr(self, '_cap') or not self._cap or not self._cap.isOpened():
            logger.warning("Capture device not available, waiting for reconnection...")
            await asyncio.sleep(1)
            raise MediaStreamError("Capture device not available")

        # Get the next frame from the queue with timeout
        try:
            frame = await asyncio.wait_for(self._queue.get(), timeout=FRAME_TIMEOUT)

            # Get timestamp for this frame
            pts, time_base = await self.next_timestamp()

            # Create a video frame from the numpy array
            try:
                from av import VideoFrame
                video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
                video_frame.pts = pts
                video_frame.time_base = time_base
                return video_frame
            except Exception as frame_error:
                logger.error(f"Error creating video frame: {str(frame_error)}")
                # If we can't create a frame from the numpy array, create a black frame
                black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                video_frame = VideoFrame.from_ndarray(black_frame, format="rgb24")
                video_frame.pts = pts
                video_frame.time_base = time_base
                return video_frame

        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for frame, generating black frame")
            # Create a black frame as fallback
            from av import VideoFrame
            black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            video_frame = VideoFrame.from_ndarray(black_frame, format="rgb24")
            pts, time_base = await self.next_timestamp()
            video_frame.pts = pts
            video_frame.time_base = time_base
            return video_frame

        except Exception as e:
            logger.error(f"Error in recv: {str(e)}")
            # Create a black frame as fallback
            from av import VideoFrame
            black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            video_frame = VideoFrame.from_ndarray(black_frame, format="rgb24")
            pts, time_base = await self.next_timestamp()
            video_frame.pts = pts
            video_frame.time_base = time_base
            return video_frame

    def stop(self):
        """Stop the stream track"""
        if self._task is not None:
            self._task.cancel()
            self._task = None
        super().stop()

def create_webrtc_stream(rtsp_url, stream_name):
    """
    Create a WebRTC stream from an RTSP URL.

    Args:
        rtsp_url: The RTSP URL to stream from
        stream_name: A unique name for this stream

    Returns:
        The stream ID that can be used to access this stream
    """
    # Mask credentials for logging
    def mask_credentials(url):
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.username and parsed.password:
                masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
                if parsed.port:
                    masked_netloc += f":{parsed.port}"
                return urllib.parse.urlunparse(parsed._replace(netloc=masked_netloc))
        except Exception:
            pass
        return url

    logger.info(f"Creating WebRTC stream for {mask_credentials(rtsp_url)} with name {stream_name}")

    # Create a unique stream ID
    stream_id = f"webrtc_{stream_name}"

    # Create a video track from the RTSP stream
    video_track = RTSPVideoStreamTrack(rtsp_url)

    # Store the stream
    webrtc_streams[stream_id] = {
        'track': video_track,
        'rtsp_url': rtsp_url,
        'name': stream_name,
        'created_at': time.time()
    }

    return stream_id

def get_webrtc_stream(stream_id):
    """
    Get a WebRTC stream by ID.

    Args:
        stream_id: The ID of the stream to get

    Returns:
        The stream if it exists, None otherwise
    """
    return webrtc_streams.get(stream_id)

def stop_webrtc_stream(stream_id):
    """
    Stop a WebRTC stream.

    Args:
        stream_id: The ID of the stream to stop
    """
    if stream_id in webrtc_streams:
        logger.info(f"Stopping WebRTC stream {stream_id}")
        stream = webrtc_streams[stream_id]
        stream['track'].stop()
        del webrtc_streams[stream_id]

def cleanup_webrtc_streams():
    """Clean up all WebRTC streams"""
    for stream_id in list(webrtc_streams.keys()):
        stop_webrtc_stream(stream_id)
