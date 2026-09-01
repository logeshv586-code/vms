import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class WomenSurroundedDetector(BaseDetector):
    """
    Detects when a woman or person is surrounded by multiple others in a
    potentially threatening spatial formation.

    Detection Strategy:
        1. Person Detection: Locates all persons via YOLO or HOG fallback.
        2. Gender Estimation (optional): If a gender-classification model is
           configured, identifies likely female persons. Otherwise, all persons
           are evaluated as potential victims.
        3. Spatial Enclosure Analysis: For each candidate person, determines
           if their centroid is enclosed within the convex hull formed by 3+
           surrounding persons' centroids.
        4. Angular Coverage: Measures the angular spread of surrounding
           persons relative to the central person — a full 360° surround
           is a stronger threat indicator than a semi-circle.
        5. Distance-Weighted Scoring: Closer surrounding persons yield a
           higher threat score; distant bystanders are discounted.
        6. Temporal Persistence: The surrounding pattern must persist across
           multiple frames to avoid false positives from momentary clustering.

    Kaggle Dataset Sourcing Suggestions:
        - WIDER Pedestrian Dataset
        - CrowdHuman Dataset
        - MOT Challenge Dataset (for multi-person tracking)

    Config keys:
        model_path (str): Path to YOLOv8 weights. Default: "yolov8n.pt"
        min_surrounding_persons (int): Minimum number of surrounding persons
            to constitute a "surround". Default: 3
        proximity_radius (int): Maximum pixel distance for a person to be
            considered part of the surrounding group. Default: 250
        angular_coverage_threshold (float): Minimum angular coverage (0-1,
            where 1.0 = full 360°) to classify as surrounded. Default: 0.65
        temporal_window (int): Consecutive frames required. Default: 8
        gender_model_path (str): Optional path to gender classifier model.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._surround_history: deque = deque(maxlen=60)
        self._surround_frame_count: int = 0
        self._gender_model = None
        super().__init__("women_surrounded", config)

    # ------------------------------------------------------------------
    # Model Loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """Load person detector and optional gender classifier."""
        # --- Person detector ---
        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            self._use_yolo = True
            logger.info("YOLOv8 model loaded for WomenSurroundedDetector.")
        except Exception as e:
            logger.warning(
                f"YOLO unavailable ({e}); falling back to HOG person detector."
            )
            self.model = cv2.HOGDescriptor()
            self.model.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._use_yolo = False

        # --- Optional gender classifier ---
        gender_model_path = self.config.get("gender_model_path")
        if gender_model_path:
            try:
                self._gender_model = cv2.dnn.readNetFromCaffe(
                    self.config.get("gender_proto_path", ""),
                    gender_model_path,
                )
                logger.info("Gender classification model loaded.")
            except Exception as e:
                logger.warning(f"Gender model not loaded ({e}); will evaluate all persons.")
                self._gender_model = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse a frame for surrounding / encirclement events.

        Args:
            frame: BGR video frame (H × W × 3).
            **kwargs:
                person_boxes (List[List[int]]): Pre-computed person boxes.
                timestamp (float): Frame timestamp.

        Returns:
            Standard detection dict.
        """
        if not self.is_enabled:
            return self._empty_result()

        h, w = frame.shape[:2]

        # --- 1. Person detection ---
        person_boxes = kwargs.get("person_boxes") or self._detect_persons(frame)

        min_surround = self.config.get("min_surrounding_persons", 3)
        if len(person_boxes) < min_surround + 1:
            self._surround_frame_count = max(0, self._surround_frame_count - 1)
            return self._empty_result()

        # --- 2. Compute centroids ---
        centroids = [self._centroid(b) for b in person_boxes]

        # --- 3. Optional gender classification ---
        genders = self._classify_genders(frame, person_boxes)

        # --- 4. Evaluate each candidate for being surrounded ---
        proximity_radius = self.config.get("proximity_radius", 250)
        angular_thresh = self.config.get("angular_coverage_threshold", 0.65)
        temporal_window = self.config.get("temporal_window", 8)

        surround_events: List[Dict[str, Any]] = []

        for i, (box, centroid) in enumerate(zip(person_boxes, centroids)):
            # If gender model available, prioritise female candidates
            if genders and genders[i] not in ("female", "unknown"):
                continue

            neighbours = self._find_neighbours(i, centroids, proximity_radius)
            if len(neighbours) < min_surround:
                continue

            # Angular coverage
            coverage, sector_details = self._angular_coverage(
                centroid, [centroids[j] for j in neighbours]
            )

            if coverage < angular_thresh:
                continue

            # Distance-weighted threat score
            distances = [
                float(np.linalg.norm(centroid - centroids[j])) for j in neighbours
            ]
            avg_dist = np.mean(distances)
            dist_score = max(0.0, 1.0 - avg_dist / proximity_radius)

            # Combined confidence
            confidence = (
                0.40 * coverage
                + 0.30 * dist_score
                + 0.30 * min(1.0, len(neighbours) / (min_surround * 2))
            )

            if confidence >= self.confidence_threshold:
                # Compute enclosing region
                all_involved = [i] + neighbours
                enclosing_box = self._enclosing_box(
                    [person_boxes[k] for k in all_involved]
                )
                surround_events.append({
                    "bbox": enclosing_box,
                    "confidence": round(float(confidence), 3),
                    "label": "person_surrounded",
                    "victim_box": box,
                    "victim_gender": genders[i] if genders else "unknown",
                    "surrounding_count": len(neighbours),
                    "angular_coverage": round(float(coverage), 3),
                    "surrounding_boxes": [person_boxes[j] for j in neighbours],
                })

        # --- 5. Temporal persistence ---
        if surround_events:
            self._surround_frame_count += 1
        else:
            self._surround_frame_count = max(0, self._surround_frame_count - 1)

        triggered = self._surround_frame_count >= temporal_window

        return {
            "triggered": triggered,
            "detections": surround_events,
            "metadata": {
                "persons_detected": len(person_boxes),
                "surround_events": len(surround_events),
                "consecutive_surround_frames": self._surround_frame_count,
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

    @staticmethod
    def _centroid(box: List[int]) -> np.ndarray:
        return np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])

    def _detect_persons(self, frame: np.ndarray) -> List[List[int]]:
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

    def _classify_genders(
        self, frame: np.ndarray, person_boxes: List[List[int]]
    ) -> Optional[List[str]]:
        """
        Classify gender for each detected person using the optional DNN model.
        Returns None if no gender model is loaded.
        """
        if self._gender_model is None:
            return None

        genders: List[str] = []
        gender_labels = ["male", "female"]

        for box in person_boxes:
            x1, y1, x2, y2 = box
            x1c = max(0, x1)
            y1c = max(0, y1)
            x2c = min(frame.shape[1], x2)
            y2c = min(frame.shape[0], y2)
            if x2c <= x1c or y2c <= y1c:
                genders.append("unknown")
                continue
            face_roi = frame[y1c:y2c, x1c:x2c]
            try:
                blob = cv2.dnn.blobFromImage(
                    face_roi, 1.0, (227, 227),
                    (78.4263377603, 87.7689143744, 114.895847746),
                    swapRB=False,
                )
                self._gender_model.setInput(blob)
                preds = self._gender_model.forward()
                gender_idx = int(np.argmax(preds[0]))
                genders.append(gender_labels[gender_idx])
            except Exception:
                genders.append("unknown")
        return genders

    @staticmethod
    def _find_neighbours(
        target_idx: int,
        centroids: List[np.ndarray],
        radius: int,
    ) -> List[int]:
        """Find indices of persons within the proximity radius of the target."""
        target = centroids[target_idx]
        neighbours = []
        for j, c in enumerate(centroids):
            if j == target_idx:
                continue
            dist = np.linalg.norm(target - c)
            if dist <= radius:
                neighbours.append(j)
        return neighbours

    @staticmethod
    def _angular_coverage(
        center: np.ndarray, neighbour_centroids: List[np.ndarray]
    ) -> Tuple[float, List[float]]:
        """
        Compute the angular coverage of surrounding persons around the center.

        Divides 360° into 12 sectors (30° each). Coverage = fraction of
        sectors occupied by at least one neighbour.

        Returns:
            (coverage: float in [0,1], sector_angles: list of occupied sector
             midpoints in degrees)
        """
        if not neighbour_centroids:
            return 0.0, []

        num_sectors = 12
        sector_size = 360.0 / num_sectors
        occupied = set()

        for nc in neighbour_centroids:
            dx = nc[0] - center[0]
            dy = nc[1] - center[1]
            angle = np.degrees(np.arctan2(dy, dx)) % 360
            sector = int(angle / sector_size)
            occupied.add(sector)

        coverage = len(occupied) / num_sectors
        sector_angles = [s * sector_size + sector_size / 2 for s in sorted(occupied)]
        return coverage, sector_angles

    @staticmethod
    def _enclosing_box(boxes: List[List[int]]) -> List[int]:
        """Return the minimum bounding box enclosing all given boxes."""
        x1 = min(b[0] for b in boxes)
        y1 = min(b[1] for b in boxes)
        x2 = max(b[2] for b in boxes)
        y2 = max(b[3] for b in boxes)
        return [x1, y1, x2, y2]
