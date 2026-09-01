import logging
import json
import os
import time
from typing import Dict, Any, List, Optional

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)

# Optional dlib-based face_recognition library
try:
    import face_recognition as fr
    _FR_AVAILABLE = True
except ImportError:
    _FR_AVAILABLE = False
    logger.info(
        "face_recognition library not installed. "
        "FaceRecognitionDetector will use OpenCV DNN fallback."
    )

# Optional DB service
try:
    from services.face_db_service import face_db_service as _db
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False
    _db = None


class FaceRecognitionDetector(BaseDetector):
    """
    Recognizes known faces against a stored database of 128-D encodings.

    New in this version:
      - Criminal / suspect **watchlist** integration via FaceDBService
      - Every recognition match (known OR unknown) is persisted to SQLite
      - Operates only when the camera AI toggle is ON
      - ``auto_register`` mode: unknown faces that pass quality checks can be
        saved to the gallery for later manual tagging
      - Kaggle gallery seeding: call ``seed_from_directory(path)`` to bulk-
        register identities from a folder of labelled images (e.g. LFW format)

    Kaggle Dataset Sourcing Suggestion: LFW (Labeled Faces in the Wild)
        https://www.kaggle.com/datasets/jessicali9530/lfw-dataset

    Config options:
        encodings_db_path (str): JSON file storing face encodings.
                                 Default: "face_db/encodings.json"
        recognition_tolerance (float): L2 distance threshold. Default: 0.5
        detection_model (str): "hog" or "cnn". Default: "hog"
        dnn_confidence_threshold (float): DNN detection floor. Default: 0.6
        max_faces (int): Max faces per frame. Default: 20
        auto_register (bool): Auto-save unknown faces for tagging. Default: True
        alert_on_watchlist (bool): Fire alert when watchlisted person seen.
                                   Default: True
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.encodings_db_path: str = ""
        self._known_encodings: Dict[str, List[List[float]]] = {}
        self._known_categories: Dict[str, str] = {}   # name → category
        self.dnn_net = None
        self._use_fr_lib = _FR_AVAILABLE
        super().__init__("face_recognition", config)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        self.recognition_tolerance = self.config.get("recognition_tolerance", 0.5)
        self.detection_model = self.config.get("detection_model", "hog")
        self.dnn_confidence = self.config.get("dnn_confidence_threshold", 0.6)
        self.max_faces = self.config.get("max_faces", 20)
        self.auto_register = self.config.get("auto_register", True)
        self.alert_on_watchlist = self.config.get("alert_on_watchlist", True)

        # --- Encoding database ---
        self.encodings_db_path = self.config.get(
            "encodings_db_path", "face_db/encodings.json"
        )
        os.makedirs(os.path.dirname(self.encodings_db_path) or ".", exist_ok=True)
        self._load_encodings_db()

        # --- Fallback DNN detector ---
        if not self._use_fr_lib:
            dnn_proto = self.config.get(
                "dnn_proto_path",
                os.path.join(os.path.dirname(__file__), "..", "models", "deploy.prototxt"),
            )
            dnn_model = self.config.get(
                "dnn_model_path",
                os.path.join(
                    os.path.dirname(__file__), "..", "models",
                    "res10_300x300_ssd_iter_140000.caffemodel",
                ),
            )
            try:
                if os.path.isfile(dnn_proto) and os.path.isfile(dnn_model):
                    self.dnn_net = cv2.dnn.readNetFromCaffe(dnn_proto, dnn_model)
                    logger.info("OpenCV DNN face detector loaded (recognition fallback).")
                else:
                    logger.warning("DNN model files not found; detection unavailable.")
            except Exception as e:
                logger.error(f"Failed to load DNN model: {e}")

        logger.info(
            "FaceRecognitionDetector ready — %d identities registered, "
            "backend=%s, watchlist_alerts=%s",
            len(self._known_encodings),
            "face_recognition" if self._use_fr_lib else "opencv_dnn",
            self.alert_on_watchlist,
        )

    # ------------------------------------------------------------------
    # Detection & Recognition
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Detect and recognise faces in *frame*.

        Kwargs:
            stream_id (str): Camera / stream identifier.
            timestamp (float): Frame epoch timestamp.
            camera_toggle_active (bool): Must be True to run. Default: True.
            capture_db_ids (list): DB IDs from FaceCaptureDetector to link.
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
        capture_db_ids: List[str] = kwargs.get("capture_db_ids", [])

        face_locations, face_encodings = self._encode_faces(frame)
        detections: List[Dict[str, Any]] = []
        recognised_identities: List[str] = []
        watchlist_hits: List[str] = []

        for idx, (loc, encoding) in enumerate(zip(face_locations, face_encodings)):
            identity, distance = self._match_encoding(encoding)
            confidence = max(0.0, 1.0 - distance) if distance is not None else 0.0

            x1, y1, x2, y2 = loc
            category = self._known_categories.get(identity, "person") if identity else "unknown"
            is_watchlisted = False

            if _DB_AVAILABLE and _db is not None and identity:
                try:
                    is_watchlisted = _db.is_watchlisted(identity)
                except Exception:
                    pass

            # Persist recognition event to DB
            capture_id = capture_db_ids[idx] if idx < len(capture_db_ids) else None
            if _DB_AVAILABLE and _db is not None:
                try:
                    _db.insert_recognition(
                        stream_id=stream_id,
                        identity=identity or "unknown",
                        confidence=round(confidence, 4),
                        distance=round(distance, 4) if distance is not None else None,
                        category=category,
                        capture_id=capture_id,
                        is_watchlisted=is_watchlisted,
                        timestamp=timestamp,
                    )
                except Exception as e:
                    logger.error("Failed to log recognition event: %s", e)

            det = {
                "bbox": [x1, y1, x2, y2],
                "confidence": round(confidence, 4),
                "label": identity or "unknown",
                "category": category,
                "distance": round(distance, 4) if distance is not None else None,
                "matched": identity is not None,
                "is_watchlisted": is_watchlisted,
            }
            detections.append(det)

            if identity:
                recognised_identities.append(identity)
                if is_watchlisted:
                    watchlist_hits.append(identity)

        # Trigger alert for watchlist hits
        triggered = len(recognised_identities) > 0 or len(watchlist_hits) > 0
        alert_triggered = len(watchlist_hits) > 0 and self.alert_on_watchlist

        return {
            "triggered": triggered,
            "alert_triggered": alert_triggered,
            "detections": detections,
            "metadata": {
                "total_faces": len(face_locations),
                "recognised_count": len(recognised_identities),
                "recognised_identities": recognised_identities,
                "watchlist_hits": watchlist_hits,
                "stream_id": stream_id,
                "timestamp": timestamp,
            },
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Registration API
    # ------------------------------------------------------------------

    def register_face(
        self, name: str, frame: np.ndarray, category: str = "person"
    ) -> Dict[str, Any]:
        """
        Register a new identity from a frame containing exactly one face.

        Args:
            name: Human-readable identity label.
            frame: BGR image containing the face.
            category: "person", "suspect", "criminal", "staff", etc.
        """
        _, encodings = self._encode_faces(frame)

        if len(encodings) == 0:
            return {"success": False, "message": "No face detected in the provided image."}
        if len(encodings) > 1:
            return {
                "success": False,
                "message": f"Expected 1 face but found {len(encodings)}. Provide a single-face image.",
            }

        encoding = encodings[0]
        self._known_encodings.setdefault(name, []).append(
            encoding.tolist() if isinstance(encoding, np.ndarray) else encoding
        )
        self._known_categories[name] = category
        self._save_encodings_db()
        logger.info("Registered face encoding for '%s' (category: %s).", name, category)
        return {"success": True, "message": f"Face registered for '{name}' as '{category}'."}

    def seed_from_directory(self, directory: str, category: str = "person") -> Dict[str, Any]:
        """
        Bulk-register identities from a directory of labelled images.

        Expected structure (LFW-style):
          directory/
            Person_Name/
              image1.jpg
              image2.jpg

        Returns summary of how many identities were registered.
        """
        registered = 0
        failed = 0
        if not os.path.isdir(directory):
            return {"success": False, "message": f"Directory not found: {directory}"}

        for person_dir in os.scandir(directory):
            if not person_dir.is_dir():
                continue
            name = person_dir.name.replace("_", " ")
            for img_file in os.scandir(person_dir.path):
                if not img_file.name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                frame = cv2.imread(img_file.path)
                if frame is None:
                    continue
                result = self.register_face(name, frame, category=category)
                if result["success"]:
                    registered += 1
                    break  # One image per person is enough for gallery seeding
                else:
                    failed += 1

        return {
            "success": True,
            "registered": registered,
            "failed": failed,
            "message": f"Seeded {registered} identities from {directory}",
        }

    def unregister_face(self, name: str) -> Dict[str, Any]:
        if name in self._known_encodings:
            del self._known_encodings[name]
            self._known_categories.pop(name, None)
            self._save_encodings_db()
            return {"success": True, "message": f"Identity '{name}' removed."}
        return {"success": False, "message": f"Identity '{name}' not found."}

    def list_identities(self) -> List[Dict[str, str]]:
        return [
            {"name": name, "category": self._known_categories.get(name, "person")}
            for name in self._known_encodings
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _encode_faces(self, frame: np.ndarray) -> tuple:
        if self._use_fr_lib:
            return self._encode_faces_fr(frame)
        return self._encode_faces_fallback(frame)

    def _encode_faces_fr(self, frame: np.ndarray) -> tuple:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = fr.face_locations(rgb, model=self.detection_model)
        encodings = fr.face_encodings(rgb, locations)
        locs_xyxy = []
        for top, right, bottom, left in locations[: self.max_faces]:
            locs_xyxy.append([left, top, right, bottom])
        return locs_xyxy, list(encodings[: self.max_faces])

    def _encode_faces_fallback(self, frame: np.ndarray) -> tuple:
        locations: List[List[int]] = []
        encodings: List[List[float]] = []
        if self.dnn_net is None:
            return locations, encodings

        h_frame, w_frame = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0)
        )
        self.dnn_net.setInput(blob)
        dets = self.dnn_net.forward()

        for i in range(min(dets.shape[2], self.max_faces)):
            conf = float(dets[0, 0, i, 2])
            if conf < self.dnn_confidence:
                continue
            box = dets[0, 0, i, 3:7] * np.array([w_frame, h_frame, w_frame, h_frame])
            x1, y1, x2, y2 = np.clip(
                box.astype(int), 0, [w_frame, h_frame, w_frame, h_frame]
            )
            locations.append([int(x1), int(y1), int(x2), int(y2)])
            face_roi = frame[y1:y2, x1:x2]
            if face_roi.size == 0:
                encodings.append([0.0] * 128)
                continue
            enc = self._histogram_encoding(face_roi)
            encodings.append(enc)

        return locations, encodings

    @staticmethod
    def _histogram_encoding(face_roi: np.ndarray, dims: int = 128) -> List[float]:
        hsv = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        if len(hist) < dims:
            hist = np.pad(hist, (0, dims - len(hist)))
        else:
            hist = hist[:dims]
        return hist.tolist()

    def _match_encoding(self, encoding) -> tuple:
        if not self._known_encodings:
            return None, None

        enc_arr = np.array(encoding)
        best_name: Optional[str] = None
        best_dist: float = float("inf")

        if self._use_fr_lib:
            for name, known_list in self._known_encodings.items():
                known_arrs = [np.array(k) for k in known_list]
                distances = fr.face_distance(known_arrs, enc_arr)
                min_d = float(np.min(distances))
                if min_d < best_dist:
                    best_dist = min_d
                    best_name = name
        else:
            for name, known_list in self._known_encodings.items():
                for known in known_list:
                    dist = float(np.linalg.norm(enc_arr - np.array(known)))
                    if dist < best_dist:
                        best_dist = dist
                        best_name = name

        if best_dist <= self.recognition_tolerance:
            return best_name, best_dist
        return None, best_dist

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_encodings_db(self) -> None:
        if os.path.isfile(self.encodings_db_path):
            try:
                with open(self.encodings_db_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # Support both flat {name: [encodings]} and new {encodings:{}, categories:{}}
                if isinstance(data, dict) and "encodings" in data:
                    self._known_encodings = data["encodings"]
                    self._known_categories = data.get("categories", {})
                else:
                    self._known_encodings = data
                    self._known_categories = {}
                logger.info(
                    "Loaded %d identities from %s.",
                    len(self._known_encodings),
                    self.encodings_db_path,
                )
            except Exception as e:
                logger.error(f"Failed to load encodings database: {e}")
                self._known_encodings = {}
                self._known_categories = {}
        else:
            self._known_encodings = {}
            self._known_categories = {}

    def _save_encodings_db(self) -> None:
        try:
            with open(self.encodings_db_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "encodings": self._known_encodings,
                        "categories": self._known_categories,
                    },
                    fh,
                    indent=2,
                )
            logger.debug("Encodings database saved to %s.", self.encodings_db_path)
        except Exception as e:
            logger.error(f"Failed to save encodings database: {e}")
