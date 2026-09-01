"""
Intrusion Detection Module
==========================

Detects unauthorized entry into restricted zones defined as configurable
polygon regions on the video frame. When a detected person's bounding box
centroid enters a restricted zone polygon, an intrusion alert is triggered.

Supports multiple zones with different security levels (e.g., critical,
high, medium, low).

Kaggle Dataset Suggestion:
    - PETS 2009 Benchmark Dataset
      https://www.kaggle.com/datasets/... (PETS 2009 Benchmark Data)
      Multi-sensor surveillance sequences for pedestrian tracking and
      crowd density estimation. Ideal for training intrusion zone models.

Usage:
    config = {
        "confidence_threshold": 0.5,
        "zones": [
            {
                "name": "Server Room Entrance",
                "polygon": [[100, 200], [400, 200], [400, 500], [100, 500]],
                "security_level": "critical"
            },
            {
                "name": "Parking Lot Perimeter",
                "polygon": [[500, 100], [800, 100], [800, 600], [500, 600]],
                "security_level": "high"
            }
        ],
        "person_detection_method": "contour",  # "contour" or "yolo"
        "min_person_area": 3000,
    }
    detector = IntrusionDetectionDetector(config=config)
    result = detector.detect(frame, timestamp=time.time())
"""

import logging
import time
from typing import Dict, Any, List, Tuple

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class IntrusionDetectionDetector(BaseDetector):
    """
    Detects unauthorized entry into restricted zones.

    Restricted zones are defined as polygon regions on the video frame.
    The detector identifies persons in the frame (via contour analysis or
    an optional YOLO model), computes each person's bounding box centroid,
    and checks whether the centroid falls inside any restricted zone polygon
    using OpenCV's pointPolygonTest.

    Each zone can be assigned a security level (critical, high, medium, low)
    which is included in the event metadata for downstream severity routing.

    Attributes:
        zones (List[Dict]): List of zone definitions, each containing:
            - name (str): Human-readable zone label.
            - polygon (List[List[int]]): Ordered vertices [[x,y], ...].
            - security_level (str): One of critical/high/medium/low.
        bg_subtractor: MOG2 background subtractor for person silhouette extraction.
        min_person_area (int): Minimum contour area to consider as a person.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(name="intrusion_detection", config=config)

    # ------------------------------------------------------------------
    # Model / resource loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """
        Initialise zone polygons, background subtractor, and optional YOLO
        model for person detection.
        """
        # Parse zone definitions from config
        raw_zones = self.config.get("zones", [])
        self.zones: List[Dict[str, Any]] = []
        for z in raw_zones:
            polygon_pts = np.array(z["polygon"], dtype=np.int32)
            self.zones.append({
                "name": z.get("name", "Unnamed Zone"),
                "polygon": polygon_pts,
                "security_level": z.get("security_level", "medium"),
            })

        if not self.zones:
            logger.warning(
                "IntrusionDetectionDetector: No zones configured. "
                "Add zones via config['zones'] for meaningful detection."
            )

        # Background subtractor for person silhouette extraction
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=50,
            detectShadows=True,
        )

        # Minimum contour area to classify as a person-sized object
        self.min_person_area: int = self.config.get("min_person_area", 3000)

        # Optional: load YOLO model for higher-accuracy person detection
        self._person_detection_method: str = self.config.get(
            "person_detection_method", "contour"
        )
        if self._person_detection_method == "yolo":
            try:
                from ultralytics import YOLO
                model_path = self.config.get("yolo_model_path", "yolov8n.pt")
                self.model = YOLO(model_path)
                logger.info("IntrusionDetectionDetector: YOLO model loaded.")
            except ImportError:
                logger.warning(
                    "ultralytics not installed — falling back to contour method."
                )
                self._person_detection_method = "contour"
        else:
            self.model = None

        logger.info(
            f"IntrusionDetectionDetector loaded with {len(self.zones)} zone(s), "
            f"person detection method='{self._person_detection_method}'."
        )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Run intrusion detection on a single video frame.

        Args:
            frame: BGR video frame (H×W×3 uint8 numpy array).
            **kwargs:
                timestamp (float): Unix epoch timestamp of the frame.
                external_detections (List[Dict]): Pre-computed person bounding
                    boxes from an upstream detector. Each dict should contain
                    keys ``bbox`` [x1, y1, x2, y2] and optionally ``confidence``.

        Returns:
            Dict with keys:
                triggered (bool): True if any person centroid is inside a zone.
                detections (List[Dict]): Per-person detection records.
                metadata (Dict): Intrusion-specific metadata.
                event_type (str): ``"intrusion_detection"``.
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

        # ----- Step 1: Obtain person bounding boxes -----
        if external_detections:
            person_boxes = self._parse_external_detections(external_detections)
        elif self._person_detection_method == "yolo" and self.model is not None:
            person_boxes = self._detect_persons_yolo(frame)
        else:
            person_boxes = self._detect_persons_contour(frame)

        # ----- Step 2: Check each person against each zone -----
        detections: List[Dict[str, Any]] = []
        violated_zones: List[Dict[str, Any]] = []

        for bbox in person_boxes:
            x1, y1, x2, y2 = bbox["bbox"]
            confidence = bbox.get("confidence", 0.0)
            cx = int((x1 + x2) / 2)
            cy = int((y1 + y2) / 2)

            for zone in self.zones:
                # pointPolygonTest returns +1 inside, 0 on edge, -1 outside
                dist = cv2.pointPolygonTest(
                    zone["polygon"].reshape((-1, 1, 2)),
                    (float(cx), float(cy)),
                    measureDist=False,
                )
                if dist >= 0:  # inside or on edge
                    detection_record = {
                        "bbox": [x1, y1, x2, y2],
                        "centroid": [cx, cy],
                        "confidence": round(confidence, 3),
                        "label": "person",
                        "zone_name": zone["name"],
                        "security_level": zone["security_level"],
                    }
                    detections.append(detection_record)
                    violated_zones.append({
                        "zone_name": zone["name"],
                        "security_level": zone["security_level"],
                    })

        triggered = len(detections) > 0

        # Determine highest severity among violated zones
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        max_severity = "low"
        for vz in violated_zones:
            if severity_order.get(vz["security_level"], 0) > severity_order.get(max_severity, 0):
                max_severity = vz["security_level"]

        metadata = {
            "total_persons_detected": len(person_boxes),
            "intrusions_detected": len(detections),
            "violated_zones": violated_zones,
            "highest_severity": max_severity if triggered else None,
            "zones_configured": len(self.zones),
            "timestamp": timestamp,
            "detection_method": self._person_detection_method,
        }

        if triggered:
            logger.warning(
                f"INTRUSION DETECTED — {len(detections)} person(s) in "
                f"{len(set(vz['zone_name'] for vz in violated_zones))} zone(s) "
                f"[severity={max_severity}]"
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
    def _detect_persons_contour(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect person-sized objects using MOG2 background subtraction and
        contour analysis.

        Returns:
            List of dicts with keys ``bbox`` [x1, y1, x2, y2] and ``confidence``.
        """
        fg_mask = self.bg_subtractor.apply(frame)

        # Remove shadows (shadow pixels = 127 in MOG2)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        persons: List[Dict[str, Any]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_person_area:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            aspect_ratio = h / max(w, 1)

            # Simple heuristic: person bounding boxes are usually taller than
            # wide (aspect ratio > 1.2). This filters out vehicles, etc.
            if aspect_ratio < 1.0:
                continue

            # Confidence approximation based on area and aspect ratio
            confidence = min(1.0, area / (self.min_person_area * 5))
            if confidence < self.confidence_threshold:
                continue

            persons.append({
                "bbox": [x, y, x + w, y + h],
                "confidence": round(confidence, 3),
            })

        return persons

    def _detect_persons_yolo(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect persons using an Ultralytics YOLO model (class 0 = person).

        Returns:
            List of dicts with keys ``bbox`` [x1, y1, x2, y2] and ``confidence``.
        """
        results = self.model(frame, verbose=False)
        persons: List[Dict[str, Any]] = []

        for r in results:
            boxes = r.boxes
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i])
                conf = float(boxes.conf[i])
                if cls_id == 0 and conf >= self.confidence_threshold:  # person class
                    x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                    persons.append({
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "confidence": round(conf, 3),
                    })

        return persons

    @staticmethod
    def _parse_external_detections(
        external: List[Dict],
    ) -> List[Dict[str, Any]]:
        """Normalise externally supplied detections to internal format."""
        parsed: List[Dict[str, Any]] = []
        for det in external:
            bbox = det.get("bbox")
            if bbox is None or len(bbox) != 4:
                continue
            parsed.append({
                "bbox": [int(v) for v in bbox],
                "confidence": float(det.get("confidence", 0.0)),
            })
        return parsed
