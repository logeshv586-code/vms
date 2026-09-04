"""Hardened Eagle VMS runtime entry point.

The original server implementation is preserved in ``main_legacy.py`` so all
existing APIs, WebRTC routes, archive functions and compatibility endpoints stay
available.  This entry point applies the production fixes around that server:

* stable camera IDs for every stream creation path;
* persisted per-camera 24/7 AI preferences;
* one event-dispatch path (PatternEngine owns deterministic dispatch);
* annotated pre/post-event evidence instead of a second raw RTSP recording;
* Layer-3 candidate pinning so slow validation does not lose the incident;
* English-only camera AI preference APIs.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from copy import deepcopy
from urllib.parse import urlsplit

import cv2
import uvicorn

try:
    import main_legacy as legacy
    from routes import camera_ai
    from services.camera_ai_preferences import get_camera_ai_preferences
    from services.event_evidence import event_evidence_service
except ImportError:  # Support package-style imports such as ``backend.main``.
    from backend import main_legacy as legacy
    from backend.routes import camera_ai
    from backend.services.camera_ai_preferences import get_camera_ai_preferences
    from backend.services.event_evidence import event_evidence_service

logger = logging.getLogger(__name__)


def _infer_stream_id(rtsp_url: str) -> str | None:
    """Resolve a configured RTSP URL back to the canonical collection_IP ID."""
    try:
        with open(legacy.CAMERA_JSON_PATH, "r", encoding="utf-8") as handle:
            camera_data = json.load(handle)
    except Exception:
        return None

    if not isinstance(camera_data, dict):
        return None

    # Exact URL match is authoritative.
    for collection_name, cameras in camera_data.items():
        if not isinstance(cameras, dict):
            continue
        for camera_ip, configured_url in cameras.items():
            if str(configured_url) == str(rtsp_url):
                return f"{collection_name}_{camera_ip}"

    # Legacy call sites can add harmless transport/query details.  Fall back to
    # the RTSP hostname without ever logging credentials.
    try:
        hostname = urlsplit(str(rtsp_url)).hostname
    except Exception:
        hostname = None
    if hostname:
        for collection_name, cameras in camera_data.items():
            if isinstance(cameras, dict) and hostname in cameras:
                return f"{collection_name}_{hostname}"
    return None


class HardenedRTSPStream(legacy.RTSPStream):
    """RTSP stream with stable identity and persisted 24/7 AI monitoring."""

    def __init__(self, rtsp_url: str, stream_id: str = None):
        resolved_stream_id = stream_id or _infer_stream_id(rtsp_url)
        if not resolved_stream_id:
            raise ValueError("A stable stream_id is required for an unconfigured RTSP source")
        super().__init__(rtsp_url, resolved_stream_id)
        preferences = get_camera_ai_preferences(self.stream_id)
        self.detection_enabled = bool(preferences.get("enabled", True)) and legacy.pattern_engine.has_active_rules(self.stream_id)

    def enable_detection(self):
        """Enable the live view flag; persisted camera preferences remain authoritative."""
        with self.lock:
            self.detection_enabled = True
        logger.info("AI view enabled for stream: %s", self.stream_id)

    def disable_detection(self):
        """Do not stop persisted 24/7 monitoring when a UI viewer disconnects."""
        preferences = get_camera_ai_preferences(self.stream_id)
        if bool(preferences.get("enabled", True)) and legacy.pattern_engine.has_active_rules(self.stream_id):
            with self.lock:
                self.detection_enabled = True
            logger.debug("Viewer detached; 24/7 AI monitoring continues for %s", self.stream_id)
            return
        with self.lock:
            self.detection_enabled = False
            self.last_annotated_frame = None
        legacy.pattern_engine.clear_source_data(self.stream_id)
        event_evidence_service.clear_stream(self.stream_id)
        logger.info("AI monitoring disabled for stream: %s", self.stream_id)

    def stop(self):
        try:
            super().stop()
        finally:
            event_evidence_service.clear_stream(self.stream_id)
            try:
                legacy.pattern_engine.clear_source_data(self.stream_id)
            except Exception:
                pass

    def _run_deep_reasoning(self, frame, event_context, stream_id=None):
        """Validate one candidate and preserve evidence around the original trigger."""
        source_id = stream_id or self.stream_id
        try:
            logger.info("Triggering Layer 3 Reasoning for %s - Rule ID: %s", source_id, event_context.get("id"))
            reasoning_result = legacy.gemma_engine.analyze_behavior(frame, event_context)
            if reasoning_result and "error" not in reasoning_result:
                event_context["deep_reasoning"] = reasoning_result
                with self.lock:
                    for index, existing in enumerate(self.last_events):
                        if existing.get("id") == event_context.get("id"):
                            self.last_events[index] = event_context
                            break
                if reasoning_result.get("event_validated"):
                    legacy.pattern_engine.trigger_alert_api(source_id, event_context)
                else:
                    event_evidence_service.discard_candidate(source_id, event_context)
            else:
                event_evidence_service.discard_candidate(source_id, event_context)
        except Exception as exc:
            event_evidence_service.discard_candidate(source_id, event_context)
            logger.error("Error in deep reasoning thread for %s: %s", source_id, exc)

    def _ai_processing_loop(self):
        """Run rule-driven camera AI continuously, independent of UI visibility."""
        logger.info("24/7 AI processing thread started for %s", self.stream_id)
        last_processed_time = 0.0

        while self.is_running:
            if not self.frame_ready_event.wait(timeout=1.0):
                continue
            self.frame_ready_event.clear()

            active_rule_ids = legacy.pattern_engine.get_active_rules_for_source(self.stream_id)
            preferences = get_camera_ai_preferences(self.stream_id)
            monitoring_enabled = bool(preferences.get("enabled", True)) and bool(active_rule_ids)
            with self.lock:
                self.detection_enabled = monitoring_enabled

            if not monitoring_enabled:
                with self.lock:
                    self.last_detections = {"detections": [], "counts": {}, "frame_width": 640, "frame_height": 480}
                    self.last_annotated_frame = None
                time.sleep(0.25)
                continue

            ai_fps = max(0.5, min(30.0, float(preferences.get("ai_fps", 4.0) or 4.0)))
            current_time = time.time()
            if current_time - last_processed_time < (1.0 / ai_fps):
                continue
            last_processed_time = current_time

            with self.lock:
                frame_to_process = self.last_frame.copy() if self.last_frame is not None else None
            if frame_to_process is None:
                continue

            try:
                annotated_frame, detections_data = legacy.cascaded_ai_service.process_frame(
                    frame_to_process,
                    stream_id=self.stream_id,
                )
                height, width = frame_to_process.shape[:2]
                detections_data["frame_width"] = width
                detections_data["frame_height"] = height
                detections_data["processed_fps"] = ai_fps

                # PatternEngine enriches each detection with zone membership.
                # Deterministic events are persisted inside PatternEngine only.
                events = legacy.pattern_engine.process_detections(self.stream_id, detections_data)

                # Register immediately after PatternEngine so the exact trigger
                # frame is captured with bbox/centre/track and zone metadata.
                # If a deterministic event was just persisted, register_frame
                # appends this frame to its already-created proof capture.
                event_evidence_service.register_frame(self.stream_id, annotated_frame, detections_data)

                # PatternEngine already persists deterministic (non-L3) events.
                # Only Layer-3 candidates are handled here; this removes the old
                # second trigger_alert_api call for deterministic events.
                current_time = time.time()
                for event in events:
                    if not event.get("trigger_layer3"):
                        continue
                    if current_time - self.last_reasoning_time <= 30:
                        logger.debug("Throttling Layer 3 reasoning for %s (%s)", self.stream_id, event.get("type"))
                        continue
                    self.last_reasoning_time = current_time
                    event_evidence_service.pin_candidate(self.stream_id, event)
                    threading.Thread(
                        target=self._run_deep_reasoning,
                        args=(frame_to_process.copy(), event, self.stream_id),
                        daemon=True,
                        name=f"VMS-L3-{self.stream_id}",
                    ).start()

                self._run_sub_detections(frame_to_process, current_time, active_rule_ids)

                with self.lock:
                    self.last_annotated_frame = annotated_frame
                    self.last_detections = detections_data
                    self.last_events = events
                    try:
                        ok, buffer = cv2.imencode(".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                        if ok:
                            self.last_jpeg_annotated = buffer.tobytes()
                    except Exception:
                        pass
            except Exception as exc:
                logger.error("Error in 24/7 AI processing loop for %s: %s", self.stream_id, exc)
                time.sleep(0.1)


# Every endpoint and startup handler in main_legacy resolves this module-global
# class at call time, so this fixes auto-start, restart, collection-start and
# legacy start paths without removing any existing API.
legacy.RTSPStream = HardenedRTSPStream


# Replace PatternEngine's old raw-RTSP proof callback while retaining its event
# database, deduplication and alert logic.  Thread-local context lets the callback
# receive the exact event object without changing the established method API.
_evidence_context = threading.local()
_original_trigger_alert_api = legacy.pattern_engine.trigger_alert_api


def _trigger_alert_with_annotated_evidence(source_id: str, event: dict):
    _evidence_context.event = deepcopy(event) if isinstance(event, dict) else {}
    try:
        return _original_trigger_alert_api(source_id, event)
    finally:
        try:
            del _evidence_context.event
        except AttributeError:
            pass


def _start_annotated_proof(event_id: str, source_id: str, update_event_record):
    del update_event_record  # EventEvidenceService updates the same SQLite record directly.
    event = getattr(_evidence_context, "event", {})
    event_evidence_service.start_event(event_id, source_id, event)


legacy.pattern_engine.trigger_alert_api = _trigger_alert_with_annotated_evidence
legacy.pattern_engine._start_proof_recording = _start_annotated_proof


# Register the new English-only camera AI preference API alongside every legacy
# route already mounted on the application.
legacy.app.include_router(camera_ai.router)


@legacy.app.get("/api/ai/evidence/status")
async def get_evidence_status():
    return {"success": True, "data": event_evidence_service.get_status()}


@legacy.app.get("/api/ai/detection-schema")
async def get_detection_schema():
    return {
        "success": True,
        "schema": "vms-detection-1",
        "canonical_fields": [
            "track_id",
            "class_name",
            "class_id",
            "confidence",
            "bbox",
            "centroid",
            "norm_bbox",
            "norm_centroid",
            "timestamp",
        ],
    }


# Re-export the application and common runtime objects for existing imports.
app = legacy.app
active_streams = legacy.active_streams
get_stream_by_id = legacy.get_stream_by_id


def __getattr__(name):
    """Forward legacy module attributes so existing imports remain compatible."""
    return getattr(legacy, name)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        access_log=False,
        log_level="info",
    )
