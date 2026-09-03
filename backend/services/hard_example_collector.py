"""Opt-in hard-example mining for improving the VMS detector with real camera data.

This module deliberately does NOT auto-train on YOLO's own predictions. Frames are saved to a
review queue with proposal metadata and must be human-reviewed/labelled before training. This
prevents self-training feedback loops from turning false positives into ground truth.
"""

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2

logger = logging.getLogger(__name__)


class HardExampleCollector:
    def __init__(self):
        self.enabled = os.getenv("VMS_COLLECT_HARD_EXAMPLES", "false").lower() == "true"
        self.root = Path(
            os.getenv(
                "VMS_HARD_EXAMPLE_DIR",
                os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "training_data", "review_queue")
                ),
            )
        )
        try:
            self.low_conf = float(os.getenv("VMS_HARD_EXAMPLE_LOW_CONF", "0.18"))
            self.high_conf = float(os.getenv("VMS_HARD_EXAMPLE_HIGH_CONF", "0.55"))
            self.min_interval = float(os.getenv("VMS_HARD_EXAMPLE_INTERVAL_SECONDS", "10"))
            self.max_per_day = int(os.getenv("VMS_HARD_EXAMPLE_MAX_PER_DAY", "500"))
        except ValueError:
            self.low_conf, self.high_conf, self.min_interval, self.max_per_day = 0.18, 0.55, 10.0, 500

        self.low_conf = max(0.0, min(1.0, self.low_conf))
        self.high_conf = max(self.low_conf, min(1.0, self.high_conf))
        self.min_interval = max(1.0, self.min_interval)
        self.max_per_day = max(1, self.max_per_day)
        self._last_saved = {}
        self._daily_counts = {}
        self._lock = threading.RLock()

    @staticmethod
    def _safe_stream_id(stream_id: Optional[str]) -> str:
        value = str(stream_id or "default")
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)[:100] or "default"

    def _is_hard_example(self, metadata: dict) -> tuple[bool, str]:
        detections = metadata.get("detections", []) if isinstance(metadata, dict) else []
        if not isinstance(detections, list) or not detections:
            return False, ""

        uncertain = []
        for det in detections:
            if not isinstance(det, dict):
                continue
            try:
                confidence = float(det.get("confidence", 0.0))
            except (TypeError, ValueError):
                continue
            if self.low_conf <= confidence <= self.high_conf:
                uncertain.append(det)

        if uncertain:
            labels = sorted({str(item.get("class", "object")) for item in uncertain})
            return True, "uncertain_yolo:" + ",".join(labels[:10])

        if int(metadata.get("tier2_error_count", 0) or 0) > 0:
            return True, "semantic_verifier_error"

        return False, ""

    def consider(self, frame, metadata: dict, stream_id: Optional[str] = None) -> bool:
        if not self.enabled or frame is None or getattr(frame, "size", 0) == 0:
            return False

        should_save, reason = self._is_hard_example(metadata)
        if not should_save:
            return False

        now = time.time()
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        safe_stream = self._safe_stream_id(stream_id)
        key = f"{day}:{safe_stream}"

        with self._lock:
            if now - self._last_saved.get(key, 0.0) < self.min_interval:
                return False
            if self._daily_counts.get(day, 0) >= self.max_per_day:
                return False
            self._last_saved[key] = now
            self._daily_counts[day] = self._daily_counts.get(day, 0) + 1

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        target_dir = self.root / day / safe_stream
        target_dir.mkdir(parents=True, exist_ok=True)
        image_path = target_dir / f"{timestamp}.jpg"
        json_path = target_dir / f"{timestamp}.json"

        try:
            jpeg_quality = max(50, min(100, int(os.getenv("VMS_HARD_EXAMPLE_JPEG_QUALITY", "90"))))
            if not cv2.imwrite(str(image_path), frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]):
                raise RuntimeError("cv2.imwrite returned False")

            sidecar = {
                "schema_version": 1,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "stream_id": stream_id,
                "reason": reason,
                "review_status": "pending",
                "ground_truth": None,
                "proposal_only": True,
                "model": metadata.get("model"),
                "device": metadata.get("device"),
                "detections": metadata.get("detections", []),
                "counts": metadata.get("counts", {}),
                "motion_score": metadata.get("motion_score"),
                "blur_score": metadata.get("blur_score"),
                "luminance": metadata.get("luminance"),
            }
            with open(json_path, "w", encoding="utf-8") as handle:
                json.dump(sidecar, handle, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.warning("Failed to save hard example for stream=%s: %s", stream_id, exc)
            for path in (image_path, json_path):
                try:
                    if path.exists():
                        path.unlink()
                except Exception:
                    pass
            return False


hard_example_collector = HardExampleCollector()
