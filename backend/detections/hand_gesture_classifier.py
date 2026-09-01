"""
Hand Gesture Classifier
========================
Rule-based and optional CNN-based classifier for:
  - ASL (American Sign Language) static hand-shape letters A-Z & digits 0-9
  - SOS / help signals
  - Criminal / threat gestures
  - Accessibility communication gestures for deaf/mute users

MediaPipe landmark indices (21 per hand):
  0=WRIST, 1-4=THUMB, 5-8=INDEX, 9-12=MIDDLE, 13-16=RING, 17-20=PINKY

Kaggle dataset used for gallery seeding (Option A):
  - ASL Alphabet: https://www.kaggle.com/datasets/grassknoted/asl-alphabet
    (87,000 images, 29 classes A-Z + space + del + nothing)
  - Indian Sign Language:
    https://www.kaggle.com/datasets/vaishnaviasonawane/indian-sign-language-dataset
"""

import logging
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ── MediaPipe landmark indices ────────────────────────────────────────────────
_WRIST       = 0
_THUMB_CMC   = 1;  _THUMB_MCP  = 2;  _THUMB_IP   = 3;  _THUMB_TIP  = 4
_INDEX_MCP   = 5;  _INDEX_PIP  = 6;  _INDEX_DIP  = 7;  _INDEX_TIP  = 8
_MIDDLE_MCP  = 9;  _MIDDLE_PIP = 10; _MIDDLE_DIP = 11; _MIDDLE_TIP = 12
_RING_MCP    = 13; _RING_PIP   = 14; _RING_DIP   = 15; _RING_TIP   = 16
_PINKY_MCP   = 17; _PINKY_PIP  = 18; _PINKY_DIP  = 19; _PINKY_TIP  = 20


# ── Gesture vocabulary ────────────────────────────────────────────────────────
# category: "help" | "threat" | "asl" | "accessibility" | "neutral"
GESTURE_VOCABULARY: Dict[str, Dict[str, str]] = {
    # ── Help / SOS ──────────────────────────────────────────────────────────
    "open_palm": {
        "description": "All five fingers extended — universal STOP / HELP signal",
        "category": "help",
        "emoji": "✋",
    },
    "sos_wave": {
        "description": "Rapid open-close hand motion — ITV SOS signal",
        "category": "help",
        "emoji": "🆘",
    },
    "call_me": {
        "description": "Pinky + thumb extended (phone shape) — distress call signal",
        "category": "help",
        "emoji": "🤙",
    },
    "distress_fist_raise": {
        "description": "Raised closed fist — silent domestic distress signal",
        "category": "help",
        "emoji": "✊",
    },
    # ── Criminal / Threat ───────────────────────────────────────────────────
    "gun_sign": {
        "description": "Index + thumb L-shape — weapon reference gesture",
        "category": "threat",
        "emoji": "🔫",
    },
    "fist": {
        "description": "All fingers curled — aggressive threat gesture",
        "category": "threat",
        "emoji": "👊",
    },
    "middle_finger": {
        "description": "Middle finger extended — offensive gesture",
        "category": "threat",
        "emoji": "🖕",
    },
    "throat_slash": {
        "description": "Index finger drawn across throat — threat gesture",
        "category": "threat",
        "emoji": "⚠️",
    },
    # ── Neutral / Contextual ────────────────────────────────────────────────
    "thumbs_up": {
        "description": "Thumb extended — positive / OK signal",
        "category": "neutral",
        "emoji": "👍",
    },
    "thumbs_down": {
        "description": "Thumb down — negative signal",
        "category": "neutral",
        "emoji": "👎",
    },
    "pointing": {
        "description": "Index finger extended — direction signal",
        "category": "neutral",
        "emoji": "☝️",
    },
    "peace_sign": {
        "description": "Index + middle extended — peace / victory sign",
        "category": "neutral",
        "emoji": "✌️",
    },
    "ok_sign": {
        "description": "Circle formed by thumb + index — OK gesture",
        "category": "neutral",
        "emoji": "👌",
    },
    # ── ASL Static Letters ──────────────────────────────────────────────────
    **{
        f"asl_{letter}": {
            "description": f"ASL letter {letter}",
            "category": "asl",
            "emoji": "🤟",
        }
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    },
    # ── ASL Digits ──────────────────────────────────────────────────────────
    **{
        f"asl_{digit}": {
            "description": f"ASL digit {digit}",
            "category": "asl",
            "emoji": "🔢",
        }
        for digit in range(10)
    },
    # ── Accessibility / Deaf-mute common signs ──────────────────────────────
    "help_sign": {
        "description": "ASL HELP — flat hand under thumb of other fist, both move up",
        "category": "accessibility",
        "emoji": "🆘",
    },
    "police_sign": {
        "description": "ASL POLICE — C-hand on chest",
        "category": "accessibility",
        "emoji": "👮",
    },
    "fire_sign": {
        "description": "ASL FIRE — fingers wiggle upward",
        "category": "accessibility",
        "emoji": "🔥",
    },
    "stop_sign": {
        "description": "ASL STOP — open hand chops down",
        "category": "accessibility",
        "emoji": "🛑",
    },
    "water_sign": {
        "description": "ASL WATER — W hand tapped on chin",
        "category": "accessibility",
        "emoji": "💧",
    },
    "pain_sign": {
        "description": "ASL PAIN — index fingers point at each other",
        "category": "accessibility",
        "emoji": "😣",
    },
    "yes_sign": {
        "description": "ASL YES — fist nodding",
        "category": "accessibility",
        "emoji": "✅",
    },
    "no_sign": {
        "description": "ASL NO — index + middle tap thumb",
        "category": "accessibility",
        "emoji": "❌",
    },
}


class HandGestureClassifier:
    """
    Classifies hand gestures from MediaPipe 21-landmark data.

    Priority order for classification:
      1. SOS / help signals  →  immediate alert
      2. Criminal / threat   →  security alert
      3. ASL letters (rule-based landmark analysis)
      4. Accessibility signs
      5. Neutral / unknown

    Usage:
        classifier = HandGestureClassifier()
        label, category, confidence = classifier.classify(landmarks, hand_side)
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Args:
            model_path: Optional path to a trained CNN .h5 model for ASL.
                        If None or unavailable, falls back to rule-based classification.
        """
        self._cnn_model = None
        self._use_cnn = False

        if model_path and os.path.isfile(model_path):
            try:
                # Lazy import to avoid hard dependency
                import tensorflow as tf  # type: ignore
                self._cnn_model = tf.keras.models.load_model(model_path)
                self._use_cnn = True
                logger.info("ASL CNN model loaded from %s", model_path)
            except Exception as e:
                logger.warning("CNN model load failed (%s); using rule-based classifier.", e)

    def classify(
        self,
        landmarks,              # MediaPipe NormalizedLandmarkList
        hand_side: str = "Right",
    ) -> Tuple[str, str, float]:
        """
        Classify a single hand's landmarks.

        Returns:
            (gesture_label, category, confidence)
        """
        if landmarks is None:
            return "unknown", "neutral", 0.0

        lm = landmarks.landmark
        fingers = self._fingers_extended(lm, hand_side)
        thumb, index, middle, ring, pinky = fingers
        finger_count = sum(fingers)

        # ── Priority 1: Help / SOS ──────────────────────────────────────────
        if all(fingers):
            return "open_palm", "help", 0.92

        # Call-me sign: thumb + pinky, others down
        if thumb and not index and not middle and not ring and pinky:
            return "call_me", "help", 0.88

        # ── Priority 2: Threat ──────────────────────────────────────────────
        if not any(fingers):
            return "fist", "threat", 0.90

        # Middle finger only
        if not thumb and not index and middle and not ring and not pinky:
            return "middle_finger", "threat", 0.90

        # Gun sign: thumb + index, others down
        if thumb and index and not middle and not ring and not pinky:
            # Distinguish from ASL L by checking thumb angle
            if self._is_gun_sign(lm):
                return "gun_sign", "threat", 0.82

        # ── Priority 3: ASL letter rules ────────────────────────────────────
        asl_result = self._classify_asl(lm, fingers, hand_side)
        if asl_result:
            label, confidence = asl_result
            return f"asl_{label}", "asl", confidence

        # ── Priority 4: Neutral gestures ────────────────────────────────────
        if thumb and not index and not middle and not ring and not pinky:
            # Determine up vs down from landmark y-coords
            if lm[_THUMB_TIP].y < lm[_WRIST].y:
                return "thumbs_up", "neutral", 0.88
            else:
                return "thumbs_down", "neutral", 0.85

        if not thumb and index and not middle and not ring and not pinky:
            return "pointing", "neutral", 0.88

        if not thumb and index and middle and not ring and not pinky:
            return "peace_sign", "neutral", 0.87

        if finger_count == 0:
            return "fist", "threat", 0.80

        return "unknown", "neutral", 0.40

    # ------------------------------------------------------------------
    # ASL rule-based classification
    # ------------------------------------------------------------------

    def _classify_asl(
        self,
        lm,
        fingers: List[bool],
        hand_side: str,
    ) -> Optional[Tuple[str, float]]:
        """
        Rule-based ASL static letter classifier using landmark geometry.
        Covers the most common letters with clear landmark distinctions.

        Returns (letter, confidence) or None.
        """
        thumb, index, middle, ring, pinky = fingers
        finger_count = sum(fingers)

        # ASL A: fist with thumb to side
        if not index and not middle and not ring and not pinky:
            if self._thumb_side(lm):
                return "A", 0.78

        # ASL B: four fingers up, thumb tucked across palm
        if not thumb and index and middle and ring and pinky:
            if self._thumb_across_palm(lm):
                return "B", 0.80

        # ASL C: curved hand (all fingers curved, forming C shape)
        if self._is_c_shape(lm):
            return "C", 0.72

        # ASL D: index up, middle+ring+pinky curled, thumb touching middle
        if not thumb and index and not middle and not ring and not pinky:
            if self._thumb_touches_middle(lm):
                return "D", 0.74

        # ASL E: all fingers curled tightly (different from A by thumb pos)
        if not any(fingers) and not self._thumb_side(lm):
            return "E", 0.70

        # ASL F: index + thumb touching, others up
        if not index and middle and ring and pinky and thumb:
            if self._index_thumb_touching(lm):
                return "F", 0.76

        # ASL G / H - pointing variants (handled separately)

        # ASL I: only pinky up
        if not thumb and not index and not middle and not ring and pinky:
            return "I", 0.85

        # ASL K: index + middle up in V, thumb between them
        if not thumb and index and middle and not ring and not pinky:
            if self._thumb_between_index_middle(lm):
                return "K", 0.74

        # ASL L: index + thumb up (L-shape)
        if thumb and index and not middle and not ring and not pinky:
            if not self._is_gun_sign(lm):  # gun sign has different angle
                return "L", 0.80

        # ASL O: all fingers form circle
        if self._is_o_shape(lm):
            return "O", 0.74

        # ASL R: index + middle crossed
        if not thumb and index and middle and not ring and not pinky:
            if self._fingers_crossed(lm):
                return "R", 0.72

        # ASL U: index + middle parallel up
        if not thumb and index and middle and not ring and not pinky:
            if not self._fingers_crossed(lm):
                return "U", 0.77

        # ASL V: same as U but spread wider (peace sign)
        # (already handled above as peace_sign in neutral)

        # ASL W: index + middle + ring up
        if not thumb and index and middle and ring and not pinky:
            return "W", 0.78

        # ASL Y: thumb + pinky up
        if thumb and not index and not middle and not ring and pinky:
            return "Y", 0.82

        return None

    # ------------------------------------------------------------------
    # Landmark geometry helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fingers_extended(lm, hand_side: str = "Right") -> List[bool]:
        """Returns [thumb, index, middle, ring, pinky] extension states."""
        fingers: List[bool] = []

        # Thumb — x-axis comparison (inverted for left hand)
        if hand_side == "Right":
            thumb_ext = lm[_THUMB_TIP].x > lm[_THUMB_MCP].x
        else:
            thumb_ext = lm[_THUMB_TIP].x < lm[_THUMB_MCP].x
        fingers.append(thumb_ext)

        # Other fingers — tip above PIP
        for tip, pip in [
            (_INDEX_TIP, _INDEX_PIP),
            (_MIDDLE_TIP, _MIDDLE_PIP),
            (_RING_TIP, _RING_PIP),
            (_PINKY_TIP, _PINKY_PIP),
        ]:
            fingers.append(lm[tip].y < lm[pip].y)

        return fingers

    @staticmethod
    def _dist(lm, a: int, b: int) -> float:
        """Euclidean distance between two landmarks."""
        return math.sqrt(
            (lm[a].x - lm[b].x) ** 2 +
            (lm[a].y - lm[b].y) ** 2 +
            (lm[a].z - lm[b].z) ** 2
        )

    def _is_gun_sign(self, lm) -> bool:
        """Check if the L-shape is horizontal (gun) vs vertical (ASL L)."""
        # Gun sign: thumb points roughly perpendicular to index
        dx = lm[_THUMB_TIP].x - lm[_THUMB_MCP].x
        dy = lm[_INDEX_TIP].y - lm[_INDEX_MCP].y
        # If thumb is extending horizontally while index is vertical
        return abs(dx) > abs(dy) * 0.5

    def _thumb_side(self, lm) -> bool:
        """Thumb tip is to the side of the hand (not wrapped over fingers)."""
        return abs(lm[_THUMB_TIP].x - lm[_INDEX_MCP].x) > 0.05

    def _thumb_across_palm(self, lm) -> bool:
        """Thumb tucked across the palm (tip near ring MCP)."""
        return self._dist(lm, _THUMB_TIP, _RING_MCP) < 0.08

    def _is_c_shape(self, lm) -> bool:
        """All fingertips curved inward forming C shape."""
        # Tips and MCPs should be at similar x-coords with tips higher
        tips = [_THUMB_TIP, _INDEX_TIP, _MIDDLE_TIP, _RING_TIP, _PINKY_TIP]
        mcps = [_THUMB_MCP, _INDEX_MCP, _MIDDLE_MCP, _RING_MCP, _PINKY_MCP]
        curved_count = 0
        for tip, mcp in zip(tips[1:], mcps[1:]):  # skip thumb
            if lm[tip].y > lm[mcp].y and abs(lm[tip].x - lm[mcp].x) < 0.1:
                curved_count += 1
        return curved_count >= 3

    def _thumb_touches_middle(self, lm) -> bool:
        return self._dist(lm, _THUMB_TIP, _MIDDLE_DIP) < 0.06

    def _index_thumb_touching(self, lm) -> bool:
        return self._dist(lm, _THUMB_TIP, _INDEX_TIP) < 0.05

    def _thumb_between_index_middle(self, lm) -> bool:
        thumb_x = lm[_THUMB_TIP].x
        idx_x = lm[_INDEX_TIP].x
        mid_x = lm[_MIDDLE_TIP].x
        return min(idx_x, mid_x) < thumb_x < max(idx_x, mid_x)

    def _is_o_shape(self, lm) -> bool:
        """All fingertips close together forming circle."""
        tips = [_THUMB_TIP, _INDEX_TIP, _MIDDLE_TIP, _RING_TIP, _PINKY_TIP]
        center_x = sum(lm[t].x for t in tips) / len(tips)
        center_y = sum(lm[t].y for t in tips) / len(tips)
        max_dist = max(
            math.sqrt((lm[t].x - center_x) ** 2 + (lm[t].y - center_y) ** 2)
            for t in tips
        )
        return max_dist < 0.07

    def _fingers_crossed(self, lm) -> bool:
        """Index and middle fingers cross over each other."""
        return lm[_INDEX_TIP].x < lm[_MIDDLE_TIP].x and \
               lm[_INDEX_MCP].x > lm[_MIDDLE_MCP].x
