from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Dict, Optional, List, Any
import os
import sys
import cv2
import time
import threading
import logging
import numpy as np
from pathlib import Path

# Add the ALPR module directory to the Python path
CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ALPR_DIR = os.path.join(BACKEND_DIR, "Event_Detections", "Automatic-License-Plate-Recognition and Vehicle Detection")
sys.path.append(ALPR_DIR)

logger = logging.getLogger(__name__)

ALPR_AVAILABLE = None
util_get_car = None
util_read_license_plate = None
YOLO = None
Sort = None

def _lazy_init_alpr():
    global ALPR_AVAILABLE, util_get_car, util_read_license_plate, YOLO, Sort
    if ALPR_AVAILABLE is not None:
        return ALPR_AVAILABLE
    try:
        from util import get_car, read_license_plate
        from ultralytics import YOLO as _YOLO
        try:
            from sort.sort import Sort as _Sort
        except (ImportError, ModuleNotFoundError):
            logger.warning("SORT tracker not found. Using mock tracker.")
            class _Sort:
                def __init__(self, *args, **kwargs): pass
                def update(self, detections):
                    if len(detections) == 0:
                        return np.empty((0, 5))
                    return np.column_stack((detections[:, :4], np.arange(len(detections))))
        util_get_car = get_car
        util_read_license_plate = read_license_plate
        YOLO = _YOLO
        Sort = _Sort
        ALPR_AVAILABLE = True
    except Exception as e:
        ALPR_AVAILABLE = False
        logger.warning(f"Vehicle monitoring ALPR dependencies delayed/unavailable: {e}")
    return ALPR_AVAILABLE

router = APIRouter(prefix="/api/vehicle-monitoring", tags=["vehicle-monitoring"])

# Storage paths
VEHICLE_DATA_DIR = Path(BACKEND_DIR) / "vehicle_data"
SNAPSHOTS_DIR = VEHICLE_DATA_DIR / "snapshots"
VEHICLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Load camera configuration
CAMERA_CONFIG_PATH = os.path.join(BACKEND_DIR, "data", "camera_configuration.json")

def load_camera_config() -> Dict[str, Dict[str, str]]:
    try:
        import json
        with open(CAMERA_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load camera configuration: {e}")
        return {}

import json

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
    snapshots: Dict[str, str]  # {'vehicle': url, 'plate': url}
    vehicle_type: Optional[str] = "Unknown"
    vehicle_category: Optional[str] = "Vehicle"

def is_vehicle_monitoring_enabled_for_camera(stream_id: str) -> bool:
    """
    Checks if rule 22 (Vehicle Monitoring) is enabled globally and active for this camera stream.
    """
    try:
        # Load global events config
        events_path = os.path.join(BACKEND_DIR, "..", "events_configuration.json")
        if os.path.exists(events_path):
            with open(events_path, "r") as f:
                rules = json.load(f).get("rules", [])
                vehicle_rule = next((r for r in rules if r.get("id") == 22), None)
                if not vehicle_rule or not vehicle_rule.get("enabled", False):
                    return False
        else:
            return False

        # Load camera rules
        rules_path = os.path.join(BACKEND_DIR, "..", "camera_rules.json")
        if os.path.exists(rules_path):
            with open(rules_path, "r") as f:
                camera_rules = json.load(f).get("camera_rules", {})
                
                # Normalize stream_id matching
                def normalize_id(id_str):
                    if not id_str: return ""
                    clean = id_str.lower().replace("camera-", "").replace("camera_", "")
                    for char in ['-', '_', '.', ' ']:
                        clean = clean.replace(char, "")
                    return clean

                norm_stream = normalize_id(stream_id)
                for cam_id, rids in camera_rules.items():
                    if normalize_id(cam_id) == norm_stream:
                        return 22 in rids
        return False
    except Exception as e:
        logger.error(f"Error checking camera rules for {stream_id}: {e}")
        return False

class VehicleMonitorWorker:
    def __init__(self, stream_id: str, rtsp_url: str, coco_model_path: str, plate_model_path: str):
        self.stream_id = stream_id
        self.rtsp_url = rtsp_url
        self.coco_model_path = coco_model_path
        self.plate_model_path = plate_model_path
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._mot = Sort()
        self._captured_keys = set()  # track unique vehicle_id + plate
        self._events: List[DetectionEvent] = []
        self._max_events = 500
        # Models
        self._coco_model = YOLO(self.coco_model_path)
        self._plate_model = YOLO(self.plate_model_path)

        # Load persisted events if any
        try:
            safe_stream = self.stream_id.replace('/', '_')
            events_file = VEHICLE_DATA_DIR / f"events_{safe_stream}.json"
            if events_file.exists():
                with open(events_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        evt = DetectionEvent(**item)
                        self._events.append(evt)
                        self._captured_keys.add(f"{evt.vehicle_id}_{evt.license_plate}")
                logger.info(f"Loaded {len(self._events)} persisted vehicle events for {self.stream_id}")
        except Exception as e:
            logger.error(f"Error loading persisted vehicle events: {e}")

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Vehicle monitor started for {self.stream_id}")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
            logger.info(f"Vehicle monitor stopped for {self.stream_id}")

    def _save_event(self, evt: DetectionEvent):
        with self._lock:
            self._events.append(evt)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]
            try:
                safe_stream = self.stream_id.replace('/', '_')
                events_file = VEHICLE_DATA_DIR / f"events_{safe_stream}.json"
                with open(events_file, "w") as f:
                    json.dump([e.dict() for e in self._events], f, indent=2)
            except Exception as e:
                logger.error(f"Failed to persist vehicle events: {e}")

    def _run(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 3)
        cap.set(cv2.CAP_PROP_FPS, 24)
        vehicles = {2, 3, 5, 7}  # bicycle(1) excluded; using car, motorcycle, bus, truck ids from COCO
        frame_idx = 0
        skip_frames = 2
        while not self._stop.is_set():
            ret, frame = cap.read()
            if not ret or frame is None:
                time.sleep(0.1)
                continue
            frame_idx += 1
            # Optionally skip frames for performance
            if frame_idx % (skip_frames + 1) != 0:
                continue
            try:
                det = self._coco_model(frame)[0]
                detections_ = []
                original_detections = []
                for d in det.boxes.data.tolist():
                    x1, y1, x2, y2, score, class_id = d
                    if int(class_id) in vehicles:
                        detections_.append([x1, y1, x2, y2, score])
                        original_detections.append([x1, y1, x2, y2, score, int(class_id)])
                track_ids = self._mot.update(np.asarray(detections_)) if len(detections_) else np.empty((0, 5))

                lp_det = self._plate_model(frame)[0]
                for lp in lp_det.boxes.data.tolist():
                    x1, y1, x2, y2, score, class_id = lp
                    xcar1, ycar1, xcar2, ycar2, car_id = get_car(lp, track_ids)
                    if car_id == -1:
                        continue
                    # Read plate
                    plate_crop = frame[int(y1):int(y2), int(x1): int(x2), :]
                    if plate_crop.size == 0:
                        continue
                    try:
                        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
                        _, thresh = cv2.threshold(gray, 64, 255, cv2.THRESH_BINARY_INV)
                    except Exception:
                        thresh = plate_crop
                    plate_text, plate_score = read_license_plate(thresh)
                    if plate_text is None:
                        continue
                    vehicle_key = f"{int(car_id)}_{plate_text}"
                    if vehicle_key in self._captured_keys:
                        continue
                    self._captured_keys.add(vehicle_key)
                    # Save snapshots
                    ts = int(time.time() * 1000)
                    safe_stream = self.stream_id.replace('/', '_')
                    stream_dir = SNAPSHOTS_DIR / safe_stream
                    stream_dir.mkdir(parents=True, exist_ok=True)
                    veh_crop = frame[int(ycar1):int(ycar2), int(xcar1):int(xcar2), :]
                    veh_name = f"veh_{ts}_id{int(car_id)}.jpg"
                    plate_name = f"plate_{ts}_id{int(car_id)}.jpg"
                    veh_path = stream_dir / veh_name
                    plate_path = stream_dir / plate_name
                    try:
                        if veh_crop.size > 0:
                            cv2.imwrite(str(veh_path), veh_crop)
                        cv2.imwrite(str(plate_path), plate_crop)
                    except Exception as e:
                        logger.warning(f"Failed to save snapshots: {e}")

                    # Determine vehicle type and category by finding matching original box
                    best_iou = -1
                    best_cls_id = 2  # default to car
                    for ox1, oy1, ox2, oy2, oscore, oclass_id in original_detections:
                        ix1 = max(xcar1, ox1)
                        iy1 = max(ycar1, oy1)
                        ix2 = min(xcar2, ox2)
                        iy2 = min(ycar2, oy2)
                        if ix2 > ix1 and iy2 > iy1:
                            intersection = (ix2 - ix1) * (iy2 - iy1)
                            area1 = (xcar2 - xcar1) * (ycar2 - ycar1)
                            area2 = (ox2 - ox1) * (oy2 - oy1)
                            union = area1 + area2 - intersection
                            iou = intersection / union if union > 0 else 0
                            if iou > best_iou:
                                best_iou = iou
                                best_cls_id = oclass_id

                    # Map to type and category
                    vehicle_type = "Car"
                    vehicle_category = "Sedan/SUV"
                    if best_cls_id == 3:
                        vehicle_type = "Motorcycle"
                        vehicle_category = "Two-Wheeler"
                    elif best_cls_id == 5:
                        vehicle_type = "Bus"
                        vehicle_category = "Heavy Vehicle"
                    elif best_cls_id == 7:
                        vehicle_type = "Truck"
                        vehicle_category = "Heavy Commercial Vehicle"

                    evt = DetectionEvent(
                        id=f"{safe_stream}_{ts}_{int(car_id)}",
                        stream_id=self.stream_id,
                        timestamp=time.time(),
                        camera_ip=self.stream_id.split('_')[-1] if '_' in self.stream_id else None,
                        vehicle_id=int(car_id),
                        license_plate=plate_text,
                        license_plate_score=float(plate_score) if plate_score is not None else None,
                        vehicle_bbox=[float(xcar1), float(ycar1), float(xcar2), float(ycar2)],
                        plate_bbox=[float(x1), float(y1), float(x2), float(y2)],
                        snapshots={
                            "vehicle": f"/api/vehicle-monitoring/snapshot/{safe_stream}/{veh_name}",
                            "plate": f"/api/vehicle-monitoring/snapshot/{safe_stream}/{plate_name}"
                        },
                        vehicle_type=vehicle_type,
                        vehicle_category=vehicle_category
                    )
                    self._save_event(evt)
            except Exception as e:
                logger.error(f"Error in vehicle monitoring loop for {self.stream_id}: {e}")
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
        self._monitors: Dict[str, VehicleMonitorWorker] = {}
        # Model paths (prefer backend root yolo for coco)
        coco_default = os.path.join(BACKEND_DIR, 'yolov8n.pt')
        plate_default = os.path.join(ALPR_DIR, 'license_plate_detector.pt')
        if not os.path.exists(coco_default):
            coco_default = os.path.join(ALPR_DIR, 'yolov8n.pt')
        self.coco_model_path = coco_default
        self.plate_model_path = plate_default

    def start(self, stream_id: str, rtsp_url: str) -> bool:
        if not ALPR_AVAILABLE:
            raise RuntimeError("ALPR dependencies not available on server")
        if stream_id in self._monitors:
            return False
        worker = VehicleMonitorWorker(stream_id, rtsp_url, self.coco_model_path, self.plate_model_path)
        self._monitors[stream_id] = worker
        worker.start()
        return True

    def stop(self, stream_id: str) -> bool:
        w = self._monitors.get(stream_id)
        if not w:
            return False
        try:
            w.stop()
        finally:
            self._monitors.pop(stream_id, None)
        return True

    def list_streams(self) -> List[Dict[str, Any]]:
        return [
            {"stream_id": sid, "status": "running"}
            for sid in self._monitors.keys()
        ]

    def get_events(self, stream_id: Optional[str], limit: int) -> List[DetectionEvent]:
        events: List[DetectionEvent] = []
        if stream_id:
            w = self._monitors.get(stream_id)
            if w:
                events.extend(w.get_events(limit))
        else:
            for w in self._monitors.values():
                events.extend(w.get_events(limit))
            # Sort by timestamp desc
            events.sort(key=lambda e: e.timestamp, reverse=True)
            events = events[:limit]
        return events

    def start_all_from_config(self) -> List[str]:
        started: List[str] = []
        cam_cfg = load_camera_config()
        for collection, cams in cam_cfg.items():
            for ip, url in cams.items():
                stream_id = f"{collection}_{ip}"
                try:
                    if stream_id not in self._monitors:
                        if is_vehicle_monitoring_enabled_for_camera(stream_id):
                            self.start(stream_id, url)
                            started.append(stream_id)
                        else:
                            logger.info(f"Skipping starting vehicle monitoring for stream {stream_id} because rule 22 is not enabled/assigned.")
                except Exception as e:
                    logger.error(f"Failed to start vehicle monitor for {stream_id}: {e}")
        return started

# Global manager
_manager: Optional[VehicleMonitoringManager] = None

def get_manager() -> VehicleMonitoringManager:
    global _manager
    if _manager is None:
        _manager = VehicleMonitoringManager()
    return _manager

@router.get("/health")
async def health():
    status = "ready" if ALPR_AVAILABLE else "unavailable"
    return {"status": status}

@router.post("/start")
async def start_monitoring(stream_id: Optional[str] = Query(None), rtsp_url: Optional[str] = Query(None)):
    if not ALPR_AVAILABLE:
        raise HTTPException(status_code=503, detail="ALPR dependencies not available")
    mgr = get_manager()
    if not rtsp_url:
        # Resolve from config
        if not stream_id:
            raise HTTPException(status_code=400, detail="Provide stream_id or rtsp_url")
        cam_cfg = load_camera_config()
        try:
            collection, ip = stream_id.split('_', 1)
            rtsp_url = cam_cfg.get(collection, {}).get(ip)
        except Exception:
            rtsp_url = None
        if not rtsp_url:
            raise HTTPException(status_code=404, detail="RTSP URL not found for stream_id")
    if not stream_id:
        # Generate from URL host if possible
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(rtsp_url)
            host = parsed.hostname or "unknown"
            stream_id = f"auto_{host}"
        except Exception:
            stream_id = f"auto_{int(time.time())}"
    created = mgr.start(stream_id, rtsp_url)
    return {"success": True, "started": created, "stream_id": stream_id}

@router.post("/stop")
async def stop_monitoring(stream_id: str = Query(...)):
    mgr = get_manager()
    stopped = mgr.stop(stream_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Stream not found")
    return {"success": True}

@router.get("/streams")
async def list_streams():
    mgr = get_manager()
    return {"streams": mgr.list_streams()}

@router.get("/detections")
async def get_detections(stream_id: Optional[str] = Query(None), limit: int = Query(50)):
    mgr = get_manager()
    events = mgr.get_events(stream_id, limit)
    return {"detections": [e.dict() for e in events]}


@router.post("/start-all")
async def start_all():
    if not ALPR_AVAILABLE:
        raise HTTPException(status_code=503, detail="ALPR dependencies not available")
    mgr = get_manager()
    started = mgr.start_all_from_config()
    return {"success": True, "started": started}

@router.get("/snapshot/{stream}/{filename}")
async def get_snapshot(stream: str, filename: str):
    safe_stream = stream.replace('..', '').replace('/', '_')
    file_path = SNAPSHOTS_DIR / safe_stream / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path=str(file_path), media_type="image/jpeg", filename=filename)

# Helper callable for startup integration
async def start_all_vehicle_monitors_on_startup() -> List[str]:
    if not ALPR_AVAILABLE:
        logger.warning("ALPR not available; skipping vehicle monitoring startup")
        return []
    mgr = get_manager()
    started = mgr.start_all_from_config()
    if started:
        logger.info(f"Started vehicle monitors for: {started}")
    return started

