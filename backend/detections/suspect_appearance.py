import logging
import os
import time
from typing import Dict, Any, List, Tuple

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)

# Optional YOLO for person detection — fall back to HOG if unavailable.
try:
    from ultralytics import YOLO

    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False
    logger.info(
        "ultralytics not installed. SuspectAppearanceDetector will use "
        "OpenCV HOG person detector as fallback."
    )


class SuspectAppearanceDetector(BaseDetector):
    """
    Detects persons whose appearance matches a *suspect profile*:
    masked / concealed face, suspicious clothing patterns (all-black attire,
    hoodies in warm weather), and anomalous behavioural cues.

    The detector runs a three-stage pipeline per detected person:

    1. **Person detection** — YOLOv8 (preferred) or OpenCV HOG.
    2. **Face-visibility analysis** — Haar-cascade face detection within
       the person crop; a low face-to-body ratio suggests concealment.
    3. **Clothing & appearance scoring** — colour-histogram analysis of
       the torso region, dark-ratio computation, skin-exposure estimation,
       and overall suspicion scoring.

    A weighted sum of sub-scores yields a final ``suspicion_score``
    between 0 and 1.  If it exceeds the configured threshold the
    detection is triggered.

    Kaggle Dataset Sourcing Suggestion: Disguised Faces in the Wild Dataset
        https://www.kaggle.com/datasets/divyashah/disguised-faces-in-the-wild

    Config options:
        model_path (str): YOLOv8 weights path.  Default: "yolov8n.pt"
        person_confidence (float): Minimum person detection confidence.
                                   Default: 0.45
        suspicion_threshold (float): Overall suspicion score above which
                                     the event fires.  Default: 0.6
        dark_clothing_ratio (float): Fraction of dark pixels in the torso
                                     region that qualifies as "all black".
                                     Default: 0.65
        face_visibility_weight (float): Weight of face-visibility sub-score.
                                        Default: 0.40
        clothing_weight (float): Weight of clothing sub-score.  Default: 0.35
        skin_exposure_weight (float): Weight of skin-exposure sub-score.
                                      Default: 0.25
        dark_value_threshold (int): V-channel ceiling (HSV) to count a pixel
                                    as "dark".  Default: 50
        dnn_proto_path (str): OpenCV DNN face-detector prototxt.
        dnn_model_path (str): OpenCV DNN face-detector caffemodel.
        warm_weather_mode (bool): If True, wearing a hood/high-coverage
                                  top scores higher suspicion.  Default: False
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._person_model = None
        self._face_cascade = None
        self._dnn_net = None
        self._hog = None
        self._use_yolo = False
        super().__init__("suspect_appearance", config)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """
        Loads person-detection and face-detection models.
        """
        # Scoring weights
        self.suspicion_threshold = self.config.get("suspicion_threshold", 0.6)
        self.dark_clothing_ratio = self.config.get("dark_clothing_ratio", 0.65)
        self.face_vis_weight = self.config.get("face_visibility_weight", 0.40)
        self.clothing_weight = self.config.get("clothing_weight", 0.35)
        self.skin_weight = self.config.get("skin_exposure_weight", 0.25)
        self.dark_value_thresh = self.config.get("dark_value_threshold", 50)
        self.person_confidence = self.config.get("person_confidence", 0.45)
        self.warm_weather = self.config.get("warm_weather_mode", False)

        # --- Person detector ---
        if _YOLO_AVAILABLE:
            try:
                model_path = self.config.get("model_path", "yolov8n.pt")
                self._person_model = YOLO(model_path)
                self._use_yolo = True
                logger.info("YOLOv8 person detector loaded for SuspectAppearanceDetector.")
            except Exception as e:
                logger.warning(f"YOLO load failed ({e}); falling back to HOG.")
                self._use_yolo = False

        if not self._use_yolo:
            self._hog = cv2.HOGDescriptor()
            self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            logger.info("OpenCV HOG person detector loaded as fallback.")

        # --- Face detector (Haar cascade) ---
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._face_cascade = cv2.CascadeClassifier(cascade_path)
        if self._face_cascade.empty():
            logger.warning("Haar cascade face classifier failed to load.")
            self._face_cascade = None

        # --- Optional DNN face detector for higher accuracy ---
        dnn_proto = self.config.get("dnn_proto_path", "models/deploy.prototxt")
        dnn_model = self.config.get(
            "dnn_model_path",
            "models/res10_300x300_ssd_iter_140000.caffemodel",
        )
        try:
            if os.path.isfile(dnn_proto) and os.path.isfile(dnn_model):
                self._dnn_net = cv2.dnn.readNetFromCaffe(dnn_proto, dnn_model)
                logger.info("DNN face detector loaded for face-visibility analysis.")
        except Exception as e:
            logger.warning(f"DNN face detector unavailable: {e}")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse each detected person for suspect-appearance indicators.

        Args:
            frame: BGR input video frame.
            **kwargs:
                stream_id (str): Camera / stream identifier.
                timestamp (float): Frame epoch timestamp.

        Returns:
            Standard detection dict.  Each detection includes a breakdown
            of sub-scores and the overall ``suspicion_score``.
        """
        if not self.is_enabled:
            return {
                "triggered": False,
                "detections": [],
                "metadata": {},
                "event_type": self.name,
            }

        stream_id = kwargs.get("stream_id", "unknown")
        timestamp = kwargs.get("timestamp", time.time())

        person_boxes = self._detect_persons(frame)

        detections: List[Dict[str, Any]] = []
        suspects: List[Dict[str, Any]] = []

        for (x1, y1, x2, y2, person_conf) in person_boxes:
            person_crop = frame[y1:y2, x1:x2]
            if person_crop.size == 0:
                continue

            # Sub-score 1 — Face visibility
            face_vis_score, face_details = self._face_visibility_score(person_crop)

            # Sub-score 2 — Clothing analysis
            clothing_score, clothing_details = self._clothing_score(person_crop)

            # Sub-score 3 — Skin exposure
            skin_score, skin_details = self._skin_exposure_score(person_crop)

            # Weighted overall suspicion score (higher = more suspicious)
            suspicion = (
                self.face_vis_weight * face_vis_score
                + self.clothing_weight * clothing_score
                + self.skin_weight * skin_score
            )
            suspicion = round(min(1.0, suspicion), 4)

            is_suspect = suspicion >= self.suspicion_threshold

            det = {
                "bbox": [x1, y1, x2, y2],
                "confidence": round(person_conf, 4),
                "label": "suspect" if is_suspect else "person",
                "suspicion_score": suspicion,
                "is_suspect": is_suspect,
                "breakdown": {
                    "face_visibility": {
                        "score": round(face_vis_score, 4),
                        "weight": self.face_vis_weight,
                        **face_details,
                    },
                    "clothing": {
                        "score": round(clothing_score, 4),
                        "weight": self.clothing_weight,
                        **clothing_details,
                    },
                    "skin_exposure": {
                        "score": round(skin_score, 4),
                        "weight": self.skin_weight,
                        **skin_details,
                    },
                },
            }
            detections.append(det)
            if is_suspect:
                suspects.append(det)

        triggered = len(suspects) > 0

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "total_persons": len(person_boxes),
                "suspects_detected": len(suspects),
                "suspicion_threshold": self.suspicion_threshold,
                "warm_weather_mode": self.warm_weather,
                "stream_id": stream_id,
                "timestamp": timestamp,
            },
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Person detection
    # ------------------------------------------------------------------

    def _detect_persons(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int, int, int, float]]:
        """Return a list of ``(x1, y1, x2, y2, confidence)`` for persons."""
        h, w = frame.shape[:2]
        persons: List[Tuple[int, int, int, int, float]] = []

        if self._use_yolo and self._person_model is not None:
            results = self._person_model(frame, verbose=False)
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    label = self._person_model.names[cls_id]
                    conf = float(box.conf[0])
                    if label.lower() == "person" and conf >= self.person_confidence:
                        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        persons.append((
                            max(0, bx1), max(0, by1),
                            min(w, bx2), min(h, by2),
                            conf,
                        ))
        elif self._hog is not None:
            rects, weights = self._hog.detectMultiScale(
                frame, winStride=(8, 8), padding=(4, 4), scale=1.05
            )
            for (rx, ry, rw, rh), weight in zip(rects, weights):
                conf = float(weight)
                if conf >= self.person_confidence:
                    persons.append((
                        max(0, rx), max(0, ry),
                        min(w, rx + rw), min(h, ry + rh),
                        min(conf, 1.0),
                    ))

        return persons

    # ------------------------------------------------------------------
    # Sub-score: face visibility
    # ------------------------------------------------------------------

    def _face_visibility_score(
        self, person_crop: np.ndarray
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Score how *concealed* the person's face is.

        A score of **1.0** means fully concealed (no face found), 0.0 means
        a clearly visible, large face relative to body.
        """
        ph, pw = person_crop.shape[:2]
        person_area = max(pw * ph, 1)

        # Expected face region: top 35% of the person bounding box
        head_region = person_crop[0 : int(ph * 0.35), :]

        faces = self._detect_faces_in_crop(head_region)
        if len(faces) == 0:
            return 1.0, {"face_detected": False, "face_area_ratio": 0.0}

        # Largest face
        largest_area = max(fw * fh for (_, _, fw, fh) in faces)
        face_ratio = largest_area / person_area

        # Heuristic: a typical visible face is ~5-15% of person box area
        if face_ratio >= 0.05:
            score = 0.0  # clearly visible
        elif face_ratio >= 0.02:
            score = 0.5  # partially visible
        else:
            score = 0.8  # very small / partially occluded

        return score, {
            "face_detected": True,
            "face_count": len(faces),
            "face_area_ratio": round(face_ratio, 4),
        }

    def _detect_faces_in_crop(
        self, crop: np.ndarray
    ) -> List[Tuple[int, int, int, int]]:
        """Detect faces within a small crop using DNN or Haar cascade."""
        if crop.size == 0:
            return []

        # Try DNN first
        if self._dnn_net is not None:
            h, w = crop.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(crop, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0)
            )
            self._dnn_net.setInput(blob)
            dets = self._dnn_net.forward()
            faces = []
            for i in range(dets.shape[2]):
                conf = float(dets[0, 0, i, 2])
                if conf < 0.5:
                    continue
                box = dets[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                faces.append((x1, y1, x2 - x1, y2 - y1))
            if faces:
                return faces

        # Haar fallback
        if self._face_cascade is not None:
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            rects = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=4, minSize=(20, 20)
            )
            return [(x, y, w, h) for (x, y, w, h) in rects]

        return []

    # ------------------------------------------------------------------
    # Sub-score: clothing analysis
    # ------------------------------------------------------------------

    def _clothing_score(
        self, person_crop: np.ndarray
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Analyse the torso region for suspicious clothing patterns.

        A score of 1.0 indicates highly suspicious (e.g. all-black attire).
        """
        ph, pw = person_crop.shape[:2]

        # Torso region: roughly 30%–65% of height
        torso = person_crop[int(ph * 0.30) : int(ph * 0.65), :]
        if torso.size == 0:
            return 0.0, {"dark_ratio": 0.0, "dominant_hue": None}

        hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]

        # Fraction of very dark pixels
        dark_mask = v_channel < self.dark_value_thresh
        dark_ratio = float(np.count_nonzero(dark_mask)) / max(v_channel.size, 1)

        # Dominant hue (ignoring very dark pixels)
        light_mask = ~dark_mask
        dominant_hue: float | None = None
        if np.any(light_mask):
            dominant_hue = float(np.median(hsv[:, :, 0][light_mask]))

        # Colour uniformity (low saturation std ⇒ monotone attire)
        sat_std = float(np.std(hsv[:, :, 1]))
        uniformity = max(0.0, 1.0 - sat_std / 64.0)  # normalised 0–1

        # Scoring
        score = 0.0
        if dark_ratio >= self.dark_clothing_ratio:
            score += 0.6
        elif dark_ratio >= 0.4:
            score += 0.3

        # High uniformity adds suspicion (monotone clothing)
        score += 0.2 * uniformity

        # Warm-weather hoodie heuristic — high coverage + dark ⇒ extra suspicion
        if self.warm_weather and dark_ratio >= 0.5:
            score += 0.2

        score = min(1.0, score)

        return score, {
            "dark_ratio": round(dark_ratio, 4),
            "dominant_hue": round(dominant_hue, 1) if dominant_hue is not None else None,
            "colour_uniformity": round(uniformity, 4),
            "saturation_std": round(sat_std, 2),
        }

    # ------------------------------------------------------------------
    # Sub-score: skin exposure
    # ------------------------------------------------------------------

    def _skin_exposure_score(
        self, person_crop: np.ndarray
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Estimate how much skin is visible.

        Low skin exposure (heavy covering) contributes to a higher
        suspicion score — particularly in warm-weather mode.
        """
        hsv = cv2.cvtColor(person_crop, cv2.COLOR_BGR2HSV)

        # Broad skin-colour range in HSV
        lower_skin = np.array([0, 30, 60])
        upper_skin = np.array([25, 170, 255])
        skin_mask = cv2.inRange(hsv, lower_skin, upper_skin)

        # Secondary range for darker / lighter skin tones
        lower_skin2 = np.array([160, 30, 60])
        upper_skin2 = np.array([180, 170, 255])
        skin_mask2 = cv2.inRange(hsv, lower_skin2, upper_skin2)
        skin_mask = cv2.bitwise_or(skin_mask, skin_mask2)

        skin_ratio = float(np.count_nonzero(skin_mask)) / max(skin_mask.size, 1)

        # Lower skin exposure ⇒ higher score (more suspicious)
        if skin_ratio >= 0.15:
            score = 0.0  # Normal amount of visible skin
        elif skin_ratio >= 0.08:
            score = 0.4
        elif skin_ratio >= 0.03:
            score = 0.7
        else:
            score = 1.0  # Almost no skin visible — fully covered

        # In warm weather, low skin is more suspicious
        if self.warm_weather and skin_ratio < 0.10:
            score = min(1.0, score + 0.2)

        return score, {
            "skin_ratio": round(skin_ratio, 4),
            "warm_weather_mode": self.warm_weather,
        }
