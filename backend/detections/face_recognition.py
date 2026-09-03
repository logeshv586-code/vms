"""Face detection, reviewed identity matching and watchlist alerting.

The detector deliberately fails closed for identity. OpenCV DNN may locate a
face when the embedding backend is unavailable, but only a real 128-D
``face_recognition`` embedding may match a registered identity. Unknown people
are never auto-enrolled and image histograms are never used as identity.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)

try:
    import face_recognition as fr
    _FR_AVAILABLE = True
except ImportError:
    fr = None
    _FR_AVAILABLE = False
    logger.warning(
        "face_recognition is not installed; face identity/watchlist matching is disabled."
    )

try:
    from services.face_db_service import face_db_service as _db
    _DB_AVAILABLE = True
except ImportError:
    _db = None
    _DB_AVAILABLE = False


class FaceRecognitionDetector(BaseDetector):
    """Recognise reviewed identities and alert only on real watchlist matches."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.encodings_db_path = ""
        self._known_encodings: Dict[str, List[List[float]]] = {}
        self._known_categories: Dict[str, str] = {}
        self.dnn_net = None
        self._use_fr_lib = _FR_AVAILABLE
        self._lock = threading.RLock()
        super().__init__("face_recognition", config)

    def load_model(self) -> None:
        self.recognition_tolerance = max(
            0.1,
            min(
                0.9,
                float(
                    self.config.get(
                        "recognition_tolerance",
                        os.getenv("VMS_FACE_RECOGNITION_TOLERANCE", "0.5"),
                    )
                ),
            ),
        )
        self.detection_model = str(self.config.get("detection_model", "hog"))
        self.dnn_confidence = max(
            0.1, min(0.99, float(self.config.get("dnn_confidence_threshold", 0.6)))
        )
        self.max_faces = max(1, int(self.config.get("max_faces", 20)))
        self.auto_register = False
        self.alert_on_watchlist = bool(self.config.get("alert_on_watchlist", True))

        self.encodings_db_path = os.path.abspath(
            self.config.get(
                "encodings_db_path",
                os.path.join(os.path.dirname(__file__), "..", "face_db", "encodings.json"),
            )
        )
        os.makedirs(os.path.dirname(self.encodings_db_path), exist_ok=True)
        self._load_encodings_db()

        if not self._use_fr_lib:
            proto = os.path.abspath(
                self.config.get(
                    "dnn_proto_path",
                    os.path.join(os.path.dirname(__file__), "..", "models", "deploy.prototxt"),
                )
            )
            model = os.path.abspath(
                self.config.get(
                    "dnn_model_path",
                    os.path.join(
                        os.path.dirname(__file__),
                        "..",
                        "models",
                        "res10_300x300_ssd_iter_140000.caffemodel",
                    ),
                )
            )
            try:
                if os.path.isfile(proto) and os.path.isfile(model):
                    self.dnn_net = cv2.dnn.readNetFromCaffe(proto, model)
                    logger.info("OpenCV DNN face detector loaded in detection-only mode")
                else:
                    logger.warning("OpenCV DNN face detector assets are missing")
            except Exception as exc:
                logger.error("Failed to load OpenCV face detector: %s", exc)
                self.dnn_net = None

        logger.info(
            "FaceRecognitionDetector ready: identities=%d backend=%s auto_register=false",
            len(self._known_encodings),
            self.backend_name,
        )

    @property
    def backend_name(self) -> str:
        if self._use_fr_lib:
            return "face_recognition"
        if self.dnn_net is not None:
            return "opencv_dnn_detection_only"
        return "unavailable"

    @property
    def recognition_available(self) -> bool:
        return bool(self._use_fr_lib)

    def health(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.is_enabled,
            "backend": self.backend_name,
            "recognition_available": self.recognition_available,
            "registered_identities": len(self._known_encodings),
            "watchlist_alerts": self.alert_on_watchlist,
            "auto_register": False,
        }

    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        if not self.is_enabled or not kwargs.get("camera_toggle_active", True):
            return self._empty_result("detection_toggle_off")
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return self._empty_result("invalid_frame")

        stream_id = str(kwargs.get("stream_id", kwargs.get("camera_id", "unknown")))
        timestamp = float(kwargs.get("timestamp", time.time()))
        capture_db_ids = list(kwargs.get("capture_db_ids", []) or [])

        try:
            with self._lock:
                face_locations, face_encodings = self._encode_faces(frame)
        except Exception as exc:
            logger.exception("Face recognition inference failed for %s: %s", stream_id, exc)
            result = self._empty_result("inference_error")
            result["metadata"]["error"] = str(exc)
            return result

        detections: List[Dict[str, Any]] = []
        recognised: List[str] = []
        watchlist_hits: List[str] = []
        best_watchlist_confidence = 0.0

        for idx, loc in enumerate(face_locations):
            encoding = face_encodings[idx] if idx < len(face_encodings) else None
            identity, distance = self._match_encoding(encoding)
            confidence = self._distance_to_confidence(distance) if identity else 0.0
            x1, y1, x2, y2 = [int(value) for value in loc]
            category = self._known_categories.get(identity, "person") if identity else "unknown"
            is_watchlisted = False

            if identity and _DB_AVAILABLE and _db is not None:
                try:
                    is_watchlisted = bool(_db.is_watchlisted(identity))
                except Exception as exc:
                    logger.warning("Watchlist lookup failed for '%s': %s", identity, exc)

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
                except Exception as exc:
                    logger.warning("Recognition audit log write failed: %s", exc)

            detection = {
                "bbox": [x1, y1, x2, y2],
                "confidence": round(confidence, 4),
                "label": identity or "unknown",
                "category": category,
                "distance": round(distance, 4) if distance is not None else None,
                "matched": identity is not None,
                "is_watchlisted": is_watchlisted,
                "identity_backend": self.backend_name,
            }
            detections.append(detection)

            if identity:
                recognised.append(identity)
            if is_watchlisted and identity:
                watchlist_hits.append(identity)
                best_watchlist_confidence = max(best_watchlist_confidence, confidence)

        alert_triggered = bool(watchlist_hits) and self.alert_on_watchlist
        if alert_triggered:
            try:
                from services.event_dispatcher import dispatch_confirmed_event

                names = ", ".join(sorted(set(watchlist_hits)))
                dispatch_confirmed_event(
                    stream_id,
                    "Face Recognition",
                    "critical",
                    f"Watchlist identity matched: {names}",
                    rule_id=7,
                    confidence=best_watchlist_confidence,
                    data={
                        "watchlist_matches": sorted(set(watchlist_hits)),
                        "backend": self.backend_name,
                    },
                )
            except Exception as exc:
                logger.exception("Failed to dispatch watchlist event for %s: %s", stream_id, exc)

        return {
            "triggered": bool(recognised),
            "alert_triggered": alert_triggered,
            "detections": detections,
            "watchlist_matches": sorted(set(watchlist_hits)),
            "metadata": {
                "total_faces": len(face_locations),
                "recognised_count": len(recognised),
                "recognised_identities": recognised,
                "watchlist_hits": watchlist_hits,
                "stream_id": stream_id,
                "timestamp": timestamp,
                "backend": self.backend_name,
                "recognition_available": self.recognition_available,
                "auto_register": False,
            },
            "event_type": self.name,
        }

    def register_face(self, name: str, frame: np.ndarray, category: str = "person") -> Dict[str, Any]:
        name = str(name or "").strip()
        if not name:
            return {"success": False, "message": "Identity name is required."}
        if not self.recognition_available:
            return {"success": False, "message": "Face identity backend is unavailable."}
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return {"success": False, "message": "Invalid registration image."}

        with self._lock:
            _, encodings = self._encode_faces_fr(frame)
            if len(encodings) != 1:
                return {
                    "success": False,
                    "message": f"Expected exactly one face but found {len(encodings)}.",
                }
            embedding = np.asarray(encodings[0], dtype=np.float64)
            if embedding.shape != (128,) or not np.isfinite(embedding).all():
                return {"success": False, "message": "Face embedding was invalid."}
            self._known_encodings.setdefault(name, []).append(embedding.tolist())
            self._known_categories[name] = str(category or "person")
            self._save_encodings_db()
        return {"success": True, "message": f"Face registered for '{name}' as '{category}'."}

    def seed_from_directory(self, directory: str, category: str = "person") -> Dict[str, Any]:
        if not self.recognition_available:
            return {"success": False, "registered": 0, "failed": 0, "message": "Identity backend unavailable."}
        if not os.path.isdir(directory):
            return {"success": False, "registered": 0, "failed": 0, "message": f"Directory not found: {directory}"}

        registered = 0
        failed = 0
        for person_dir in os.scandir(directory):
            if not person_dir.is_dir():
                continue
            identity = person_dir.name.replace("_", " ").strip()
            enrolled = False
            for image_file in os.scandir(person_dir.path):
                if not image_file.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    continue
                image = cv2.imread(image_file.path)
                if image is None:
                    continue
                result = self.register_face(identity, image, category=category)
                if result.get("success"):
                    registered += 1
                    enrolled = True
                    break
            if not enrolled:
                failed += 1
        return {"success": True, "registered": registered, "failed": failed}

    def unregister_face(self, name: str) -> Dict[str, Any]:
        with self._lock:
            if name not in self._known_encodings:
                return {"success": False, "message": f"Identity '{name}' not found."}
            self._known_encodings.pop(name, None)
            self._known_categories.pop(name, None)
            self._save_encodings_db()
        return {"success": True, "message": f"Identity '{name}' removed."}

    def list_identities(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "category": self._known_categories.get(name, "person"),
                "samples": len(samples),
            }
            for name, samples in sorted(self._known_encodings.items())
        ]

    def _encode_faces(self, frame: np.ndarray) -> Tuple[List[List[int]], List[Optional[np.ndarray]]]:
        if self._use_fr_lib:
            locations, encodings = self._encode_faces_fr(frame)
            return locations, list(encodings)
        return self._detect_faces_dnn(frame), []

    def _encode_faces_fr(self, frame: np.ndarray) -> Tuple[List[List[int]], List[np.ndarray]]:
        if not self._use_fr_lib or fr is None:
            return [], []
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        raw_locations = fr.face_locations(rgb, model=self.detection_model)[: self.max_faces]
        raw_encodings = fr.face_encodings(rgb, raw_locations)
        locations = [[left, top, right, bottom] for top, right, bottom, left in raw_locations]
        return locations, list(raw_encodings[: self.max_faces])

    def _detect_faces_dnn(self, frame: np.ndarray) -> List[List[int]]:
        if self.dnn_net is None:
            return []
        height, width = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0)
        )
        self.dnn_net.setInput(blob)
        output = self.dnn_net.forward()
        locations: List[List[int]] = []
        for idx in range(output.shape[2]):
            confidence = float(output[0, 0, idx, 2])
            if confidence < self.dnn_confidence:
                continue
            x1, y1, x2, y2 = (
                output[0, 0, idx, 3:7] * np.array([width, height, width, height])
            ).astype(int)
            x1 = max(0, min(width - 1, x1))
            y1 = max(0, min(height - 1, y1))
            x2 = max(x1 + 1, min(width, x2))
            y2 = max(y1 + 1, min(height, y2))
            locations.append([x1, y1, x2, y2])
            if len(locations) >= self.max_faces:
                break
        return locations

    def _match_encoding(self, encoding: Optional[Sequence[float]]) -> Tuple[Optional[str], Optional[float]]:
        if encoding is None or not self.recognition_available or fr is None:
            return None, None
        probe = np.asarray(encoding, dtype=np.float64)
        if probe.shape != (128,) or not np.isfinite(probe).all():
            return None, None

        best_name: Optional[str] = None
        best_distance = float("inf")
        for name, known_list in self._known_encodings.items():
            valid = []
            for item in known_list:
                sample = np.asarray(item, dtype=np.float64)
                if sample.shape == (128,) and np.isfinite(sample).all():
                    valid.append(sample)
            if not valid:
                continue
            distance = float(np.min(fr.face_distance(valid, probe)))
            if distance < best_distance:
                best_name, best_distance = name, distance
        if best_name is not None and best_distance <= self.recognition_tolerance:
            return best_name, best_distance
        return None, best_distance if np.isfinite(best_distance) else None

    @staticmethod
    def _distance_to_confidence(distance: Optional[float]) -> float:
        if distance is None:
            return 0.0
        return max(0.0, min(1.0, 1.0 - float(distance)))

    def _load_encodings_db(self) -> None:
        self._known_encodings = {}
        self._known_categories = {}
        if not os.path.isfile(self.encodings_db_path):
            return
        try:
            with open(self.encodings_db_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            encodings = data.get("encodings", data) if isinstance(data, dict) else {}
            categories = data.get("categories", {}) if isinstance(data, dict) else {}
            cleaned: Dict[str, List[List[float]]] = {}
            for name, samples in encodings.items() if isinstance(encodings, dict) else []:
                valid_samples: List[List[float]] = []
                for sample in samples if isinstance(samples, list) else []:
                    array = np.asarray(sample, dtype=np.float64)
                    if array.shape == (128,) and np.isfinite(array).all():
                        valid_samples.append(array.tolist())
                if valid_samples:
                    cleaned[str(name)] = valid_samples
            self._known_encodings = cleaned
            self._known_categories = categories if isinstance(categories, dict) else {}
        except Exception as exc:
            logger.error("Failed to load face encodings database: %s", exc)

    def _save_encodings_db(self) -> None:
        temporary = f"{self.encodings_db_path}.tmp"
        payload = {"encodings": self._known_encodings, "categories": self._known_categories}
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.encodings_db_path)
        finally:
            if os.path.exists(temporary):
                try:
                    os.remove(temporary)
                except OSError:
                    pass

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "triggered": False,
            "alert_triggered": False,
            "detections": [],
            "watchlist_matches": [],
            "metadata": {
                "skipped": reason,
                "backend": self.backend_name,
                "recognition_available": self.recognition_available,
            },
            "event_type": self.name,
        }
