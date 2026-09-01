from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import json
import os
import io
# Force single-threaded FFmpeg RTSP decoding to eliminate 'Assertion fctx->async_lock failed at libavcodec/pthread_frame.c:178'
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "threads;1|rtsp_transport;tcp|probesize;5000000|analyzeduration;5000000|max_delay;500000"
os.environ["OPENCV_FFMPEG_THREADS"] = "1"

import atexit
import shutil
import logging
import time
import cv2
cv2.setNumThreads(1)
try:
    cv2.ocl.setUseOpenCL(False)
except Exception:
    pass

import threading
import asyncio
import signal

_FFMPEG_CAPTURE_LOCK = threading.RLock()

from typing import Dict, Optional
from routes import analytics, users, events, camera_rules, camera_zones, collections, webrtc, augment, archive, dashboard_analytics, appearance_search, camera_settings
# New detection analytics routes
try:
    from routes import face_analytics, gesture_analytics
    _FACE_GESTURE_ROUTES = True
except Exception as _fgr_err:
    _FACE_GESTURE_ROUTES = False
    logger_msg = f"Face/Gesture routes not loaded: {_fgr_err}"
from services.archive_manager import ArchiveRecordingManager
from fastapi import status
import uvicorn
from services import webrtc_signaling
from services.yolo26_engine import yolo26_engine
from services.pattern_engine import pattern_engine
from services.gemma_engine import gemma_engine
from services.cascaded_ai_service import cascaded_ai_service

# ── Rule Constants ───────────────────────────────────────────────────────────
RULE_FACE_CAPTURE = 6
RULE_FACE_RECOGNITION = 7
RULE_GESTURE_DETECTION = 8

# ── Sub-detection singletons (face capture, face recognition, sign language) ─
# Wrapped in try/except so a missing optional dependency doesn't break startup.
try:
    from detections.face_capture import FaceCaptureDetector
    _face_capture_detector = FaceCaptureDetector({
        "gallery_dir": "face_db/captures",
        "min_face_size": 80,
        "blur_threshold": 80.0,
        "capture_every_n_frames": 5,
        "save_faces": True,
        "use_haar_fallback": True,
    })
    _face_capture_detector.is_enabled = True
except Exception as _fc_err:
    _face_capture_detector = None
    print(f"[WARN] FaceCaptureDetector not loaded: {_fc_err}")

try:
    from detections.face_recognition import FaceRecognitionDetector
    _face_recognition_detector = FaceRecognitionDetector({
        "encodings_db_path": "face_db/encodings.json",
        "recognition_tolerance": 0.5,
        "detection_model": "hog",
        "max_faces": 10,
        "auto_register": True,
        "alert_on_watchlist": True,
    })
    _face_recognition_detector.is_enabled = True
except Exception as _fr_err:
    _face_recognition_detector = None
    print(f"[WARN] FaceRecognitionDetector not loaded: {_fr_err}")

try:
    from detections.sign_language import SignLanguageDetector
    _sign_language_detector = SignLanguageDetector({
        "min_detection_confidence": 0.7,
        "min_tracking_confidence": 0.5,
        "max_num_hands": 2,
        "sos_wave_threshold": 3,
        "enable_db_logging": True,
        "alert_categories": ["help", "threat"],
    })
    _sign_language_detector.is_enabled = True
except Exception as _sl_err:
    _sign_language_detector = None
    print(f"[WARN] SignLanguageDetector not loaded: {_sl_err}")

# Set up logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure backend/logs directory exists for security audit logging
os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)

# Import stream configuration
try:
    from config.stream_config import stream_config
    logger_config_msg = "Using custom stream configuration"
except ImportError:
    # Fallback configuration if config file is not available
    class FallbackConfig:
        RTSP_OPEN_TIMEOUT = 45
        RTSP_READ_TIMEOUT = 90
        MAX_RECONNECT_ATTEMPTS = 10
        MAX_FRAME_RETRIES = 5
        FRAME_TIMEOUT_THRESHOLD = 60
        BUFFER_SIZE_STABLE = 3
        TARGET_FPS_STABLE = 25
        HEALTH_CHECK_INTERVAL = 30
        CONNECTION_TEST_FRAMES = 5
        MIN_SUCCESSFUL_TEST_FRAMES = 3
        TIMEOUT_ERROR_DELAY = 15
        GENERAL_ERROR_DELAY = 30
        CRITICAL_ERROR_DELAY = 300

        CONNECTION_METHODS = [
            {'name': 'TCP', 'url_suffix': '?tcp', 'timeout_open_ms': 45000, 'timeout_read_ms': 90000, 'buffer_size': 3},
            {'name': 'Original', 'url_suffix': '', 'timeout_open_ms': 35000, 'timeout_read_ms': 75000, 'buffer_size': 2},
            {'name': 'TCP Max', 'url_suffix': '', 'timeout_open_ms': 45000, 'timeout_read_ms': 90000, 'buffer_size': 4},
            {'name': 'UDP', 'url_suffix': '?udp', 'timeout_open_ms': 25000, 'timeout_read_ms': 60000, 'buffer_size': 2}
        ]

    stream_config = FallbackConfig()
    logger_config_msg = "Using fallback stream configuration"

# Import stream monitoring
try:
    from services.stream_monitor import stream_monitor, get_stream_diagnostics
    monitor_available = True
except ImportError:
    monitor_available = False
    logger.warning("Stream monitoring not available")

logger.info(logger_config_msg)

class RTSPStream:
    """Thread-safe RTSP stream handler for MJPEG streaming"""

    def __init__(self, rtsp_url: str, stream_id: str = None):
        self.rtsp_url = rtsp_url
        self.stream_id = stream_id or f"stream_{int(time.time())}"
        self.cap = None
        self.is_running = False
        self.lock = threading.Lock()
        self.last_frame = None
        self.thread = None

        # Detection state
        self.detection_enabled = False
        self.last_annotated_frame = None
        self.last_detections = {"detections": [], "counts": {}}
        self.last_events = []
        self.last_reasoning_time = 0
        self.ai_thread = None
        self.frame_ready_event = threading.Event()
        
        # JPEG Cache (Zero-computation streaming)
        self.last_jpeg_raw = None
        self.last_jpeg_annotated = None
        
        # Register with monitor if available
        if monitor_available:
            stream_monitor.register_stream(self.stream_id, rtsp_url)

    def start(self):
        """Start the RTSP stream capture in a separate thread"""
        with self.lock:
            if self.is_running:
                return

            self.is_running = True
            
            # 1. Start Capture Thread
            self.thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            
            # 2. Start AI Processing Thread
            self.ai_thread = threading.Thread(target=self._ai_processing_loop, daemon=True)
            self.ai_thread.start()
            
            logger.info(f"Started RTSP stream and AI pipeline for {self.rtsp_url}")

    def stop(self):
        """Stop the RTSP stream capture gracefully"""
        with self.lock:
            if not self.is_running:
                return
            self.is_running = False
            
        # Wait for threads to exit
        for t in [self.thread, self.ai_thread]:
            if t and t.is_alive():
                try:
                    t.join(timeout=1.0)
                except Exception as e:
                    logger.error(f"Error joining stream thread: {e}")

        with self.lock:
            if self.cap:
                try:
                    with _FFMPEG_CAPTURE_LOCK:
                        self.cap.release()
                except Exception as e:
                    logger.error(f"Error releasing RTSP capture: {e}")
                self.cap = None
            logger.info(f"Stopped RTSP stream for {self.rtsp_url}")


    def _capture_frames(self):
        """Continuously capture frames from RTSP stream with improved stability"""
        retry_count = 0
        max_retries = 15  # High tolerance for transient H.264 decode errors
        reconnect_attempts = 0
        max_reconnect_attempts = 10
        last_successful_frame_time = time.time()
        connection_health_check_interval = 30
        last_health_check = time.time()

        while self.is_running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    logger.info(f"Connecting to RTSP stream: {self.rtsp_url}")

                    # Exponential backoff for reconnection attempts
                    if reconnect_attempts > 0:
                        backoff_delay = min(2 ** reconnect_attempts, 60)  # Max 60 seconds
                        logger.info(f"Waiting {backoff_delay} seconds before reconnection attempt {reconnect_attempts + 1}")
                        time.sleep(backoff_delay)

                    # Try different connection methods with improved timeout settings
                    connection_methods = [
                        # Method 1: TCP transport with extended timeouts and deep probe
                        {
                            'url': f"{self.rtsp_url}?tcp",
                            'timeout_open': 60000, 
                            'timeout_read': 120000,
                            'buffer_size': 10, # Increased buffer for stability on high-bitrate cameras
                            'name': 'TCP with deep-probe'
                        },
                        # Method 2: UDP fallback for situations where TCP handshake is failing
                        {
                            'url': f"{self.rtsp_url}?udp",
                            'timeout_open': 35000, 
                            'timeout_read': 90000,
                            'buffer_size': 5,
                            'name': 'UDP fallback'
                        }
                    ]

                    connection_successful = False
                    for i, method in enumerate(connection_methods):
                        try:
                            method_name = method.get('name', f"Method {i+1}")
                            logger.info(f"Trying {method_name}: {method['url']} (open: {method['timeout_open']/1000}s, read: {method['timeout_read']/1000}s)")

                            # Create VideoCapture with timeout and global thread lock
                            with _FFMPEG_CAPTURE_LOCK:
                                self.cap = cv2.VideoCapture(method['url'])

                            # Set timeouts and buffer settings with error handling
                            try:
                                self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, method['timeout_open'])
                                self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, method['timeout_read'])
                                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, method.get('buffer_size', 5)) # Use optimal buffer size for stability

                                # Additional stability settings
                                self.cap.set(cv2.CAP_PROP_FPS, 25)  # Set to 25 FPS for stability

                                # Try to set codec preferences if available
                                try:
                                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('H', '2', '6', '4'))
                                except:
                                    pass  # Ignore if not supported

                                # Set additional properties for better stability
                                try:
                                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                                except:
                                    pass  # Ignore if not supported

                            except Exception as prop_error:
                                logger.warning(f"Failed to set some capture properties: {prop_error}")
                                # Continue anyway as basic capture might still work

                            # Test if connection works with multiple frame reads
                            if self.cap.isOpened():
                                # Try to read multiple frames to ensure stable connection
                                test_frames_count = 0
                                for _ in range(5):  # Test with 5 frames
                                    try:
                                        test_ret, test_frame = self.cap.read()
                                    except Exception:
                                        test_ret, test_frame = False, None
                                    if test_ret and test_frame is not None:
                                        test_frames_count += 1
                                        with self.lock:
                                            self.last_frame = test_frame
                                    time.sleep(0.1)  # Small delay between test reads

                                if test_frames_count >= 3:  # At least 3 successful frames
                                    logger.info(f"✅ Successfully connected using {method_name}: {method['url']} ({test_frames_count}/5 test frames)")
                                    connection_successful = True
                                    reconnect_attempts = 0  # Reset reconnect counter on success
                                    last_successful_frame_time = time.time()

                                    # Update monitoring
                                    if monitor_available:
                                        stream_monitor.update_connection_attempt(self.stream_id, success=True)
                                    break
                                else:
                                    logger.warning(f"❌ {method_name} unstable: only {test_frames_count}/5 test frames successful")
                                    with _FFMPEG_CAPTURE_LOCK:
                                        self.cap.release()
                                        self.cap = None
                            else:
                                logger.warning(f"❌ {method_name} failed to open stream")
                                with _FFMPEG_CAPTURE_LOCK:
                                    self.cap.release()
                                    self.cap = None

                        except Exception as method_error:
                            error_msg = str(method_error).lower()
                            if 'timeout' in error_msg:
                                logger.warning(f"⏱️ {method_name} timed out: {method_error}")
                            else:
                                logger.warning(f"❌ {method_name} failed: {method_error}")
                            with _FFMPEG_CAPTURE_LOCK:
                                if self.cap:
                                    self.cap.release()
                                    self.cap = None
                            continue


                    if not connection_successful:
                        reconnect_attempts += 1
                        if reconnect_attempts >= max_reconnect_attempts:
                            logger.error(f"Max reconnection attempts ({max_reconnect_attempts}) reached for {self.rtsp_url}")
                            time.sleep(300)  # Wait 5 minutes before trying again
                            reconnect_attempts = 0
                        raise Exception("All connection methods failed")

                # Main frame capture loop
                if not self.is_running:
                    break
                    
                try:
                    ret, frame = self.cap.read()
                except Exception as read_ex:
                    logger.warning(f"Transient decode read exception on {self.rtsp_url}: {read_ex}")
                    ret, frame = False, None

                current_time = time.time()

                if ret and frame is not None:
                    # 1. Update latest raw frame
                    with self.lock:
                        self.last_frame = frame
                        
                        # Pre-encode raw frame for standard feeds
                        try:
                            # Encode frame as JPEG (Quality 80 for standard raw feeds)
                            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            self.last_jpeg_raw = buffer.tobytes()
                        except:
                            pass
                    
                    # 2. Notify AI thread that a new frame is available
                    self.frame_ready_event.set()

                    retry_count = 0
                    last_successful_frame_time = current_time

                    # Update monitoring
                    if monitor_available:
                        stream_monitor.update_frame_received(self.stream_id)

                    # Removed sleep to ensure capture loop does not fall behind real-time stream framerate
                    pass
                else:
                    retry_count += 1
                    # Only log every 5th failure to reduce spam from transient H.264 errors
                    if retry_count % 5 == 1:
                        logger.warning(f"Failed to read frame from {self.rtsp_url} (attempt {retry_count}/{max_retries})")

                    # Check if we've been without frames for too long
                    if current_time - last_successful_frame_time > 60:
                        logger.error(f"No frames received for 60 seconds from {self.rtsp_url}, forcing reconnection")
                        with _FFMPEG_CAPTURE_LOCK:
                            if self.cap:
                                self.cap.release()
                                self.cap = None
                        retry_count = 0
                        continue

                    if retry_count >= max_retries:
                        logger.error(f"Max retries reached for {self.rtsp_url}, reconnecting...")
                        with _FFMPEG_CAPTURE_LOCK:
                            if self.cap:
                                self.cap.release()
                                self.cap = None
                        retry_count = 0
                        time.sleep(3)
                    else:
                        time.sleep(0.1)  # Brief pause; most failures are transient decode errors


                # Periodic connection health check
                if current_time - last_health_check > connection_health_check_interval:
                    if self.cap and self.cap.isOpened():
                        # Try to get stream properties to check if connection is still alive
                        try:
                            fps = self.cap.get(cv2.CAP_PROP_FPS)
                            if fps <= 0:  # Invalid FPS might indicate connection issues
                                logger.warning(f"Connection health check failed for {self.rtsp_url} (invalid FPS: {fps})")
                        except:
                            logger.warning(f"Connection health check failed for {self.rtsp_url}")
                    last_health_check = current_time

            except Exception as e:
                error_msg = str(e).lower()
                error_type = 'general'

                if 'hevc' in error_msg or 'h.265' in error_msg or 'cabac' in error_msg or 'cu_qp_delta' in error_msg:
                    logger.warning(f"🎥 HEVC/H.265 codec issue for {self.rtsp_url}: {e}")
                    logger.info("🔄 Attempting to reconnect with different codec settings...")
                    error_type = 'codec'
                elif 'timeout' in error_msg or 'stream timeout triggered' in error_msg:
                    logger.warning(f"⏱️ Stream timeout for {self.rtsp_url} (will retry with longer timeouts): {e}")
                    error_type = 'timeout'
                elif 'connection' in error_msg or 'network' in error_msg:
                    logger.warning(f"🌐 Network connection issue for {self.rtsp_url}: {e}")
                    error_type = 'network'
                elif 'authentication' in error_msg or 'unauthorized' in error_msg:
                    logger.error(f"🔐 Authentication failed for {self.rtsp_url}: {e}")
                    error_type = 'auth'
                else:
                    logger.error(f"❌ General error in RTSP capture for {self.rtsp_url}: {e}")

                # Update monitoring
                if monitor_available:
                    stream_monitor.update_error(self.stream_id, str(e), error_type)

                if self.cap:
                    self.cap.release()
                    self.cap = None

                # Progressive delay based on error type
                if error_type == 'timeout':
                    time.sleep(10)  # Shorter wait for timeout errors - will try with longer timeouts
                elif error_type == 'network':
                    time.sleep(20)  # Medium wait for network issues
                elif error_type == 'auth':
                    time.sleep(60)  # Longer wait for auth issues (likely persistent)
                else:
                    time.sleep(30)  # Standard wait for other errors

    def _run_deep_reasoning(self, frame, event_context, stream_id=None):
        """Perform Layer 3 Vision LLM validation (Gemma 4 / Ollama)"""
        try:
            logger.info(f"Triggering Layer 3 Reasoning for {stream_id} - Rule ID: {event_context.get('id')}")
            from services.gemma_engine import gemma_engine
            reasoning_result = gemma_engine.analyze_behavior(frame, event_context)
            if reasoning_result and "error" not in reasoning_result:
                with self.lock:
                    for i, e in enumerate(self.last_events):
                        if e.get("id") == event_context.get("id"):
                            self.last_events[i]["deep_reasoning"] = reasoning_result
                            logger.info(f"Layer 3 Reasoning complete for {stream_id}")
                            
                            # Trigger Alert API if result is validated
                            if reasoning_result.get("event_validated"):
                                pattern_engine.trigger_alert_api(stream_id, self.last_events[i])
                            break
        except Exception as e:
            logger.error(f"Error in deep reasoning thread: {e}")

    def _ai_processing_loop(self):
        """Background thread for AI inference (Layers 1 & 2) to prevent capture lag"""
        logger.info(f"AI Processing thread started for {self.stream_id}")
        
        last_processed_time = 0
        while self.is_running:
            # Wait for a new frame from the capture thread
            # Timeout ensures we check 'is_running' periodically
            if not self.frame_ready_event.wait(timeout=1.0):
                continue
                
            self.frame_ready_event.clear()
            
            # Check if active rules exist for this camera
            from services.pattern_engine import pattern_engine
            active_rule_ids = pattern_engine.get_active_rules_for_source(self.stream_id) if pattern_engine else set()
            
            # If AI detection is disabled or no active rules exist for this camera, skip processing
            if not self.detection_enabled or not active_rule_ids:
                with self.lock:
                    self.last_detections = {"detections": [], "counts": {}, "frame_width": 640, "frame_height": 480}
                    self.last_annotated_frame = None
                time.sleep(0.5)
                continue
            
            # Limit AI inference to max 4 FPS (at least 250ms gap) to save CPU
            current_time = time.time()
            if current_time - last_processed_time < 0.25:
                continue
            
            last_processed_time = current_time
            
            # Get the latest frame
            with self.lock:
                frame_to_process = self.last_frame.copy() if self.last_frame is not None else None
            
            if frame_to_process is None:
                continue

            try:
                # 1. Process Cascaded AI (YOLO + Gemma ONNX)
                annotated_frame, detections_data = cascaded_ai_service.process_frame(frame_to_process, stream_id=self.stream_id)
                h, w = frame_to_process.shape[:2]
                detections_data["frame_width"] = w
                detections_data["frame_height"] = h
                
                # 2. Process Layer 2 (Pattern Engine)
                events = pattern_engine.process_detections(self.stream_id, detections_data)
                
                # 3. Process Layer 3 (Deep Reasoning)
                current_time = time.time()
                for event in events:
                    if event.get("trigger_layer3"):
                        if current_time - self.last_reasoning_time > 30:
                            self.last_reasoning_time = current_time
                            threading.Thread(
                                target=self._run_deep_reasoning,
                                args=(frame_to_process, event, self.stream_id),
                                daemon=True
                            ).start()
                        else:
                            logger.debug(f"Throttling Layer 3 Reasoning for {self.stream_id} ({event.get('type')})")
                    else:
                        # Non-Layer 3 event: Trigger Alert API immediately
                        pattern_engine.trigger_alert_api(self.stream_id, event)
                
                # 4. Sub-detections: face capture + recognition + hand gesture
                #    These run ONLY if their corresponding rule IDs are active for this camera
                self._run_sub_detections(frame_to_process, current_time, active_rule_ids)

                # Update state
                with self.lock:
                    self.last_annotated_frame = annotated_frame
                    self.last_detections = detections_data
                    self.last_events = events
                    
                    # Pre-encode annotated frame for AI Lab feeds (Quality 70 for throughput)
                    try:
                        _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        self.last_jpeg_annotated = buffer.tobytes()
                    except:
                        pass
                    
            except Exception as e:
                logger.error(f"Error in AI processing loop for {self.stream_id}: {e}")
                time.sleep(0.1)

    def _run_sub_detections(self, frame: 'cv2.Mat', timestamp: float, active_rule_ids: set):
        """
        Run face capture, face recognition, and hand gesture detection
        as lightweight sub-detections within the AI loop ONLY if their corresponding rule IDs are active.
        """
        kwargs = {
            "stream_id": self.stream_id,
            "timestamp": timestamp,
            "camera_toggle_active": True,
        }

        capture_db_ids = []
        # ── Face capture (Rule 6) ──────────────────────────────────────────
        if RULE_FACE_CAPTURE in active_rule_ids and _face_capture_detector:
            try:
                fc_result = _face_capture_detector.detect(frame, **kwargs)
                capture_db_ids = fc_result.get("metadata", {}).get("db_ids", [])
            except Exception as e:
                logger.debug("Face capture sub-detection error: %s", e)

        # ── Face recognition (Rule 7) ───────────────────────────────────────
        if RULE_FACE_RECOGNITION in active_rule_ids and _face_recognition_detector:
            try:
                _face_recognition_detector.detect(
                    frame, **{**kwargs, "capture_db_ids": capture_db_ids}
                )
            except Exception as e:
                logger.debug("Face recognition sub-detection error: %s", e)

        # ── Hand gesture / sign language (Rule 8) ─────────────────────────
        if RULE_GESTURE_DETECTION in active_rule_ids and _sign_language_detector:
            try:
                _sign_language_detector.detect(frame, **kwargs)
            except Exception as e:
                logger.debug("Sign language sub-detection error: %s", e)

    def enable_detection(self):
        """Enable AI processing for this stream (idempotent)"""
        with self.lock:
            if self.detection_enabled:
                return  # Already enabled
            self.detection_enabled = True
            logger.info(f"AI Detection enabled for stream: {self.stream_id}")

    def disable_detection(self):
        """Disable AI processing for this stream to save CPU (idempotent)"""
        with self.lock:
            if not self.detection_enabled:
                return  # Already disabled
            self.detection_enabled = False
            self.last_annotated_frame = None
            pattern_engine.clear_source_data(self.stream_id)
            logger.info(f"AI Detection disabled for stream: {self.stream_id}")

    def get_annotated_frame(self) -> Optional[bytes]:
        """Get the latest processed frame from JPEG cache"""
        with self.lock:
            return self.last_jpeg_annotated

    def get_events(self):
        """Return the latest AI security events for this stream"""
        with self.lock:
            return self.last_events

    def get_frame(self) -> Optional[bytes]:
        """Get the latest raw frame from JPEG cache"""
        with self.lock:
            return self.last_jpeg_raw

    def gemma_analyze_scene(self):
        """Trigger an on-demand deep scene analysis using Gemma"""
        with self.lock:
            frame = self.last_frame.copy() if self.last_frame is not None else None
        
        if frame is not None:
            return gemma_engine.analyze_scene(frame, self.stream_id)
        return {"error": "No frame available for analysis"}

class WebcamStream:
    """Thread-safe Webcam stream handler with YOLO26 detection and tracking"""

    def __init__(self, device_id: int = 0):
        self.device_id = device_id
        self.stream_id = "webcam"
        self.cap = None
        self.is_running = False
        self.lock = threading.Lock()
        self.last_frame = None
        self.last_annotated_frame = None
        self.last_detections = {"detections": [], "counts": {}}
        self.last_events = []
        self.last_reasoning_time = 0
        self.thread = None
        self.ai_thread = None
        self.frame_ready_event = threading.Event()
        
        # JPEG Cache
        self.last_jpeg_raw = None
        self.last_jpeg_annotated = None
        self.detection_enabled = False

    def enable_detection(self):
        """Enable AI processing for this webcam (idempotent)"""
        with self.lock:
            if self.detection_enabled:
                return  # Already enabled
            self.detection_enabled = True
            logger.info("AI Detection enabled for webcam")

    def disable_detection(self):
        """Disable AI processing for this webcam to save CPU (idempotent)"""
        with self.lock:
            if not self.detection_enabled:
                return  # Already disabled
            self.detection_enabled = False
            self.last_annotated_frame = None
            pattern_engine.clear_source_data("webcam")
            logger.info("AI Detection disabled for webcam")

    def start(self):
        """Start the Webcam stream capture and processing"""
        with self.lock:
            if self.is_running:
                return
            self.is_running = True
            
            # Start Capture Thread
            self.thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            
            # Start AI Processing Thread
            self.ai_thread = threading.Thread(target=self._ai_processing_loop, daemon=True)
            self.ai_thread.start()
            
            logger.info(f"Started Webcam stream and AI pipeline (Device: {self.device_id})")

    def stop(self):
        """Stop the Webcam stream"""
        with self.lock:
            self.is_running = False
            
        # Wait for threads to exit
        for t in [self.thread, self.ai_thread]:
            if t and t.is_alive():
                try:
                    t.join(timeout=1.0)
                except Exception as e:
                    logger.error(f"Error joining webcam thread: {e}")

        with self.lock:
            if self.cap:
                self.cap.release()
                self.cap = None
            logger.info("Stopped Webcam stream")

    def _capture_frames(self):
        """Capture frames from webcam in a dedicated thread"""
        self.cap = cv2.VideoCapture(self.device_id)
        
        # Set resolution and buffer for performance
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 3) # Prevent dropping frames
        
        while self.is_running:
            ret, frame = self.cap.read()
            if ret and frame is not None:
                with self.lock:
                    self.last_frame = frame
                    
                    # Pre-encode raw JPEG
                    try:
                        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                        self.last_jpeg_raw = buffer.tobytes()
                    except:
                        pass
                
                # Notify AI processing thread
                self.frame_ready_event.set()
                
                # Removed sleep to prevent read loop from accumulating lag
                pass
            else:
                logger.warning("Failed to read from webcam, retrying...")
                self.cap.release()
                time.sleep(2)
                self.cap = cv2.VideoCapture(self.device_id)

    def _ai_processing_loop(self):
        """Background thread for Webcam AI inference"""
        logger.info("Webcam AI Processing thread started")
        
        last_processed_time = 0
        while self.is_running:
            # Wait for a new frame
            if not self.frame_ready_event.wait(timeout=1.0):
                continue
                
            self.frame_ready_event.clear()
            
            # Check if active rules exist for webcam
            from services.pattern_engine import pattern_engine
            active_rule_ids = pattern_engine.get_active_rules_for_source("webcam") if pattern_engine else set()
            
            if not self.detection_enabled or not active_rule_ids:
                # Clear lingering detections
                with self.lock:
                    self.last_detections = {"detections": [], "counts": {}, "frame_width": 640, "frame_height": 480}
                    self.last_annotated_frame = None
                time.sleep(0.5)
                continue
            
            # Limit AI inference to max 4 FPS (at least 250ms gap) to save CPU
            current_time = time.time()
            if current_time - last_processed_time < 0.25:
                continue
            
            last_processed_time = current_time
            
            # Get latest frame
            with self.lock:
                frame_to_process = self.last_frame.copy() if self.last_frame is not None else None
            
            if frame_to_process is None:
                continue

            try:
                # 1. Process Cascaded AI (YOLO + Gemma ONNX)
                annotated_frame, detections_data = cascaded_ai_service.process_frame(frame_to_process, stream_id="webcam")
                
                # Enrich with frame dimensions for coordinate mapping
                h, w = frame_to_process.shape[:2]
                detections_data["frame_width"] = w
                detections_data["frame_height"] = h
                
                # 2. Process Layer 2 (Pattern Engine)
                events = pattern_engine.process_detections("webcam", detections_data)
                
                # 3. Layer 3: Deep Behavioral Reasoning
                current_time = time.time()
                for event in events:
                    if event.get("trigger_layer3"):
                        if current_time - self.last_reasoning_time > 30:
                            self.last_reasoning_time = current_time
                            threading.Thread(
                                target=self._run_deep_reasoning,
                                args=(frame_to_process, event),
                                daemon=True
                            ).start()

                # 4. Sub-detections: face capture, face recognition, hand gesture
                self._run_sub_detections(frame_to_process, current_time, active_rule_ids)
                
                with self.lock:
                    self.last_annotated_frame = annotated_frame
                    self.last_detections = detections_data
                    self.last_events = events
                    
                    # Pre-encode annotated JPEG
                    try:
                        _, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        self.last_jpeg_annotated = buffer.tobytes()
                    except:
                        pass
                    
            except Exception as e:
                logger.error(f"Error in Webcam AI loop: {e}")
                time.sleep(0.1)

    def _run_sub_detections(self, frame: 'cv2.Mat', timestamp: float, active_rule_ids: set):
        """Run sub-detections for webcam ONLY if corresponding rule IDs are active."""
        kwargs = {
            "stream_id": "webcam",
            "timestamp": timestamp,
            "camera_toggle_active": True,
        }

        capture_db_ids = []
        if RULE_FACE_CAPTURE in active_rule_ids and _face_capture_detector:
            try:
                fc_result = _face_capture_detector.detect(frame, **kwargs)
                capture_db_ids = fc_result.get("metadata", {}).get("db_ids", [])
            except Exception as e:
                logger.debug("Face capture sub-detection error: %s", e)

        if RULE_FACE_RECOGNITION in active_rule_ids and _face_recognition_detector:
            try:
                _face_recognition_detector.detect(
                    frame, **{**kwargs, "capture_db_ids": capture_db_ids}
                )
            except Exception as e:
                logger.debug("Face recognition sub-detection error: %s", e)

        if RULE_GESTURE_DETECTION in active_rule_ids and _sign_language_detector:
            try:
                _sign_language_detector.detect(frame, **kwargs)
            except Exception as e:
                logger.debug("Sign language sub-detection error: %s", e)

    def _run_deep_reasoning(self, frame, event_context):
        """Perform Layer 3 Vision LLM validation (Gemma 4)"""
        try:
            logger.info(f"Triggering Layer 3 Reasoning for: {event_context['type']}")
            reasoning_result = gemma_engine.analyze_behavior(frame, event_context)
            
            # Attach reasoning to the event
            if reasoning_result and "error" not in reasoning_result:
                with self.lock:
                    for i, e in enumerate(self.last_events):
                        if e.get("id") == event_context.get("id"):
                            self.last_events[i]["deep_reasoning"] = reasoning_result
                            break
                logger.info(f"Layer 3 result: {reasoning_result.get('threat_type')}")
        except Exception as e:
            logger.error(f"Error in webcam deep reasoning: {e}")

    def get_annotated_frame(self) -> Optional[bytes]:
        """Get the latest processed frame from JPEG cache"""
        with self.lock:
            return self.last_jpeg_annotated

    def get_detections(self):
        """Get the latest detections metadata"""
        with self.lock:
            return self.last_detections

    def get_active_events(self):
        """Get the latest Layer 2 & 3 security events"""
        with self.lock:
            return self.last_events

    def get_frame(self) -> Optional[bytes]:
        """Get the latest raw frame from JPEG cache"""
        with self.lock:
            return self.last_jpeg_raw

    def gemma_analyze_scene(self):
        """Trigger an on-demand deep scene analysis using Gemma"""
        with self.lock:
            frame = self.last_frame.copy() if self.last_frame is not None else None
        
        if frame is not None:
            return gemma_engine.analyze_scene(frame, self.stream_id)
        return {"error": "No frame available for analysis"}

# Global dictionary to store active RTSP streams
active_streams: Dict[str, RTSPStream] = {}

# Global webcam stream instance
webcam_stream: Optional[WebcamStream] = None

# Global archive recording manager
archive_recording_manager: Optional[ArchiveRecordingManager] = None

# Helper to find a stream by ID with fuzzy matching (converts dashes to underscores/dots)
def get_stream_by_id(stream_id: str) -> Optional[RTSPStream]:
    """
    Finds an active stream by its ID, supporting both original and normalized formats.
    e.g., 'eagle-192-168-4-243' -> 'Eagle_192.168.4.243'
    """
    # 1. Exact match
    if stream_id in active_streams:
        return active_streams[stream_id]
        
    # 2. Case-insensitive or normalized match
    normalized_target = stream_id.lower().replace('-', '.')
    for sid, stream in active_streams.items():
        # Match if IDs are the same after normalization
        if sid.lower().replace('_', '.').replace('-', '.') == normalized_target:
            return stream
            
    # 3. Last resort: check if the ID is just the IP
    for sid, stream in active_streams.items():
        if stream_id in sid:
            return stream
            
    return None

# Health check task
health_check_task = None

async def periodic_health_check():
    """Periodic health check for recording processes"""
    global archive_recording_manager

    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes

            if archive_recording_manager:
                logger.info("Running periodic recording health check...")
                archive_recording_manager.restart_failed_recordings()

                # Log current status
                status = archive_recording_manager.get_recording_status()
                active_count = status.get('active_recordings', 0)
                logger.info(f"Health check complete: {active_count} active recordings")

        except Exception as e:
            logger.error(f"Error in periodic health check: {e}")

def start_health_check_task():
    """Start the periodic health check task"""
    global health_check_task

    if health_check_task is None:
        health_check_task = asyncio.create_task(periodic_health_check())
        logger.info("Started periodic health check task")

app = FastAPI(title="VMS RTSP & Webcam Streaming Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event to auto-start all configured camera streams
@app.on_event("startup")
async def startup_event():
    """Auto-start all configured camera streams and archive recording when the server starts"""
    global archive_recording_manager

    logger.info("Starting VMS RTSP Streaming Server...")

    # Initialize archive recording manager
    try:
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        archive_recording_manager = ArchiveRecordingManager(CAMERA_JSON_PATH, os.path.join(backend_dir, "recordings"))
        # Set the archive manager in the archive routes module
        archive.set_archive_manager(archive_recording_manager)

        # Start recording for all configured cameras
        archive_recording_manager.start_all_recordings()
        logger.info("Archive recording system initialized and started")

        # Start periodic health check
        start_health_check_task()

    except Exception as e:
        logger.error(f"Critical error in startup_event: {e}")
        # Continue anyway; the server starts, even if archive system fails
        pass

    logger.info("Auto-starting configured camera streams...")
    auto_start_all_streams()

# Shutdown event to ensure clean shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of all recording processes and streams"""
    logger.info("FastAPI shutdown event triggered, cleaning up...")
    cleanup_streams()

# Get the backend directory
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
CAMERA_JSON_PATH = os.path.join(BACKEND_DIR, "data/camera_configuration.json")
CAMERA_LOCATIONS_PATH = os.path.join(BACKEND_DIR, "data/camera_locations.json")

# Log the paths for debugging
logger.debug(f"Backend directory: {BACKEND_DIR}")
logger.debug(f"Looking for camera config at: {CAMERA_JSON_PATH}")
logger.debug(f"File exists: {os.path.exists(CAMERA_JSON_PATH)}")

def cleanup_streams():
    """Clean up all active streams and archive recording"""
    global active_streams, archive_recording_manager, webcam_stream

    # Stop webcam stream
    if webcam_stream:
        try:
            webcam_stream.stop()
        except Exception as e:
            logger.error(f"Error stopping webcam stream: {e}")

    # Stop all active streams
    for stream_id, stream in active_streams.items():
        try:
            stream.stop()
        except Exception as e:
            logger.error(f"Error stopping stream {stream_id}: {e}")
    active_streams.clear()
    logger.info("All streams cleaned up")

    # Stop archive recording
    if archive_recording_manager:
        try:
            archive_recording_manager.stop_all_recordings()
            logger.info("Archive recording stopped")
        except Exception as e:
            logger.error(f"Error stopping archive recording: {e}")

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    # Use a simpler cleanup approach for signals to avoid recursion or lock issues
    try:
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        # Since uvicorn handles its own signals, we primarily want to ensure
        # that our custom background processes (FFmpeg, etc.) are stopped.
        if archive_recording_manager:
            archive_recording_manager.stop_all_recordings()
    except:
        pass
    # We don't call exit(0) here as uvicorn's own shutdown will handle the process exit

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Register cleanup function
atexit.register(cleanup_streams)

def auto_start_all_streams():
    """Automatically start streams for all configured cameras on startup"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            logger.warning(f"Camera configuration file not found at: {CAMERA_JSON_PATH}")
            return

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        total_started = 0
        total_errors = 0

        for collection_name, cameras in camera_data.items():
            logger.info(f"Auto-starting streams for collection: {collection_name}")

            for camera_ip, rtsp_url in cameras.items():
                # Use consistent stream ID format: collection_cameraip
                stream_id = f"{collection_name}_{camera_ip}"

                try:
                    # Skip if stream already exists and is running
                    if stream_id in active_streams:
                        existing_stream = active_streams[stream_id]
                        if existing_stream.is_running and existing_stream.rtsp_url == rtsp_url:
                            logger.info(f"Stream {stream_id} already running, skipping...")
                            continue
                        else:
                            # Stop existing stream if URL changed or not running
                            existing_stream.stop()
                            del active_streams[stream_id]

                    # Create and start new stream
                    logger.info(f"Auto-starting stream {stream_id} for URL: {rtsp_url}")
                    stream = RTSPStream(rtsp_url, stream_id)
                    stream.start()
                    active_streams[stream_id] = stream
                    total_started += 1

                except Exception as e:
                    logger.error(f"Failed to auto-start stream for {camera_ip} in {collection_name}: {e}")
                    total_errors += 1

        logger.info(f"Auto-startup complete: {total_started} streams started, {total_errors} errors")

    except Exception as e:
        logger.error(f"Error during auto-startup of streams: {e}")

async def generate_mjpeg_stream(stream_id: str):
    """Generate MJPEG stream for a given stream ID using JPEG cache"""
    stream = get_stream_by_id(stream_id)
    if not stream:
        logger.error(f"Stream {stream_id} not found")
        return

    try:
        while stream.is_running:
            frame_data = stream.get_frame()
            if frame_data:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
            
            # Use small async sleep to yield to event loop
            await asyncio.sleep(0.01)
    except GeneratorExit:
        logger.debug(f"Video feed generator exit for {stream_id}")
    except Exception as e:
        logger.error(f"Error in video feed generator: {e}")

@app.get("/api/video_feed/webcam")
async def webcam_video_feed():
    """Serve MJPEG video feed for the local webcam with YOLO26 annotations"""
    global webcam_stream
    if webcam_stream is None or not webcam_stream.is_running:
        return JSONResponse({"error": "Webcam stream not started"}, status_code=400)

    async def generate_webcam_mjpeg():
        try:
            while webcam_stream.is_running:
                frame_data = webcam_stream.get_annotated_frame()
                if frame_data:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                
                await asyncio.sleep(0.01)
        except GeneratorExit:
            logger.debug(f"Webcam generator exit")
        except Exception as e:
            logger.error(f"Error in webcam generator: {e}")

    return StreamingResponse(
        generate_webcam_mjpeg(),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )

@app.get("/api/video_feed/webcam/raw")
async def webcam_raw_video_feed():
    """Serve raw MJPEG video feed for the local webcam"""
    global webcam_stream
    if webcam_stream is None or not webcam_stream.is_running:
        return JSONResponse({"error": "Webcam stream not started"}, status_code=400)

    async def generate_webcam_raw_mjpeg():
        try:
            while webcam_stream.is_running:
                frame_data = webcam_stream.get_frame()
                if frame_data:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                
                await asyncio.sleep(0.01)
        except GeneratorExit:
            logger.debug(f"Webcam raw generator exit")
        except Exception as e:
            logger.error(f"Error in webcam raw generator: {e}")

    return StreamingResponse(
        generate_webcam_raw_mjpeg(),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )

@app.get("/api/webcam/detections")
async def get_webcam_detections():
    """Get the latest real-time detections and counts from the webcam"""
    global webcam_stream
    if webcam_stream is None:
        return {"detections": [], "counts": {}}
    return webcam_stream.get_detections()

@app.get("/api/webcam/events")
async def get_webcam_events():
    """Get the latest security events (Crowd, Rapid Motion, etc.)"""
    global webcam_stream
    if webcam_stream is None:
        return {"events": []}
    return {"events": webcam_stream.get_active_events()}

@app.post("/api/webcam/start")
async def start_webcam_stream(device_id: int = 0):
    """Start the local webcam stream with YOLO26 tracking"""
    global webcam_stream
    try:
        if webcam_stream is None:
            webcam_stream = WebcamStream(device_id)
        
        webcam_stream.start()
        return {"success": True, "message": "Webcam stream started"}
    except Exception as e:
        logger.error(f"Error starting webcam: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/webcam/stop")
async def stop_webcam_stream():
    """Stop the local webcam stream"""
    global webcam_stream
    if webcam_stream:
        webcam_stream.stop()
        return {"success": True, "message": "Webcam stream stopped"}
    return {"success": False, "message": "Webcam stream not active"}

@app.get("/api/gemma/analyze/{stream_id}")
async def analyze_scene_with_gemma(stream_id: str):
    """Trigger deep AI reasoning on the current frame of a stream"""
    stream = get_stream_by_id(stream_id)
    if not stream:
        # Check webcam
        if webcam_stream and stream_id == "webcam":
            stream = webcam_stream
        else:
            return JSONResponse({"error": "Stream not found"}, status_code=404)
    
    result = stream.gemma_analyze_scene()
    return result

@app.get("/api/video_feed/{stream_id}")
async def video_feed(stream_id: str):
    """Serve MJPEG video feed for a specific stream (Auto-starts if needed)"""
    stream = get_stream_by_id(stream_id)
    
    if not stream:
        # Try to find and start this stream automatically
        logger.info(f"Stream {stream_id} not active. Attempting auto-start...")
        
        # Parse stream_id (could be collection_ip or normalized)
        # We'll use the camera configuration to find the RTSP URL
        try:
            if not os.path.exists(CAMERA_JSON_PATH):
                return JSONResponse({"error": "Stream not found and config missing"}, status_code=404)
                
            with open(CAMERA_JSON_PATH, "r") as f:
                camera_data = json.load(f)
                
            found_rtsp = None
            found_sid = None
            
            # Normalize target for matching
            target = stream_id.lower().replace('-', '.').replace('_', '.')
            
            for coll_name, cameras in camera_data.items():
                for ip, rtsp in cameras.items():
                    sid = f"{coll_name}_{ip}"
                    if sid.lower().replace('-', '.').replace('_', '.') == target or ip in target:
                        found_rtsp = rtsp
                        found_sid = sid
                        break
                if found_rtsp: break
                
            if found_rtsp:
                logger.info(f"Auto-starting {found_sid} for requested feed {stream_id}")
                stream = RTSPStream(found_rtsp, found_sid)
                stream.start()
                active_streams[found_sid] = stream
            else:
                return JSONResponse({"error": "Stream not found in active or configured list"}, status_code=404)
        except Exception as e:
            logger.error(f"Error auto-starting stream: {e}")
            return JSONResponse({"error": f"Failed to auto-start stream: {str(e)}"}, status_code=500)

    return StreamingResponse(
        generate_mjpeg_stream(stream.stream_id),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )

@app.get("/api/snapshot/{stream_id}")
async def get_snapshot(stream_id: str):
    """Capture a single frame from a stream"""
    stream = get_stream_by_id(stream_id)
    if not stream:
        # Try auto-start if configured
        await video_feed(stream_id)
        stream = get_stream_by_id(stream_id)
        
    if not stream or not stream.is_running:
        return JSONResponse({"error": "Stream not active"}, status_code=404)
        
    frame_data = stream.get_frame()
    if frame_data:
        return StreamingResponse(
            io.BytesIO(frame_data),
            media_type="image/jpeg"
        )
    return JSONResponse({"error": "Failed to capture frame"}, status_code=500)

@app.get("/api/get_stream_for_camera")
async def get_stream_for_camera(camera_ip: str, collection_name: str = None):
    """Get existing stream information for a camera, or suggest consistent stream ID"""
    try:
        # If collection_name not provided, try to find it in the configuration
        if not collection_name:
            if not os.path.exists(CAMERA_JSON_PATH):
                return JSONResponse({"error": "camera_configuration.json not found"}, status_code=404)

            with open(CAMERA_JSON_PATH, "r") as f:
                camera_data = json.load(f)

            # Find which collection contains this camera IP
            for coll_name, cameras in camera_data.items():
                if camera_ip in cameras:
                    collection_name = coll_name
                    break

            if not collection_name:
                return JSONResponse({"error": "Camera IP not found in any collection"}, status_code=404)

        # Generate consistent stream ID
        consistent_stream_id = f"{collection_name}_{camera_ip}"

        # Check if stream already exists
        if consistent_stream_id in active_streams:
            existing_stream = active_streams[consistent_stream_id]
            if existing_stream.is_running:
                return JSONResponse({
                    "success": True,
                    "stream_id": consistent_stream_id,
                    "feed_url": f"/api/video_feed/{consistent_stream_id}",
                    "exists": True,
                    "is_running": True
                })

        return JSONResponse({
            "success": True,
            "stream_id": consistent_stream_id,
            "feed_url": f"/api/video_feed/{consistent_stream_id}",
            "exists": False,
            "is_running": False
        })

    except Exception as e:
        logger.error(f"Error getting stream for camera: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/start_stream")
async def start_stream(request: Request):
    """Start a new RTSP stream with improved existing stream handling"""
    try:
        body = await request.json()
        rtsp_url = body.get("rtsp_url")
        stream_id = body.get("stream_id")

        if not rtsp_url or not stream_id:
            return JSONResponse({"error": "rtsp_url and stream_id are required"}, status_code=400)

        # Check if stream already exists and is running
        if stream_id in active_streams:
            existing_stream = active_streams[stream_id]
            if existing_stream.is_running and existing_stream.rtsp_url == rtsp_url:
                logger.debug(f"Stream {stream_id} already exists and running, reusing...")
                return JSONResponse({
                    "success": True,
                    "stream_id": stream_id,
                    "feed_url": f"/api/video_feed/{stream_id}",
                    "reused": True
                })
            else:
                # Stop existing stream if URL is different or not running
                logger.info(f"Stopping existing stream {stream_id} (URL changed or not running)")
                existing_stream.stop()
                del active_streams[stream_id]

        # Only log new stream creation, not reuse
        logger.info(f"Creating new stream {stream_id} for URL: {rtsp_url}")
        stream = RTSPStream(rtsp_url, stream_id)
        stream.start()
        active_streams[stream_id] = stream

        logger.info(f"Started stream {stream_id} for URL: {rtsp_url}")

        return JSONResponse({
            "success": True,
            "stream_id": stream_id,
            "feed_url": f"/api/video_feed/{stream_id}"
        })

    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/api/stop_stream/{stream_id}")
async def stop_stream(stream_id: str):
    """Stop a specific stream"""
    try:
        if stream_id in active_streams:
            active_streams[stream_id].stop()
            del active_streams[stream_id]
            logger.info(f"Stopped stream {stream_id}")
            return JSONResponse({"success": True, "message": f"Stream {stream_id} stopped"})
        else:
            return JSONResponse({"error": "Stream not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error stopping stream {stream_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/video_feed/detection/{stream_id}")
async def detection_feed(stream_id: str):
    """Serve MJPEG video feed WITH AI annotations for a specific stream"""
    # Use fuzzy lookup to resolve ID mismatches
    stream = get_stream_by_id(stream_id)
    
    if not stream:
        # Special case for webcam
        if stream_id == "webcam" and webcam_stream:
            return await webcam_video_feed()
        logger.warning(f"Detection feed requested for unknown stream: {stream_id}")
        return JSONResponse({"error": f"Stream '{stream_id}' not found"}, status_code=404)

    # Enable detection on-demand (Production CPU Optimization)
    stream.enable_detection()

    async def generate_detection_mjpeg():
        try:
            while stream.is_running:
                frame_data = stream.get_annotated_frame()
                if frame_data:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                
                # Small sleep to prevent event loop blocking
                await asyncio.sleep(0.01)
        except GeneratorExit:
            logger.debug(f"Detection feed generator exit for {stream_id}")
        except Exception as e:
            logger.error(f"Error in detection feed generator: {e}")
        finally:
            # We don't disable here to allow multiple viewers
            pass

    return StreamingResponse(
        generate_detection_mjpeg(),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )

@app.get("/api/stream/events/{stream_id}")
async def get_stream_events(stream_id: str):
    """Retrieve the latest Layer 2/3 events for a specific RTSP stream"""
    stream = get_stream_by_id(stream_id)
    if not stream:
        if stream_id == "webcam":
            return await get_webcam_events()
        return {"events": []}
    
    return {"events": stream.get_events()}

@app.post("/api/stream/detection/stop/{stream_id}")
async def stop_detection_processing(stream_id: str):
    """Explicitly disable AI processing for a stream to save CPU resources"""
    stream = get_stream_by_id(stream_id)
    if stream:
        stream.disable_detection()
        return {"success": True}
    elif stream_id == "webcam" and webcam_stream:
        webcam_stream.disable_detection()
        return {"success": True}
    return {"success": False}

@app.post("/api/stream/detection/start/{stream_id}")
async def start_detection_processing(stream_id: str):
    """Explicitly enable AI processing for a stream to start detection"""
    stream = get_stream_by_id(stream_id)
    if stream:
        stream.enable_detection()
        return {"success": True}
    elif stream_id == "webcam" and webcam_stream:
        webcam_stream.enable_detection()
        return {"success": True}
    return {"success": False}

@app.get("/api/stream/detections/{stream_id}")
async def get_stream_detections(stream_id: str):
    """Get real-time detection counts and metadata for a stream"""
    stream = get_stream_by_id(stream_id)
    if not stream:
        if stream_id == "webcam" and webcam_stream:
            return webcam_stream.get_detections()
        return {"detections": [], "counts": {}, "motion_score": 0}
    
    with stream.lock:
        return stream.last_detections

@app.get("/api/ai/status")
async def get_ai_status():
    """Get the current AI engine status (Gemma, YOLO, PatternEngine)"""
    gemma_status = gemma_engine.get_status()
    return {
        "gemma": gemma_status,
        "yolo": {
            "model": "YOLO26 Nano",
            "status": "active",
            "skip_frames": yolo26_engine.skip_n_frames,
        },
        "rules_total": 23,
        "active_streams": len(active_streams),
    }

@app.get("/api/streams")
async def list_streams():
    """List all active streams"""
    try:
        stream_info = {}
        for stream_id, stream in active_streams.items():
            stream_info[stream_id] = {
                "rtsp_url": stream.rtsp_url,
                "is_running": stream.is_running,
                "feed_url": f"/api/video_feed/{stream_id}"
            }
        return JSONResponse({"streams": stream_info})
    except Exception as e:
        logger.error(f"Error listing streams: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Integration with existing camera configuration system
@app.get("/api/start_collection_streams/{collection_name}")
async def start_collection_streams(collection_name: str):
    """Start streams for all cameras in a collection"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return JSONResponse({"error": "camera_configuration.json not found"}, status_code=404)

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        if collection_name not in camera_data:
            return JSONResponse({"error": "Collection not found"}, status_code=404)

        started_streams = []
        errors = []

        for camera_ip, rtsp_url in camera_data[collection_name].items():
            stream_id = f"{collection_name}_{camera_ip}"

            try:
                # Stop existing stream if it exists
                if stream_id in active_streams:
                    active_streams[stream_id].stop()
                    del active_streams[stream_id]

                # Create and start new stream
                stream = RTSPStream(rtsp_url)
                stream.start()
                active_streams[stream_id] = stream

                started_streams.append({
                    "stream_id": stream_id,
                    "camera_ip": camera_ip,
                    "rtsp_url": rtsp_url,
                    "feed_url": f"/api/video_feed/{stream_id}"
                })

                logger.info(f"Started stream {stream_id} for camera {camera_ip}")

            except Exception as e:
                error_msg = f"Failed to start stream for camera {camera_ip}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        response = {
            "collection": collection_name,
            "started_streams": started_streams,
            "count": len(started_streams)
        }

        if errors:
            response["errors"] = errors

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Error starting collection streams: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Legacy endpoints for compatibility with existing frontend
@app.get("/restart-stream/{collection_name}/{camera_ip}")
async def restart_stream(collection_name: str, camera_ip: str):
    """Restart a specific camera stream using new MJPEG system"""
    try:
        logger.debug(f"Restarting stream for camera {camera_ip} in collection {collection_name}")

        if not os.path.exists(CAMERA_JSON_PATH):
            logger.error(f"Config file not found at: {CAMERA_JSON_PATH}")
            return {"error": "camera_configuration.json not found"}

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        if collection_name not in camera_data:
            logger.error(f"Collection '{collection_name}' not found in camera data")
            return {"error": "Collection not found"}

        if camera_ip not in camera_data[collection_name]:
            logger.error(f"Camera IP '{camera_ip}' not found in collection '{collection_name}'")
            return {"error": "Camera IP not found in collection"}

        # Get the RTSP URL for this camera
        rtsp_url = camera_data[collection_name][camera_ip]
        stream_id = f"{collection_name}_{camera_ip}"

        # Stop existing stream if it exists
        if stream_id in active_streams:
            active_streams[stream_id].stop()
            del active_streams[stream_id]

        # Create and start new stream
        stream = RTSPStream(rtsp_url)
        stream.start()
        active_streams[stream_id] = stream

        logger.info(f"Restarted stream {stream_id} for camera {camera_ip}")

        return {
            "status": "success",
            "stream_url": f"/api/video_feed/{stream_id}",
            "stream_id": stream_id
        }

    except Exception as e:
        logger.error(f"Error restarting stream: {str(e)}")
        return {"error": str(e)}

@app.get("/start-streams/{collection_name}")
async def start_camera_streams(collection_name: str):
    """Start MJPEG streams for all cameras in a collection (legacy endpoint)"""
    try:
        logger.debug(f"Starting streams for collection: {collection_name}")
        logger.debug(f"Looking for config file at: {CAMERA_JSON_PATH}")

        if not os.path.exists(CAMERA_JSON_PATH):
            logger.error(f"Config file not found at: {CAMERA_JSON_PATH}")
            return {"error": "camera_configuration.json not found"}

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)
            logger.debug(f"Loaded camera data: {json.dumps(camera_data, indent=2)}")
            logger.debug(f"Available collections: {list(camera_data.keys())}")

        if collection_name not in camera_data:
            logger.error(f"Collection '{collection_name}' not found in camera data")
            return {"error": "Collection not found"}

        # Start MJPEG streams
        stream_urls = []
        errors = []

        for camera_ip, rtsp_url in camera_data[collection_name].items():
            stream_id = f"{collection_name}_{camera_ip}"
            logger.debug(f"Starting stream for {stream_id} with URL: {rtsp_url}")

            try:
                # Stop existing stream if it exists
                if stream_id in active_streams:
                    active_streams[stream_id].stop()
                    del active_streams[stream_id]

                # Create and start new stream
                stream = RTSPStream(rtsp_url)
                stream.start()
                active_streams[stream_id] = stream

                # Store the stream URL in our list
                stream_urls.append(f"/api/video_feed/{stream_id}")

            except Exception as e:
                error_msg = f"Camera {camera_ip}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        response = {
            "collection": collection_name,
            "streams": stream_urls,
            "count": len(stream_urls)
        }

        if errors:
            response["warnings"] = errors

        return response
    except Exception as e:
        logger.error(f"Error starting streams: {str(e)}")
        return {"error": str(e)}

@app.get("/collections")
async def get_collections():
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return {"error": "camera_configuration.json not found"}

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        collections = list(camera_data.keys())
        return {"collections": collections}
    except Exception as e:
        return {"error": str(e)}

@app.get("/webrtc-streams/{collection_name}")
async def get_webrtc_streams(collection_name: str):
    """Get WebRTC stream information for all cameras in a collection"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return JSONResponse({"error": "camera_configuration.json not found"}, status_code=404)

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        if collection_name not in camera_data:
            return JSONResponse({"error": "Collection not found"}, status_code=404)

        # Create stream info for each camera in the collection
        streams = []
        for camera_ip, rtsp_url in camera_data[collection_name].items():
            stream_info = {
                "stream_id": f"webrtc_{collection_name}_{camera_ip}",
                "room_id": f"{collection_name}_{camera_ip}",
                "camera_ip": camera_ip,
                "rtsp_url": rtsp_url,
                "collection_name": collection_name
            }
            streams.append(stream_info)

        return JSONResponse({
            "success": True,
            "streams": streams,
            "collection": collection_name,
            "count": len(streams)
        })

    except Exception as e:
        logger.error(f"Error getting WebRTC streams for collection {collection_name}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/cameras")
async def get_cameras():
    """Get all cameras from the configuration file"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return {"error": "camera_configuration.json not found"}

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        return {"cameras": camera_data}
    except Exception as e:
        logger.error(f"Error getting cameras: {str(e)}")
        return {"error": str(e)}

@app.get("/api/camera-locations")
async def get_camera_locations():
    """Get all camera latitude/longitude coordinates and custom map settings"""
    try:
        if not os.path.exists(CAMERA_LOCATIONS_PATH):
            # Create default empty template if doesn't exist
            default_config = {
                "settings": {
                    "defaultProvider": "leaflet",
                    "center": [12.9716, 77.5946],
                    "zoom": 13
                },
                "locations": {}
            }
            os.makedirs(os.path.dirname(CAMERA_LOCATIONS_PATH), exist_ok=True)
            with open(CAMERA_LOCATIONS_PATH, "w") as f:
                json.dump(default_config, f, indent=2)
            return default_config

        with open(CAMERA_LOCATIONS_PATH, "r") as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Error getting camera locations: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/camera-locations")
async def save_camera_locations(request: Request):
    """Save camera coordinates and map preferences"""
    try:
        data = await request.json()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(CAMERA_LOCATIONS_PATH), exist_ok=True)
        
        # Backup old file if it exists
        if os.path.exists(CAMERA_LOCATIONS_PATH):
            backup_path = CAMERA_LOCATIONS_PATH + ".bak"
            shutil.copy2(CAMERA_LOCATIONS_PATH, backup_path)
            
        # Write to temporary file first
        temp_path = CAMERA_LOCATIONS_PATH + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, CAMERA_LOCATIONS_PATH)
        
        return {"success": True, "message": "Camera locations saved successfully"}
    except Exception as e:
        logger.error(f"Error saving camera locations: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/geocode")
async def geocode(q: str):
    """
    Proxy geocoding endpoint to Nominatim.openstreetmap.org.
    Bypasses CORS, browser header restrictions, and uses a reliable User-Agent.
    """
    import urllib.request
    import urllib.parse
    import json
    import time

    if not q or not q.strip():
        return {"results": []}

    query = q.strip()

    def fetch_nominatim(query_str):
        encoded_query = urllib.parse.quote(query_str)
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_query}&limit=5"
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'VMS-System-CamMapConfig/1.0.0 (contact@vms.local)',
                'Accept-Language': 'en'
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            logger.error(f"Error fetching geocode from Nominatim: {e}")
            return None

    # Generate unique progressive candidate queries to handle typos, landmark noise, and singular/plurals
    seen = set()
    candidate_queries = []
    
    seen.add(query.lower())
    candidate_queries.append((query, False, None))
    
    words = query.lower().split()
    
    def add_candidate(q_str, is_rel, rel_q):
        q_lower = q_str.lower()
        if q_lower not in seen:
            seen.add(q_lower)
            candidate_queries.append((q_str, is_rel, rel_q))
            
    # Suffix translation candidates (singular/plural corrections for common search terms)
    if "light" in words:
        alt = " ".join([w if w != "light" else "lights" for w in words])
        add_candidate(alt, True, "thousand lights")
    elif "lights" in words:
        alt = " ".join([w if w != "lights" else "light" for w in words])
        add_candidate(alt, True, "thousand light")
        
    # Clean noise words candidates
    noise_words = {'eagle', 'tower', 'camera', 'cctv', 'pin', 'marker', 'station', 'office', 'building', 'room', 'gate'}
    filtered = [w for w in words if w not in noise_words]
    cleaned = " ".join(filtered).strip()
    if cleaned:
        add_candidate(cleaned, True, cleaned)
        
        # Suffix translation on cleaned query
        cleaned_words = cleaned.split()
        if "light" in cleaned_words:
            alt_cleaned = " ".join([w if w != "light" else "lights" for w in cleaned_words])
            add_candidate(alt_cleaned, True, alt_cleaned)
        elif "lights" in cleaned_words:
            alt_cleaned = " ".join([w if w != "lights" else "light" for w in cleaned_words])
            add_candidate(alt_cleaned, True, alt_cleaned)

    # Perform sequential progressive searches, respecting Nominatim's 1 req/sec limit
    results = None
    is_relaxed = False
    relaxed_query = None
    
    for idx, (q, is_rel, rel_q) in enumerate(candidate_queries):
        if idx > 0:
            time.sleep(1.1)  # Enforce rate limit delay
            
        candidate_results = fetch_nominatim(q)
        if candidate_results is not None:
            if len(candidate_results) > 0:
                results = candidate_results
                is_relaxed = is_rel
                relaxed_query = rel_q
                break
        else:
            # If fetch failed due to network/service error, keep going or return None
            pass

    if results is None:
        return JSONResponse({"error": "Failed to connect to geocoding service"}, status_code=502)

    return {
        "results": results,
        "is_relaxed": is_relaxed,
        "relaxed_query": relaxed_query if is_relaxed else None
    }


# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    basic_health = {
        "status": "healthy",
        "active_streams": len(active_streams),
        "stream_ids": list(active_streams.keys())
    }

    if monitor_available:
        basic_health["monitoring"] = stream_monitor.get_summary_stats()

    return basic_health

# Stream health monitoring endpoints
@app.get("/api/stream_health/{stream_id}")
async def get_stream_health(stream_id: str):
    """Get detailed health information for a specific stream"""
    if not monitor_available:
        return JSONResponse({"error": "Stream monitoring not available"}, status_code=503)

    health_data = get_stream_diagnostics(stream_id)
    if "error" in health_data:
        return JSONResponse(health_data, status_code=404)

    return JSONResponse(health_data)

@app.get("/api/stream_health")
async def get_all_streams_health():
    """Get health information for all streams"""
    if not monitor_available:
        return JSONResponse({"error": "Stream monitoring not available"}, status_code=503)

    return JSONResponse({
        "streams": stream_monitor.get_all_streams_health(),
        "summary": stream_monitor.get_summary_stats()
    })

@app.get("/api/stream_diagnostics/{stream_id}")
async def get_detailed_stream_diagnostics(stream_id: str):
    """Get comprehensive diagnostics and recommendations for a stream"""
    if not monitor_available:
        return JSONResponse({"error": "Stream monitoring not available"}, status_code=503)

    diagnostics = get_stream_diagnostics(stream_id)
    if "error" in diagnostics:
        return JSONResponse(diagnostics, status_code=404)

    # Add current stream status from active_streams
    if stream_id in active_streams:
        stream = active_streams[stream_id]
        diagnostics["current_stream_info"] = {
            "is_running": stream.is_running,
            "rtsp_url": stream.rtsp_url,
            "has_capture": stream.cap is not None and stream.cap.isOpened() if stream.cap else False
        }

    return JSONResponse(diagnostics)

# Include the routers
app.include_router(analytics.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(camera_rules.router)
app.include_router(collections.router)
app.include_router(augment.router)
app.include_router(webrtc.router)
app.include_router(archive.router)
app.include_router(camera_settings.router)
app.include_router(dashboard_analytics.router)
app.include_router(appearance_search.router)
app.include_router(camera_zones.router)
# Face & gesture analytics routes
if _FACE_GESTURE_ROUTES:
    app.include_router(face_analytics.router)
    app.include_router(gesture_analytics.router)
    logger.info("Face & gesture analytics routes registered.")
else:
    logger.warning("Face & gesture analytics routes skipped (import error).")
# Vehicle monitoring routes
try:
    from routes import vehicle_monitoring
    app.include_router(vehicle_monitoring.router)

    @app.on_event("startup")
    async def _start_vehicle_monitors():
        try:
            await vehicle_monitoring.start_all_vehicle_monitors_on_startup()
        except Exception as e:
            logger.error(f"Vehicle monitoring startup failed: {e}")
except Exception as e:
    logger.warning(f"Vehicle monitoring routes not available: {e}")


# Setup Socket.IO for WebRTC signaling
webrtc_signaling.setup_socketio(app, '/socket.io')

@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """
    Delete a collection from camera_configuration.json.
    - Backs up the old file to camera_configuration.json.bak
    - Returns 200 OK on success, 404 if not found, 500 on error
    """
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            logger.error(f"Config file not found at: {CAMERA_JSON_PATH}")
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "camera_configuration.json not found"})

        # Read current config
        with open(CAMERA_JSON_PATH, "r") as f:
            try:
                camera_data = json.load(f)
            except Exception as e:
                logger.error(f"Error parsing camera_configuration.json: {e}")
                return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "Malformed camera_configuration.json"})

        if collection_name not in camera_data:
            logger.warning(f"Collection '{collection_name}' not found in configuration")
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": f"Collection '{collection_name}' not found in configuration"})

        # Remove the collection
        del camera_data[collection_name]

        # Backup the old file
        backup_path = CAMERA_JSON_PATH + ".bak"
        try:
            shutil.copy2(CAMERA_JSON_PATH, backup_path)
        except Exception as e:
            logger.error(f"Failed to backup camera_configuration.json: {e}")
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "Failed to backup configuration file"})

        # Write to a temp file first
        temp_path = CAMERA_JSON_PATH + ".tmp"
        try:
            with open(temp_path, "w") as f:
                json.dump(camera_data, f, indent=2)
            os.replace(temp_path, CAMERA_JSON_PATH)
        except Exception as e:
            logger.error(f"Failed to write updated configuration: {e}")
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "Failed to write updated configuration"})

        logger.info(f"Collection '{collection_name}' deleted successfully.")
        return {"message": f"Collection '{collection_name}' deleted successfully."}
    except Exception as e:
        logger.error(f"Unexpected error deleting collection: {e}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": str(e)})

if __name__ == "__main__":
    # Configure uvicorn to disable access logging to reduce noise
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        access_log=False,  # Disable access logging to prevent unwanted HTTP request logs
        log_level="info"   # Keep application logs at info level
    )