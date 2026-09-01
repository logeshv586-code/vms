import logging
import os
import time
import uuid
from typing import Dict, Any, List, Optional

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)

# ── Optional DB service ───────────────────────────────────────────────────────
try:
    from services.face_db_service import face_db_service as _db
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False
    _db = None
    logger.warning("FaceDBService not available — face captures will only be saved to disk.")


class FaceCaptureDetector(BaseDetector):
    """
    Captures and stores high-quality face images from video frames.

    Runs only when the camera AI detection toggle is ON (``camera_toggle_active``
    kwarg or ``is_enabled`` flag on this detector).  Detected faces are evaluated
    through quality checks — blur (Laplacian variance), minimum size, and aspect
    ratio — before being cropped and persisted.

    Each capture is:
      - Saved to disk under ``{gallery_dir}/{stream_id}/YYYYMMDD/face_{id}.jpg``
      - Inserted into the SQLite ``face_captures`` table (via FaceDBService)

    Kaggle Dataset Sourcing Suggestion: WIDER FACE Dataset
        https://www.kaggle.com/datasets/suvoo/wider-face

    Config options:
        gallery_dir (str): Root directory for face image storage.
                           Default: "face_db/captures"
        min_face_size (int): Minimum face width/height in pixels. Default: 80
        blur_threshold (float): Laplacian variance threshold. Default: 100.0
        aspect_ratio_range (list): Acceptable [min, max] ratio. Default: [0.7, 1.4]
        dnn_model_path (str): Path to Caffe caffemodel weights.
        dnn_proto_path (str): Path to Caffe prototxt deploy file.
        use_haar_fallback (bool): Fallback to Haar cascade. Default: True
        save_faces (bool): Persist face crops to disk. Default: True
        dnn_confidence_threshold (float): DNN detection floor. Default: 0.6
        capture_every_n_frames (int): Throttle — capture 1 face every N frames.
                                      Default: 5
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.gallery_dir: str = ""
        self.face_cascade = None
        self.dnn_net = None
        self._use_dnn = False
        self._frame_counter: int = 0
        super().__init__("face_capture", config)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """
        Loads the face detection model and creates storage directories.
        """
        # Gallery root
        self.gallery_dir = self.config.get("gallery_dir", "face_db/captures")

        # Quality-gate parameters
        self.min_face_size = self.config.get("min_face_size", 80)
        self.blur_threshold = self.config.get("blur_threshold", 100.0)
        self.aspect_ratio_range = self.config.get("aspect_ratio_range", [0.7, 1.4])
        self.save_faces = self.config.get("save_faces", True)
        self.dnn_confidence = self.config.get("dnn_confidence_threshold", 0.6)
        self.capture_every_n = self.config.get("capture_every_n_frames", 5)

        # --- DNN backend ---
        dnn_proto = self.config.get(
            "dnn_proto_path",
            os.path.join(os.path.dirname(__file__), "..", "models", "deploy.prototxt"),
        )
        dnn_model = self.config.get(
            "dnn_model_path",
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "models",
                "res10_300x300_ssd_iter_140000.caffemodel",
            ),
        )

        try:
            if os.path.isfile(dnn_proto) and os.path.isfile(dnn_model):
                self.dnn_net = cv2.dnn.readNetFromCaffe(dnn_proto, dnn_model)
                self._use_dnn = True
                logger.info("DNN face detector loaded for FaceCaptureDetector.")
            else:
                raise FileNotFoundError("DNN weight files not found.")
        except Exception as e:
            logger.warning(f"DNN face detector unavailable ({e}); trying Haar cascade.")

        # --- Haar fallback ---
        if not self._use_dnn and self.config.get("use_haar_fallback", True):
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            if self.face_cascade.empty():
                logger.error("Failed to load Haar cascade classifier.")
                self.face_cascade = None
            else:
                logger.info("Haar cascade loaded as fallback for FaceCaptureDetector.")

        if not self._use_dnn and self.face_cascade is None:
            logger.error("No face detection backend available for FaceCaptureDetector.")

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Detect and capture high-quality faces in *frame*.

        Kwargs:
            stream_id (str): Camera / stream identifier.
            timestamp (float): Frame epoch timestamp.
            camera_toggle_active (bool): If explicitly False, skip capture.
                                         Defaults to True (respects is_enabled).
        """
        # Honour the camera AI-detection toggle
        camera_toggle_active = kwargs.get("camera_toggle_active", True)
        if not self.is_enabled or not camera_toggle_active:
            return {
                "triggered": False,
                "detections": [],
                "metadata": {"skipped": "detection_toggle_off"},
                "event_type": self.name,
            }

        # Frame throttling
        self._frame_counter += 1
        if self._frame_counter % self.capture_every_n != 0:
            return {
                "triggered": False,
                "detections": [],
                "metadata": {"skipped": "throttled"},
                "event_type": self.name,
            }

        stream_id = kwargs.get("stream_id", "unknown")
        timestamp = kwargs.get("timestamp", time.time())

        raw_faces = self._detect_faces(frame)
        detections: List[Dict[str, Any]] = []
        saved_paths: List[str] = []
        db_ids: List[str] = []

        for (x, y, w, h, confidence) in raw_faces:
            quality = self._assess_quality(frame, x, y, w, h)
            if not quality["passed"]:
                continue

            face_crop = frame[y: y + h, x: x + w].copy()

            # Persist to disk
            save_path: Optional[str] = None
            if self.save_faces:
                save_path = self._save_face(face_crop, stream_id, timestamp)
                if save_path:
                    saved_paths.append(save_path)

            # Persist to DB
            db_id: Optional[str] = None
            if _DB_AVAILABLE and _db is not None and save_path:
                try:
                    db_id = _db.insert_capture(
                        stream_id=stream_id,
                        image_path=save_path,
                        confidence=confidence,
                        bbox=[x, y, x + w, y + h],
                        quality=quality,
                        timestamp=timestamp,
                    )
                    db_ids.append(db_id)
                except Exception as e:
                    logger.error("Failed to insert face capture to DB: %s", e)

            detections.append(
                {
                    "bbox": [x, y, x + w, y + h],
                    "confidence": round(confidence, 4),
                    "label": "face",
                    "quality": quality,
                    "saved_path": save_path,
                    "db_id": db_id,
                }
            )

        triggered = len(detections) > 0

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "total_faces_detected": len(raw_faces),
                "quality_faces_captured": len(detections),
                "saved_paths": saved_paths,
                "db_ids": db_ids,
                "stream_id": stream_id,
                "timestamp": timestamp,
            },
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_faces(self, frame: np.ndarray) -> List[tuple]:
        h_frame, w_frame = frame.shape[:2]
        faces: List[tuple] = []

        if self._use_dnn and self.dnn_net is not None:
            blob = cv2.dnn.blobFromImage(
                cv2.resize(frame, (300, 300)),
                1.0,
                (300, 300),
                (104.0, 177.0, 123.0),
            )
            self.dnn_net.setInput(blob)
            detections = self.dnn_net.forward()

            for i in range(detections.shape[2]):
                conf = float(detections[0, 0, i, 2])
                if conf < self.dnn_confidence:
                    continue
                box = detections[0, 0, i, 3:7] * np.array(
                    [w_frame, h_frame, w_frame, h_frame]
                )
                x1, y1, x2, y2 = box.astype(int)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w_frame, x2), min(h_frame, y2)
                faces.append((x1, y1, x2 - x1, y2 - y1, conf))

        elif self.face_cascade is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            for (x, y, w, h) in rects:
                faces.append((x, y, w, h, 0.90))

        return faces

    def _assess_quality(
        self, frame: np.ndarray, x: int, y: int, w: int, h: int
    ) -> Dict[str, Any]:
        size_ok = w >= self.min_face_size and h >= self.min_face_size
        aspect_ratio = w / max(h, 1)
        ar_min, ar_max = self.aspect_ratio_range
        aspect_ok = ar_min <= aspect_ratio <= ar_max

        face_roi = frame[y: y + h, x: x + w]
        if face_roi.size == 0:
            return {"passed": False, "blur_score": 0, "size_ok": False, "aspect_ok": False}
        gray_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray_roi, cv2.CV_64F).var())
        blur_ok = blur_score >= self.blur_threshold

        passed = size_ok and aspect_ok and blur_ok
        return {
            "passed": passed,
            "blur_score": round(blur_score, 2),
            "blur_ok": blur_ok,
            "size_ok": size_ok,
            "aspect_ok": aspect_ok,
            "face_width": w,
            "face_height": h,
            "aspect_ratio": round(aspect_ratio, 3),
        }

    def _save_face(
        self, face_crop: np.ndarray, stream_id: str, timestamp: float
    ) -> Optional[str]:
        """
        Save a face crop under:
          {gallery_dir}/{stream_id}/YYYYMMDD/face_{uid}.jpg
        Returns the absolute path, or None on error.
        """
        try:
            date_str = time.strftime("%Y%m%d", time.localtime(timestamp))
            folder = os.path.join(self.gallery_dir, stream_id, date_str)
            os.makedirs(folder, exist_ok=True)

            uid = uuid.uuid4().hex[:10]
            filename = f"face_{uid}.jpg"
            filepath = os.path.join(folder, filename)

            cv2.imwrite(filepath, face_crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
            logger.debug("Saved face crop → %s", filepath)
            return filepath
        except Exception as e:
            logger.error("Failed to save face crop: %s", e)
            return None
