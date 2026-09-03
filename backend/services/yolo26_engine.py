import cv2
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import numpy as np
import torch
from ultralytics import YOLO

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
CAMERA_ZONES_PATH = os.path.join(DATA_DIR, "camera_zones.json")
logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _normalize_camera_id(value: Optional[str]) -> str:
    if not value:
        return "default"
    return re.sub(r"[^a-z0-9]", "", str(value).lower()) or "default"


@dataclass
class _StreamState:
    """State that must never leak between unrelated cameras."""

    model: Any
    frame_count: int = 0
    last_annotated: Optional[np.ndarray] = None
    last_metadata: Dict[str, Any] = field(default_factory=lambda: {"detections": [], "counts": {}})
    prev_gray: Optional[np.ndarray] = None
    last_seen_monotonic: float = field(default_factory=time.monotonic)
    lock: threading.RLock = field(default_factory=threading.RLock)


class YOLO26Engine:
    """Realtime YOLO + ByteTrack engine with camera-isolated tracker state."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(YOLO26Engine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.model_path = os.getenv("VMS_YOLO_MODEL", "yolo26n.pt")
        self.device = self._resolve_device()
        self.confidence = max(0.01, min(0.99, _env_float("VMS_YOLO_CONF", 0.25)))
        self.iou = max(0.01, min(0.99, _env_float("VMS_YOLO_IOU", 0.55)))
        self.tracker = os.getenv("VMS_YOLO_TRACKER", "bytetrack.yaml")
        self.inactive_stream_ttl = max(30, _env_int("VMS_YOLO_STREAM_TTL_SECONDS", 300))
        self.cleanup_interval = max(10, _env_int("VMS_YOLO_CLEANUP_INTERVAL_SECONDS", 30))
        self._last_cleanup = 0.0

        default_skip = 0 if self.device != "cpu" else 1
        self.skip_n_frames = max(0, _env_int("VMS_YOLO_SKIP_FRAMES", default_skip))

        self.zones_config: Dict[str, Any] = {}
        self._zones_mtime: Optional[float] = None
        self._streams: Dict[str, _StreamState] = {}
        self._streams_lock = threading.RLock()
        self._default_model_claimed = False

        try:
            self.model = self._create_model()
            self._load_zones(force=True)
            self._initialized = True
            logger.info(
                "YOLO initialized: model=%s device=%s conf=%.2f iou=%.2f skip=%s ttl=%ss",
                self.model_path,
                self.device,
                self.confidence,
                self.iou,
                self.skip_n_frames,
                self.inactive_stream_ttl,
            )
        except Exception as exc:
            logger.exception("Failed to load YOLO model: %s", exc)
            raise

    @staticmethod
    def _resolve_device() -> str:
        configured = os.getenv("VMS_YOLO_DEVICE", "").strip()
        if configured:
            return configured
        if torch.cuda.is_available():
            return "cuda:0"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _create_model(self):
        model = YOLO(self.model_path)
        model.to(self.device)
        return model

    def _cleanup_inactive_streams(self, keep_key: Optional[str] = None) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < self.cleanup_interval:
            return
        self._last_cleanup = now
        stale = []
        with self._streams_lock:
            for key, state in self._streams.items():
                if key == keep_key:
                    continue
                if now - state.last_seen_monotonic > self.inactive_stream_ttl:
                    stale.append(key)
        for key in stale:
            self.reset_stream(key, normalized=True)

    def _get_stream_state(self, stream_id: Optional[str]) -> _StreamState:
        key = _normalize_camera_id(stream_id)
        self._cleanup_inactive_streams(keep_key=key)
        with self._streams_lock:
            state = self._streams.get(key)
            if state is not None:
                state.last_seen_monotonic = time.monotonic()
                return state

            if not self._default_model_claimed:
                model = self.model
                self._default_model_claimed = True
            else:
                # Ultralytics persist=True retains predictor/tracker state; use a
                # distinct instance for every unrelated camera.
                model = self._create_model()
            state = _StreamState(model=model)
            self._streams[key] = state
            logger.info("Created isolated YOLO tracker for stream=%s", key)
            return state

    def _load_zones(self, force: bool = False):
        try:
            if not os.path.exists(CAMERA_ZONES_PATH):
                self.zones_config = {}
                self._zones_mtime = None
                return
            mtime = os.path.getmtime(CAMERA_ZONES_PATH)
            if not force and self._zones_mtime == mtime:
                return
            with open(CAMERA_ZONES_PATH, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            self.zones_config = raw if isinstance(raw, dict) else {}
            self._zones_mtime = mtime
        except Exception as exc:
            logger.error("Error loading zones in YOLO engine: %s", exc)

    def reload_config(self):
        self._load_zones(force=True)
        logger.info("YOLO configuration reloaded")

    def _camera_zones(self, stream_id: Optional[str]):
        if not stream_id:
            return []
        if stream_id in self.zones_config:
            value = self.zones_config.get(stream_id, {})
            return value.get("zones", []) if isinstance(value, dict) else []
        wanted = _normalize_camera_id(stream_id)
        for camera_id, value in self.zones_config.items():
            if _normalize_camera_id(camera_id) == wanted and isinstance(value, dict):
                return value.get("zones", [])
        return []

    def _draw_zones(self, image: np.ndarray, stream_id: Optional[str]):
        height, width = image.shape[:2]
        for zone in self._camera_zones(stream_id):
            if not isinstance(zone, dict):
                continue
            color = (0, 255, 255)
            name = str(zone.get("name", "Zone"))
            if zone.get("type") == "circle":
                center = zone.get("center", [0.5, 0.5])
                radius = float(zone.get("radius", 0.1))
                if len(center) < 2:
                    continue
                cx, cy = int(float(center[0]) * width), int(float(center[1]) * height)
                radius_px = max(1, int(radius * width))
                cv2.circle(image, (cx, cy), radius_px, color, 2)
                cv2.putText(image, name, (max(0, cx - radius_px), max(15, cy - radius_px - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                continue
            polygon = zone.get("polygon", [])
            if len(polygon) < 3:
                continue
            points = np.array(
                [[int(float(point[0]) * width), int(float(point[1]) * height)] for point in polygon],
                dtype=np.int32,
            ).reshape((-1, 1, 2))
            cv2.polylines(image, [points], isClosed=True, color=color, thickness=2)
            cv2.putText(image, name, (int(points[0][0][0]), max(15, int(points[0][0][1]) - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    @staticmethod
    def _draw_cached_detections(image: np.ndarray, detections):
        for detection in detections:
            bbox = detection.get("bbox", [])
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = map(int, bbox)
            label = str(detection.get("class", "object"))
            track_id = detection.get("id")
            color = (0, 212, 255) if label == "person" else (0, 255, 0)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            text = f"{label} {track_id}" if track_id is not None else label
            cv2.putText(image, text, (x1, max(15, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    def process_frame(self, frame: np.ndarray, persist: bool = True, stream_id: str = None):
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return frame, {"detections": [], "counts": {}, "error": "invalid_frame"}

        self._load_zones()
        state = self._get_stream_state(stream_id)
        state.last_seen_monotonic = time.monotonic()
        height, width = frame.shape[:2]

        try:
            with state.lock:
                state.frame_count += 1
                if persist and self.skip_n_frames > 0 and state.frame_count % (self.skip_n_frames + 1) != 0:
                    display_frame = frame.copy()
                    self._draw_cached_detections(display_frame, state.last_metadata.get("detections", []))
                    self._draw_zones(display_frame, stream_id)
                    cached = dict(state.last_metadata)
                    cached["skipped"] = True
                    cached["stream_id"] = stream_id
                    cached["frame_width"] = width
                    cached["frame_height"] = height
                    return display_frame, cached

                results = state.model.track(
                    frame,
                    persist=persist,
                    tracker=self.tracker,
                    verbose=False,
                    conf=self.confidence,
                    iou=self.iou,
                    device=self.device,
                )
                result = results[0]
                annotated_frame = frame.copy()
                self._draw_zones(annotated_frame, stream_id)

                detections = []
                counts: Dict[str, int] = {}
                boxes = result.boxes
                if boxes is not None:
                    names = state.model.names
                    for box in boxes:
                        track_id = int(box.id[0]) if box.id is not None else None
                        class_id = int(box.cls[0])
                        label = str(names[class_id])
                        confidence = float(box.conf[0])
                        raw_box = box.xyxy[0].tolist()
                        x1 = max(0.0, min(float(width), float(raw_box[0])))
                        y1 = max(0.0, min(float(height), float(raw_box[1])))
                        x2 = max(0.0, min(float(width), float(raw_box[2])))
                        y2 = max(0.0, min(float(height), float(raw_box[3])))
                        if x2 <= x1 or y2 <= y1:
                            continue
                        cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                        color = (0, 212, 255) if label == "person" else (0, 255, 0)
                        ix1, iy1, ix2, iy2 = map(int, (x1, y1, x2, y2))
                        cv2.rectangle(annotated_frame, (ix1, iy1), (ix2, iy2), color, 2)
                        text = f"{label} {track_id}" if track_id is not None else label
                        cv2.putText(annotated_frame, text, (ix1, max(15, iy1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                        detections.append(
                            {
                                "id": track_id,
                                "class": label,
                                "class_id": class_id,
                                "confidence": confidence,
                                "bbox": [x1, y1, x2, y2],
                                "norm_bbox": [x1 / width, y1 / height, x2 / width, y2 / height],
                                "centroid": [cx, cy],
                                "norm_centroid": [cx / width, cy / height],
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                        counts[label] = counts.get(label, 0) + 1

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
                luminance = float(np.mean(gray))
                stdev = float(np.std(gray))
                motion_score = 0.0
                if state.prev_gray is not None and state.prev_gray.shape == gray.shape:
                    motion_score = float(np.mean(cv2.absdiff(gray, state.prev_gray)))
                state.prev_gray = gray
                state.last_seen_monotonic = time.monotonic()
                state.last_annotated = annotated_frame
                state.last_metadata = {
                    "detections": detections,
                    "counts": counts,
                    "motion_score": motion_score,
                    "blur_score": blur_score,
                    "luminance": luminance,
                    "stdev": stdev,
                    "stream_id": stream_id,
                    "frame_width": width,
                    "frame_height": height,
                    "device": self.device,
                    "model": self.model_path,
                    "skipped": False,
                }
                return annotated_frame, dict(state.last_metadata)
        except Exception as exc:
            logger.exception("Error processing frame in YOLO stream=%s: %s", stream_id, exc)
            return frame, {
                "detections": [],
                "counts": {},
                "motion_score": 0.0,
                "blur_score": 0.0,
                "stream_id": stream_id,
                "frame_width": width,
                "frame_height": height,
                "error": str(exc),
            }

    def reset_stream(self, stream_id: Optional[str], normalized: bool = False):
        """Drop tracker/model temporal state for a disconnected or stale camera."""
        key = str(stream_id) if normalized else _normalize_camera_id(stream_id)
        with self._streams_lock:
            removed = self._streams.pop(key, None)
            if removed is not None and removed.model is self.model:
                self._default_model_claimed = False
        if removed is not None:
            removed.prev_gray = None
            removed.last_annotated = None
            removed.last_metadata = {"detections": [], "counts": {}}
            logger.info("Reset YOLO state for stream=%s", key)
            if self.device.startswith("cuda") and removed.model is not self.model:
                try:
                    del removed.model
                    torch.cuda.empty_cache()
                except Exception:
                    pass

    def get_status(self) -> Dict[str, Any]:
        self._cleanup_inactive_streams()
        with self._streams_lock:
            streams = len(self._streams)
        return {
            "available": True,
            "model": self.model_path,
            "device": self.device,
            "confidence": self.confidence,
            "iou": self.iou,
            "tracker": self.tracker,
            "active_stream_states": streams,
            "inactive_stream_ttl_seconds": self.inactive_stream_ttl,
        }

    def get_annotated_frame_only(self, frame: np.ndarray, stream_id: str = None):
        annotated_frame, _ = self.process_frame(frame, stream_id=stream_id)
        return annotated_frame


yolo26_engine = YOLO26Engine()
