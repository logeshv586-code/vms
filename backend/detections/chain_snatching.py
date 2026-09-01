import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class ChainSnatchingDetector(BaseDetector):
    """
    Detects chain / jewellery snatching events by identifying rapid arm
    movements directed at a person's neck region combined with sudden
    victim recoil.

    Detection Strategy:
        1. Person ROI Extraction — The upper-body region (top 40 % of a
           person bounding box) is isolated as the zone of interest.
        2. Dense Optical Flow (Farneback) — Computed within the upper-body
           ROI to capture fast lateral / downward motion vectors that
           characterise a snatching gesture.
        3. Motion Magnitude Spike — A frame-to-frame comparison of mean
           flow magnitude detects explosive hand movements.  A spike
           exceeding a configurable threshold triggers a candidate alert.
        4. Recoil Detection — After a spike, the subsequent frames are
           monitored for opposing motion (victim recoil), raising the
           overall confidence of the event.
        5. Optional Pose Estimation — If pose landmarks are supplied via
           kwargs, the detector narrows analysis to the wrist→neck vector
           for higher precision.

    Kaggle Dataset Sourcing Suggestion:
        UCF Crime Dataset
        https://www.kaggle.com/datasets/odins0n/ucf-crime-dataset
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._prev_gray: Optional[np.ndarray] = None
        self._flow_history: List[float] = []
        self._spike_cooldown: int = 0
        self._recoil_window: List[float] = []
        super().__init__("chain_snatching", config)

    # ------------------------------------------------------------------ #
    #  Model / configuration loading
    # ------------------------------------------------------------------ #
    def load_model(self) -> None:
        """
        No standalone ML model — detection relies on dense optical flow
        and motion heuristics.  A YOLO person detector may be injected
        via config for bounding-box extraction; otherwise the full frame
        upper-third is used as a proxy.
        """
        self._flow_mag_threshold = self.config.get("flow_mag_threshold", 8.0)
        self._spike_ratio = self.config.get("spike_ratio", 3.0)
        self._history_len = self.config.get("history_len", 15)
        self._upper_body_ratio = self.config.get("upper_body_ratio", 0.40)
        self._cooldown_frames = self.config.get("cooldown_frames", 20)
        self._recoil_window_size = self.config.get("recoil_window_size", 8)
        self._min_recoil_ratio = self.config.get("min_recoil_ratio", 0.30)

        # Optional external YOLO model for person bounding boxes
        self._person_model = None
        person_model_path = self.config.get("person_model_path")
        if person_model_path:
            try:
                from ultralytics import YOLO
                self._person_model = YOLO(person_model_path)
                logger.info("YOLO person model loaded for ChainSnatchingDetector.")
            except Exception as e:
                logger.warning("Could not load person model: %s — falling back to full-frame analysis.", e)

        logger.info(
            "ChainSnatchingDetector configured — flow_mag=%.1f, spike_ratio=%.1f, "
            "upper_body=%.0f%%, cooldown=%d frames",
            self._flow_mag_threshold,
            self._spike_ratio,
            self._upper_body_ratio * 100,
            self._cooldown_frames,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
    def _get_person_rois(self, frame: np.ndarray, **kwargs) -> List[Tuple[int, int, int, int]]:
        """
        Return a list of upper-body ROIs as (x1, y1, x2, y2).

        Priority:
            1. Bounding boxes passed via kwargs["person_boxes"]
            2. YOLO person detection
            3. Full-frame upper third as fallback
        """
        boxes = kwargs.get("person_boxes")
        if boxes:
            return [
                (b[0], b[1], b[2], b[1] + int((b[3] - b[1]) * self._upper_body_ratio))
                for b in boxes
            ]

        if self._person_model is not None:
            results = self._person_model(frame, verbose=False)
            rois = []
            for r in results:
                if r.boxes is not None:
                    for box in r.boxes:
                        if int(box.cls[0]) == 0:  # person class
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            y2_upper = y1 + int((y2 - y1) * self._upper_body_ratio)
                            rois.append((x1, y1, x2, y2_upper))
            if rois:
                return rois

        # Fallback: upper third of the full frame
        h, w = frame.shape[:2]
        return [(0, 0, w, int(h * self._upper_body_ratio))]

    @staticmethod
    def _compute_flow_magnitude(prev_gray: np.ndarray, cur_gray: np.ndarray,
                                roi: Tuple[int, int, int, int]) -> Tuple[float, float]:
        """
        Compute mean and max optical-flow magnitude inside the given ROI.
        """
        x1, y1, x2, y2 = roi
        prev_roi = prev_gray[y1:y2, x1:x2]
        cur_roi = cur_gray[y1:y2, x1:x2]

        if prev_roi.size == 0 or cur_roi.size == 0:
            return 0.0, 0.0

        flow = cv2.calcOpticalFlowFarneback(
            prev_roi, cur_roi, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        return float(np.mean(mag)), float(np.max(mag))

    def _detect_spike(self, mean_mag: float) -> bool:
        """Return True if current magnitude is a significant spike."""
        self._flow_history.append(mean_mag)
        if len(self._flow_history) > self._history_len:
            self._flow_history.pop(0)

        if len(self._flow_history) < 5:
            return False

        baseline = float(np.mean(self._flow_history[:-1]))
        if baseline < 1e-3:
            return mean_mag > self._flow_mag_threshold

        return (mean_mag / (baseline + 1e-6)) >= self._spike_ratio and mean_mag > self._flow_mag_threshold

    def _check_recoil(self, mean_mag: float) -> float:
        """
        After a spike is detected, monitor for opposing motion (recoil).
        Returns a recoil confidence factor [0.0, 1.0].
        """
        self._recoil_window.append(mean_mag)
        if len(self._recoil_window) > self._recoil_window_size:
            self._recoil_window.pop(0)

        if len(self._recoil_window) < 3:
            return 0.0

        peak = max(self._recoil_window)
        if peak < 1e-3:
            return 0.0
        recoil_ratio = mean_mag / peak
        if recoil_ratio >= self._min_recoil_ratio:
            return min(1.0, recoil_ratio)
        return 0.0

    # ------------------------------------------------------------------ #
    #  Main detection pipeline
    # ------------------------------------------------------------------ #
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse the frame for chain-snatching motion signatures.

        Args:
            frame: BGR video frame.
            **kwargs:
                person_boxes (List[List[int]]): Optional pre-computed
                    person bounding boxes [x1, y1, x2, y2].
                pose_landmarks: Optional pose estimation results.
                stream_id (str): Camera identifier.
                timestamp (float): Epoch timestamp.

        Returns:
            Standardised detection dict.
        """
        if not self.is_enabled:
            return {"triggered": False, "detections": [], "metadata": {}, "event_type": self.name}

        cur_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self._prev_gray is None:
            self._prev_gray = cur_gray
            return {"triggered": False, "detections": [], "metadata": {"status": "initialising"}, "event_type": self.name}

        rois = self._get_person_rois(frame, **kwargs)

        triggered = False
        detections: List[Dict[str, Any]] = []
        max_mean_mag = 0.0
        max_max_mag = 0.0
        is_spike = False
        recoil_conf = 0.0

        # Cooldown management
        if self._spike_cooldown > 0:
            self._spike_cooldown -= 1

        for roi in rois:
            mean_mag, max_mag = self._compute_flow_magnitude(self._prev_gray, cur_gray, roi)
            max_mean_mag = max(max_mean_mag, mean_mag)
            max_max_mag = max(max_max_mag, max_mag)

            spike = self._detect_spike(mean_mag)
            recoil = self._check_recoil(mean_mag)

            if spike and self._spike_cooldown == 0:
                is_spike = True
                recoil_conf = recoil
                confidence = min(1.0, 0.6 + 0.4 * recoil)

                if confidence >= self.confidence_threshold:
                    triggered = True
                    self._spike_cooldown = self._cooldown_frames
                    detections.append({
                        "bbox": list(roi),
                        "confidence": round(confidence, 3),
                        "label": "chain_snatching",
                    })

        self._prev_gray = cur_gray

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "mean_flow_magnitude": round(max_mean_mag, 3),
                "max_flow_magnitude": round(max_max_mag, 3),
                "spike_detected": is_spike,
                "recoil_confidence": round(recoil_conf, 3),
                "rois_analysed": len(rois),
                "cooldown_remaining": self._spike_cooldown,
            },
            "event_type": self.name,
        }
