"""
Addiction Detection Module - Substance Abuse Indicator Detector
===============================================================

Detects visual indicators of substance abuse in surveillance footage:
    • **Smoking detection**  – Cigarette-shaped objects near mouth/face region
    • **Drinking detection** – Bottles / cans held in restricted areas
    • **Posture analysis**   – Unusual body postures associated with intoxication
                               or substance use (swaying, slumping, erratic movement)
    • **Gesture patterns**   – Repetitive hand-to-mouth motions typical of smoking

The detector combines person detection with spatial analysis of small objects
relative to body keypoints. When a full pose-estimation model is unavailable
it falls back to geometric heuristics on the upper body region.

Kaggle Dataset Sourcing Suggestions:
    - Smoking Detection Dataset: https://www.kaggle.com/datasets/vitaminc/cigarette-smoker-detection
    - Custom Behavioral Dataset: https://www.kaggle.com/datasets/deepcontractor/smoking-and-drinking-dataset
    - MPII Human Pose Dataset:   https://www.kaggle.com/datasets/harshsingh2209/mpii-human-pose
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

# ── Constants ───────────────────────────────────────────────────────────────
# Approximate COCO class IDs for objects of interest
PERSON_CLASS_ID = 0
BOTTLE_CLASS_ID = 39
CUP_CLASS_ID = 41
WINE_GLASS_CLASS_ID = 40

SUBSTANCE_OBJECTS = {BOTTLE_CLASS_ID, CUP_CLASS_ID, WINE_GLASS_CLASS_ID}

# Skin-tone ranges in HSV colour space (broad multi-ethnic range)
SKIN_HSV_LOWER = np.array([0, 30, 60], dtype=np.uint8)
SKIN_HSV_UPPER = np.array([25, 180, 255], dtype=np.uint8)
SKIN_HSV_LOWER2 = np.array([160, 30, 60], dtype=np.uint8)
SKIN_HSV_UPPER2 = np.array([180, 180, 255], dtype=np.uint8)


class AddictionDetectionDetector(BaseDetector):
    """
    Detects substance-abuse indicators in camera frames.

    The pipeline operates in three phases:
    1. **Person detection** – identify all persons in the frame.
    2. **Object proximity analysis** – find small objects (bottles, cigarettes)
       within each person's upper-body region.
    3. **Gesture / posture scoring** – evaluate hand-to-mouth frequency,
       body sway, and slump angle to produce a behavioural risk score.

    Config keys:
        model_path               (str)  : YOLOv8 weights. Default ``"yolov8n.pt"``
        smoking_proximity_ratio  (float): How close object must be to mouth
                                          as fraction of head height. Default ``0.6``
        hand_mouth_window_sec    (float): Time window for gesture counting. Default ``10.0``
        gesture_trigger_count    (int)  : Hand-to-mouth events to trigger. Default ``3``
        sway_threshold_px        (float): Centroid sway to flag posture. Default ``25.0``
        restricted_zone          (list) : [x1,y1,x2,y2] zone where drinking is banned.
        posture_slump_angle      (float): Shoulder-hip angle for slump. Default ``60.0``

    Kaggle Datasets:
        - Smoking Detection Dataset
        - Custom Behavioral Dataset
    """

    # ── Lifecycle ───────────────────────────────────────────────────────────
    def __init__(self, config: Dict[str, Any] = None):
        # Per-person tracking state
        self._gesture_history: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=120)
        )
        self._centroid_history: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=60)
        )
        self._prev_centroids: List[Tuple[int, int, int]] = []
        self._next_id: int = 0
        super().__init__("addiction_detection", config)

    def load_model(self) -> None:
        """Load YOLOv8 for person + object detection; fallback to OpenCV."""
        self.smoking_prox = self.config.get("smoking_proximity_ratio", 0.6)
        self.gesture_window = self.config.get("hand_mouth_window_sec", 10.0)
        self.gesture_trigger = self.config.get("gesture_trigger_count", 3)
        self.sway_threshold = self.config.get("sway_threshold_px", 25.0)
        self.restricted_zone = self.config.get("restricted_zone", None)
        self.slump_angle = self.config.get("posture_slump_angle", 60.0)

        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            logger.info("YOLOv8 loaded for AddictionDetectionDetector (%s).", model_path)
        except Exception as exc:
            logger.warning(
                "YOLOv8 unavailable (%s). AddictionDetectionDetector will use "
                "OpenCV-based fallback.", exc
            )
            self.model = None

    # ── Main Inference ──────────────────────────────────────────────────────
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse a single video frame for substance-abuse indicators.

        Args:
            frame:      BGR numpy array.
            **kwargs:
                stream_id   (str)  : Camera identifier.
                timestamp   (float): Frame epoch timestamp.

        Returns:
            Dict with:
                triggered   – True when any indicator is detected.
                detections  – Per-person detection records.
                metadata    – smoking_events, drinking_events, posture_alerts,
                              gesture_alerts and aggregate risk_score.
                event_type  – ``"addiction_detection"``.
        """
        if not self.is_enabled:
            return self._empty_result()

        ts_start = time.perf_counter()
        timestamp = kwargs.get("timestamp", time.time())

        # Phase 1: detect persons and objects
        persons, objects = self._detect_entities(frame)

        # Phase 2 & 3: per-person analysis
        smoking_events: List[Dict] = []
        drinking_events: List[Dict] = []
        posture_alerts: List[Dict] = []
        gesture_alerts: List[Dict] = []
        all_detections: List[Dict] = []

        current_centroids: List[Tuple[int, int, int]] = []

        for person in persons:
            px1, py1, px2, py2 = person["bbox"]
            cx, cy = (px1 + px2) // 2, (py1 + py2) // 2
            track_id = self._associate(cx, cy)
            self._centroid_history[track_id].append((cx, cy, timestamp))
            current_centroids.append((cx, cy, track_id))
            person["track_id"] = track_id

            # ── Smoking detection ───────────────────────────────────────────
            smoking_score = self._check_smoking(frame, person, objects)
            person["smoking_score"] = smoking_score
            if smoking_score >= self.confidence_threshold:
                smoking_events.append({
                    "track_id": track_id,
                    "bbox": person["bbox"],
                    "score": smoking_score,
                })

            # ── Drinking detection ──────────────────────────────────────────
            drinking_score = self._check_drinking(person, objects)
            person["drinking_score"] = drinking_score
            if drinking_score >= self.confidence_threshold:
                in_restricted = self._in_restricted_zone(cx, cy)
                drinking_events.append({
                    "track_id": track_id,
                    "bbox": person["bbox"],
                    "score": drinking_score,
                    "in_restricted_zone": in_restricted,
                })

            # ── Posture analysis ────────────────────────────────────────────
            posture_score = self._check_posture(track_id, frame, person)
            person["posture_score"] = posture_score
            if posture_score >= self.confidence_threshold:
                posture_alerts.append({
                    "track_id": track_id,
                    "bbox": person["bbox"],
                    "score": posture_score,
                })

            # ── Gesture pattern (hand-to-mouth repetition) ─────────────────
            gesture_detected = self._check_hand_mouth_gesture(
                frame, person, timestamp, track_id
            )
            if gesture_detected:
                gesture_alerts.append({
                    "track_id": track_id,
                    "bbox": person["bbox"],
                })

            all_detections.append(person)

        self._prev_centroids = current_centroids

        triggered = bool(
            smoking_events or drinking_events or posture_alerts or gesture_alerts
        )

        elapsed_ms = (time.perf_counter() - ts_start) * 1000

        return {
            "triggered": triggered,
            "detections": all_detections,
            "metadata": {
                "persons_analysed": len(persons),
                "smoking_events": smoking_events,
                "drinking_events": drinking_events,
                "posture_alerts": posture_alerts,
                "gesture_alerts": gesture_alerts,
                "risk_score": self._aggregate_risk(
                    smoking_events, drinking_events, posture_alerts, gesture_alerts
                ),
                "inference_time_ms": round(elapsed_ms, 2),
                "model_backend": "yolov8" if self.model else "opencv_fallback",
                "stream_id": kwargs.get("stream_id"),
            },
            "event_type": self.name,
        }

    # ── Entity Detection ────────────────────────────────────────────────────
    def _detect_entities(
        self, frame: np.ndarray
    ) -> Tuple[List[Dict], List[Dict]]:
        """Return (persons, objects) detected in the frame."""
        if self.model is not None:
            return self._detect_entities_yolo(frame)
        return self._detect_entities_fallback(frame)

    def _detect_entities_yolo(
        self, frame: np.ndarray
    ) -> Tuple[List[Dict], List[Dict]]:
        results = self.model(frame, conf=self.confidence_threshold, verbose=False)
        persons: List[Dict] = []
        objects: List[Dict] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = self.model.names.get(cls_id, f"class_{cls_id}")
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                entry = {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(conf, 4),
                    "label": label,
                    "class_id": cls_id,
                }
                if cls_id == PERSON_CLASS_ID:
                    persons.append(entry)
                elif cls_id in SUBSTANCE_OBJECTS:
                    objects.append(entry)
        return persons, objects

    def _detect_entities_fallback(
        self, frame: np.ndarray
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Fallback: detect person-like contours via skin-colour segmentation
        and large-contour extraction. Objects are not detected in fallback.
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, SKIN_HSV_LOWER, SKIN_HSV_UPPER)
        mask2 = cv2.inRange(hsv, SKIN_HSV_LOWER2, SKIN_HSV_UPPER2)
        skin_mask = cv2.bitwise_or(mask1, mask2)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = frame.shape[:2]
        min_area = (h * w) * 0.008
        persons: List[Dict] = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bh / max(bw, 1)
            # Person heuristic: taller than wide
            if aspect > 1.2:
                confidence = min(0.30 + (area / (h * w)), 0.70)
                persons.append({
                    "bbox": [x, y, x + bw, y + bh],
                    "confidence": round(confidence, 4),
                    "label": "person",
                    "class_id": PERSON_CLASS_ID,
                })
        return persons, []

    # ── Smoking Detection ───────────────────────────────────────────────────
    def _check_smoking(
        self, frame: np.ndarray, person: Dict, objects: List[Dict]
    ) -> float:
        """
        Score likelihood of smoking by:
        1. Finding small elongated objects near the person's head region.
        2. Checking for smoke-like colour/texture in the head vicinity.
        """
        px1, py1, px2, py2 = person["bbox"]
        head_h = (py2 - py1) * 0.25
        head_region = [px1, py1, px2, int(py1 + head_h)]

        score = 0.0

        # Check proximity of detected objects to head
        for obj in objects:
            ox1, oy1, ox2, oy2 = obj["bbox"]
            ocx, ocy = (ox1 + ox2) // 2, (oy1 + oy2) // 2
            if self._point_in_box(ocx, ocy, head_region, margin=int(head_h * self.smoking_prox)):
                score += 0.35

        # Look for small bright elongated blobs in head region (cigarette shape)
        hr_y1 = max(0, head_region[1])
        hr_y2 = min(frame.shape[0], head_region[3])
        hr_x1 = max(0, head_region[0])
        hr_x2 = min(frame.shape[1], head_region[2])

        if hr_y2 > hr_y1 and hr_x2 > hr_x1:
            crop = frame[hr_y1:hr_y2, hr_x1:hr_x2]
            score += self._detect_cigarette_shape(crop)

        return min(round(score, 3), 1.0)

    def _detect_cigarette_shape(self, crop: np.ndarray) -> float:
        """
        Search for small, thin, bright elongated blobs that resemble a
        cigarette within a cropped head region.
        """
        if crop.size == 0:
            return 0.0

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        _, bright = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 15 or area > 800:
                continue
            rect = cv2.minAreaRect(cnt)
            (_, (rw, rh), _) = rect
            if min(rw, rh) < 1:
                continue
            elongation = max(rw, rh) / min(rw, rh)
            if elongation > 3.0:
                return 0.30  # elongated bright object found
        return 0.0

    # ── Drinking Detection ──────────────────────────────────────────────────
    def _check_drinking(self, person: Dict, objects: List[Dict]) -> float:
        """
        Score likelihood of drinking by checking proximity of bottle/cup
        objects to the person's upper body.
        """
        px1, py1, px2, py2 = person["bbox"]
        upper_body = [px1, py1, px2, int(py1 + (py2 - py1) * 0.55)]
        score = 0.0

        for obj in objects:
            if obj.get("class_id") not in SUBSTANCE_OBJECTS:
                continue
            ox1, oy1, ox2, oy2 = obj["bbox"]
            ocx, ocy = (ox1 + ox2) // 2, (oy1 + oy2) // 2
            if self._point_in_box(ocx, ocy, upper_body, margin=30):
                score += 0.45
                # Closer to head = higher score
                head_cy = py1 + (py2 - py1) * 0.15
                dist_to_head = abs(ocy - head_cy) / max((py2 - py1), 1)
                score += max(0, 0.3 - dist_to_head)

        return min(round(score, 3), 1.0)

    # ── Posture Analysis ────────────────────────────────────────────────────
    def _check_posture(self, track_id: int, frame: np.ndarray, person: Dict) -> float:
        """
        Evaluate body posture for signs of intoxication:
        - Excessive centroid sway (wobbling)
        - Abnormal aspect ratio (slumped / collapsed)
        """
        score = 0.0
        px1, py1, px2, py2 = person["bbox"]
        bw, bh = px2 - px1, py2 - py1

        # Slump detection: aspect ratio collapse
        if bh > 0:
            aspect = bw / bh
            if aspect > 1.5:
                # Person bbox wider than tall → likely slumped / on ground
                score += 0.40

        # Sway detection from centroid history
        history = self._centroid_history.get(track_id)
        if history and len(history) >= 10:
            items = list(history)
            xs = [p[0] for p in items[-20:]]
            ys = [p[1] for p in items[-20:]]
            x_range = max(xs) - min(xs)
            y_range = max(ys) - min(ys)
            sway = math.hypot(x_range, y_range)
            if sway > self.sway_threshold:
                score += min(0.35 * (sway / self.sway_threshold), 0.50)

        return min(round(score, 3), 1.0)

    # ── Hand-to-Mouth Gesture ───────────────────────────────────────────────
    def _check_hand_mouth_gesture(
        self,
        frame: np.ndarray,
        person: Dict,
        timestamp: float,
        track_id: int,
    ) -> bool:
        """
        Detect repetitive hand-to-mouth motion by tracking skin-coloured
        blobs moving into the head region over time.
        """
        px1, py1, px2, py2 = person["bbox"]
        head_h = (py2 - py1) * 0.25
        head_region_y = (py1, int(py1 + head_h))

        # Crop upper body
        ub_y1 = max(0, py1)
        ub_y2 = min(frame.shape[0], int(py1 + (py2 - py1) * 0.5))
        ub_x1 = max(0, px1)
        ub_x2 = min(frame.shape[1], px2)

        if ub_y2 <= ub_y1 or ub_x2 <= ub_x1:
            return False

        crop = frame[ub_y1:ub_y2, ub_x1:ub_x2]
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

        mask1 = cv2.inRange(hsv, SKIN_HSV_LOWER, SKIN_HSV_UPPER)
        mask2 = cv2.inRange(hsv, SKIN_HSV_LOWER2, SKIN_HSV_UPPER2)
        skin = cv2.bitwise_or(mask1, mask2)

        # Check if skin pixels exist in the head sub-region of the crop
        head_local_y2 = min(int(head_h), crop.shape[0])
        head_skin_pixels = cv2.countNonZero(skin[:head_local_y2, :])
        head_area = max(head_local_y2 * crop.shape[1], 1)
        skin_ratio = head_skin_pixels / head_area

        # A hand near the mouth increases the skin ratio in the head area
        gesture_present = skin_ratio > 0.35

        self._gesture_history[track_id].append((timestamp, gesture_present))

        # Count gestures within window
        cutoff = timestamp - self.gesture_window
        recent = [g for t, g in self._gesture_history[track_id] if t >= cutoff and g]
        return len(recent) >= self.gesture_trigger

    # ── Zone Check ──────────────────────────────────────────────────────────
    def _in_restricted_zone(self, cx: int, cy: int) -> bool:
        """Check whether a point falls inside the configured restricted zone."""
        if self.restricted_zone is None:
            return False
        zx1, zy1, zx2, zy2 = self.restricted_zone
        return zx1 <= cx <= zx2 and zy1 <= cy <= zy2

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _associate(self, cx: int, cy: int, max_dist: int = 80) -> int:
        """Nearest-neighbour centroid association for simple tracking."""
        best_id, best_dist = -1, max_dist
        for px, py, tid in self._prev_centroids:
            d = math.hypot(cx - px, cy - py)
            if d < best_dist:
                best_dist = d
                best_id = tid
        if best_id < 0:
            best_id = self._next_id
            self._next_id += 1
        return best_id

    @staticmethod
    def _point_in_box(
        px: int, py: int, box: List[int], margin: int = 0
    ) -> bool:
        """Check if point (px, py) is inside box with optional margin."""
        return (
            box[0] - margin <= px <= box[2] + margin
            and box[1] - margin <= py <= box[3] + margin
        )

    @staticmethod
    def _aggregate_risk(
        smoking: List, drinking: List, posture: List, gestures: List
    ) -> float:
        """Compute a 0-1 aggregate risk score across all indicators."""
        total = len(smoking) * 0.3 + len(drinking) * 0.3 + len(posture) * 0.2 + len(gestures) * 0.2
        return min(round(total, 2), 1.0)

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "triggered": False,
            "detections": [],
            "metadata": {},
            "event_type": self.name,
        }
