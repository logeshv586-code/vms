import logging
from typing import Dict, Any, List, Tuple
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class CrowdDetectionDetector(BaseDetector):
    """
    Detects crowd formation, measures crowd density per spatial zone,
    and identifies crowd-flow anomalies.

    Detection Strategy:
        1. Person Counting — Uses a YOLO model to detect all *person*
           instances in the frame.  The total count is compared against
           a configurable crowd threshold (default 20).
        2. Zone-Based Density — The frame is divided into an NxM grid.
           Person centroids are mapped to grid cells, producing a
           density heat-map that highlights congestion hot-spots.
        3. Crowd Flow Anomaly — Dense optical flow (Farneback) is
           computed.  If the dominant flow direction changes abruptly
           or the variance of flow angles exceeds a threshold, a
           crowd-flow anomaly is flagged (e.g. stampede, counter-flow).

    Kaggle Dataset Sourcing Suggestion:
        ShanghaiTech Crowd Counting Dataset
        https://www.kaggle.com/datasets/tthien/shanghaitech
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._prev_gray: np.ndarray | None = None
        super().__init__("crowd_detection", config)

    # ------------------------------------------------------------------ #
    #  Model loading
    # ------------------------------------------------------------------ #
    def load_model(self) -> None:
        """
        Loads a YOLOv8 model for person detection and reads crowd
        configuration parameters.
        """
        # Crowd thresholds
        self._crowd_threshold = self.config.get("crowd_threshold", 20)
        self._grid_cols = self.config.get("grid_cols", 4)
        self._grid_rows = self.config.get("grid_rows", 3)
        self._zone_density_threshold = self.config.get("zone_density_threshold", 5)
        self._flow_angle_var_threshold = self.config.get("flow_angle_var_threshold", 1.2)

        # YOLO person detector
        model_path = self.config.get("model_path", "yolov8n.pt")
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            logger.info("YOLOv8 model loaded for CrowdDetectionDetector (%s).", model_path)
        except Exception as e:
            logger.error("Failed to load YOLO model for crowd detection: %s", e)
            self.model = None

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
    def _detect_persons(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Run YOLO inference and return a list of person detections."""
        if self.model is None:
            return []

        results = self.model(frame, verbose=False)
        persons: List[Dict[str, Any]] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                if self.model.names[cls_id].lower() != "person":
                    continue
                conf = float(box.conf[0])
                if conf < self.confidence_threshold:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                persons.append({
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(conf, 3),
                    "label": "person",
                    "centroid": (cx, cy),
                })
        return persons

    def _compute_zone_density(
        self, persons: List[Dict[str, Any]], frame_w: int, frame_h: int
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        Map person centroids onto an NxM grid and return:
            - density_map: 2-D numpy array (rows × cols) of counts
            - hot_zones: list of zones exceeding the density threshold
        """
        density = np.zeros((self._grid_rows, self._grid_cols), dtype=np.int32)
        cell_w = frame_w / self._grid_cols
        cell_h = frame_h / self._grid_rows

        for p in persons:
            cx, cy = p["centroid"]
            col = min(int(cx / cell_w), self._grid_cols - 1)
            row = min(int(cy / cell_h), self._grid_rows - 1)
            density[row, col] += 1

        hot_zones = []
        for r in range(self._grid_rows):
            for c in range(self._grid_cols):
                if density[r, c] >= self._zone_density_threshold:
                    hot_zones.append({
                        "zone": f"R{r}C{c}",
                        "row": r,
                        "col": c,
                        "count": int(density[r, c]),
                        "bbox": [
                            int(c * cell_w), int(r * cell_h),
                            int((c + 1) * cell_w), int((r + 1) * cell_h),
                        ],
                    })

        return density, hot_zones

    def _compute_flow_anomaly(self, cur_gray: np.ndarray) -> Dict[str, Any]:
        """
        Compute dense optical flow and check for crowd-flow anomalies by
        measuring the circular variance of the dominant flow angles.
        """
        if self._prev_gray is None:
            self._prev_gray = cur_gray
            return {"anomaly": False, "angle_variance": 0.0, "mean_magnitude": 0.0}

        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray, cur_gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
        )
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        # Focus on areas with meaningful motion
        motion_mask = mag > 1.0
        if np.sum(motion_mask) < 50:
            self._prev_gray = cur_gray
            return {"anomaly": False, "angle_variance": 0.0, "mean_magnitude": 0.0}

        active_angles = ang[motion_mask]
        mean_mag = float(np.mean(mag[motion_mask]))

        # Circular variance: 1 - |mean resultant length|
        sin_sum = np.mean(np.sin(active_angles))
        cos_sum = np.mean(np.cos(active_angles))
        resultant_length = np.sqrt(sin_sum ** 2 + cos_sum ** 2)
        circ_var = 1.0 - resultant_length  # range [0, 1]

        anomaly = circ_var > self._flow_angle_var_threshold
        self._prev_gray = cur_gray

        return {
            "anomaly": anomaly,
            "angle_variance": round(float(circ_var), 4),
            "mean_magnitude": round(mean_mag, 3),
        }

    # ------------------------------------------------------------------ #
    #  Main detection pipeline
    # ------------------------------------------------------------------ #
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Count persons, compute zone density, and check for crowd-flow
        anomalies.

        Args:
            frame: BGR video frame.
            **kwargs:
                stream_id (str): Camera identifier.
                timestamp (float): Epoch timestamp.
                crowd_threshold (int): Override default threshold at
                    call-time.

        Returns:
            Standardised detection dict.
        """
        if not self.is_enabled:
            return {"triggered": False, "detections": [], "metadata": {}, "event_type": self.name}

        h, w = frame.shape[:2]
        cur_threshold = kwargs.get("crowd_threshold", self._crowd_threshold)

        # 1. Person detection
        external_detections = kwargs.get("external_detections", [])
        if external_detections:
            persons = []
            for det in external_detections:
                label = det.get("label", det.get("class", ""))
                if label == "person":
                    bbox = det.get("bbox", [0, 0, w, h])
                    cx, cy = det.get("centroid", ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2))
                    persons.append({
                        "bbox": bbox,
                        "confidence": float(det.get("confidence", 1.0)),
                        "label": "person",
                        "centroid": (cx, cy),
                    })
        else:
            persons = self._detect_persons(frame)
        person_count = len(persons)

        # 2. Zone density
        density_map, hot_zones = self._compute_zone_density(persons, w, h)

        # 3. Crowd flow anomaly
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        flow_info = self._compute_flow_anomaly(gray)

        # 4. Trigger evaluation
        count_exceeded = person_count >= cur_threshold
        has_hot_zone = len(hot_zones) > 0
        flow_anomaly = flow_info["anomaly"]
        triggered = count_exceeded or flow_anomaly

        detections: List[Dict[str, Any]] = []
        if count_exceeded:
            detections.append({
                "label": "crowd",
                "confidence": round(min(1.0, person_count / cur_threshold), 3),
                "bbox": [0, 0, w, h],
            })
        for zone in hot_zones:
            detections.append({
                "label": "crowd_hotspot",
                "confidence": round(min(1.0, zone["count"] / self._zone_density_threshold), 3),
                "bbox": zone["bbox"],
            })

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "person_count": person_count,
                "crowd_threshold": cur_threshold,
                "density_map": density_map.tolist(),
                "hot_zones": hot_zones,
                "flow_anomaly": flow_info,
                "count_exceeded": count_exceeded,
            },
            "event_type": self.name,
        }
