"""
Object Detection Module - General-Purpose YOLOv8 Multi-Class Detector
=====================================================================

Detects all 80 COCO classes using YOLOv8. Returns categorized results
grouped into persons, vehicles, animals, and items. Supports configurable
class filtering to narrow down detection scope per camera/stream.

Kaggle Dataset Sourcing Suggestions:
    - COCO Dataset: https://www.kaggle.com/datasets/awsaf49/coco-2017-dataset
    - Open Images Dataset: https://www.kaggle.com/datasets/googleai/open-images-v7
    - Pascal VOC: https://www.kaggle.com/datasets/aladdinpersson/pascal-voc-dataset
"""

import logging
import time
from typing import Dict, Any, List, Optional
import numpy as np
import cv2

from .base_detector import BaseDetector

logger = logging.getLogger(__name__)

# ── COCO-80 Class Taxonomy ─────────────────────────────────────────────────
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush"
]

CATEGORY_MAP = {
    "persons": {"person"},
    "vehicles": {"bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"},
    "animals": {
        "bird", "cat", "dog", "horse", "sheep", "cow",
        "elephant", "bear", "zebra", "giraffe"
    },
    "items": set(COCO_CLASSES) - {"person", "bicycle", "car", "motorcycle", "airplane",
                                   "bus", "train", "truck", "boat", "bird", "cat", "dog",
                                   "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}
}


class ObjectDetectionDetector(BaseDetector):
    """
    General-purpose object detection using YOLOv8 across all 80 COCO classes.

    Returns categorised results split into **persons**, **vehicles**, **animals**,
    and **items**. Supports an optional class filter list so that individual
    cameras can be configured to only report a subset of detections.

    Config keys:
        model_path       (str)  : Path to YOLOv8 weights. Default ``"yolov8n.pt"``
        allowed_classes  (list) : Whitelist of class names. ``None`` = all classes.
        max_detections   (int)  : Cap per frame. Default ``100``.
        nms_iou_threshold(float): NMS IoU overlap threshold. Default ``0.45``.
        input_size       (int)  : Model input resolution. Default ``640``.

    Kaggle Datasets:
        - COCO 2017 Dataset
        - Open Images Dataset v7
    """

    # ── Lifecycle ───────────────────────────────────────────────────────────
    def __init__(self, config: Dict[str, Any] = None):
        self.allowed_classes: Optional[set] = None
        self.max_detections: int = 100
        self.nms_iou_threshold: float = 0.45
        self.input_size: int = 640
        super().__init__("object_detection", config)

    def load_model(self) -> None:
        """
        Loads the YOLOv8 model for multi-class COCO detection.
        Falls back to OpenCV-based contour analysis if YOLO is unavailable.
        """
        # Parse optional config
        allowed = self.config.get("allowed_classes", None)
        self.allowed_classes = set(allowed) if allowed else None
        self.max_detections = self.config.get("max_detections", 100)
        self.nms_iou_threshold = self.config.get("nms_iou_threshold", 0.45)
        self.input_size = self.config.get("input_size", 640)

        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            logger.info(
                "YOLOv8 model loaded for ObjectDetectionDetector (%s). "
                "Classes: %s",
                model_path,
                "ALL" if self.allowed_classes is None else list(self.allowed_classes),
            )
        except Exception as exc:
            logger.warning(
                "YOLOv8 unavailable (%s). ObjectDetectionDetector will use "
                "OpenCV contour-based fallback.", exc
            )
            self.model = None

    # ── Inference ───────────────────────────────────────────────────────────
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Run object detection on a single video frame.

        Args:
            frame:  BGR numpy array from cv2.VideoCapture.
            **kwargs:
                stream_id  (str) : Camera / stream identifier.
                timestamp  (float): Frame epoch timestamp.
                roi        (list) : Optional [x1,y1,x2,y2] region of interest.

        Returns:
            Dict with keys:
                triggered   – True when ≥ 1 detection passes filters.
                detections  – List of detection dicts (bbox, label, confidence, category).
                metadata    – Category-level counts + timing info.
                event_type  – ``"object_detection"``.
        """
        if not self.is_enabled:
            return self._empty_result()

        start = time.perf_counter()

        # Optionally crop to ROI
        roi = kwargs.get("roi")
        analysis_frame = self._crop_roi(frame, roi) if roi else frame

        if self.model is not None:
            detections = self._detect_yolo(analysis_frame, roi_offset=roi)
        else:
            detections = self._detect_fallback(analysis_frame, roi_offset=roi)

        # Apply class filter
        if self.allowed_classes:
            detections = [d for d in detections if d["label"] in self.allowed_classes]

        # Enforce max cap
        detections = sorted(detections, key=lambda d: d["confidence"], reverse=True)[
            : self.max_detections
        ]

        # Categorise
        categorised = self._categorise(detections)
        elapsed_ms = (time.perf_counter() - start) * 1000

        return {
            "triggered": len(detections) > 0,
            "detections": detections,
            "metadata": {
                "total_objects": len(detections),
                "category_counts": {k: len(v) for k, v in categorised.items()},
                "categories": categorised,
                "inference_time_ms": round(elapsed_ms, 2),
                "model_backend": "yolov8" if self.model else "opencv_fallback",
                "stream_id": kwargs.get("stream_id"),
            },
            "event_type": self.name,
        }

    # ── YOLOv8 Pathway ─────────────────────────────────────────────────────
    def _detect_yolo(self, frame: np.ndarray, roi_offset=None) -> List[Dict]:
        """Run YOLOv8 inference and return normalised detection dicts."""
        results = self.model(
            frame,
            imgsz=self.input_size,
            conf=self.confidence_threshold,
            iou=self.nms_iou_threshold,
            verbose=False,
        )
        detections: List[Dict] = []
        ox, oy = (roi_offset[0], roi_offset[1]) if roi_offset else (0, 0)

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0])
                label = self.model.names.get(cls_id, f"class_{cls_id}")
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                detections.append({
                    "bbox": [x1 + ox, y1 + oy, x2 + ox, y2 + oy],
                    "confidence": round(confidence, 4),
                    "label": label,
                    "class_id": cls_id,
                    "category": self._label_to_category(label),
                })
        return detections

    # ── OpenCV Fallback ─────────────────────────────────────────────────────
    def _detect_fallback(self, frame: np.ndarray, roi_offset=None) -> List[Dict]:
        """
        Lightweight contour-based object candidate extraction.

        Uses adaptive thresholding + morphology to find salient blobs,
        then assigns a generic ``"object"`` label. Useful as a placeholder
        until a trained model is deployed.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)

        # Adaptive threshold to handle uneven lighting
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 15, 4
        )

        # Morphological close to merge fragmented blobs
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h, w = frame.shape[:2]
        min_area = (h * w) * 0.002  # ignore very small blobs
        max_area = (h * w) * 0.85   # ignore frame-spanning blobs

        detections: List[Dict] = []
        ox, oy = (roi_offset[0], roi_offset[1]) if roi_offset else (0, 0)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / max(bh, 1)

            # Heuristic classification by aspect ratio / size
            if 0.3 < aspect < 0.7 and area > (h * w) * 0.01:
                label = "person"
            elif aspect > 1.3:
                label = "vehicle"
            else:
                label = "object"

            confidence = min(0.35 + (area / (h * w)), 0.85)
            detections.append({
                "bbox": [x + ox, y + oy, x + bw + ox, y + bh + oy],
                "confidence": round(confidence, 4),
                "label": label,
                "class_id": -1,
                "category": self._label_to_category(label),
            })
        return detections

    # ── Helpers ─────────────────────────────────────────────────────────────
    @staticmethod
    def _crop_roi(frame: np.ndarray, roi: List[int]) -> np.ndarray:
        """Crop frame to [x1, y1, x2, y2] region of interest."""
        x1, y1, x2, y2 = roi
        return frame[y1:y2, x1:x2]

    @staticmethod
    def _label_to_category(label: str) -> str:
        """Map a COCO class name to its high-level category."""
        for cat, members in CATEGORY_MAP.items():
            if label in members:
                return cat
        return "items"

    @staticmethod
    def _categorise(detections: List[Dict]) -> Dict[str, List[Dict]]:
        """Group a flat detection list into category buckets."""
        buckets: Dict[str, List[Dict]] = {
            "persons": [], "vehicles": [], "animals": [], "items": []
        }
        for d in detections:
            cat = d.get("category", "items")
            buckets.setdefault(cat, []).append(d)
        return buckets

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "triggered": False,
            "detections": [],
            "metadata": {},
            "event_type": self.name,
        }
