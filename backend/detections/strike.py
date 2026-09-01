import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class StrikeDetector(BaseDetector):
    """
    Detects organised strikes, protests, and demonstrations in video feeds.

    Detection Strategy:
        1. Crowd Density Estimation: Counts persons in the frame and computes
           an occupancy ratio. A protest requires a minimum crowd size.
        2. Banner / Placard Detection: Detects rectangular, high-contrast
           objects held above head-level using contour analysis, aspect-ratio
           filtering, and colour-saturation checks (banners are often brightly
           coloured).
        3. Uniform Clothing Colour: Computes colour histograms in the upper
           torso region of each person. High similarity across a group
           suggests coordinated attire — a protest indicator.
        4. Crowd Movement Analysis: Uses sparse optical flow (Lucas-Kanade)
           to detect coherent unidirectional movement (marching) vs. normal
           random pedestrian motion.
        5. Temporal Persistence: Requires indicators to persist across a
           configurable number of frames to avoid false positives from brief
           gatherings.

    Kaggle Dataset Sourcing Suggestions:
        - Protest Activity Detection Dataset
        - UCLA Protest Image Dataset
        - CrowdHuman Dataset (for crowd density)

    Config keys:
        model_path (str): Path to YOLOv8 weights. Default: "yolov8n.pt"
        min_crowd_size (int): Minimum persons to consider a crowd. Default: 8
        banner_min_area (int): Minimum contour area for a banner. Default: 3000
        banner_aspect_range (Tuple[float,float]): Width/Height aspect ratio
            range for banner shapes. Default: (2.0, 8.0)
        colour_similarity_threshold (float): Histogram correlation above
            which two torsos are considered "similar". Default: 0.70
        uniform_group_fraction (float): Fraction of the crowd wearing
            similar colours to flag coordinated dress. Default: 0.40
        coherent_motion_threshold (float): Fraction of flow vectors that
            must agree in direction (±30°) to count as marching. Default: 0.55
        temporal_window (int): Consecutive frames for persistence. Default: 10
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._prev_gray: Optional[np.ndarray] = None
        self._prev_keypoints: Optional[np.ndarray] = None
        self._indicator_history: deque = deque(maxlen=60)
        self._strike_frame_count: int = 0
        super().__init__("strike", config)

    # ------------------------------------------------------------------
    # Model Loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """Load YOLOv8 or fall back to HOG person detector."""
        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            self._use_yolo = True
            logger.info("YOLOv8 model loaded for StrikeDetector.")
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
        Analyse a frame for protest / strike activity.

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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # --- 1. Person detection & crowd density ---
        person_boxes = kwargs.get("person_boxes") or self._detect_persons(frame)
        min_crowd = self.config.get("min_crowd_size", 8)
        crowd_present = len(person_boxes) >= min_crowd
        crowd_density = len(person_boxes) / max(1, (h * w) / (200 * 400))

        # --- 2. Banner / placard detection ---
        banners = self._detect_banners(frame, gray, person_boxes, h, w)

        # --- 3. Uniform clothing colour analysis ---
        uniform_score = self._analyse_clothing_uniformity(frame, person_boxes)

        # --- 4. Coherent crowd motion ---
        motion_coherence = self._analyse_crowd_motion(gray)

        # --- 5. Composite scoring ---
        crowd_score = min(1.0, len(person_boxes) / max(1, min_crowd * 2))
        banner_score = min(1.0, len(banners) / 3.0)  # 3+ banners → max
        motion_score = motion_coherence

        composite = (
            0.30 * crowd_score
            + 0.25 * banner_score
            + 0.20 * uniform_score
            + 0.25 * motion_score
        )

        # --- 6. Temporal persistence ---
        temporal_window = self.config.get("temporal_window", 10)
        strike_threshold = self.config.get("strike_score_threshold", 0.50)

        if composite >= strike_threshold and crowd_present:
            self._strike_frame_count += 1
        else:
            self._strike_frame_count = max(0, self._strike_frame_count - 1)

        triggered = self._strike_frame_count >= temporal_window

        # --- 7. Build detections ---
        detections: List[Dict[str, Any]] = []
        if triggered or composite >= strike_threshold:
            # Report overall crowd region
            if person_boxes:
                all_x1 = min(b[0] for b in person_boxes)
                all_y1 = min(b[1] for b in person_boxes)
                all_x2 = max(b[2] for b in person_boxes)
                all_y2 = max(b[3] for b in person_boxes)
                detections.append({
                    "bbox": [all_x1, all_y1, all_x2, all_y2],
                    "confidence": round(float(composite), 3),
                    "label": "strike_protest",
                })
            # Report individual banners
            for banner in banners:
                detections.append({
                    "bbox": banner["bbox"],
                    "confidence": round(banner["confidence"], 3),
                    "label": "banner_placard",
                })

        self._prev_gray = gray
        self._indicator_history.append(composite)

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "persons_detected": len(person_boxes),
                "crowd_density": round(crowd_density, 2),
                "banners_detected": len(banners),
                "uniform_clothing_score": round(uniform_score, 3),
                "motion_coherence": round(motion_coherence, 3),
                "composite_score": round(composite, 3),
                "consecutive_strike_frames": self._strike_frame_count,
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

    def _detect_banners(
        self,
        frame: np.ndarray,
        gray: np.ndarray,
        person_boxes: List[List[int]],
        h: int,
        w: int,
    ) -> List[Dict[str, Any]]:
        """
        Detect rectangular banner / placard shapes above person heads.
        Uses edge detection + contour filtering for high-aspect-ratio rectangles.
        """
        min_area = self.config.get("banner_min_area", 3000)
        ar_lo, ar_hi = self.config.get("banner_aspect_range", (2.0, 8.0))

        # Focus on the upper portion of the frame (banners are usually held high)
        upper_region = gray[: int(h * 0.6), :]
        blurred = cv2.GaussianBlur(upper_region, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 3))
        edges = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        banners: List[Dict[str, Any]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, cw, ch = cv2.boundingRect(cnt)
            if ch == 0:
                continue
            aspect = cw / ch
            if ar_lo <= aspect <= ar_hi:
                # Check colour saturation — banners tend to be colourful
                roi_hsv = cv2.cvtColor(frame[y:y + ch, x:x + cw], cv2.COLOR_BGR2HSV)
                mean_sat = float(np.mean(roi_hsv[:, :, 1]))
                confidence = min(1.0, (mean_sat / 128.0) * (area / (min_area * 3)))
                banners.append({
                    "bbox": [int(x), int(y), int(x + cw), int(y + ch)],
                    "confidence": confidence,
                    "area": area,
                    "aspect_ratio": round(aspect, 2),
                })
        return banners

    def _analyse_clothing_uniformity(
        self, frame: np.ndarray, person_boxes: List[List[int]]
    ) -> float:
        """
        Compute colour-histogram similarity across the upper-torso region
        of detected persons to identify uniform/coordinated dress.

        Returns a score in [0, 1] indicating the fraction of persons with
        similar clothing colours.
        """
        if len(person_boxes) < 3:
            return 0.0

        sim_thresh = self.config.get("colour_similarity_threshold", 0.70)
        uniform_frac = self.config.get("uniform_group_fraction", 0.40)

        histograms: List[np.ndarray] = []
        for box in person_boxes:
            x1, y1, x2, y2 = box
            bh = y2 - y1
            # Upper 40 % of person box ≈ torso
            torso_y1 = y1 + int(bh * 0.15)
            torso_y2 = y1 + int(bh * 0.55)
            torso_y1 = max(0, torso_y1)
            torso_y2 = min(frame.shape[0], torso_y2)
            x1c = max(0, x1)
            x2c = min(frame.shape[1], x2)
            if torso_y2 <= torso_y1 or x2c <= x1c:
                continue
            roi = frame[torso_y1:torso_y2, x1c:x2c]
            hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv_roi], [0, 1], None, [18, 8], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            histograms.append(hist)

        if len(histograms) < 3:
            return 0.0

        # Pairwise correlation
        n = len(histograms)
        similar_count = 0
        total_pairs = 0
        for i in range(n):
            for j in range(i + 1, n):
                corr = cv2.compareHist(histograms[i], histograms[j], cv2.HISTCMP_CORREL)
                total_pairs += 1
                if corr >= sim_thresh:
                    similar_count += 1

        similarity_ratio = similar_count / max(1, total_pairs)
        return min(1.0, similarity_ratio / uniform_frac)

    def _analyse_crowd_motion(self, gray: np.ndarray) -> float:
        """
        Analyse motion coherence using sparse Lucas-Kanade optical flow.
        Returns a score in [0, 1] representing the fraction of flow vectors
        that agree in direction — high coherence indicates marching.
        """
        coherence_thresh = self.config.get("coherent_motion_threshold", 0.55)

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_keypoints = cv2.goodFeaturesToTrack(
                gray, maxCorners=200, qualityLevel=0.01, minDistance=10
            )
            return 0.0

        if self._prev_keypoints is None or len(self._prev_keypoints) < 10:
            self._prev_keypoints = cv2.goodFeaturesToTrack(
                gray, maxCorners=200, qualityLevel=0.01, minDistance=10
            )
            return 0.0

        new_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            self._prev_gray, gray, self._prev_keypoints, None
        )
        if new_pts is None:
            self._prev_keypoints = cv2.goodFeaturesToTrack(
                gray, maxCorners=200, qualityLevel=0.01, minDistance=10
            )
            return 0.0

        good_mask = status.flatten() == 1
        old_good = self._prev_keypoints[good_mask]
        new_good = new_pts[good_mask]

        if len(old_good) < 5:
            self._prev_keypoints = cv2.goodFeaturesToTrack(
                gray, maxCorners=200, qualityLevel=0.01, minDistance=10
            )
            return 0.0

        # Flow vectors
        dx = new_good[:, 0, 0] - old_good[:, 0, 0]
        dy = new_good[:, 0, 1] - old_good[:, 0, 1]
        magnitudes = np.sqrt(dx ** 2 + dy ** 2)
        angles = np.arctan2(dy, dx) * 180 / np.pi  # degrees

        # Filter out near-static points
        moving = magnitudes > 1.0
        if np.sum(moving) < 5:
            self._prev_keypoints = cv2.goodFeaturesToTrack(
                gray, maxCorners=200, qualityLevel=0.01, minDistance=10
            )
            return 0.0

        moving_angles = angles[moving]

        # Find dominant direction via histogram
        hist, bin_edges = np.histogram(moving_angles, bins=36, range=(-180, 180))
        dominant_bin = np.argmax(hist)
        dominant_angle = (bin_edges[dominant_bin] + bin_edges[dominant_bin + 1]) / 2.0

        # Count how many vectors agree within ±30°
        angle_diff = np.abs(moving_angles - dominant_angle)
        angle_diff = np.minimum(angle_diff, 360 - angle_diff)
        agreeing = np.sum(angle_diff < 30)
        coherence = agreeing / len(moving_angles)

        # Refresh keypoints periodically
        self._prev_keypoints = cv2.goodFeaturesToTrack(
            gray, maxCorners=200, qualityLevel=0.01, minDistance=10
        )

        return float(coherence)
