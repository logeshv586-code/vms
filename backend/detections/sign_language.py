import logging
import math
import time
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np

from .base_detector import BaseDetector
from .hand_gesture_classifier import HandGestureClassifier, GESTURE_VOCABULARY

logger = logging.getLogger(__name__)

# Optional MediaPipe dependency
try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False
    logger.info(
        "mediapipe not installed. SignLanguageDetector will use "
        "OpenCV contour-based hand detection as fallback."
    )

# Optional DB service
try:
    from services.face_db_service import face_db_service as _db
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False
    _db = None


class SignLanguageDetector(BaseDetector):
    """
    Detects sign-language and hand gestures across three domains:

    1. **Help / SOS signals** — open palm, SOS wave, call-me, distress fist
    2. **Criminal / threat gestures** — gun sign, throat slash, fist, middle finger
    3. **ASL / deaf-community** — A-Z letters (rule-based landmarks), digits 0-9,
       common ASL words (HELP, POLICE, FIRE, STOP, YES, NO, WATER, PAIN)

    Uses **MediaPipe Hands** (21 landmarks) when available, with a skin-colour
    segmentation + contour analysis fallback when MediaPipe is absent.

    All detections are persisted to the gesture_log table via FaceDBService.

    Kaggle Dataset Sourcing (Option A — gallery reference, no training required):
        • ASL Alphabet:
          https://www.kaggle.com/datasets/grassknoted/asl-alphabet
        • Indian Sign Language:
          https://www.kaggle.com/datasets/vaishnaviasonawane/indian-sign-language-dataset

    Config options:
        gesture_vocab (dict): Override the default gesture vocabulary.
        min_detection_confidence (float): MediaPipe detection confidence. Default: 0.7
        min_tracking_confidence (float): MediaPipe tracking confidence.  Default: 0.5
        max_num_hands (int): Max simultaneous hands to detect. Default: 2
        sos_wave_window (int): Frames to analyse for SOS wave. Default: 15
        sos_wave_threshold (int): Transitions needed to trigger SOS. Default: 3
        skin_lower_hsv (list): Lower HSV bound for skin segmentation. Default: [0,30,60]
        skin_upper_hsv (list): Upper HSV bound for skin segmentation. Default: [20,150,255]
        min_contour_area (int): Minimum hand-contour area in pixels. Default: 5000
        asl_model_path (str): Optional path to trained ASL CNN .h5 file.
        enable_db_logging (bool): Persist gestures to SQLite. Default: True
        alert_categories (list): Categories that trigger security alerts.
                                 Default: ["help", "threat"]
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._mp_hands = None
        self._classifier: Optional[HandGestureClassifier] = None
        self._hand_state_buffer: List[bool] = []
        super().__init__("sign_language", config)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        self._gesture_vocab = self.config.get("gesture_vocab", GESTURE_VOCABULARY)
        self.min_detection_confidence = self.config.get("min_detection_confidence", 0.7)
        self.min_tracking_confidence = self.config.get("min_tracking_confidence", 0.5)
        self.max_num_hands = self.config.get("max_num_hands", 2)
        self.sos_wave_window = self.config.get("sos_wave_window", 15)
        self.sos_wave_threshold = self.config.get("sos_wave_threshold", 3)
        self.skin_lower = np.array(self.config.get("skin_lower_hsv", [0, 30, 60]))
        self.skin_upper = np.array(self.config.get("skin_upper_hsv", [20, 150, 255]))
        self.min_contour_area = self.config.get("min_contour_area", 5000)
        self.enable_db_logging = self.config.get("enable_db_logging", True)
        self.alert_categories = self.config.get("alert_categories", ["help", "threat"])

        # Initialise gesture classifier (rule-based; optional CNN)
        asl_model_path = self.config.get("asl_model_path", None)
        self._classifier = HandGestureClassifier(model_path=asl_model_path)

        if _MP_AVAILABLE:
            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_num_hands,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
            )
            logger.info("MediaPipe Hands loaded for SignLanguageDetector.")
        else:
            logger.info("Using OpenCV contour fallback for hand detection.")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Detect and classify hand gestures in *frame*.

        Kwargs:
            stream_id (str): Camera identifier.
            timestamp (float): Frame epoch timestamp.
            camera_toggle_active (bool): Skip if False. Default: True.
        """
        camera_toggle_active = kwargs.get("camera_toggle_active", True)
        if not self.is_enabled or not camera_toggle_active:
            return {
                "triggered": False,
                "detections": [],
                "metadata": {"skipped": "detection_toggle_off"},
                "event_type": self.name,
            }

        stream_id = kwargs.get("stream_id", "unknown")
        timestamp = kwargs.get("timestamp", time.time())

        if _MP_AVAILABLE and self._mp_hands is not None:
            detections, hand_states = self._detect_mediapipe(frame)
        else:
            detections, hand_states = self._detect_contour_fallback(frame)

        # ── SOS wave detection (temporal) ───────────────────────────────────
        sos_triggered = False
        for state in hand_states:
            self._hand_state_buffer.append(state)
        self._hand_state_buffer = self._hand_state_buffer[-self.sos_wave_window:]

        if len(self._hand_state_buffer) >= 4:
            transitions = sum(
                1
                for i in range(1, len(self._hand_state_buffer))
                if self._hand_state_buffer[i] != self._hand_state_buffer[i - 1]
            )
            if transitions >= self.sos_wave_threshold:
                sos_triggered = True
                detections.append(
                    {
                        "bbox": [0, 0, frame.shape[1], frame.shape[0]],
                        "confidence": round(min(1.0, transitions / (self.sos_wave_threshold + 2)), 4),
                        "label": "sos_wave",
                        "category": "help",
                        "gesture_info": GESTURE_VOCABULARY.get("sos_wave", {}),
                        "asl_letter": None,
                    }
                )

        # ── Categorise results ──────────────────────────────────────────────
        help_gestures = [d for d in detections if d.get("category") == "help"]
        threat_gestures = [d for d in detections if d.get("category") == "threat"]
        asl_gestures = [d for d in detections if d.get("category") == "asl"]
        accessibility_gestures = [d for d in detections if d.get("category") == "accessibility"]

        triggered = any(
            d.get("category") in self.alert_categories for d in detections
        ) or sos_triggered

        # ── Persist to DB ───────────────────────────────────────────────────
        if self.enable_db_logging and _DB_AVAILABLE and _db is not None:
            for det in detections:
                if det.get("category") in ("help", "threat", "asl", "accessibility"):
                    try:
                        _db.insert_gesture(
                            stream_id=stream_id,
                            gesture=det["label"],
                            category=det["category"],
                            confidence=det["confidence"],
                            bbox=det.get("bbox"),
                            fingers_up=det.get("fingers_up"),
                            asl_letter=det.get("asl_letter"),
                            timestamp=timestamp,
                        )
                    except Exception as e:
                        logger.error("Failed to log gesture to DB: %s", e)

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "total_hands_detected": len(hand_states),
                "gestures_detected": len(detections),
                "help_signals": len(help_gestures),
                "threat_signals": len(threat_gestures),
                "asl_events": len(asl_gestures),
                "accessibility_events": len(accessibility_gestures),
                "sos_wave_detected": sos_triggered,
                "stream_id": stream_id,
                "timestamp": timestamp,
            },
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # MediaPipe pipeline
    # ------------------------------------------------------------------

    def _detect_mediapipe(
        self, frame: np.ndarray
    ) -> Tuple[List[Dict[str, Any]], List[bool]]:
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._mp_hands.process(rgb)

        detections: List[Dict[str, Any]] = []
        hand_states: List[bool] = []

        if not results.multi_hand_landmarks:
            return detections, hand_states

        handedness_list = results.multi_handedness or []

        for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            lm = hand_landmarks.landmark

            # Bounding box
            xs = [l.x for l in lm]
            ys = [l.y for l in lm]
            x1 = max(0, int(min(xs) * w) - 10)
            y1 = max(0, int(min(ys) * h) - 10)
            x2 = min(w, int(max(xs) * w) + 10)
            y2 = min(h, int(max(ys) * h) + 10)

            # Determine hand side
            hand_side = "Right"
            if hand_idx < len(handedness_list):
                hand_side = handedness_list[hand_idx].classification[0].label

            # Classify using HandGestureClassifier
            gesture_label, category, confidence = self._classifier.classify(
                hand_landmarks, hand_side
            )

            # Track open/closed for SOS wave
            fingers_up = HandGestureClassifier._fingers_extended(lm, hand_side)
            is_open = sum(fingers_up) >= 4
            hand_states.append(is_open)

            # Extract ASL letter if applicable
            asl_letter = None
            if category == "asl" and gesture_label.startswith("asl_"):
                asl_letter = gesture_label.replace("asl_", "")

            gesture_info = self._gesture_vocab.get(gesture_label, {})

            detections.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(confidence, 4),
                    "label": gesture_label,
                    "category": category,
                    "fingers_up": [bool(f) for f in fingers_up],
                    "asl_letter": asl_letter,
                    "hand_side": hand_side,
                    "gesture_info": gesture_info,
                }
            )

        return detections, hand_states

    # ------------------------------------------------------------------
    # Contour-based fallback
    # ------------------------------------------------------------------

    def _detect_contour_fallback(
        self, frame: np.ndarray
    ) -> Tuple[List[Dict[str, Any]], List[bool]]:
        """
        Skin-colour segmentation + contour analysis fallback.
        Estimates finger count from convexity defects.
        """
        detections: List[Dict[str, Any]] = []
        hand_states: List[bool] = []

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.skin_lower, self.skin_upper)

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_contour_area:
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect_ratio = cw / max(ch, 1)
            if not (0.3 <= aspect_ratio <= 2.5):
                continue

            hull_indices = cv2.convexHull(cnt, returnPoints=False)
            try:
                defects = cv2.convexityDefects(cnt, hull_indices)
            except cv2.error:
                defects = None

            finger_count = 0
            if defects is not None:
                for i in range(defects.shape[0]):
                    s, e, f, d = defects[i, 0]
                    start = tuple(cnt[s][0])
                    end = tuple(cnt[e][0])
                    far = tuple(cnt[f][0])

                    a = math.dist(start, end)
                    b = math.dist(start, far)
                    c = math.dist(end, far)

                    denom = 2 * b * c
                    if denom == 0:
                        continue
                    cos_angle = (b ** 2 + c ** 2 - a ** 2) / denom
                    angle = math.acos(max(-1.0, min(1.0, cos_angle)))

                    if angle <= math.pi / 2 and d > 5000:
                        finger_count += 1

            finger_count = min(finger_count + 1, 5)
            is_open = finger_count >= 4
            hand_states.append(is_open)

            if finger_count >= 5:
                gesture_label, category = "open_palm", "help"
            elif finger_count == 0:
                gesture_label, category = "fist", "threat"
            elif finger_count == 1:
                gesture_label, category = "pointing", "neutral"
            else:
                gesture_label, category = "unknown", "neutral"

            detections.append(
                {
                    "bbox": [x, y, x + cw, y + ch],
                    "confidence": 0.6,
                    "label": gesture_label,
                    "category": category,
                    "finger_count_estimate": finger_count,
                    "asl_letter": None,
                    "gesture_info": self._gesture_vocab.get(gesture_label, {}),
                }
            )

        return detections, hand_states
