"""Annotated pre-event/post-event evidence recording for VMS alerts.

The live AI loop feeds already-annotated frames into a bounded JPEG ring buffer.
When an event is persisted, this service writes the buffered frames before the
incident plus frames after it into a validated MP4. This avoids opening a new
raw RTSP session after the incident and preserves bounding boxes, centre points,
track IDs, confidence labels and zone overlays in the evidence itself.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from collections import defaultdict, deque
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import cv2
import numpy as np

from services.camera_ai_preferences import get_camera_ai_preferences, normalize_camera_id

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPOSITORY_DIR = BACKEND_DIR.parent
DATA_DIR = BACKEND_DIR / "data"
PROOFS_DIR = DATA_DIR / "proofs"
PROOFS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FramePacket:
    timestamp: float
    jpeg: bytes
    detections: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateCapture:
    stream_id: str
    signature: str
    trigger_ts: float
    frames: List[FramePacket]
    event: Dict[str, Any]
    expires_at: float


@dataclass
class EventCapture:
    event_id: str
    stream_id: str
    trigger_ts: float
    deadline: float
    frames: List[FramePacket]
    event: Dict[str, Any]
    preferences: Dict[str, Any]
    last_packet_ts: float = 0.0


class EventEvidenceService:
    """Thread-safe rolling annotated evidence recorder."""

    def __init__(self) -> None:
        self._buffers: Dict[str, Deque[FramePacket]] = defaultdict(deque)
        self._pending: Dict[str, EventCapture] = {}
        self._candidates: Dict[Tuple[str, str], CandidateCapture] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._watchdog = threading.Thread(
            target=self._watchdog_loop,
            daemon=True,
            name="VMS-Evidence-Watchdog",
        )
        self._watchdog.start()

    @staticmethod
    def _signature(event: Dict[str, Any]) -> str:
        rule_id = event.get("id") if isinstance(event, dict) else None
        rule_name = event.get("type") if isinstance(event, dict) else None
        return f"{rule_id}:{str(rule_name or 'event').strip().lower()}"

    @staticmethod
    def _safe_detection(det: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(det, dict):
            return {}
        return {
            "track_id": det.get("track_id", det.get("id")),
            "class_name": det.get("class_name", det.get("class", det.get("label"))),
            "class_id": det.get("class_id"),
            "confidence": det.get("confidence"),
            "bbox": det.get("bbox", det.get("box")),
            "centroid": det.get("centroid", det.get("center")),
            "zone_id": det.get("zone_id"),
            "zone_name": det.get("zone_name"),
        }

    def register_frame(
        self,
        stream_id: str,
        annotated_frame: np.ndarray,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add one annotated AI frame to the rolling buffer and active captures."""
        if (
            not stream_id
            or annotated_frame is None
            or not isinstance(annotated_frame, np.ndarray)
            or annotated_frame.size == 0
        ):
            return

        try:
            quality = int(os.getenv("VMS_EVIDENCE_JPEG_QUALITY", "78"))
            quality = max(45, min(95, quality))
            ok, encoded = cv2.imencode(
                ".jpg",
                annotated_frame,
                [cv2.IMWRITE_JPEG_QUALITY, quality],
            )
            if not ok:
                return
        except Exception as exc:
            logger.debug("Evidence frame encoding skipped for %s: %s", stream_id, exc)
            return

        metadata = metadata if isinstance(metadata, dict) else {}
        detections = [
            self._safe_detection(item)
            for item in metadata.get("detections", [])
            if isinstance(item, dict)
        ]
        now = time.time()
        packet = FramePacket(
            timestamp=now,
            jpeg=encoded.tobytes(),
            detections=detections,
            metadata={
                "frame_width": metadata.get("frame_width"),
                "frame_height": metadata.get("frame_height"),
                "model": metadata.get("model"),
                "device": metadata.get("device"),
                "tracker": metadata.get("tracker"),
                "detector_settings": deepcopy(metadata.get("detector_settings", {})),
            },
        )
        key = normalize_camera_id(stream_id) or stream_id
        prefs = get_camera_ai_preferences(stream_id)
        keep_seconds = max(
            12.0,
            float(prefs.get("evidence_pre_seconds", 10.0)) + 2.0,
        )

        ready_to_finalize: List[str] = []
        with self._lock:
            buffer = self._buffers[key]
            buffer.append(packet)
            cutoff = now - keep_seconds
            while buffer and buffer[0].timestamp < cutoff:
                buffer.popleft()

            for capture in self._pending.values():
                if normalize_camera_id(capture.stream_id) != key:
                    continue
                # Do not let late frames extend the user-configured post-event window.
                if (
                    packet.timestamp > capture.last_packet_ts
                    and packet.timestamp <= capture.deadline
                ):
                    capture.frames.append(packet)
                    capture.last_packet_ts = packet.timestamp
                if now >= capture.deadline:
                    ready_to_finalize.append(capture.event_id)

            for candidate_key, candidate in list(self._candidates.items()):
                if normalize_camera_id(candidate.stream_id) != key:
                    continue
                if now > candidate.expires_at:
                    self._candidates.pop(candidate_key, None)
                    continue
                if not candidate.frames or packet.timestamp > candidate.frames[-1].timestamp:
                    candidate.frames.append(packet)

        for event_id in set(ready_to_finalize):
            self._finalize_async(event_id)

    def pin_candidate(self, stream_id: str, event: Dict[str, Any]) -> None:
        """Pin pre-event frames before a slower Layer-3 validation starts."""
        if not stream_id or not isinstance(event, dict):
            return
        now = time.time()
        prefs = get_camera_ai_preferences(stream_id)
        pre_seconds = float(prefs.get("evidence_pre_seconds", 10.0))
        signature = self._signature(event)
        key = normalize_camera_id(stream_id) or stream_id
        candidate_key = (key, signature)

        with self._lock:
            existing = self._candidates.get(candidate_key)
            if existing and existing.expires_at > now:
                return
            frames = [
                packet
                for packet in self._buffers.get(key, ())
                if packet.timestamp >= now - pre_seconds
            ]
            self._candidates[candidate_key] = CandidateCapture(
                stream_id=stream_id,
                signature=signature,
                trigger_ts=now,
                frames=list(frames),
                event=deepcopy(event),
                expires_at=now + 180.0,
            )

    def discard_candidate(self, stream_id: str, event: Dict[str, Any]) -> None:
        key = normalize_camera_id(stream_id) or stream_id
        with self._lock:
            self._candidates.pop((key, self._signature(event)), None)

    def start_event(self, event_id: str, stream_id: str, event: Dict[str, Any]) -> None:
        """Bind a persisted event ID to buffered annotated frames."""
        if not event_id or not stream_id:
            return
        now = time.time()
        prefs = get_camera_ai_preferences(stream_id)
        pre_seconds = float(prefs.get("evidence_pre_seconds", 10.0))
        post_seconds = float(prefs.get("evidence_post_seconds", 20.0))
        key = normalize_camera_id(stream_id) or stream_id
        candidate_key = (key, self._signature(event))

        with self._lock:
            if event_id in self._pending:
                return
            candidate = self._candidates.pop(candidate_key, None)
            if candidate:
                trigger_ts = candidate.trigger_ts
                start_ts = trigger_ts - pre_seconds
                end_ts = trigger_ts + post_seconds
                # Layer-3 validation may finish after the requested post window.
                # Retain only the configured evidence interval instead of every
                # candidate frame gathered while the VLM was reasoning.
                frames = [
                    packet
                    for packet in candidate.frames
                    if start_ts <= packet.timestamp <= end_ts
                ]
            else:
                trigger_ts = now
                frames = [
                    packet
                    for packet in self._buffers.get(key, ())
                    if packet.timestamp >= now - pre_seconds
                ]

            last_packet_ts = frames[-1].timestamp if frames else 0.0
            self._pending[event_id] = EventCapture(
                event_id=event_id,
                stream_id=stream_id,
                trigger_ts=trigger_ts,
                deadline=trigger_ts + post_seconds,
                frames=frames,
                event=deepcopy(event) if isinstance(event, dict) else {},
                preferences=deepcopy(prefs),
                last_packet_ts=last_packet_ts,
            )

        self._mark_event_status(event_id, "recording")
        if now >= trigger_ts + post_seconds:
            self._finalize_async(event_id)

    def _watchdog_loop(self) -> None:
        while not self._stop.wait(0.5):
            now = time.time()
            finalize: List[str] = []
            with self._lock:
                for event_id, capture in self._pending.items():
                    if now >= capture.deadline:
                        finalize.append(event_id)
                for key, candidate in list(self._candidates.items()):
                    if now > candidate.expires_at:
                        self._candidates.pop(key, None)
            for event_id in finalize:
                self._finalize_async(event_id)

    def _finalize_async(self, event_id: str) -> None:
        with self._lock:
            capture = self._pending.pop(event_id, None)
        if capture is None:
            return
        threading.Thread(
            target=self._finalize_capture,
            args=(capture,),
            daemon=True,
            name=f"VMS-Evidence-{event_id}",
        ).start()

    @staticmethod
    def _draw_event_banner(
        frame: np.ndarray,
        capture: EventCapture,
        frame_ts: float,
    ) -> np.ndarray:
        image = frame.copy()
        height, width = image.shape[:2]
        event_name = str(
            capture.event.get("type")
            or capture.event.get("rule_name")
            or "AI Event"
        )
        severity = str(
            capture.event.get("severity")
            or capture.event.get("priority")
            or ""
        ).upper()
        timestamp_text = datetime.fromtimestamp(
            frame_ts,
            tz=timezone.utc,
        ).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (width, min(64, height)), (0, 0, 0), -1)
        cv2.rectangle(
            overlay,
            (0, max(0, height - 34)),
            (width, height),
            (0, 0, 0),
            -1,
        )
        image = cv2.addWeighted(overlay, 0.68, image, 0.32, 0)

        cv2.putText(
            image,
            f"EVENT {capture.event_id} | {event_name} | {severity}",
            (14, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            f"CAMERA: {capture.stream_id}",
            (14, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            image,
            timestamp_text,
            (14, height - 11),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        return image

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        configured = os.getenv("VMS_FFMPEG_PATH", "").strip()
        candidates = [
            Path(configured) if configured else None,
            BACKEND_DIR / "ffmpeg-master-latest-win64-gpl-shared" / "bin" / "ffmpeg.exe",
            BACKEND_DIR / "ffmpeg" / "ffmpeg.exe",
            REPOSITORY_DIR / "ffmpeg" / "ffmpeg.exe",
        ]
        for candidate in candidates:
            if candidate and candidate.exists() and candidate.is_file():
                return str(candidate)
        return shutil.which("ffmpeg")

    def _make_browser_compatible(
        self,
        source: Path,
        destination: Path,
    ) -> str:
        """Prefer H.264/yuv420p + faststart, with validated MP4V fallback."""
        ffmpeg = self._find_ffmpeg()
        compatibility_temp = destination.with_name(
            f".{destination.stem}.h264-writing.mp4"
        )

        if ffmpeg:
            command = [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "22",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(compatibility_temp),
            ]
            try:
                result = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=180,
                    check=False,
                )
                if (
                    result.returncode == 0
                    and compatibility_temp.exists()
                    and compatibility_temp.stat().st_size > 10_240
                    and self._validate_video(compatibility_temp)
                ):
                    if destination.exists():
                        destination.unlink()
                    os.replace(compatibility_temp, destination)
                    try:
                        source.unlink()
                    except OSError:
                        pass
                    return "h264"
            except Exception as exc:
                logger.warning(
                    "H.264 evidence finalization failed; using MP4V fallback: %s",
                    exc,
                )
            finally:
                try:
                    if compatibility_temp.exists():
                        compatibility_temp.unlink()
                except OSError:
                    pass

        if destination.exists():
            destination.unlink()
        os.replace(source, destination)
        return "mp4v-fallback"

    def _finalize_capture(self, capture: EventCapture) -> None:
        output = PROOFS_DIR / f"{capture.event_id}.mp4"
        metadata_path = PROOFS_DIR / f"{capture.event_id}.json"
        temp_output = PROOFS_DIR / f".{capture.event_id}.writing.mp4"
        writer = None

        try:
            packets = sorted(capture.frames, key=lambda item: item.timestamp)
            if len(packets) < 2:
                raise RuntimeError("Insufficient annotated frames for event evidence")

            decoded_first = cv2.imdecode(
                np.frombuffer(packets[0].jpeg, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
            if decoded_first is None or decoded_first.size == 0:
                raise RuntimeError("Unable to decode first annotated evidence frame")
            height, width = decoded_first.shape[:2]

            configured_fps = float(capture.preferences.get("ai_fps", 4.0) or 4.0)
            fps = max(1.0, min(30.0, configured_fps))
            writer = cv2.VideoWriter(
                str(temp_output),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                (width, height),
            )
            if not writer.isOpened():
                raise RuntimeError("OpenCV MP4 writer could not be opened")

            written = 0
            for packet in packets:
                frame = cv2.imdecode(
                    np.frombuffer(packet.jpeg, dtype=np.uint8),
                    cv2.IMREAD_COLOR,
                )
                if frame is None or frame.size == 0:
                    continue
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(
                        frame,
                        (width, height),
                        interpolation=cv2.INTER_LINEAR,
                    )
                frame = self._draw_event_banner(frame, capture, packet.timestamp)
                writer.write(frame)
                written += 1

            writer.release()
            writer = None
            if (
                written < 2
                or not temp_output.exists()
                or temp_output.stat().st_size <= 10_240
            ):
                raise RuntimeError("Annotated evidence MP4 is empty or too small")

            video_codec = self._make_browser_compatible(temp_output, output)
            if not self._validate_video(output):
                raise RuntimeError("Annotated evidence MP4 failed validation")

            nearest = min(
                packets,
                key=lambda item: abs(item.timestamp - capture.trigger_ts),
            )
            detection_snapshot = nearest.detections
            metadata = {
                "event_id": capture.event_id,
                "camera_id": capture.stream_id,
                "rule_id": capture.event.get("id"),
                "rule_name": capture.event.get("type"),
                "severity": capture.event.get("severity"),
                "message": capture.event.get("message"),
                "event_timestamp_utc": datetime.fromtimestamp(
                    capture.trigger_ts,
                    timezone.utc,
                ).isoformat(),
                "evidence_start_utc": datetime.fromtimestamp(
                    packets[0].timestamp,
                    timezone.utc,
                ).isoformat(),
                "evidence_end_utc": datetime.fromtimestamp(
                    packets[-1].timestamp,
                    timezone.utc,
                ).isoformat(),
                "frame_count": written,
                "fps": fps,
                "resolution": {"width": width, "height": height},
                "detections_at_event": detection_snapshot,
                "detector": nearest.metadata,
                "preferences": capture.preferences,
                "video_file": output.name,
                "video_codec": video_codec,
                "video_size_bytes": output.stat().st_size,
                "validated": True,
            }
            self._atomic_json_write(metadata_path, metadata)

            self._update_event(
                capture.event_id,
                {
                    "video_proof_url": f"/api/augment/events/proofs/{output.name}",
                    "proof_status": "ready",
                    "proof_validated": True,
                    "proof_frame_count": written,
                    "proof_video_codec": video_codec,
                    "proof_start_at": metadata["evidence_start_utc"],
                    "proof_end_at": metadata["evidence_end_utc"],
                    "detection_snapshot": detection_snapshot,
                    "detector_metadata": nearest.metadata,
                },
            )
            logger.info(
                "Annotated event evidence ready: %s camera=%s frames=%s codec=%s",
                capture.event_id,
                capture.stream_id,
                written,
                video_codec,
            )
        except Exception as exc:
            logger.warning(
                "Annotated event evidence failed for %s: %s",
                capture.event_id,
                exc,
            )
            for path in (temp_output, output):
                try:
                    if path.exists():
                        path.unlink()
                except OSError:
                    pass
            self._update_event(
                capture.event_id,
                {
                    "video_proof_url": None,
                    "proof_status": "failed",
                    "proof_validated": False,
                    "proof_error": str(exc),
                },
            )
        finally:
            if writer is not None:
                try:
                    writer.release()
                except Exception:
                    pass

    @staticmethod
    def _validate_video(path: Path) -> bool:
        try:
            if not path.exists() or path.stat().st_size <= 10_240:
                return False
            capture = cv2.VideoCapture(str(path))
            if not capture.isOpened():
                capture.release()
                return False
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            ok, frame = capture.read()
            capture.release()
            return bool(
                ok
                and frame is not None
                and frame.size > 0
                and frame_count >= 2
            )
        except Exception:
            return False

    @staticmethod
    def _atomic_json_write(path: Path, payload: Dict[str, Any]) -> None:
        temp = path.with_suffix(path.suffix + ".tmp")
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)

    @staticmethod
    def _update_event(event_id: str, updates: Dict[str, Any]) -> None:
        try:
            from routes.events import update_event_record

            update_event_record(event_id, updates)
        except Exception as exc:
            logger.warning(
                "Could not update event evidence status for %s: %s",
                event_id,
                exc,
            )

    @classmethod
    def _mark_event_status(cls, event_id: str, status: str) -> None:
        cls._update_event(
            event_id,
            {"proof_status": status, "proof_validated": False},
        )

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "buffered_streams": len(self._buffers),
                "pending_events": len(self._pending),
                "pinned_candidates": len(self._candidates),
                "proof_directory": str(PROOFS_DIR),
                "ffmpeg_available": bool(self._find_ffmpeg()),
            }

    def clear_stream(self, stream_id: str) -> None:
        key = normalize_camera_id(stream_id) or stream_id
        with self._lock:
            self._buffers.pop(key, None)
            for event_id, capture in list(self._pending.items()):
                if normalize_camera_id(capture.stream_id) == key:
                    self._pending.pop(event_id, None)
            for candidate_key in list(self._candidates):
                if candidate_key[0] == key:
                    self._candidates.pop(candidate_key, None)


event_evidence_service = EventEvidenceService()
