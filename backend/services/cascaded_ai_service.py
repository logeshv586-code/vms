import logging
import os
import time
from typing import Iterable, Optional

from services.yolo26_engine import yolo26_engine
from services.gemma_onnx_engine import gemma_onnx_engine

try:
    from services.hard_example_collector import hard_example_collector
except Exception:
    hard_example_collector = None

logger = logging.getLogger(__name__)

# Standard COCO names plus custom names used by security-trained YOLO weights.
# The previous implementation checked only generic `vehicle` and `bag`, which means normal
# Ultralytics COCO detections such as car/truck/bus/backpack/handbag never reached Tier 2.
SEMANTIC_CLASSES = {
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "bus",
    "truck",
    "vehicle",
    "backpack",
    "handbag",
    "suitcase",
    "bag",
    "umbrella",
    "bottle",
    "laptop",
    "cell phone",
    "knife",
    "scissors",
    "weapon",
    "gun",
    "helmet",
    "fire",
    "smoke",
}


class CascadedAIService:
    """
    Realtime cascaded pipeline.

    Tier 1: YOLO26 + per-camera tracking.
    Tier 2: optional PaliGemma ONNX region analysis.

    Tier 2 enriches a YOLO proposal; it never silently replaces geometry/tracking metadata.
    """

    def __init__(self):
        self.yolo = yolo26_engine
        self.gemma = gemma_onnx_engine
        try:
            self.semantic_min_conf = float(os.getenv("VMS_SEMANTIC_MIN_YOLO_CONF", "0.20"))
        except ValueError:
            self.semantic_min_conf = 0.20
        self.semantic_min_conf = max(0.01, min(0.99, self.semantic_min_conf))
        self.semantic_all_classes = os.getenv("VMS_SEMANTIC_ALL_CLASSES", "false").lower() == "true"

    def _semantic_candidate(self, detection: dict) -> bool:
        try:
            confidence = float(detection.get("confidence", 0.0))
        except (TypeError, ValueError):
            return False
        if confidence < self.semantic_min_conf:
            return False
        label = str(detection.get("class", "")).strip().lower()
        return self.semantic_all_classes or label in SEMANTIC_CLASSES

    def process_frame(
        self,
        frame,
        stream_id: Optional[str] = None,
        tasks: Optional[Iterable[str]] = None,
    ):
        """Run the live detector and attach semantic results to the exact source detection."""
        start_total = time.perf_counter()
        requested_tasks = tuple(tasks or ("caption",))

        annotated_frame, metadata = self.yolo.process_frame(frame, stream_id=stream_id)
        metadata = metadata if isinstance(metadata, dict) else {"detections": []}

        # Feed uncertain examples into a review queue only when explicitly enabled.
        if hard_example_collector is not None:
            try:
                hard_example_collector.consider(frame, metadata, stream_id=stream_id)
            except Exception as exc:
                logger.debug("Hard-example collection skipped: %s", exc)

        if metadata.get("skipped", False):
            metadata["tier2_active"] = bool(getattr(self.gemma, "initialized", False))
            metadata["tier2_backend"] = "paligemma_onnx" if metadata["tier2_active"] else "unavailable"
            metadata["total_latency_ms"] = (time.perf_counter() - start_total) * 1000.0
            return annotated_frame, metadata

        detections = metadata.get("detections", [])
        if not isinstance(detections, list) or not detections:
            metadata["tier2_active"] = bool(getattr(self.gemma, "initialized", False))
            metadata["tier2_backend"] = "paligemma_onnx" if metadata["tier2_active"] else "unavailable"
            metadata["total_latency_ms"] = (time.perf_counter() - start_total) * 1000.0
            return annotated_frame, metadata

        regions_to_analyze = []
        for detection_index, det in enumerate(detections):
            if not isinstance(det, dict) or not self._semantic_candidate(det):
                continue
            bbox = det.get("bbox")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                continue
            regions_to_analyze.append(
                {
                    "box": list(bbox),
                    "label": str(det.get("class", "object")),
                    "id": det.get("id"),
                    # Index is the authoritative merge key. Track IDs can be None and can change.
                    "detection_index": detection_index,
                }
            )

        tier2_active = bool(getattr(self.gemma, "initialized", False))
        tier2_errors = 0
        if regions_to_analyze and tier2_active:
            for task in requested_tasks:
                if task not in {"caption", "ocr", "verify", "context"}:
                    logger.warning("Ignoring unsupported Tier 2 task: %s", task)
                    continue
                try:
                    gemma_results = self.gemma.analyze_regions(
                        frame,
                        regions_to_analyze,
                        task_type=task,
                    )
                except Exception as exc:
                    logger.exception("Tier 2 task %s failed: %s", task, exc)
                    tier2_errors += len(regions_to_analyze)
                    continue

                for res in gemma_results or []:
                    if not isinstance(res, dict):
                        tier2_errors += 1
                        continue
                    region = res.get("region") or {}
                    detection_index = region.get("detection_index")
                    if not isinstance(detection_index, int) or not 0 <= detection_index < len(detections):
                        tier2_errors += 1
                        continue
                    if "error" in res:
                        detections[detection_index][f"gemma_{task}_error"] = str(res.get("error"))
                        tier2_errors += 1
                        continue
                    detections[detection_index][f"gemma_{task}"] = res.get("analysis", "")

        metadata["detections"] = detections
        metadata["tier2_active"] = tier2_active
        metadata["tier2_backend"] = "paligemma_onnx" if tier2_active else "unavailable"
        metadata["tier2_candidate_count"] = len(regions_to_analyze)
        metadata["tier2_error_count"] = tier2_errors
        metadata["total_latency_ms"] = (time.perf_counter() - start_total) * 1000.0
        return annotated_frame, metadata


cascaded_ai_service = CascadedAIService()
