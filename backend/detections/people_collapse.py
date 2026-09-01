import logging
import time
from typing import Dict, Any, List, Optional, Tuple
from collections import deque, defaultdict
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class PeopleCollapseDetector(BaseDetector):
    """
    Detects when a person collapses or falls down in video frames.

    Detection Strategy:
        1. Person Detection: Locates persons via YOLO or HOG fallback.
        2. Aspect-Ratio Tracking: A standing person has aspect ratio
           (height/width) > 1.3. A collapsed person typically has ratio < 1.0.
           The detector tracks per-person aspect-ratio history and triggers
           when the ratio drops dramatically within a short time window.
        3. Centroid Vertical Velocity: Monitors the Y-coordinate of each
           person's centroid. A rapid downward movement (increasing Y in
           image coordinates) indicates a fall.
        4. Bounding-Box Area Change: A person going from upright to lying
           down may cause a sudden expansion of box width and shrinkage of
           box height, detected as area-shape change.
        5. Temporal Window: Requires the transition from "standing" to
           "collapsed" to happen within a configurable time window to
           distinguish falls from sitting/crouching.

    Kaggle Dataset Sourcing Suggestions:
        - UR Fall Detection Dataset
        - Le2i Fall Detection Dataset
        - UP-Fall Detection Dataset

    Config keys:
        model_path (str): Path to YOLOv8 weights. Default: "yolov8n.pt"
        standing_aspect_ratio (float): Minimum H/W ratio for "standing".
            Default: 1.3
        collapsed_aspect_ratio (float): Maximum H/W ratio for "collapsed".
            Default: 1.0
        centroid_velocity_threshold (float): Minimum downward pixel velocity
            of centroid per frame to flag rapid descent. Default: 15.0
        transition_window_frames (int): Number of frames within which the
            aspect ratio must transition for a collapse. Default: 15
        history_length (int): Per-person tracking buffer size. Default: 30
    """

    def __init__(self, config: Dict[str, Any] = None):
        # Per-person tracking state keyed by a simple spatial-hash id
        self._person_tracks: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=self.config.get("history_length", 30))
        )
        self._collapse_cooldown: Dict[int, int] = {}
        self._frame_index: int = 0
        super().__init__("people_collapse", config)

    # ------------------------------------------------------------------
    # Model Loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """Load YOLOv8 or fallback to OpenCV HOG person detector."""
        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            self._use_yolo = True
            logger.info("YOLOv8 model loaded for PeopleCollapseDetector.")
        except Exception as e:
            logger.warning(
                f"YOLO unavailable ({e}); falling back to HOG person detector."
            )
            self.model = cv2.HOGDescriptor()
            self.model.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._use_yolo = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse a single frame for person collapse / fall events.

        Args:
            frame: BGR video frame (H × W × 3).
            **kwargs:
                person_boxes (List[List[int]]): Pre-computed person boxes.
                timestamp (float): Frame timestamp in seconds.

        Returns:
            Standard detection dict.
        """
        if not self.is_enabled:
            return self._empty_result()

        self._frame_index += 1
        h, w = frame.shape[:2]

        # --- 1. Person detection ---
        person_boxes = kwargs.get("person_boxes") or self._detect_persons(frame)

        # --- 2. Track each person ---
        collapse_events: List[Dict[str, Any]] = []
        standing_ar = self.config.get("standing_aspect_ratio", 1.3)
        collapsed_ar = self.config.get("collapsed_aspect_ratio", 1.0)
        velocity_thresh = self.config.get("centroid_velocity_threshold", 15.0)
        trans_window = self.config.get("transition_window_frames", 15)
        cooldown_frames = self.config.get("cooldown_frames", 30)

        for box in person_boxes:
            x1, y1, x2, y2 = box
            bw = max(x2 - x1, 1)
            bh = max(y2 - y1, 1)
            aspect_ratio = bh / bw
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0

            track_id = self._assign_track_id(cx, cy, bw, bh, w, h)

            # Store observation
            observation = {
                "frame": self._frame_index,
                "bbox": box,
                "aspect_ratio": aspect_ratio,
                "centroid": (cx, cy),
            }
            track = self._person_tracks[track_id]
            track.append(observation)

            # Skip if in cooldown (already reported recently)
            if track_id in self._collapse_cooldown:
                if self._frame_index - self._collapse_cooldown[track_id] < cooldown_frames:
                    continue

            # --- 3. Analyse aspect-ratio transition ---
            collapse_detected, confidence = self._analyse_collapse(
                track, standing_ar, collapsed_ar, velocity_thresh, trans_window
            )

            if collapse_detected and confidence >= self.confidence_threshold:
                collapse_events.append({
                    "bbox": box,
                    "confidence": round(confidence, 3),
                    "label": "person_collapse",
                    "track_id": track_id,
                    "current_aspect_ratio": round(aspect_ratio, 2),
                })
                self._collapse_cooldown[track_id] = self._frame_index

        triggered = len(collapse_events) > 0

        return {
            "triggered": triggered,
            "detections": collapse_events,
            "metadata": {
                "persons_detected": len(person_boxes),
                "active_tracks": len(self._person_tracks),
                "collapse_events": len(collapse_events),
                "frame_index": self._frame_index,
            },
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _empty_result(self) -> Dict[str, Any]:
        return {
            "triggered": False,
            "detections": [],
            "metadata": {},
            "event_type": self.name,
        }

    def _detect_persons(self, frame: np.ndarray) -> List[List[int]]:
        """Detect person bounding boxes."""
        boxes: List[List[int]] = []
        if self._use_yolo and self.model is not None:
            results = self.model(frame, verbose=False)
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        label = self.model.names[cls_id]
                        conf = float(box.conf[0])
                        if label == "person" and conf >= self.confidence_threshold:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            boxes.append([x1, y1, x2, y2])
        else:
            rects, _ = self.model.detectMultiScale(
                frame, winStride=(8, 8), padding=(4, 4), scale=1.05
            )
            for (x, y, bw, bh) in rects:
                boxes.append([int(x), int(y), int(x + bw), int(y + bh)])
        return boxes

    def _assign_track_id(
        self, cx: float, cy: float, bw: int, bh: int, w: int, h: int
    ) -> int:
        """
        Simple nearest-neighbour track assignment.
        Matches the new centroid to the closest existing track whose last
        known centroid is within a distance threshold, or creates a new id.
        """
        match_thresh = max(bw, bh) * 1.5
        best_id: Optional[int] = None
        best_dist = float("inf")

        for tid, track in self._person_tracks.items():
            if not track:
                continue
            last_obs = track[-1]
            lcx, lcy = last_obs["centroid"]
            dist = np.sqrt((cx - lcx) ** 2 + (cy - lcy) ** 2)
            if dist < best_dist and dist < match_thresh:
                best_dist = dist
                best_id = tid

        if best_id is not None:
            return best_id

        # New track — use a hash of the centroid position
        new_id = hash((round(cx, -1), round(cy, -1), self._frame_index)) % (10**8)
        return new_id

    def _analyse_collapse(
        self,
        track: deque,
        standing_ar: float,
        collapsed_ar: float,
        velocity_thresh: float,
        trans_window: int,
    ) -> Tuple[bool, float]:
        """
        Determine if the tracked person has just collapsed.

        Returns:
            (collapse_detected: bool, confidence: float)
        """
        if len(track) < 3:
            return False, 0.0

        current = track[-1]
        current_ar = current["aspect_ratio"]

        # Must currently look collapsed
        if current_ar > collapsed_ar:
            return False, 0.0

        # Look back within the transition window for a standing posture
        was_standing = False
        standing_ar_max = 0.0
        for obs in list(track):
            frame_diff = current["frame"] - obs["frame"]
            if 0 < frame_diff <= trans_window:
                if obs["aspect_ratio"] >= standing_ar:
                    was_standing = True
                    standing_ar_max = max(standing_ar_max, obs["aspect_ratio"])

        if not was_standing:
            return False, 0.0

        # --- Aspect-ratio drop score ---
        ar_drop = standing_ar_max - current_ar
        ar_score = min(1.0, ar_drop / standing_ar)  # normalised

        # --- Centroid vertical velocity ---
        velocities = []
        track_list = list(track)
        for k in range(1, min(len(track_list), trans_window)):
            dy = track_list[-k]["centroid"][1] - track_list[-k - 1]["centroid"][1]
            velocities.append(dy)

        avg_downward_velocity = max(0.0, np.mean(velocities)) if velocities else 0.0
        vel_score = min(1.0, avg_downward_velocity / velocity_thresh)

        # --- Combined confidence ---
        confidence = 0.60 * ar_score + 0.40 * vel_score
        return True, confidence

    def reset_tracks(self) -> None:
        """Clear all tracking state (useful on camera change)."""
        self._person_tracks.clear()
        self._collapse_cooldown.clear()
        self._frame_index = 0
        logger.info("PeopleCollapseDetector tracks have been reset.")
