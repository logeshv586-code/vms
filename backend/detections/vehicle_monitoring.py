"""
Vehicle Monitoring Module - Comprehensive Vehicle Analytics Detector
====================================================================

Provides multi-faceted vehicle intelligence:
    • Detection & classification  – car, truck, bus, motorcycle, bicycle
    • Speed estimation            – frame-to-frame centroid displacement
    • Wrong-way detection         – travel direction vs. configured flow vector
    • Parking violation           – stationary duration exceeding threshold
    • License plate ROI extraction– bounding-box crop of plate region

Kaggle Dataset Sourcing Suggestions:
    - UA-DETRAC Vehicle Dataset: https://www.kaggle.com/datasets/dtrnhx2510/ua-detrac-dataset
    - KITTI Dataset:             https://www.kaggle.com/datasets/klemenko/kitti-dataset
    - Indian Vehicle Dataset:    https://www.kaggle.com/datasets/dataclusterlabs/indian-vehicle-dataset
    - License Plate Dataset:     https://www.kaggle.com/datasets/andrewmvd/car-plate-detection
"""

import logging
import math
import time
from collections import defaultdict, deque
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)

# ── Vehicle class IDs in COCO ───────────────────────────────────────────────
VEHICLE_COCO_IDS: Dict[int, str] = {
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
VEHICLE_LABELS = set(VEHICLE_COCO_IDS.values())


class VehicleMonitoringDetector(BaseDetector):
    """
    Comprehensive vehicle analytic engine for surveillance cameras.

    Beyond simple detection this module provides:
    - **Classification** of five vehicle types using YOLOv8 or OpenCV fallback.
    - **Speed estimation** via inter-frame centroid displacement converted
      to approximate km/h using a configurable pixels-per-metre calibration.
    - **Wrong-way detection** comparing travel vectors against a configured
      allowed-flow direction.
    - **Parking violation** flagging when a vehicle remains stationary longer
      than a configurable timeout.
    - **License plate ROI** extraction using a proportional crop of the
      lower portion of each detected vehicle bounding box.

    Config keys:
        model_path             (str)  : YOLO weights path. Default ``"yolov8n.pt"``
        pixels_per_metre       (float): Calibration factor. Default ``8.0``
        fps                    (float): Stream FPS for speed calc. Default ``25.0``
        speed_limit_kmh        (float): Alert threshold. Default ``60.0``
        parking_timeout_sec    (float): Seconds before parking alert. Default ``300.0``
        allowed_flow_angle_deg (float): Expected traffic direction (0=right). Default ``0.0``
        flow_angle_tolerance   (float): ± degrees tolerance. Default ``45.0``
        track_history_len      (int)  : Centroid history per track. Default ``30``
        plate_crop_ratio       (float): Bottom % of vehicle bbox for plate. Default ``0.35``

    Kaggle Datasets:
        - UA-DETRAC Vehicle Dataset
        - KITTI Dataset
    """

    # ── Lifecycle ───────────────────────────────────────────────────────────
    def __init__(self, config: Dict[str, Any] = None):
        # Tracking state – keyed by a simple track id
        self._tracks: Dict[int, deque] = defaultdict(lambda: deque(maxlen=30))
        self._stationary_timers: Dict[int, float] = {}
        self._next_track_id: int = 0
        self._prev_centroids: List[Tuple[int, int, int]] = []  # (cx, cy, track_id)
        super().__init__("vehicle_monitoring", config)

    def load_model(self) -> None:
        """Load YOLOv8 for vehicle detection; gracefully fall back to OpenCV."""
        self.pixels_per_metre = self.config.get("pixels_per_metre", 8.0)
        self.fps = self.config.get("fps", 25.0)
        self.speed_limit = self.config.get("speed_limit_kmh", 60.0)
        self.parking_timeout = self.config.get("parking_timeout_sec", 300.0)
        self.allowed_flow_angle = self.config.get("allowed_flow_angle_deg", 0.0)
        self.flow_tolerance = self.config.get("flow_angle_tolerance", 45.0)
        self.track_history_len = self.config.get("track_history_len", 30)
        self.plate_crop_ratio = self.config.get("plate_crop_ratio", 0.35)

        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            logger.info("YOLOv8 loaded for VehicleMonitoringDetector (%s).", model_path)
        except Exception as exc:
            logger.warning(
                "YOLOv8 unavailable (%s). VehicleMonitoringDetector will use "
                "background-subtraction fallback.", exc
            )
            self.model = None
            self._bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=500, varThreshold=40, detectShadows=True
            )

    # ── Main Entry ──────────────────────────────────────────────────────────
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse a frame for vehicles and compute analytics.

        Args:
            frame:      BGR numpy array.
            **kwargs:
                stream_id   (str)  : Camera identifier.
                timestamp   (float): Epoch time for parking timer.
                roi         (list) : [x1,y1,x2,y2] optional crop.

        Returns:
            Dict with triggered, detections, metadata (speed_violations,
            wrong_way_vehicles, parking_violations, plate_regions), event_type.
        """
        if not self.is_enabled:
            return self._empty_result()

        ts_start = time.perf_counter()
        timestamp = kwargs.get("timestamp", time.time())

        # ── Step 1: detect vehicles ─────────────────────────────────────────
        if self.model is not None:
            raw_dets = self._detect_yolo(frame)
        else:
            raw_dets = self._detect_fallback(frame)

        # ── Step 2: track & compute analytics ───────────────────────────────
        current_centroids: List[Tuple[int, int, int]] = []
        speed_violations: List[Dict] = []
        wrong_way_vehicles: List[Dict] = []
        parking_violations: List[Dict] = []
        plate_regions: List[Dict] = []

        for det in raw_dets:
            x1, y1, x2, y2 = det["bbox"]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

            # Simple nearest-neighbour track association
            track_id = self._associate_track(cx, cy)
            self._tracks[track_id].append((cx, cy, timestamp))
            current_centroids.append((cx, cy, track_id))
            det["track_id"] = track_id

            # Speed estimation
            speed_kmh = self._estimate_speed(track_id)
            det["speed_kmh"] = speed_kmh
            if speed_kmh > self.speed_limit:
                speed_violations.append({
                    "track_id": track_id,
                    "speed_kmh": speed_kmh,
                    "bbox": det["bbox"],
                    "label": det["label"],
                })

            # Wrong-way detection
            if self._is_wrong_way(track_id):
                wrong_way_vehicles.append({
                    "track_id": track_id,
                    "bbox": det["bbox"],
                    "label": det["label"],
                })

            # Parking violation check
            if self._is_parking_violation(track_id, timestamp):
                parking_violations.append({
                    "track_id": track_id,
                    "bbox": det["bbox"],
                    "stationary_sec": round(timestamp - self._stationary_timers.get(track_id, timestamp), 1),
                    "label": det["label"],
                })

            # License plate ROI
            plate_roi = self._extract_plate_roi(frame, det["bbox"])
            if plate_roi is not None:
                plate_regions.append({
                    "track_id": track_id,
                    "plate_bbox": plate_roi,
                    "vehicle_bbox": det["bbox"],
                })

        self._prev_centroids = current_centroids

        # Classification summary
        class_counts: Dict[str, int] = defaultdict(int)
        for d in raw_dets:
            class_counts[d["label"]] += 1

        triggered = (
            len(raw_dets) > 0
            or len(speed_violations) > 0
            or len(wrong_way_vehicles) > 0
            or len(parking_violations) > 0
        )

        elapsed_ms = (time.perf_counter() - ts_start) * 1000

        return {
            "triggered": triggered,
            "detections": raw_dets,
            "metadata": {
                "total_vehicles": len(raw_dets),
                "classification_counts": dict(class_counts),
                "speed_violations": speed_violations,
                "wrong_way_vehicles": wrong_way_vehicles,
                "parking_violations": parking_violations,
                "plate_regions": plate_regions,
                "inference_time_ms": round(elapsed_ms, 2),
                "model_backend": "yolov8" if self.model else "opencv_bg_subtraction",
                "stream_id": kwargs.get("stream_id"),
            },
            "event_type": self.name,
        }

    # ── YOLOv8 Detection ───────────────────────────────────────────────────
    def _detect_yolo(self, frame: np.ndarray) -> List[Dict]:
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        detections: List[Dict] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = self.model.names.get(cls_id, "")
                if label not in VEHICLE_LABELS:
                    continue
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                detections.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(confidence, 4),
                    "label": label,
                    "class_id": cls_id,
                })
        return detections

    # ── OpenCV Fallback (Background Subtraction) ───────────────────────────
    def _detect_fallback(self, frame: np.ndarray) -> List[Dict]:
        """
        Detects moving vehicle-shaped blobs via MOG2 background subtraction.
        Uses aspect-ratio heuristics to filter non-vehicle contours.
        """
        fg_mask = self._bg_subtractor.apply(frame)

        # Remove shadows (shadow pixels = 127 in MOG2)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = frame.shape[:2]
        min_area = (h * w) * 0.005
        detections: List[Dict] = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / max(bh, 1)

            # Vehicle heuristic: wider than tall, reasonable size
            if aspect < 0.6:
                label = "motorcycle"
            elif aspect < 1.0:
                label = "car"
            elif aspect < 2.0:
                label = "car"
            else:
                label = "truck"

            confidence = min(0.3 + (area / (h * w)) * 2, 0.80)
            detections.append({
                "bbox": [x, y, x + bw, y + bh],
                "confidence": round(confidence, 4),
                "label": label,
                "class_id": -1,
            })
        return detections

    # ── Tracking Helpers ────────────────────────────────────────────────────
    def _associate_track(self, cx: int, cy: int, max_dist: int = 80) -> int:
        """
        Nearest-neighbour centroid association. If no existing track is close
        enough, a new track id is assigned.
        """
        best_id = -1
        best_dist = max_dist
        for px, py, tid in self._prev_centroids:
            dist = math.hypot(cx - px, cy - py)
            if dist < best_dist:
                best_dist = dist
                best_id = tid
        if best_id < 0:
            best_id = self._next_track_id
            self._next_track_id += 1
        return best_id

    def _estimate_speed(self, track_id: int) -> float:
        """
        Estimate speed in km/h from centroid displacement across recent frames.
        Uses rolling window for smoothing.
        """
        history = self._tracks.get(track_id)
        if history is None or len(history) < 2:
            return 0.0

        # Average displacement over last N pairs
        displacements: List[float] = []
        items = list(history)
        for i in range(1, min(len(items), 6)):
            dx = items[-i][0] - items[-i - 1][0] if len(items) > i else 0
            dy = items[-i][1] - items[-i - 1][1] if len(items) > i else 0
            displacements.append(math.hypot(dx, dy))

        avg_disp_px = np.mean(displacements) if displacements else 0.0
        metres_per_frame = avg_disp_px / self.pixels_per_metre
        metres_per_sec = metres_per_frame * self.fps
        kmh = metres_per_sec * 3.6
        return round(kmh, 1)

    def _is_wrong_way(self, track_id: int) -> bool:
        """
        Compare recent travel direction against allowed flow angle.
        Returns True when the vehicle is heading in the opposite direction.
        """
        history = self._tracks.get(track_id)
        if history is None or len(history) < 4:
            return False

        items = list(history)
        dx = items[-1][0] - items[-4][0]
        dy = items[-1][1] - items[-4][1]
        if abs(dx) < 3 and abs(dy) < 3:
            return False  # essentially stationary

        travel_angle = math.degrees(math.atan2(-dy, dx)) % 360
        diff = abs(travel_angle - self.allowed_flow_angle) % 360
        if diff > 180:
            diff = 360 - diff
        return diff > (180 - self.flow_tolerance)

    def _is_parking_violation(self, track_id: int, timestamp: float) -> bool:
        """
        Flag vehicles that have been essentially stationary longer than
        ``parking_timeout_sec``.
        """
        history = self._tracks.get(track_id)
        if history is None or len(history) < 5:
            return False

        items = list(history)
        total_disp = sum(
            math.hypot(items[i][0] - items[i - 1][0], items[i][1] - items[i - 1][1])
            for i in range(1, len(items))
        )
        avg_disp = total_disp / max(len(items) - 1, 1)

        if avg_disp < 3.0:
            # Vehicle is stationary
            if track_id not in self._stationary_timers:
                self._stationary_timers[track_id] = timestamp
            elapsed = timestamp - self._stationary_timers[track_id]
            return elapsed >= self.parking_timeout
        else:
            # Vehicle moved – reset timer
            self._stationary_timers.pop(track_id, None)
            return False

    def _extract_plate_roi(
        self, frame: np.ndarray, bbox: List[int]
    ) -> Optional[List[int]]:
        """
        Extract the estimated license-plate sub-region from the bottom portion
        of the vehicle bounding box.
        """
        x1, y1, x2, y2 = bbox
        bh = y2 - y1
        bw = x2 - x1
        if bh < 20 or bw < 30:
            return None  # too small to contain a plate

        plate_y1 = int(y2 - bh * self.plate_crop_ratio)
        plate_x1 = int(x1 + bw * 0.15)
        plate_x2 = int(x2 - bw * 0.15)
        return [plate_x1, plate_y1, plate_x2, y2]

    # ── Utility ─────────────────────────────────────────────────────────────
    def _empty_result(self) -> Dict[str, Any]:
        return {
            "triggered": False,
            "detections": [],
            "metadata": {},
            "event_type": self.name,
        }
