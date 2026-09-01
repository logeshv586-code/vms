"""
Appearance Search Detector
===========================
Searches for registered persons or objects within camera frames using:

1. **YOLOv8 person detection** — locates person bounding boxes
2. **Deep Re-ID feature embeddings** — extracts 512-D appearance vectors
   using OSNet (torchreid) when available, or colour histograms as fallback
3. **Cosine similarity matching** — compares against a registered gallery
   of reference embeddings (seeded from Kaggle Market-1501 dataset)

Gallery seeding (Option A — no model training):
  - Market-1501: person crops from 1501 identities used as reference embeddings
  - Person images registered via the API appear as searchable subjects
  - https://www.kaggle.com/datasets/pengcw1/market-1501

Config options:
    model_path (str): YOLOv8 weights. Default: "yolov8n.pt"
    gallery_path (str): Directory of registered person images. Default: "appearance_data/gallery"
    embeddings_db_path (str): JSON file for cached embeddings. Default: "appearance_data/embeddings.json"
    similarity_threshold (float): Cosine similarity floor for a match. Default: 0.75
    person_confidence (float): YOLO person detection floor. Default: 0.45
    reid_model (str): "osnet" | "histogram". Default: "histogram" (safe fallback)
"""

import json
import logging
import os
import time
import uuid
from typing import Dict, Any, List, Optional, Tuple

import cv2
import numpy as np

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)

# Optional YOLOv8
try:
    from ultralytics import YOLO
    _YOLO_AVAILABLE = True
except ImportError:
    _YOLO_AVAILABLE = False

# Optional torchreid for OSNet Re-ID
try:
    import torchreid
    import torch
    _REID_AVAILABLE = True
except ImportError:
    _REID_AVAILABLE = False
    logger.info("torchreid not installed. AppearanceSearchDetector will use histogram Re-ID.")


class AppearanceSearchDetector(BaseDetector):
    """
    Searches for registered persons using deep appearance embeddings.

    Workflow:
        1. YOLO detects all persons in the frame.
        2. Each person crop is passed through the Re-ID encoder to produce
           a feature vector.
        3. The vector is compared (cosine similarity) against all gallery
           embeddings to find the best match.
        4. Matches above the similarity threshold are returned as detections.

    Kaggle Dataset Sourcing Suggestion:
        Market-1501 Re-ID Dataset (Option A — gallery seeding only):
        https://www.kaggle.com/datasets/pengcw1/market-1501
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._yolo = None
        self._reid_model = None
        self._reid_transform = None
        self._gallery_embeddings: Dict[str, List[List[float]]] = {}  # name → [embedding]
        self._gallery_images: Dict[str, str] = {}                    # name → image_path
        super().__init__("appearance_search", config)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        self.person_confidence = self.config.get("person_confidence", 0.45)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.75)
        self.gallery_path = self.config.get("gallery_path", "appearance_data/gallery")
        self.embeddings_db_path = self.config.get("embeddings_db_path", "appearance_data/embeddings.json")
        self.reid_backend = self.config.get("reid_model", "histogram")

        os.makedirs(self.gallery_path, exist_ok=True)
        os.makedirs(os.path.dirname(self.embeddings_db_path), exist_ok=True)

        # --- YOLOv8 person detector ---
        if _YOLO_AVAILABLE:
            try:
                model_path = self.config.get("model_path", "yolov8n.pt")
                self._yolo = YOLO(model_path)
                logger.info("YOLOv8 model loaded for AppearanceSearchDetector.")
            except Exception as e:
                logger.warning("Failed to load YOLO model (%s).", e)

        # --- Re-ID encoder ---
        if _REID_AVAILABLE and self.reid_backend == "osnet":
            try:
                self._reid_model = torchreid.models.build_model(
                    name="osnet_x0_25",
                    num_classes=1000,
                    pretrained=True,
                )
                self._reid_model.eval()
                if torch.cuda.is_available():
                    self._reid_model = self._reid_model.cuda()

                import torchvision.transforms as T
                self._reid_transform = T.Compose([
                    T.ToPILImage(),
                    T.Resize((256, 128)),
                    T.ToTensor(),
                    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ])
                logger.info("OSNet Re-ID model loaded.")
            except Exception as e:
                logger.warning("OSNet load failed (%s); using histogram fallback.", e)
                self._reid_model = None

        # --- Load gallery embeddings ---
        self._load_embeddings()

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Detect persons matching the registered gallery in *frame*.

        Kwargs:
            stream_id (str): Camera / stream identifier.
            timestamp (float): Frame timestamp.
            search_name (str): Restrict search to a specific registered identity.
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
        search_name = kwargs.get("search_name", None)

        if not self._gallery_embeddings:
            return {
                "triggered": False,
                "detections": [],
                "metadata": {"gallery_empty": True},
                "event_type": self.name,
            }

        # Step 1: Detect persons
        person_boxes = self._detect_persons(frame)

        detections: List[Dict[str, Any]] = []

        for (x1, y1, x2, y2, det_conf) in person_boxes:
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            # Step 2: Compute embedding
            embedding = self._extract_embedding(crop)

            # Step 3: Match against gallery
            best_name, best_similarity = self._match_embedding(embedding, search_name)

            if best_similarity >= self.similarity_threshold:
                detections.append(
                    {
                        "bbox": [x1, y1, x2, y2],
                        "confidence": round(det_conf, 4),
                        "label": best_name,
                        "similarity": round(best_similarity, 4),
                        "matched": True,
                    }
                )

        triggered = len(detections) > 0

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "persons_detected": len(person_boxes),
                "matches_found": len(detections),
                "gallery_size": len(self._gallery_embeddings),
                "stream_id": stream_id,
                "timestamp": timestamp,
            },
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Gallery API
    # ------------------------------------------------------------------

    def register_person(
        self,
        name: str,
        frame: np.ndarray,
        image_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a person's appearance from a frame or image.

        The function detects the largest person in the frame, extracts an
        embedding, and stores it in the gallery.

        Args:
            name: Human-readable identity label.
            frame: BGR image (ideally containing only the target person).
            image_path: Optional path to save the reference image.
        """
        embedding = self._extract_embedding(frame)
        self._gallery_embeddings.setdefault(name, []).append(embedding)

        # Save reference image to gallery directory
        if image_path is None:
            uid = uuid.uuid4().hex[:8]
            image_path = os.path.join(self.gallery_path, f"{name.replace(' ', '_')}_{uid}.jpg")
        cv2.imwrite(image_path, frame)
        self._gallery_images[name] = image_path

        self._save_embeddings()
        logger.info("Registered person '%s' in appearance gallery.", name)
        return {"success": True, "name": name, "gallery_size": len(self._gallery_embeddings)}

    def seed_from_directory(
        self,
        directory: str,
        max_per_person: int = 3,
    ) -> Dict[str, Any]:
        """
        Bulk-register persons from a Market-1501 style directory.

        Expected structure:
          directory/
            person_id_or_name/
              img1.jpg
              img2.jpg

        Args:
            directory: Root directory to scan.
            max_per_person: Max images to register per identity.
        """
        if not os.path.isdir(directory):
            return {"success": False, "message": f"Directory not found: {directory}"}

        registered = 0
        skipped = 0

        for person_dir in os.scandir(directory):
            if not person_dir.is_dir():
                continue
            name = person_dir.name.replace("_", " ")
            count = 0
            for img_file in sorted(os.scandir(person_dir.path), key=lambda f: f.name):
                if count >= max_per_person:
                    break
                if not img_file.name.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                img = cv2.imread(img_file.path)
                if img is None:
                    continue
                self._gallery_embeddings.setdefault(name, []).append(
                    self._extract_embedding(img)
                )
                count += 1
                registered += 1

        self._save_embeddings()
        return {
            "success": True,
            "registered": registered,
            "identities": len(self._gallery_embeddings),
            "message": f"Seeded {registered} appearance vectors from {directory}",
        }

    def list_registered_persons(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "embedding_count": len(embeds),
                "image_path": self._gallery_images.get(name),
            }
            for name, embeds in self._gallery_embeddings.items()
        ]

    def remove_person(self, name: str) -> Dict[str, Any]:
        if name in self._gallery_embeddings:
            del self._gallery_embeddings[name]
            self._gallery_images.pop(name, None)
            self._save_embeddings()
            return {"success": True, "message": f"'{name}' removed from gallery."}
        return {"success": False, "message": f"'{name}' not found in gallery."}

    # ------------------------------------------------------------------
    # Person detection
    # ------------------------------------------------------------------

    def _detect_persons(
        self, frame: np.ndarray
    ) -> List[Tuple[int, int, int, int, float]]:
        h, w = frame.shape[:2]
        persons = []

        if self._yolo is not None:
            results = self._yolo(frame, verbose=False)
            for result in results:
                if result.boxes is None:
                    continue
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    label = self._yolo.names[cls_id]
                    conf = float(box.conf[0])
                    if label.lower() == "person" and conf >= self.person_confidence:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        persons.append((
                            max(0, x1), max(0, y1),
                            min(w, x2), min(h, y2),
                            conf,
                        ))
        else:
            # HOG fallback
            hog = cv2.HOGDescriptor()
            hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            rects, weights = hog.detectMultiScale(frame, winStride=(8, 8), padding=(4, 4))
            for (rx, ry, rw, rh), weight in zip(rects, weights):
                if float(weight) >= self.person_confidence:
                    persons.append((
                        max(0, rx), max(0, ry),
                        min(w, rx + rw), min(h, ry + rh),
                        min(float(weight), 1.0),
                    ))

        return persons

    # ------------------------------------------------------------------
    # Re-ID embedding
    # ------------------------------------------------------------------

    def _extract_embedding(self, crop: np.ndarray) -> List[float]:
        """Extract a feature vector from a person/object crop."""
        if self._reid_model is not None and _REID_AVAILABLE:
            return self._osnet_embedding(crop)
        return self._histogram_embedding(crop)

    def _osnet_embedding(self, crop: np.ndarray) -> List[float]:
        """Extract 512-D embedding via OSNet."""
        try:
            import torch
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            tensor = self._reid_transform(rgb).unsqueeze(0)
            if torch.cuda.is_available():
                tensor = tensor.cuda()
            with torch.no_grad():
                feat = self._reid_model(tensor)
            feat = feat.cpu().numpy().flatten()
            # L2 normalise
            norm = np.linalg.norm(feat)
            if norm > 0:
                feat = feat / norm
            return feat.tolist()
        except Exception as e:
            logger.error("OSNet embedding failed (%s); using histogram.", e)
            return self._histogram_embedding(crop)

    @staticmethod
    def _histogram_embedding(crop: np.ndarray, dims: int = 512) -> List[float]:
        """
        Colour histogram feature vector (HSV, 3 channels combined).
        Resized to `dims` dimensions and L2-normalised.
        """
        if crop.size == 0:
            return [0.0] * dims

        resized = cv2.resize(crop, (64, 128))
        hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)

        h_hist = cv2.calcHist([hsv], [0], None, [64], [0, 180])
        s_hist = cv2.calcHist([hsv], [1], None, [32], [0, 256])
        v_hist = cv2.calcHist([hsv], [2], None, [32], [0, 256])

        feat = np.concatenate([h_hist, s_hist, v_hist]).flatten()
        feat = cv2.normalize(feat, feat).flatten()

        # Pad or truncate to dims
        if len(feat) < dims:
            feat = np.pad(feat, (0, dims - len(feat)))
        else:
            feat = feat[:dims]

        return feat.tolist()

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _match_embedding(
        self,
        embedding: List[float],
        search_name: Optional[str] = None,
    ) -> Tuple[Optional[str], float]:
        """
        Find the gallery entry with the highest cosine similarity.

        Args:
            embedding: Query feature vector.
            search_name: If provided, only compare against this identity.

        Returns:
            (best_name, best_similarity) — name is None if no gallery.
        """
        if not self._gallery_embeddings:
            return None, 0.0

        query = np.array(embedding)
        norm_q = np.linalg.norm(query)
        if norm_q == 0:
            return None, 0.0
        query = query / norm_q

        best_name: Optional[str] = None
        best_sim: float = 0.0

        candidates = (
            {search_name: self._gallery_embeddings[search_name]}
            if search_name and search_name in self._gallery_embeddings
            else self._gallery_embeddings
        )

        for name, embeds in candidates.items():
            for ref in embeds:
                ref_arr = np.array(ref)
                ref_norm = np.linalg.norm(ref_arr)
                if ref_norm == 0:
                    continue
                ref_arr = ref_arr / ref_norm
                sim = float(np.dot(query, ref_arr))
                if sim > best_sim:
                    best_sim = sim
                    best_name = name

        return best_name, best_sim

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_embeddings(self) -> None:
        if os.path.isfile(self.embeddings_db_path):
            try:
                with open(self.embeddings_db_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                self._gallery_embeddings = data.get("embeddings", {})
                self._gallery_images = data.get("images", {})
                logger.info(
                    "Loaded %d appearance profiles from %s.",
                    len(self._gallery_embeddings),
                    self.embeddings_db_path,
                )
            except Exception as e:
                logger.error("Failed to load appearance embeddings: %s", e)
                self._gallery_embeddings = {}
                self._gallery_images = {}
        else:
            self._gallery_embeddings = {}
            self._gallery_images = {}

    def _save_embeddings(self) -> None:
        try:
            with open(self.embeddings_db_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {"embeddings": self._gallery_embeddings, "images": self._gallery_images},
                    fh,
                    indent=2,
                )
        except Exception as e:
            logger.error("Failed to save appearance embeddings: %s", e)
