"""
Loitering Detection Module
===========================

Detects persons who remain in the same general area for an extended period
of time. A configurable dwell-time threshold (default 60 seconds) controls
when an alert is fired.

The detector maintains a simple centroid tracker to assign persistent IDs
to detected person blobs. For each tracked ID it records:
    - ``first_seen``: Unix timestamp when the track was created.
    - ``positions``: Rolling window of recent centroid positions.
    - ``roaming_radius``: Maximum displacement from the average position.

If a person's ``dwell_time`` (now − first_seen) exceeds the threshold AND
the roaming_radius stays below a configured spatial limit, the person is
classified as loitering.

Kaggle Dataset Suggestion:
    - VIRAT Video Dataset
      https://www.kaggle.com/datasets/... (VIRAT)
      Large-scale surveillance video dataset with activity annotations
      including loitering. Ideal for training dwell-time models.

Usage:
    config = {
        "confidence_threshold": 0.5,
        "dwell_time_threshold": 60,      # seconds
        "roaming_radius_limit": 150,     # pixels — max wander distance
        "position_window": 90,           # keep last N centroid positions
        "min_person_area": 2500,
        "max_disappeared": 30,
        "max_match_distance": 80,
    }
    detector = LoiteringDetector(config=config)
    result = detector.detect(frame, timestamp=time.time())
"""

import logging
import time
from collections import OrderedDict
from typing import Dict, Any, List, Tuple

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


# ======================================================================
# Lightweight Centroid Tracker (with timestamp bookkeeping)
# ======================================================================
class _LoiteringTracker:
    """
    Centroid tracker augmented with per-track temporal and spatial state
    needed for loitering analysis.
    """

    def __init__(
        self,
        max_disappeared: int = 30,
        max_distance: float = 80.0,
        position_window: int = 90,
    ):
        self._next_id: int = 0
        self.objects: OrderedDict = OrderedDict()          # id -> centroid
        self._disappeared: OrderedDict = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

        # Per-track state
        self.first_seen: Dict[int, float] = {}
        self.positions: Dict[int, List[Tuple[int, int]]] = {}
        self.position_window = position_window

    def update(
        self, centroids: List[Tuple[int, int]], timestamp: float
    ) -> OrderedDict:
        """Match centroids, maintain state, return current objects."""
        if len(centroids) == 0:
            for oid in list(self._disappeared.keys()):
                self._disappeared[oid] += 1
                if self._disappeared[oid] > self.max_disappeared:
                    self._deregister(oid)
            return self.objects

        if len(self.objects) == 0:
            for c in centroids:
                self._register(c, timestamp)
            return self.objects

        object_ids = list(self.objects.keys())
        object_centroids = list(self.objects.values())

        D = np.linalg.norm(
            np.array(object_centroids)[:, np.newaxis]
            - np.array(centroids)[np.newaxis, :],
            axis=2,
        )

        rows = D.min(axis=1).argsort()
        cols = D.argmin(axis=1)[rows]

        used_rows: set = set()
        used_cols: set = set()

        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if D[row, col] > self.max_distance:
                continue
            oid = object_ids[row]
            self.objects[oid] = centroids[col]
            self._disappeared[oid] = 0
            # Append position history
            self.positions[oid].append(centroids[col])
            if len(self.positions[oid]) > self.position_window:
                self.positions[oid] = self.positions[oid][-self.position_window:]
            used_rows.add(row)
            used_cols.add(col)

        for row in set(range(len(object_ids))) - used_rows:
            oid = object_ids[row]
            self._disappeared[oid] += 1
            if self._disappeared[oid] > self.max_disappeared:
                self._deregister(oid)

        for col in set(range(len(centroids))) - used_cols:
            self._register(centroids[col], timestamp)

        return self.objects

    def _register(self, centroid: Tuple[int, int], timestamp: float) -> None:
        oid = self._next_id
        self.objects[oid] = centroid
        self._disappeared[oid] = 0
        self.first_seen[oid] = timestamp
        self.positions[oid] = [centroid]
        self._next_id += 1

    def _deregister(self, oid: int) -> None:
        del self.objects[oid]
        del self._disappeared[oid]
        self.first_seen.pop(oid, None)
        self.positions.pop(oid, None)

    def get_roaming_radius(self, oid: int) -> float:
        """Max displacement from mean position for given track ID."""
        pts = self.positions.get(oid, [])
        if len(pts) < 2:
            return 0.0
        arr = np.array(pts, dtype=np.float64)
        mean = arr.mean(axis=0)
        distances = np.linalg.norm(arr - mean, axis=1)
        return float(distances.max())

    def get_dwell_time(self, oid: int, now: float) -> float:
        """Elapsed seconds since first_seen for given track ID."""
        return now - self.first_seen.get(oid, now)


# ======================================================================
# Detector
# ======================================================================
class LoiteringDetector(BaseDetector):
    """
    Detects persons loitering — remaining within a small spatial area for
    longer than a configurable dwell-time threshold.

    Attributes:
        dwell_time_threshold (float): Seconds before loitering is flagged.
        roaming_radius_limit (float): Max pixel displacement from mean
            position to still be considered "stationary enough".
        tracker (_LoiteringTracker): Internal centroid tracker.
        alerted_ids (set): Track IDs for which an alert has already been
            emitted (to avoid duplicate alerts).
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(name="loitering", config=config)

    # ------------------------------------------------------------------
    # Model / resource loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """Initialise tracker, background subtractor, and thresholds."""
        self.dwell_time_threshold: float = self.config.get(
            "dwell_time_threshold", 60.0
        )
        self.roaming_radius_limit: float = self.config.get(
            "roaming_radius_limit", 150.0
        )
        position_window: int = self.config.get("position_window", 90)
        max_disappeared: int = self.config.get("max_disappeared", 30)
        max_distance: float = self.config.get("max_match_distance", 80.0)

        self.tracker = _LoiteringTracker(
            max_disappeared=max_disappeared,
            max_distance=max_distance,
            position_window=position_window,
        )

        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=True,
        )
        self.min_person_area: int = self.config.get("min_person_area", 2500)

        # Tracks for which an alert has already been sent (avoid duplicates)
        self.alerted_ids: set = set()

        logger.info(
            f"LoiteringDetector loaded — dwell threshold={self.dwell_time_threshold}s, "
            f"roaming limit={self.roaming_radius_limit}px."
        )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Run loitering analysis on a single video frame.

        Args:
            frame: BGR video frame (H×W×3 uint8 numpy array).
            **kwargs:
                timestamp (float): Unix epoch timestamp of the frame.
                external_detections (List[Dict]): Pre-computed person bboxes.

        Returns:
            Dict with keys triggered, detections, metadata, event_type.
        """
        if not self.is_enabled:
            return {
                "triggered": False,
                "detections": [],
                "metadata": {"status": "disabled"},
                "event_type": self.name,
            }

        timestamp: float = kwargs.get("timestamp", time.time())
        external_detections: List[Dict] = kwargs.get("external_detections", [])

        # ----- Step 1: Obtain person centroids -----
        if external_detections:
            centroids = self._centroids_from_external(external_detections)
        else:
            centroids = self._detect_person_centroids(frame)

        # ----- Step 2: Update tracker -----
        objects = self.tracker.update(centroids, timestamp)

        # ----- Step 3: Evaluate loitering per track -----
        detections: List[Dict[str, Any]] = []
        active_dwells: List[Dict[str, Any]] = []

        for oid, centroid in objects.items():
            dwell = self.tracker.get_dwell_time(oid, timestamp)
            radius = self.tracker.get_roaming_radius(oid)

            track_info = {
                "track_id": oid,
                "centroid": list(centroid),
                "dwell_time_s": round(dwell, 1),
                "roaming_radius_px": round(radius, 1),
            }
            active_dwells.append(track_info)

            is_loitering = (
                dwell >= self.dwell_time_threshold
                and radius <= self.roaming_radius_limit
            )

            if is_loitering and oid not in self.alerted_ids:
                self.alerted_ids.add(oid)
                detections.append({
                    "track_id": oid,
                    "centroid": list(centroid),
                    "dwell_time_s": round(dwell, 1),
                    "roaming_radius_px": round(radius, 1),
                    "label": "loitering_person",
                    "confidence": min(1.0, dwell / self.dwell_time_threshold),
                })

        # Purge alerted IDs that have been deregistered
        active_ids = set(objects.keys())
        self.alerted_ids &= active_ids

        triggered = len(detections) > 0

        metadata = {
            "total_tracked": len(objects),
            "loitering_alerts_this_frame": len(detections),
            "active_dwells": active_dwells,
            "dwell_threshold_s": self.dwell_time_threshold,
            "roaming_limit_px": self.roaming_radius_limit,
            "timestamp": timestamp,
        }

        if triggered:
            logger.warning(
                f"LOITERING DETECTED — {len(detections)} person(s) exceeded "
                f"{self.dwell_time_threshold}s dwell threshold."
            )

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": metadata,
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Person detection helpers
    # ------------------------------------------------------------------
    def _detect_person_centroids(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int]]:
        """Detect person-sized foreground blobs and return centroids."""
        fg_mask = self.bg_subtractor.apply(frame)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        centroids: List[Tuple[int, int]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_person_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if h / max(w, 1) < 1.0:
                continue
            centroids.append((x + w // 2, y + h // 2))

        return centroids

    @staticmethod
    def _centroids_from_external(
        detections: List[Dict],
    ) -> List[Tuple[int, int]]:
        """Convert external bbox detections to centroids."""
        centroids: List[Tuple[int, int]] = []
        for det in detections:
            bbox = det.get("bbox")
            if bbox is None or len(bbox) != 4:
                continue
            x1, y1, x2, y2 = bbox
            centroids.append((int((x1 + x2) / 2), int((y1 + y2) / 2)))
        return centroids
