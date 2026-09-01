import logging
import time
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class EavesdroppingDetector(BaseDetector):
    """
    Detects suspicious eavesdropping behaviour — a person lingering near
    doors, windows, or thin walls and/or leaning their head toward a
    neighbouring room or conversation.

    Detection Strategy:
        1. Person Detection — Uses YOLO to locate all persons in the
           frame.
        2. Proximity to Interest Zones — User-configurable polygonal
           zones (doors, windows, walls) are defined in the config.
           A person whose bounding-box centroid falls within the
           proximity margin of an interest zone is flagged.
        3. Dwell-Time Tracking — A per-person timer accumulates how
           long an individual remains inside the proximity margin.
           Alerts fire only after a configurable dwell threshold
           (default 10 s) to avoid false positives from passers-by.
        4. Head Lean Estimation — The upper portion of the person
           bounding box is analysed for asymmetric posture (lean
           angle).  A pronounced lean toward the interest zone raises
           the confidence score.

    Kaggle Dataset Sourcing Suggestion:
        DCSASS Dataset (Suspicious Activity Surveillance)
        https://www.kaggle.com/datasets/mateohervas/dcsass-dataset
    """

    def __init__(self, config: Dict[str, Any] = None):
        # Track dwell times keyed by a lightweight person ID (centroid bucket)
        self._dwell_tracker: Dict[str, Dict[str, Any]] = {}
        super().__init__("eavesdropping", config)

    # ------------------------------------------------------------------ #
    #  Model loading
    # ------------------------------------------------------------------ #
    def load_model(self) -> None:
        """
        Load YOLO model for person detection and parse zone
        configuration.
        """
        # YOLO person detector
        model_path = self.config.get("model_path", "yolov8n.pt")
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            logger.info("YOLOv8 loaded for EavesdroppingDetector (%s).", model_path)
        except Exception as e:
            logger.error("Failed to load YOLO model: %s", e)
            self.model = None

        # Interest zones — list of dicts with 'name' and 'polygon' keys.
        # polygon: [[x1,y1],[x2,y2],...] in pixel coords.
        # If not supplied, the detector will auto-generate edge zones
        # covering the perimeter strips of the frame.
        self._interest_zones: List[Dict[str, Any]] = self.config.get("interest_zones", [])
        self._proximity_margin = self.config.get("proximity_margin_px", 80)
        self._dwell_threshold_sec = self.config.get("dwell_threshold_sec", 10.0)
        self._lean_angle_threshold = self.config.get("lean_angle_threshold", 15.0)
        self._tracker_expiry_sec = self.config.get("tracker_expiry_sec", 5.0)
        self._centroid_bucket_size = self.config.get("centroid_bucket_size", 40)

        logger.info(
            "EavesdroppingDetector configured — zones=%d, proximity=%dpx, "
            "dwell=%.1fs, lean_angle=%.1f°",
            len(self._interest_zones),
            self._proximity_margin,
            self._dwell_threshold_sec,
            self._lean_angle_threshold,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
    def _auto_edge_zones(self, w: int, h: int) -> List[Dict[str, Any]]:
        """
        Generate default interest zones along the four frame edges.
        These approximate door/wall positions when explicit zones are
        not configured.
        """
        m = self._proximity_margin
        return [
            {"name": "left_wall",   "polygon": np.array([[0, 0], [m, 0], [m, h], [0, h]])},
            {"name": "right_wall",  "polygon": np.array([[w - m, 0], [w, 0], [w, h], [w - m, h]])},
            {"name": "top_wall",    "polygon": np.array([[0, 0], [w, 0], [w, m], [0, m]])},
            {"name": "bottom_wall", "polygon": np.array([[0, h - m], [w, h - m], [w, h], [0, h]])},
        ]

    def _resolve_zones(self, w: int, h: int) -> List[Dict[str, Any]]:
        """Return interest zones — user-configured or auto-generated."""
        if self._interest_zones:
            resolved = []
            for z in self._interest_zones:
                poly = np.array(z["polygon"], dtype=np.int32)
                resolved.append({"name": z.get("name", "zone"), "polygon": poly})
            return resolved
        return self._auto_edge_zones(w, h)

    @staticmethod
    def _point_in_polygon(point: Tuple[int, int], polygon: np.ndarray) -> bool:
        """Check if a 2-D point lies inside a convex/concave polygon."""
        result = cv2.pointPolygonTest(polygon.reshape(-1, 1, 2).astype(np.float32), point, False)
        return result >= 0

    def _bucket_key(self, cx: int, cy: int) -> str:
        """Quantise centroid to a grid bucket for lightweight tracking."""
        bx = cx // self._centroid_bucket_size
        by = cy // self._centroid_bucket_size
        return f"{bx}_{by}"

    def _update_dwell(self, key: str, now: float) -> float:
        """Update and return the dwell time in seconds for a tracked key."""
        if key not in self._dwell_tracker:
            self._dwell_tracker[key] = {"first_seen": now, "last_seen": now}
        self._dwell_tracker[key]["last_seen"] = now
        return now - self._dwell_tracker[key]["first_seen"]

    def _prune_trackers(self, now: float) -> None:
        """Remove stale entries from the dwell tracker."""
        expired = [
            k for k, v in self._dwell_tracker.items()
            if (now - v["last_seen"]) > self._tracker_expiry_sec
        ]
        for k in expired:
            del self._dwell_tracker[k]

    def _estimate_lean(self, frame_gray: np.ndarray,
                       bbox: List[int]) -> Tuple[float, str]:
        """
        Estimate lateral lean of the upper body / head by computing the
        horizontal centre of mass of the upper 30 % of the person
        bounding box relative to the box centre.

        Returns:
            (lean_angle_deg, direction)  — positive angle means leaning
            *right* (toward higher x), negative means left.
        """
        x1, y1, x2, y2 = bbox
        head_h = int((y2 - y1) * 0.30)
        head_roi = frame_gray[y1:y1 + head_h, x1:x2]
        if head_roi.size == 0:
            return 0.0, "centre"

        # Threshold to isolate foreground pixels (person silhouette)
        _, binary = cv2.threshold(head_roi, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        moments = cv2.moments(binary)
        if moments["m00"] == 0:
            return 0.0, "centre"

        com_x = moments["m10"] / moments["m00"]
        roi_cx = (x2 - x1) / 2.0
        offset_px = com_x - roi_cx
        roi_w = x2 - x1
        offset_ratio = offset_px / (roi_w / 2.0 + 1e-6)
        lean_angle = offset_ratio * 45.0  # map [-1, 1] → [-45°, 45°]

        direction = "right" if lean_angle > 2.0 else ("left" if lean_angle < -2.0 else "centre")
        return round(lean_angle, 2), direction

    def _detect_persons(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run YOLO inference and return person detections."""
        if self.model is None:
            return []
        results = self.model(frame, verbose=False)
        persons: List[Dict[str, Any]] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                if self.model.names[int(box.cls[0])].lower() != "person":
                    continue
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                persons.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(conf, 3),
                    "centroid": ((x1 + x2) // 2, (y1 + y2) // 2),
                })
        return persons

    # ------------------------------------------------------------------ #
    #  Main detection pipeline
    # ------------------------------------------------------------------ #
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Detect eavesdropping behaviour by combining person proximity to
        interest zones, dwell-time accumulation, and head lean analysis.

        Args:
            frame: BGR video frame.
            **kwargs:
                stream_id (str): Camera identifier.
                timestamp (float): Epoch timestamp (used for dwell
                    timing — falls back to wall-clock time).
                person_boxes (List[List[int]]): Optional pre-computed
                    person bounding boxes.

        Returns:
            Standardised detection dict.
        """
        if not self.is_enabled:
            return {"triggered": False, "detections": [], "metadata": {}, "event_type": self.name}

        h, w = frame.shape[:2]
        now = kwargs.get("timestamp", time.time())
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        zones = self._resolve_zones(w, h)
        persons = self._detect_persons(frame)
        self._prune_trackers(now)

        triggered = False
        detections: List[Dict[str, Any]] = []
        suspects: List[Dict[str, Any]] = []

        for person in persons:
            cx, cy = person["centroid"]
            bbox = person["bbox"]

            for zone in zones:
                if not self._point_in_polygon((cx, cy), zone["polygon"]):
                    continue

                # Person is inside a zone — update dwell time
                dwell_key = self._bucket_key(cx, cy)
                dwell_sec = self._update_dwell(dwell_key, now)

                lean_angle, lean_dir = self._estimate_lean(gray, bbox)

                # Confidence increases with dwell time and lean angle
                dwell_factor = min(1.0, dwell_sec / self._dwell_threshold_sec)
                lean_factor = min(1.0, abs(lean_angle) / (self._lean_angle_threshold + 1e-6)) * 0.3
                confidence = round(min(1.0, 0.4 + 0.4 * dwell_factor + lean_factor + person["confidence"] * 0.1), 3)

                suspect_info = {
                    "zone": zone["name"],
                    "dwell_sec": round(dwell_sec, 2),
                    "lean_angle": lean_angle,
                    "lean_direction": lean_dir,
                    "confidence": confidence,
                }
                suspects.append(suspect_info)

                if dwell_sec >= self._dwell_threshold_sec and confidence >= self.confidence_threshold:
                    triggered = True
                    detections.append({
                        "bbox": bbox,
                        "confidence": confidence,
                        "label": "eavesdropping",
                    })
                break  # one zone match per person is sufficient

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "persons_detected": len(persons),
                "suspects": suspects,
                "zones_active": [z["name"] for z in zones],
                "active_trackers": len(self._dwell_tracker),
            },
            "event_type": self.name,
        }
