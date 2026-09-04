from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Optional, List, Any
import json
import os
import sys
import cv2
import time
import threading
import logging
import numpy as np
from pathlib import Path
from urllib.parse import urlparse

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ALPR_DIR = os.path.join(BACKEND_DIR, "Event_Detections", "Automatic-License-Plate-Recognition and Vehicle Detection")
if ALPR_DIR not in sys.path:
    sys.path.append(ALPR_DIR)

logger = logging.getLogger(__name__)

ALPR_AVAILABLE: Optional[bool] = None
util_get_car = None
util_read_license_plate = None
YOLO = None
Sort = None
_INIT_LOCK = threading.RLock()


def _lazy_init_alpr() -> bool:
    """Load the real ALPR detector/tracker stack exactly once and fail closed."""
    global ALPR_AVAILABLE, util_get_car, util_read_license_plate, YOLO, Sort
    with _INIT_LOCK:
        if ALPR_AVAILABLE is not None:
            return ALPR_AVAILABLE
        try:
            from util import get_car as _get_car, read_license_plate as _read_license_plate
            from ultralytics import YOLO as _YOLO
            from sort.sort import Sort as _Sort

            util_get_car = _get_car
            util_read_license_plate = _read_license_plate
            YOLO = _YOLO
            Sort = _Sort
            ALPR_AVAILABLE = True
            logger.info("Vehicle monitoring ALPR detector and SORT tracker initialized")
        except Exception as exc:
            ALPR_AVAILABLE = False
            logger.warning("Vehicle monitoring ALPR dependencies unavailable: %s", exc)
        return bool(ALPR_AVAILABLE)


router = APIRouter(prefix="/api/vehicle-monitoring", tags=["vehicle-monitoring"])

VEHICLE_DATA_DIR = Path(BACKEND_DIR) / "vehicle_data"
SNAPSHOTS_DIR = VEHICLE_DATA_DIR / "snapshots"
VEHICLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
CAMERA_CONFIG_PATH = os.path.join(BACKEND_DIR, "data", "camera_configuration.json")


def load_camera_config() -> Dict[str, Dict[str, str]]:
    try:
        with open(CAMERA_CONFIG_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.error("Failed to load camera configuration: %s", exc)
        return {}


class DetectionEvent(BaseModel):
    id: str
    stream_id: str
    timestamp: float
    camera_ip: Optional[str]
    vehicle_id: int
    license_plate: Optional[str]
    license_plate_score: Optional[float]
    vehicle_bbox: List[float]
    plate_bbox: List[float]
    snapshots: Dict[str, str]
    vehicle_type: Optional[str] = "Unknown"
    vehicle_category: Optional[str] = "Vehicle"


def _normalize_id(value: str) -> str:
    if not value:
        return ""
    clean = str(value).lower().replace("camera-", "").replace("camera_", "")
    for char in ("-", "_", ".", " "):
        clean = clean.replace(char, "")
    return clean


def is_vehicle_monitoring_enabled_for_camera(stream_id: str) -> bool:
    """Return True only when authoritative rule 22 is global + assigned to the camera."""
    try:
        events_path = os.path.join(BACKEND_DIR, "..", "events_configuration.json")
        if not os.path.exists(events_path):
            return False
        with open(events_path, "r", encoding="utf-8") as handle:
            rules = json.load(handle).get("rules", [])
        vehicle_rule = next((rule for rule in rules if rule.get("id") == 22), None)
        if not vehicle_rule or not vehicle_rule.get("enabled", False):
            return False

        rules_path = os.path.join(BACKEND_DIR, "..", "camera_rules.json")
        if not os.path.exists(rules_path):
            return False
        with open(rules_path, "r", encoding="utf-8") as handle:
            camera_rules = json.load(handle).get("camera_rules", {})

        norm_stream = _normalize_id(stream_id)
        for camera_id, rule_ids in camera_rules.items():
            if _normalize_id(camera_id) == norm_stream:
                return 22 in {int(rule_id) for rule_id in (rule_ids or [])}
        return False
    except Exception as exc:
        logger.error("Error checking camera rules for %s: %s", stream_id, exc)
        return False


def _resolve_stream_from_url(rtsp_url: str) -> Optional[str]:
    config = load_camera_config()
    for collection, cameras in config.items():
        if not isinstance(cameras, dict):
            continue
        for ip, configured_url in cameras.items():
            if str(configured_url) == str(rtsp_url):
                return f"{collection}_{ip}"
    try:
        host = urlparse(str(rtsp_url)).hostname
    except Exception:
        host = None
    if host:
        for collection, cameras in config.items():
            if isinstance(cameras, dict) and host in cameras:
                return f"{collection}_{host}"
    return None


class VehicleMonitorWorker:
    def __init__(self, stream_id: str, rtsp_url: str, coco_model_path: str, plate_model_path: str):
        if not _lazy_init_alpr():
            raise RuntimeError("ALPR detector or SORT tracker is not available")
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.coco_model_path = coco_model_path
        self.plate_model_path = plate_model_path
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._mot = Sort()
        self._captured_keys = set()
        self._events: List[DetectionEvent] = []
        self._max_events = 500
        self._coco_model = YOLO(self.coco_model_path)
        self._plate_model = YOLO(self.plate_model_path)
        self._load_persisted_events()

    @property
    def _events_file(self) -> Path:
        safe_stream = self.stream_id.replace("/", "_").replace("\\", "_")
        return VEHICLE_DATA_DIR / f"events_{safe_stream}.json"

    def _load_persisted_events(self):
        try:
            if not self._events_file.exists():
                return
            with open(self._events_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            for item in data if isinstance(data, list) else []:
                evt = DetectionEvent(**item)
                self._events.append(evt)
                self._captured_keys.add(f"{evt.vehicle_id}_{evt.license_plate}")
            logger.info("Loaded %d persisted vehicle events for %s", len(self._events), self.stream_id)
        except Exception as exc:
            logger.error("Error loading persisted vehicle events: %s", exc)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"VMS-ALPR-{self.stream_id}")
        self._thread.start()
        logger.info("Vehicle monitor started for %s", self.stream_id)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            logger.info("Vehicle monitor stopped for %s", self.stream_id)

    def _save_event(self, evt: DetectionEvent):
        with self._lock:
            self._events.append(evt)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
            temp_path = self._events_file.with_suffix(self._events_file.suffix + ".tmp")
            try:
                with open(temp_path, "w", encoding="utf-8") as handle:
                    payload = [event.model_dump() if hasattr(event, "model_dump") else event.dict() for event in self._events]
                    json.dump(payload, handle, indent=2, ensure_ascii=False)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self._events_file)
            except Exception as exc:
                logger.error("Failed to persist vehicle events: %s", exc)
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except OSError:
                    pass

    def _publish_central_event(self, evt: DetectionEvent):
        """Route a confirmed ALPR detection into the central event/evidence path."""
        try:
            from services.pattern_engine import pattern_engine

            confidence = float(evt.license_plate_score) if evt.license_plate_score is not None else None
            plate = evt.license_plate or "unread plate"
            pattern_engine.trigger_alert_api(
                self.stream_id,
                {
                    "id": 22,
                    "type": "Vehicle Monitoring",
                    "severity": "low",
                    "message": f"{evt.vehicle_type} detected with license plate {plate}",
                    "trigger_layer3": False,
                    "data": {
                        "track_id": evt.vehicle_id,
                        "vehicle_type": evt.vehicle_type,
                        "vehicle_category": evt.vehicle_category,
                        "license_plate": evt.license_plate,
                        "confidence": confidence,
                        "vehicle_bbox": evt.vehicle_bbox,
                        "plate_bbox": evt.plate_bbox,
                        "snapshots": evt.snapshots,
                    },
                },
            )
        except Exception as exc:
            logger.warning("Could not publish central vehicle event for %s: %s", self.stream_id, exc)

    def _run(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        vehicles = {2, 3, 5, 7}  # car, motorcycle, bus, truck in COCO
        frame_idx = 0
        skip_frames = 2
        consecutive_failures = 0

        while not self._stop.is_set():
            ret, frame = cap.read()
            if not ret or frame is None:
                consecutive_failures += 1
                if consecutive_failures >= 30:
                    logger.warning("ALPR stream stalled for %s; reconnecting", self.stream_id)
                    try:
                        cap.release()
                    except Exception:
                        pass
                    time.sleep(1.0)
                    cap = cv2.VideoCapture(self.rtsp_url)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
                    consecutive_failures = 0
                else:
                    time.sleep(0.1)
                continue

            consecutive_failures = 0
            frame_idx += 1
            if frame_idx % (skip_frames + 1) != 0:
                continue

            try:
                detector_result = self._coco_model(frame, verbose=False)[0]
                detections = []
                original_detections = []
                for detection in detector_result.boxes.data.tolist():
                    x1, y1, x2, y2, score, class_id = detection
                    if int(class_id) in vehicles:
                        detections.append([x1, y1, x2, y2, score])
                        original_detections.append([x1, y1, x2, y2, score, int(class_id)])
                track_ids = self._mot.update(np.asarray(detections)) if detections else np.empty((0, 5))

                plate_result = self._plate_model(frame, verbose=False)[0]
                for plate_detection in plate_result.boxes.data.tolist():
                    x1, y1, x2, y2, score, _class_id = plate_detection
                    xcar1, ycar1, xcar2, ycar2, car_id = util_get_car(plate_detection, track_ids)
                    if car_id == -1:
                        continue

                    plate_crop = frame[int(y1):int(y2), int(x1):int(x2), :]
                    if plate_crop.size == 0:
                        continue
                    try:
                        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
                        _, threshold = cv2.threshold(gray, 64, 255, cv2.THRESH_BINARY_INV)
                    except Exception:
                        threshold = plate_crop

                    plate_text, plate_score = util_read_license_plate(threshold)
                    if plate_text is None:
                        continue
                    vehicle_key = f"{int(car_id)}_{plate_text}"
                    if vehicle_key in self._captured_keys:
                        continue
                    self._captured_keys.add(vehicle_key)

                    timestamp_ms = int(time.time() * 1000)
                    safe_stream = self.stream_id.replace("/", "_").replace("\\", "_")
                    stream_dir = SNAPSHOTS_DIR / safe_stream
                    stream_dir.mkdir(parents=True, exist_ok=True)
                    vehicle_crop = frame[int(ycar1):int(ycar2), int(xcar1):int(xcar2), :]
                    vehicle_name = f"veh_{timestamp_ms}_id{int(car_id)}.jpg"
                    plate_name = f"plate_{timestamp_ms}_id{int(car_id)}.jpg"
                    vehicle_path = stream_dir / vehicle_name
                    plate_path = stream_dir / plate_name
                    try:
                        if vehicle_crop.size > 0:
                            cv2.imwrite(str(vehicle_path), vehicle_crop)
                        cv2.imwrite(str(plate_path), plate_crop)
                    except Exception as exc:
                        logger.warning("Failed to save vehicle snapshots: %s", exc)

                    best_iou = -1.0
                    best_class_id = 2
                    for ox1, oy1, ox2, oy2, _oscore, object_class_id in original_detections:
                        ix1 = max(xcar1, ox1)
                        iy1 = max(ycar1, oy1)
                        ix2 = min(xcar2, ox2)
                        iy2 = min(ycar2, oy2)
                        if ix2 <= ix1 or iy2 <= iy1:
                            continue
                        intersection = (ix2 - ix1) * (iy2 - iy1)
                        area1 = max(1.0, (xcar2 - xcar1) * (ycar2 - ycar1))
                        area2 = max(1.0, (ox2 - ox1) * (oy2 - oy1))
                        union = area1 + area2 - intersection
                        iou = intersection / union if union > 0 else 0.0
                        if iou > best_iou:
                            best_iou = iou
                            best_class_id = object_class_id

                    vehicle_type = "Car"
                    vehicle_category = "Sedan/SUV"
                    if best_class_id == 3:
                        vehicle_type, vehicle_category = "Motorcycle", "Two-Wheeler"
                    elif best_class_id == 5:
                        vehicle_type, vehicle_category = "Bus", "Heavy Vehicle"
                    elif best_class_id == 7:
                        vehicle_type, vehicle_category = "Truck", "Heavy Commercial Vehicle"

                    evt = DetectionEvent(
                        id=f"{safe_stream}_{timestamp_ms}_{int(car_id)}",
                        stream_id=self.stream_id,
                        timestamp=time.time(),
                        camera_ip=self.stream_id.split("_")[-1] if "_" in self.stream_id else None,
                        vehicle_id=int(car_id),
                        license_plate=plate_text,
                        license_plate_score=float(plate_score) if plate_score is not None else None,
                        vehicle_bbox=[float(xcar1), float(ycar1), float(xcar2), float(ycar2)],
                        plate_bbox=[float(x1), float(y1), float(x2), float(y2)],
                        snapshots={
                            "vehicle": f"/api/vehicle-monitoring/snapshot/{safe_stream}/{vehicle_name}",
                            "plate": f"/api/vehicle-monitoring/snapshot/{safe_stream}/{plate_name}",
                        },
                        vehicle_type=vehicle_type,
                        vehicle_category=vehicle_category,
                    )
                    self._save_event(evt)
                    self._publish_central_event(evt)
            except Exception as exc:
                logger.error("Error in vehicle monitoring loop for %s: %s", self.stream_id, exc)
                time.sleep(0.05)

        try:
            cap.release()
        except Exception:
            pass

    def get_events(self, limit: int = 50) -> List[DetectionEvent]:
        with self._lock:
            return list(self._events[-limit:])[::-1]


class VehicleMonitoringManager:
    def __init__(self):
        if not _lazy_init_alpr():
            raise RuntimeError("ALPR dependencies are not available")
        self._monitors: Dict[str, VehicleMonitorWorker] = {}
        coco_default = os.path.join(BACKEND_DIR, "yolov8n.pt")
        plate_default = os.path.join(ALPR_DIR, "license_plate_detector.pt")
        if not os.path.exists(coco_default):
            coco_default = os.path.join(ALPR_DIR, "yolov8n.pt")
        self.coco_model_path = coco_default
        self.plate_model_path = plate_default

    def start(self, stream_id: str, rtsp_url: str) -> bool:
        if stream_id in self._monitors:
            return False
        worker = VehicleMonitorWorker(stream_id, rtsp_url, self.coco_model_path, self.plate_model_path)
        self._monitors[stream_id] = worker
        worker.start()
        return True

    def stop(self, stream_id: str) -> bool:
        worker = self._monitors.get(stream_id)
        if not worker:
            return False
        try:
            worker.stop()
        finally:
            self._monitors.pop(stream_id, None)
        return True

    def list_streams(self) -> List[Dict[str, Any]]:
        return [{"stream_id": stream_id, "status": "running"} for stream_id in self._monitors]

    def get_events(self, stream_id: Optional[str], limit: int) -> List[DetectionEvent]:
        events: List[DetectionEvent] = []
        if stream_id:
            worker = self._monitors.get(stream_id)
            if worker:
                events.extend(worker.get_events(limit))
        else:
            for worker in self._monitors.values():
                events.extend(worker.get_events(limit))
            events.sort(key=lambda event: event.timestamp, reverse=True)
            events = events[:limit]
        return events

    def start_all_from_config(self) -> List[str]:
        started: List[str] = []
        camera_config = load_camera_config()
        for collection, cameras in camera_config.items():
            if not isinstance(cameras, dict):
                continue
            for ip, url in cameras.items():
                stream_id = f"{collection}_{ip}"
                try:
                    if stream_id not in self._monitors and is_vehicle_monitoring_enabled_for_camera(stream_id):
                        self.start(stream_id, url)
                        started.append(stream_id)
                except Exception as exc:
                    logger.error("Failed to start vehicle monitor for %s: %s", stream_id, exc)
        return started


_manager: Optional[VehicleMonitoringManager] = None
_MANAGER_LOCK = threading.RLock()


def get_manager() -> VehicleMonitoringManager:
    global _manager
    with _MANAGER_LOCK:
        if _manager is None:
            _manager = VehicleMonitoringManager()
        return _manager


@router.get("/health")
async def health():
    available = _lazy_init_alpr()
    return {"status": "ready" if available else "unavailable", "tracker": "SORT" if available else None}


@router.post("/start")
async def start_monitoring(stream_id: Optional[str] = Query(None), rtsp_url: Optional[str] = Query(None)):
    if not _lazy_init_alpr():
        raise HTTPException(status_code=503, detail="ALPR detector or SORT tracker is not available")
    if not rtsp_url:
        if not stream_id:
            raise HTTPException(status_code=400, detail="Provide stream_id or rtsp_url")
        camera_config = load_camera_config()
        for collection, cameras in camera_config.items():
            if not isinstance(cameras, dict):
                continue
            for ip, url in cameras.items():
                if _normalize_id(f"{collection}_{ip}") == _normalize_id(stream_id):
                    rtsp_url = url
                    stream_id = f"{collection}_{ip}"
                    break
            if rtsp_url:
                break
        if not rtsp_url:
            raise HTTPException(status_code=404, detail="RTSP URL not found for stream_id")
    if not stream_id:
        stream_id = _resolve_stream_from_url(rtsp_url)
    if not stream_id:
        raise HTTPException(status_code=400, detail="A configured stable stream_id is required for vehicle monitoring")

    created = get_manager().start(stream_id, rtsp_url)
    return {"success": True, "started": created, "stream_id": stream_id}


@router.post("/stop")
async def stop_monitoring(stream_id: str = Query(...)):
    stopped = get_manager().stop(stream_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Stream not found")
    return {"success": True}


@router.get("/streams")
async def list_streams():
    return {"streams": get_manager().list_streams()}


@router.get("/detections")
async def get_detections(stream_id: Optional[str] = Query(None), limit: int = Query(50)):
    events = get_manager().get_events(stream_id, max(1, min(500, limit)))
    return {"detections": [event.model_dump() if hasattr(event, "model_dump") else event.dict() for event in events]}


@router.post("/start-all")
async def start_all():
    if not _lazy_init_alpr():
        raise HTTPException(status_code=503, detail="ALPR detector or SORT tracker is not available")
    return {"success": True, "started": get_manager().start_all_from_config()}


@router.get("/snapshot/{stream}/{filename}")
async def get_snapshot(stream: str, filename: str):
    safe_stream = stream.replace("..", "").replace("/", "_").replace("\\", "_")
    safe_filename = Path(filename).name
    if safe_filename != filename:
        raise HTTPException(status_code=400, detail="Invalid snapshot filename")
    file_path = (SNAPSHOTS_DIR / safe_stream / safe_filename).resolve()
    snapshot_root = SNAPSHOTS_DIR.resolve()
    if snapshot_root not in file_path.parents or not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path=str(file_path), media_type="image/jpeg", filename=safe_filename)


async def start_all_vehicle_monitors_on_startup() -> List[str]:
    if not _lazy_init_alpr():
        logger.warning("ALPR detector or SORT tracker unavailable; vehicle monitoring startup skipped")
        return []
    try:
        started = get_manager().start_all_from_config()
    except Exception as exc:
        logger.error("Vehicle monitoring startup failed: %s", exc)
        return []
    if started:
        logger.info("Started vehicle monitors for: %s", started)
    return started
