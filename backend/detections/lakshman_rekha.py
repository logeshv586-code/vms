"""
Lakshman Rekha — Virtual Tripwire / Boundary Crossing Detector
==============================================================

Defines virtual lines (tripwires) on the video frame and detects when a
tracked person crosses from one side of the line to the other.

The detector maintains a simple centroid tracker to assign persistent IDs
to detected person blobs across frames. When a tracked centroid's previous
and current positions form a segment that intersects the tripwire line, a
crossing event is fired. Direction is determined by the cross-product sign
relative to the line's direction vector, enabling separate entry/exit
counting.

Kaggle Dataset Suggestion:
    - MOT Challenge Dataset
      https://www.kaggle.com/datasets/... (MOT Challenge)
      Multi-Object Tracking benchmark sequences with ground-truth
      trajectories. Ideal for training and evaluating crossing detectors.

Usage:
    config = {
        "confidence_threshold": 0.5,
        "tripwires": [
            {
                "name": "Main Gate",
                "line": [[300, 0], [300, 720]],
                "direction_label": {"positive": "entry", "negative": "exit"}
            }
        ],
        "max_disappeared": 15,
        "max_match_distance": 80,
        "min_person_area": 2500,
    }
    detector = LakshmanRekhaDetector(config=config)
    result = detector.detect(frame, timestamp=time.time())
"""

import logging
import time
from collections import OrderedDict
from typing import Dict, Any, List, Tuple, Optional

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


# ======================================================================
# Lightweight Centroid Tracker
# ======================================================================
class _CentroidTracker:
    """
    Minimal centroid-based multi-object tracker.

    Assigns stable integer IDs to objects by matching new centroids to
    existing ones using Euclidean distance. Deregisters objects that have
    disappeared for more than ``max_disappeared`` consecutive frames.
    """

    def __init__(self, max_disappeared: int = 15, max_distance: float = 80.0):
        self._next_id: int = 0
        self.objects: OrderedDict = OrderedDict()          # id -> centroid (x, y)
        self.previous: OrderedDict = OrderedDict()         # id -> previous centroid
        self._disappeared: OrderedDict = OrderedDict()     # id -> frame count
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def update(self, centroids: List[Tuple[int, int]]) -> OrderedDict:
        """
        Accept a list of current-frame centroids and return an OrderedDict
        mapping object IDs to their current centroid.
        """
        if len(centroids) == 0:
            for oid in list(self._disappeared.keys()):
                self._disappeared[oid] += 1
                if self._disappeared[oid] > self.max_disappeared:
                    self._deregister(oid)
            return self.objects

        if len(self.objects) == 0:
            for c in centroids:
                self._register(c)
            return self.objects

        object_ids = list(self.objects.keys())
        object_centroids = list(self.objects.values())

        # Pairwise distance matrix
        D = np.linalg.norm(
            np.array(object_centroids)[:, np.newaxis] - np.array(centroids)[np.newaxis, :],
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
            self.previous[oid] = self.objects[oid]
            self.objects[oid] = centroids[col]
            self._disappeared[oid] = 0
            used_rows.add(row)
            used_cols.add(col)

        # Handle unmatched existing objects
        for row in set(range(len(object_ids))) - used_rows:
            oid = object_ids[row]
            self._disappeared[oid] += 1
            if self._disappeared[oid] > self.max_disappeared:
                self._deregister(oid)

        # Handle unmatched new centroids
        for col in set(range(len(centroids))) - used_cols:
            self._register(centroids[col])

        return self.objects

    def _register(self, centroid: Tuple[int, int]) -> None:
        oid = self._next_id
        self.objects[oid] = centroid
        self.previous[oid] = centroid
        self._disappeared[oid] = 0
        self._next_id += 1

    def _deregister(self, oid: int) -> None:
        del self.objects[oid]
        self.previous.pop(oid, None)
        del self._disappeared[oid]


# ======================================================================
# Detector
# ======================================================================
class LakshmanRekhaDetector(BaseDetector):
    """
    Virtual tripwire / boundary crossing detector.

    Maintains centroid tracking across frames and fires crossing events
    when a tracked person's movement path intersects a configured tripwire
    line. The crossing direction is determined via the cross-product of
    the line direction vector and the centroid movement vector.

    Attributes:
        tripwires (List[Dict]): Configured tripwire definitions.
        tracker (_CentroidTracker): Centroid tracker instance.
        entry_count (int): Cumulative entry crossings.
        exit_count (int): Cumulative exit crossings.
        crossed_ids (Dict[int, set]): Set of tripwire names already crossed
            by each tracked ID (prevents duplicate counting per crossing).
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(name="lakshman_rekha", config=config)

    # ------------------------------------------------------------------
    # Model / resource loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """
        Parse tripwire definitions, initialise centroid tracker and
        background subtractor.
        """
        # Parse tripwires
        raw_wires = self.config.get("tripwires", [])
        self.tripwires: List[Dict[str, Any]] = []
        for tw in raw_wires:
            line = tw.get("line", [[0, 0], [0, 0]])
            p1 = tuple(line[0])
            p2 = tuple(line[1])
            dir_label = tw.get("direction_label", {
                "positive": "entry",
                "negative": "exit",
            })
            self.tripwires.append({
                "name": tw.get("name", "Unnamed Tripwire"),
                "p1": p1,
                "p2": p2,
                "direction_label": dir_label,
            })

        if not self.tripwires:
            logger.warning(
                "LakshmanRekhaDetector: No tripwires configured. "
                "Add tripwires via config['tripwires'] for meaningful detection."
            )

        # Tracker
        max_disappeared = self.config.get("max_disappeared", 15)
        max_distance = self.config.get("max_match_distance", 80)
        self.tracker = _CentroidTracker(
            max_disappeared=max_disappeared,
            max_distance=max_distance,
        )

        # Background subtractor for person detection
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=True,
        )
        self.min_person_area: int = self.config.get("min_person_area", 2500)

        # Crossing state
        self.entry_count: int = 0
        self.exit_count: int = 0
        self.crossed_ids: Dict[int, set] = {}  # track_id -> set of tripwire names crossed

        logger.info(
            f"LakshmanRekhaDetector loaded with {len(self.tripwires)} tripwire(s)."
        )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Run boundary-crossing detection on a single video frame.

        Args:
            frame: BGR video frame (H×W×3 uint8 numpy array).
            **kwargs:
                timestamp (float): Unix epoch timestamp.
                external_detections (List[Dict]): Pre-computed person bboxes
                    with key ``bbox`` [x1, y1, x2, y2].

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

        # ----- Step 1: Get person centroids -----
        if external_detections:
            centroids = self._centroids_from_external(external_detections)
        else:
            centroids = self._detect_person_centroids(frame)

        # ----- Step 2: Update tracker -----
        objects = self.tracker.update(centroids)

        # ----- Step 3: Check crossings -----
        crossing_events: List[Dict[str, Any]] = []

        for oid, centroid in objects.items():
            prev = self.tracker.previous.get(oid, centroid)
            if prev == centroid:
                continue  # no movement

            for tw in self.tripwires:
                # Skip if this ID already crossed this specific tripwire
                if oid in self.crossed_ids and tw["name"] in self.crossed_ids[oid]:
                    continue

                crossed, direction = self._check_crossing(
                    prev, centroid, tw["p1"], tw["p2"]
                )
                if crossed:
                    label = tw["direction_label"].get(direction, direction)
                    if label == "entry":
                        self.entry_count += 1
                    else:
                        self.exit_count += 1

                    self.crossed_ids.setdefault(oid, set()).add(tw["name"])

                    crossing_events.append({
                        "track_id": oid,
                        "centroid": list(centroid),
                        "previous_centroid": list(prev),
                        "tripwire": tw["name"],
                        "direction": label,
                        "label": "person",
                        "confidence": 0.85,
                    })

        # Purge stale crossed_ids for deregistered objects
        active_ids = set(objects.keys())
        for stale_id in list(self.crossed_ids.keys()):
            if stale_id not in active_ids:
                del self.crossed_ids[stale_id]

        triggered = len(crossing_events) > 0

        metadata = {
            "total_tracked": len(objects),
            "crossings_this_frame": len(crossing_events),
            "cumulative_entries": self.entry_count,
            "cumulative_exits": self.exit_count,
            "tripwires_configured": len(self.tripwires),
            "timestamp": timestamp,
        }

        if triggered:
            logger.info(
                f"BOUNDARY CROSSING — {len(crossing_events)} crossing(s) detected "
                f"[entries={self.entry_count}, exits={self.exit_count}]"
            )

        return {
            "triggered": triggered,
            "detections": crossing_events,
            "metadata": metadata,
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _check_crossing(
        p_prev: Tuple[int, int],
        p_curr: Tuple[int, int],
        line_a: Tuple[int, int],
        line_b: Tuple[int, int],
    ) -> Tuple[bool, str]:
        """
        Determine whether the segment (p_prev → p_curr) intersects the
        tripwire segment (line_a → line_b) using parameterised line-segment
        intersection.

        Direction is inferred from the sign of the cross product of the
        line direction vector and the movement vector:
            positive → "positive" label direction
            negative → "negative" label direction

        Returns:
            (crossed: bool, direction: str)
        """
        # Unpack
        x1, y1 = float(p_prev[0]), float(p_prev[1])
        x2, y2 = float(p_curr[0]), float(p_curr[1])
        x3, y3 = float(line_a[0]), float(line_a[1])
        x4, y4 = float(line_b[0]), float(line_b[1])

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-10:
            return False, ""

        t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
        u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            # Cross product to determine direction
            # Line direction vector: (x4-x3, y4-y3)
            # Movement vector:       (x2-x1, y2-y1)
            cross = (x4 - x3) * (y2 - y1) - (y4 - y3) * (x2 - x1)
            direction = "positive" if cross >= 0 else "negative"
            return True, direction

        return False, ""

    # ------------------------------------------------------------------
    # Person detection helpers
    # ------------------------------------------------------------------
    def _detect_person_centroids(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int]]:
        """
        Detect person-sized foreground objects via MOG2 background subtraction
        and return their centroids.
        """
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
            # Basic person aspect-ratio filter
            if h / max(w, 1) < 1.0:
                continue
            cx = x + w // 2
            cy = y + h // 2
            centroids.append((cx, cy))

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
