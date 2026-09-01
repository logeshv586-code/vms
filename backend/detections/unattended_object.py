"""
Unattended Object Detection Module
====================================

Detects objects that appear to have been left unattended in a scene. The
algorithm uses a dual background subtraction approach:

1. **Long-term model** (slow learning rate): Captures the permanent
   background. New objects remain as foreground for a long time.
2. **Short-term model** (fast learning rate): Adapts quickly so that newly
   stationary objects are absorbed into its background.

Stationary foreground = regions present in the long-term foreground but
absent from the short-term foreground (i.e., the object has been still
long enough for the short-term model to absorb it but not the long-term
model).

A stationary region is classified as "unattended" only if no detected
person bounding box overlaps or is within a configurable proximity
distance.

Kaggle Dataset Suggestion:
    - ABODA (Abandoned Object Detection) Dataset
      https://www.kaggle.com/datasets/... (ABODA)
      Annotated sequences of abandoned luggage and packages in public
      areas. Ideal for training unattended object detectors.

Usage:
    config = {
        "confidence_threshold": 0.5,
        "stationary_time_threshold": 30,  # seconds
        "person_proximity_px": 120,       # pixels
        "min_object_area": 1500,
        "max_object_area": 80000,
        "min_person_area": 2500,
        "long_term_history": 1000,
        "short_term_history": 100,
    }
    detector = UnattendedObjectDetector(config=config)
    result = detector.detect(frame, timestamp=time.time())
"""

import logging
import time
from typing import Dict, Any, List, Tuple

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class UnattendedObjectDetector(BaseDetector):
    """
    Detects objects left unattended in the scene.

    Uses dual background subtractors (long-term and short-term) to identify
    stationary foreground regions. If a stationary region persists beyond
    ``stationary_time_threshold`` seconds and no person is detected within
    ``person_proximity_px`` pixels, an unattended-object alert is triggered.

    Attributes:
        stationary_time_threshold (float): Seconds an object must remain
            stationary before being flagged.
        person_proximity_px (float): Max pixel distance for a person to be
            considered "nearby" (suppresses the alert).
        bg_long: MOG2 background subtractor with slow learning rate.
        bg_short: MOG2 background subtractor with fast learning rate.
        stationary_candidates (Dict): Tracks candidate stationary regions
            keyed by a spatial hash with first-seen timestamps.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(name="unattended_object", config=config)

    # ------------------------------------------------------------------
    # Model / resource loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """Initialise dual background subtractors and detection parameters."""
        self.stationary_time_threshold: float = self.config.get(
            "stationary_time_threshold", 30.0
        )
        self.person_proximity_px: float = self.config.get(
            "person_proximity_px", 120.0
        )
        self.min_object_area: int = self.config.get("min_object_area", 1500)
        self.max_object_area: int = self.config.get("max_object_area", 80000)
        self.min_person_area: int = self.config.get("min_person_area", 2500)

        long_history = self.config.get("long_term_history", 1000)
        short_history = self.config.get("short_term_history", 100)

        # Long-term BGS — slow adaptation, keeps new objects as foreground
        self.bg_long = cv2.createBackgroundSubtractorMOG2(
            history=long_history, varThreshold=50, detectShadows=True,
        )
        # Short-term BGS — fast adaptation, absorbs stationary objects quickly
        self.bg_short = cv2.createBackgroundSubtractorMOG2(
            history=short_history, varThreshold=50, detectShadows=True,
        )

        # Person detection BGS (separate so it doesn't interfere)
        self.bg_person = cv2.createBackgroundSubtractorMOG2(
            history=500, varThreshold=50, detectShadows=True,
        )

        # Stationary candidate tracking: key = spatial hash, value = dict
        self.stationary_candidates: Dict[str, Dict[str, Any]] = {}

        # Spatial hash grid cell size for matching candidates across frames
        self._grid_cell: int = self.config.get("grid_cell_size", 40)

        logger.info(
            f"UnattendedObjectDetector loaded — stationary threshold="
            f"{self.stationary_time_threshold}s, person proximity="
            f"{self.person_proximity_px}px."
        )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Run unattended-object detection on a single video frame.

        Args:
            frame: BGR video frame (H×W×3 uint8 numpy array).
            **kwargs:
                timestamp (float): Unix epoch timestamp.
                external_person_detections (List[Dict]): Pre-computed person
                    bounding boxes with key ``bbox`` [x1, y1, x2, y2].

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
        external_persons: List[Dict] = kwargs.get(
            "external_person_detections", []
        )

        # ----- Step 1: Compute foreground masks -----
        fg_long = self._apply_bg_model(frame, self.bg_long)
        fg_short = self._apply_bg_model(frame, self.bg_short)

        # Stationary mask: present in long-term FG but NOT in short-term FG
        # (object has been still long enough for the short model to absorb it)
        stationary_mask = cv2.bitwise_and(fg_long, cv2.bitwise_not(fg_short))

        # Clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        stationary_mask = cv2.morphologyEx(
            stationary_mask, cv2.MORPH_CLOSE, kernel, iterations=2
        )
        stationary_mask = cv2.morphologyEx(
            stationary_mask, cv2.MORPH_OPEN, kernel, iterations=1
        )

        # ----- Step 2: Find candidate stationary contours -----
        contours, _ = cv2.findContours(
            stationary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        current_candidates: Dict[str, Dict[str, Any]] = {}
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_object_area or area > self.max_object_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            cx, cy = x + w // 2, y + h // 2
            key = self._spatial_key(cx, cy)

            # Match with existing candidate or create new
            if key in self.stationary_candidates:
                cand = self.stationary_candidates[key]
                cand["bbox"] = [x, y, x + w, y + h]
                cand["centroid"] = (cx, cy)
                cand["area"] = area
                cand["last_seen"] = timestamp
                current_candidates[key] = cand
            else:
                current_candidates[key] = {
                    "first_seen": timestamp,
                    "last_seen": timestamp,
                    "bbox": [x, y, x + w, y + h],
                    "centroid": (cx, cy),
                    "area": area,
                }

        self.stationary_candidates = current_candidates

        # ----- Step 3: Detect persons (for proximity check) -----
        if external_persons:
            person_centroids = [
                (
                    int((d["bbox"][0] + d["bbox"][2]) / 2),
                    int((d["bbox"][1] + d["bbox"][3]) / 2),
                )
                for d in external_persons
                if "bbox" in d and len(d["bbox"]) == 4
            ]
        else:
            person_centroids = self._detect_person_centroids(frame)

        # ----- Step 4: Evaluate each candidate -----
        detections: List[Dict[str, Any]] = []
        for key, cand in self.stationary_candidates.items():
            dwell = cand["last_seen"] - cand["first_seen"]
            if dwell < self.stationary_time_threshold:
                continue

            # Check proximity to any person
            obj_cx, obj_cy = cand["centroid"]
            nearby_person = False
            for pcx, pcy in person_centroids:
                dist = np.hypot(pcx - obj_cx, pcy - obj_cy)
                if dist <= self.person_proximity_px:
                    nearby_person = True
                    break

            if not nearby_person:
                confidence = min(1.0, dwell / (self.stationary_time_threshold * 2))
                if confidence >= self.confidence_threshold:
                    detections.append({
                        "bbox": cand["bbox"],
                        "centroid": [obj_cx, obj_cy],
                        "stationary_duration_s": round(dwell, 1),
                        "area": cand["area"],
                        "label": "unattended_object",
                        "confidence": round(confidence, 3),
                        "nearby_person": False,
                    })

        triggered = len(detections) > 0

        metadata = {
            "stationary_candidates": len(self.stationary_candidates),
            "unattended_alerts": len(detections),
            "persons_detected": len(person_centroids),
            "stationary_threshold_s": self.stationary_time_threshold,
            "person_proximity_px": self.person_proximity_px,
            "timestamp": timestamp,
        }

        if triggered:
            logger.warning(
                f"UNATTENDED OBJECT — {len(detections)} object(s) flagged "
                f"as unattended (>{self.stationary_time_threshold}s stationary, "
                f"no nearby person)."
            )

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": metadata,
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Background subtraction helper
    # ------------------------------------------------------------------
    @staticmethod
    def _apply_bg_model(
        frame: np.ndarray, bg_model: Any
    ) -> np.ndarray:
        """Apply a background subtractor and return a clean binary mask."""
        fg = bg_model.apply(frame)
        _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
        return fg

    # ------------------------------------------------------------------
    # Person detection helper
    # ------------------------------------------------------------------
    def _detect_person_centroids(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int]]:
        """
        Detect person-sized foreground objects and return centroids.
        Uses a dedicated background subtractor to avoid interference with
        the dual-model stationary object detection.
        """
        fg = self.bg_person.apply(frame)
        _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=2)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(
            fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        centroids: List[Tuple[int, int]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_person_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            # Person heuristic: taller than wide
            if h / max(w, 1) < 1.0:
                continue
            centroids.append((x + w // 2, y + h // 2))

        return centroids

    # ------------------------------------------------------------------
    # Spatial hashing
    # ------------------------------------------------------------------
    def _spatial_key(self, cx: int, cy: int) -> str:
        """
        Return a grid-cell key string for the given centroid.
        Nearby centroids in the same grid cell share the same key,
        enabling frame-to-frame matching of stationary candidates.
        """
        gx = cx // self._grid_cell
        gy = cy // self._grid_cell
        return f"{gx}_{gy}"
