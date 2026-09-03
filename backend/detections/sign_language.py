"""Realtime hand-gesture / emergency-signal detector.

Temporal SOS state is isolated per camera.  MediaPipe landmarks are the trusted
realtime backend.  The OpenCV contour fallback remains useful for visual
analytics, but by default it cannot create security alerts because skin-colour
and convexity heuristics are not reliable enough for that decision.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

from .base_detector import BaseDetector
from .hand_gesture_classifier import GESTURE_VOCABULARY, HandGestureClassifier

logger = logging.getLogger(__name__)

try:
    import mediapipe as mp
    _MP_AVAILABLE = True
except ImportError:
    mp = None
    _MP_AVAILABLE = False
    logger.info("mediapipe unavailable; gesture detector will use analytics-only contour fallback")

try:
    from services.face_db_service import face_db_service as _db
    _DB_AVAILABLE = True
except ImportError:
    _db = None
    _DB_AVAILABLE = False


class SignLanguageDetector(BaseDetector):
    """Detect hand gestures with camera-isolated temporal SOS state."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._mp_hands = None
        self._classifier: Optional[HandGestureClassifier] = None
        self._stream_state: Dict[str, Deque[bool]] = {}
        self._lock = threading.RLock()
        super().__init__("sign_language", config)

    def load_model(self) -> None:
        self._gesture_vocab = self.config.get("gesture_vocab", GESTURE_VOCABULARY)
        self.min_detection_confidence = float(self.config.get("min_detection_confidence", 0.7))
        self.min_tracking_confidence = float(self.config.get("min_tracking_confidence", 0.5))
        self.max_num_hands = max(1, int(self.config.get("max_num_hands", 2)))
        self.sos_wave_window = max(4, int(self.config.get("sos_wave_window", 15)))
        self.sos_wave_threshold = max(2, int(self.config.get("sos_wave_threshold", 3)))
        self.skin_lower = np.array(self.config.get("skin_lower_hsv", [0, 30, 60]))
        self.skin_upper = np.array(self.config.get("skin_upper_hsv", [20, 150, 255]))
        self.min_contour_area = max(100, int(self.config.get("min_contour_area", 5000)))
        self.enable_db_logging = bool(self.config.get("enable_db_logging", True))
        self.alert_categories = set(self.config.get("alert_categories", ["help", "threat"]))
        self.allow_fallback_alerts = bool(self.config.get("allow_fallback_alerts", False))
        self._classifier = HandGestureClassifier(model_path=self.config.get("asl_model_path"))

        if _MP_AVAILABLE and mp is not None:
            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_num_hands,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
            )
            logger.info("MediaPipe Hands loaded for gesture detection")
        else:
            logger.warning("Gesture security alerts disabled: MediaPipe backend unavailable")

    @property
    def backend_name(self) -> str:
        return "mediapipe" if self._mp_hands is not None else "opencv_contour_analytics_only"

    def health(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.is_enabled,
            "backend": self.backend_name,
            "security_alerts_available": self._mp_hands is not None or self.allow_fallback_alerts,
            "camera_state_count": len(self._stream_state),
        }

    def reset_stream(self, stream_id: str) -> None:
        self._stream_state.pop(str(stream_id or "unknown"), None)

    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        if not self.is_enabled or not kwargs.get("camera_toggle_active", True):
            return self._empty_result("detection_toggle_off")
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return self._empty_result("invalid_frame")

        stream_id = str(kwargs.get("stream_id", kwargs.get("camera_id", "unknown")))
        timestamp = float(kwargs.get("timestamp", time.time()))
        trusted_backend = self._mp_hands is not None

        try:
            with self._lock:
                if trusted_backend:
                    detections, hand_states = self._detect_mediapipe(frame)
                else:
                    detections, hand_states = self._detect_contour_fallback(frame)
        except Exception as exc:
            logger.exception("Gesture inference failed for %s: %s", stream_id, exc)
            result = self._empty_result("inference_error")
            result["metadata"]["error"] = str(exc)
            return result

        # One temporal state per frame, per camera. This prevents multiple hands
        # in one frame or unrelated cameras from manufacturing wave transitions.
        buffer = self._stream_state.setdefault(stream_id, deque(maxlen=self.sos_wave_window))
        if hand_states:
            buffer.append(any(hand_states))
        else:
            buffer.append(False)

        transitions = 0
        if len(buffer) >= 4:
            values = list(buffer)
            transitions = sum(values[idx] != values[idx - 1] for idx in range(1, len(values)))

        sos_triggered = trusted_backend and transitions >= self.sos_wave_threshold
        if sos_triggered:
            detections.append(
                {
                    "bbox": [0, 0, frame.shape[1], frame.shape[0]],
                    "confidence": round(min(1.0, transitions / float(self.sos_wave_threshold + 2)), 4),
                    "label": "sos_wave",
                    "category": "help",
                    "gesture_info": self._gesture_vocab.get("sos_wave", {}),
                    "asl_letter": None,
                    "backend": self.backend_name,
                }
            )

        help_gestures = [item for item in detections if item.get("category") == "help"]
        threat_gestures = [item for item in detections if item.get("category") == "threat"]
        asl_gestures = [item for item in detections if item.get("category") == "asl"]
        accessibility = [item for item in detections if item.get("category") == "accessibility"]

        alert_candidates = [
            item for item in detections if item.get("category") in self.alert_categories
        ]
        alert_trusted = trusted_backend or self.allow_fallback_alerts
        alert_triggered = bool(alert_candidates) and alert_trusted

        if self.enable_db_logging and _DB_AVAILABLE and _db is not None:
            for det in detections:
                if det.get("category") not in {"help", "threat", "asl", "accessibility"}:
                    continue
                try:
                    _db.insert_gesture(
                        stream_id=stream_id,
                        gesture=det.get("label", "unknown"),
                        category=det.get("category", "unknown"),
                        confidence=float(det.get("confidence", 0.0) or 0.0),
                        bbox=det.get("bbox"),
                        fingers_up=det.get("fingers_up"),
                        asl_letter=det.get("asl_letter"),
                        timestamp=timestamp,
                    )
                except Exception as exc:
                    logger.warning("Gesture audit log write failed: %s", exc)

        if alert_triggered:
            strongest = max(alert_candidates, key=lambda item: float(item.get("confidence", 0.0) or 0.0))
            try:
                from services.event_dispatcher import dispatch_confirmed_event

                label = str(strongest.get("label", "emergency_gesture"))
                category = str(strongest.get("category", "help"))
                severity = "critical" if category == "threat" or label == "sos_wave" else "high"
                dispatch_confirmed_event(
                    stream_id,
                    "Gesture Detection",
                    severity,
                    f"Confirmed {category} gesture: {label}",
                    rule_id=8,
                    confidence=float(strongest.get("confidence", 0.0) or 0.0),
                    data={"gesture": label, "category": category, "backend": self.backend_name},
                )
            except Exception as exc:
                logger.exception("Failed to dispatch gesture event for %s: %s", stream_id, exc)

        return {
            "triggered": bool(detections),
            "alert_triggered": alert_triggered,
            "detections": detections,
            "metadata": {
                "total_hands_detected": len(hand_states),
                "gestures_detected": len(detections),
                "help_signals": len(help_gestures),
                "threat_signals": len(threat_gestures),
                "asl_events": len(asl_gestures),
                "accessibility_events": len(accessibility),
                "sos_wave_detected": sos_triggered,
                "wave_transitions": transitions,
                "stream_id": stream_id,
                "timestamp": timestamp,
                "backend": self.backend_name,
                "security_alerts_available": alert_trusted,
            },
            "event_type": self.name,
        }

    def _detect_mediapipe(self, frame: np.ndarray) -> Tuple[List[Dict[str, Any]], List[bool]]:
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._mp_hands.process(rgb)
        detections: List[Dict[str, Any]] = []
        hand_states: List[bool] = []
        if not results.multi_hand_landmarks:
            return detections, hand_states

        handedness_list = results.multi_handedness or []
        for hand_idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
            landmarks = hand_landmarks.landmark
            xs = [landmark.x for landmark in landmarks]
            ys = [landmark.y for landmark in landmarks]
            x1 = max(0, int(min(xs) * width) - 10)
            y1 = max(0, int(min(ys) * height) - 10)
            x2 = min(width, int(max(xs) * width) + 10)
            y2 = min(height, int(max(ys) * height) + 10)

            hand_side = "Right"
            if hand_idx < len(handedness_list):
                hand_side = handedness_list[hand_idx].classification[0].label

            gesture_label, category, confidence = self._classifier.classify(hand_landmarks, hand_side)
            fingers_up = HandGestureClassifier._fingers_extended(landmarks, hand_side)
            hand_states.append(sum(fingers_up) >= 4)
            asl_letter = gesture_label.replace("asl_", "") if category == "asl" and gesture_label.startswith("asl_") else None
            detections.append(
                {
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(float(confidence), 4),
                    "label": gesture_label,
                    "category": category,
                    "fingers_up": [bool(value) for value in fingers_up],
                    "asl_letter": asl_letter,
                    "hand_side": hand_side,
                    "gesture_info": self._gesture_vocab.get(gesture_label, {}),
                    "backend": self.backend_name,
                }
            )
        return detections, hand_states

    def _detect_contour_fallback(self, frame: np.ndarray) -> Tuple[List[Dict[str, Any]], List[bool]]:
        detections: List[Dict[str, Any]] = []
        hand_states: List[bool] = []
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.skin_lower, self.skin_upper)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            if cv2.contourArea(contour) < self.min_contour_area:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if not 0.3 <= width / max(height, 1) <= 2.5:
                continue
            hull_indices = cv2.convexHull(contour, returnPoints=False)
            try:
                defects = cv2.convexityDefects(contour, hull_indices)
            except cv2.error:
                defects = None

            finger_count = 0
            if defects is not None:
                for idx in range(defects.shape[0]):
                    start_idx, end_idx, far_idx, depth = defects[idx, 0]
                    start = tuple(contour[start_idx][0])
                    end = tuple(contour[end_idx][0])
                    far = tuple(contour[far_idx][0])
                    side_a = math.dist(start, end)
                    side_b = math.dist(start, far)
                    side_c = math.dist(end, far)
                    denominator = 2 * side_b * side_c
                    if denominator == 0:
                        continue
                    cosine = (side_b ** 2 + side_c ** 2 - side_a ** 2) / denominator
                    angle = math.acos(max(-1.0, min(1.0, cosine)))
                    if angle <= math.pi / 2 and depth > 5000:
                        finger_count += 1
            finger_count = min(finger_count + 1, 5)
            hand_states.append(finger_count >= 4)
            if finger_count >= 5:
                label, category = "open_palm", "help"
            elif finger_count <= 1:
                label, category = "hand_shape", "neutral"
            else:
                label, category = "unknown", "neutral"
            detections.append(
                {
                    "bbox": [x, y, x + width, y + height],
                    "confidence": 0.35,
                    "label": label,
                    "category": category,
                    "finger_count_estimate": finger_count,
                    "asl_letter": None,
                    "gesture_info": self._gesture_vocab.get(label, {}),
                    "backend": self.backend_name,
                    "analytics_only": not self.allow_fallback_alerts,
                }
            )
        return detections, hand_states

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "triggered": False,
            "alert_triggered": False,
            "detections": [],
            "metadata": {"skipped": reason, "backend": self.backend_name},
            "event_type": self.name,
        }
