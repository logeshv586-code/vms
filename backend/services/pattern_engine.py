import json
import logging
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
CAMERA_RULES_PATH = os.path.join(ROOT_DIR, "camera_rules.json")
EVENTS_CONFIG_PATH = os.path.join(ROOT_DIR, "events_configuration.json")
CAMERA_ZONES_PATH = os.path.join(ROOT_DIR, "backend/data/camera_zones.json")

RULE_APPEARANCE_SEARCH = 1
RULE_CAMERA_TAMPER = 2
RULE_CHAIN_SNATCHING = 3
RULE_CROWD_DETECTION = 4
RULE_EVE_TEASING = 5
RULE_FACE_CAPTURE = 6
RULE_FACE_RECOGNITION = 7
RULE_GESTURE_DETECTION = 8
RULE_GRAFFITI_VANDALISM = 9
RULE_INTRUSION_DETECTION = 10
RULE_LAKSHMANREKHA_CROSSING = 11
RULE_LOITERING = 12
RULE_MOBILE_SNATCHING = 13
RULE_OBJECT_CLASSIFICATION = 14
RULE_PEOPLE_FIGHTING = 15
RULE_PERSON_COLLAPSING = 16
RULE_STRIKE_PROCESSION = 17
RULE_SUSPECTED_APPEARANCE = 18
RULE_UNATTENDED_OBJECT = 19
RULE_WOMEN_SURROUNDED = 20
RULE_ABDUCTION = 21
RULE_VEHICLE_MONITORING = 22
RULE_ZONE_MONITORING = 23


class PatternEngine:
    """Camera-isolated Layer-2 temporal/spatial candidate engine.

    Deterministic events are persisted here so RTSP/webcam/file sources have the
    same behavior. Semantic candidates carry ``source_id`` into Layer 3; the
    Gemma verifier persists them only when explicitly validated.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.config = {
            "crowd_threshold": 20,
            "strike_threshold": 10,
            "loitering_time_threshold": 30,
            "rapid_motion_threshold": 50,
            "collapse_vertical_threshold": 80,
            "proximity_threshold": 120,
            "unattended_object_time": 60,
            "persistence_threshold": 3,
            "tamper_blur_threshold": 30,
            "tamper_luminance_low": 20,
            "tamper_luminance_high": 240,
            "track_ttl_seconds": 10,
            "alert_dedupe_seconds": max(1, int(os.getenv("VMS_EVENT_DEDUPE_SECONDS", "300"))),
        }
        self.frame_counts: Dict[str, int] = {}
        self.track_histories: Dict[str, Dict[int, deque]] = {}
        self.track_first_seen: Dict[str, Dict[int, float]] = {}
        self.track_last_seen: Dict[str, Dict[int, float]] = {}
        self.track_classes: Dict[str, Dict[int, str]] = {}
        self.source_events: Dict[str, Dict[str, dict]] = {}
        self.static_objects: Dict[str, Dict[int, dict]] = {}
        self.persistence_counters: Dict[str, Dict[int, float]] = {}
        self.line_crossings: Dict[str, Dict[str, int]] = {}
        self.heatmaps: Dict[str, np.ndarray] = {}
        self.active_rules: Dict[str, List[int]] = {}
        self.zones: Dict[str, dict] = {}
        self.global_rules: List[dict] = []
        self._config_signature = None
        self._alert_lock = threading.RLock()
        self._load_configurations(force=True)
        self._initialized = True
        logger.info("PatternEngine initialized — 23-rule suite (%d camera mappings)", len(self.active_rules))

    @staticmethod
    def _normalize_id(value: Optional[str]) -> str:
        if not value:
            return ""
        clean = str(value).lower().replace("camera-", "").replace("camera_", "")
        for char in ("-", "_", ".", " "):
            clean = clean.replace(char, "")
        return clean

    @staticmethod
    def _file_signature(path: str):
        try:
            stat = os.stat(path)
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def _load_configurations(self, force: bool = False):
        signature = tuple(self._file_signature(path) for path in (EVENTS_CONFIG_PATH, CAMERA_RULES_PATH, CAMERA_ZONES_PATH))
        if not force and signature == self._config_signature:
            return
        try:
            self.global_rules = []
            self.active_rules = {}
            self.zones = {}
            if os.path.exists(EVENTS_CONFIG_PATH):
                with open(EVENTS_CONFIG_PATH, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                self.global_rules = data.get("rules", []) if isinstance(data, dict) else []
            if os.path.exists(CAMERA_RULES_PATH):
                with open(CAMERA_RULES_PATH, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                self.active_rules = data.get("camera_rules", {}) if isinstance(data, dict) else {}
            if os.path.exists(CAMERA_ZONES_PATH):
                with open(CAMERA_ZONES_PATH, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                self.zones = data if isinstance(data, dict) else {}
            self._config_signature = signature
        except Exception as exc:
            logger.error("Error loading PatternEngine configuration: %s", exc)

    def reload_config(self):
        self._load_configurations(force=True)

    def get_active_rules_for_source(self, source_id: str) -> set:
        if not source_id:
            return set()
        self._load_configurations()
        norm_source = self._normalize_id(source_id)
        globally_enabled = {
            int(rule["id"])
            for rule in self.global_rules
            if isinstance(rule, dict) and rule.get("enabled", False) and rule.get("id") is not None
        }
        assigned = set()
        for camera_id, rule_ids in self.active_rules.items():
            if self._normalize_id(camera_id) != norm_source:
                continue
            for rule_id in rule_ids or []:
                try:
                    assigned.add(int(rule_id))
                except (TypeError, ValueError):
                    pass
        return assigned & globally_enabled

    def has_active_rules(self, source_id: str) -> bool:
        return bool(self.get_active_rules_for_source(source_id))

    def _zones_for_source(self, source_id: str) -> List[dict]:
        norm_source = self._normalize_id(source_id)
        for camera_id, meta in self.zones.items():
            if self._normalize_id(camera_id) == norm_source and isinstance(meta, dict):
                zones = meta.get("zones", [])
                return zones if isinstance(zones, list) else []
        return []

    def is_point_in_zone(self, point, zone):
        if not point or not isinstance(zone, dict):
            return False
        if zone.get("type", "polygon") == "circle":
            return self.is_point_in_circle(point, zone.get("center", [0.5, 0.5]), zone.get("radius", 0.1))
        polygon = zone.get("polygon", [])
        if len(polygon) < 3:
            return False
        x, y = point
        inside = False
        p1x, p1y = polygon[0]
        for index in range(1, len(polygon) + 1):
            p2x, p2y = polygon[index % len(polygon)]
            if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
                if p1y != p2y:
                    xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    @staticmethod
    def is_point_in_circle(point, center, radius):
        try:
            return np.sqrt((point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2) <= float(radius)
        except (TypeError, ValueError, IndexError):
            return False

    @staticmethod
    def _centroid_distance(first, second):
        return float(np.sqrt((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2))

    @staticmethod
    def _get_persons(detections):
        return [item for item in detections if item.get("class") == "person"]

    @staticmethod
    def _get_vehicles(detections):
        classes = {"car", "truck", "bus", "motorcycle", "bicycle"}
        return [item for item in detections if item.get("class") in classes]

    @staticmethod
    def _get_objects(detections):
        excluded = {"person", "car", "truck", "bus", "motorcycle", "bicycle"}
        return [item for item in detections if item.get("class") not in excluded]

    def process_detections(self, source_id: str, detection_data: dict):
        self._load_configurations()
        if not source_id or not isinstance(detection_data, dict):
            return []
        detections = [item for item in detection_data.get("detections", []) if isinstance(item, dict) and item.get("class") and item.get("centroid")]
        motion_score = float(detection_data.get("motion_score", 0) or 0)
        frame_width = max(1.0, float(detection_data.get("frame_width", 1920) or 1920))
        frame_height = max(1.0, float(detection_data.get("frame_height", 1080) or 1080))
        active = self.get_active_rules_for_source(source_id)
        self._ensure_source_state(source_id)
        self.frame_counts[source_id] += 1
        self._update_track_history(source_id, detections)
        self._update_heatmap(source_id, detections, frame_width, frame_height)
        camera_zones = self._zones_for_source(source_id)

        for det in detections:
            det.pop("zone_id", None)
            det.pop("zone_name", None)
            norm_centroid = det.get("norm_centroid")
            if not norm_centroid:
                cx, cy = det["centroid"]
                norm_centroid = [cx / frame_width, cy / frame_height]
                det["norm_centroid"] = norm_centroid
            for zone in camera_zones:
                if self.is_point_in_zone(norm_centroid, zone):
                    det["zone_id"] = zone.get("id")
                    det["zone_name"] = zone.get("name", "Zone")
                    break

        zone_filtered = [item for item in detections if item.get("zone_id")] if RULE_ZONE_MONITORING in active else detections
        persons = self._get_persons(zone_filtered)
        vehicles = self._get_vehicles(zone_filtered)
        objects = self._get_objects(zone_filtered)
        person_count = len(persons)
        now = time.time()
        events: List[dict] = []

        # Appearance Search is only a match event. A generic person/vehicle box
        # is not evidence that an appearance-search target matched.
        if RULE_APPEARANCE_SEARCH in active:
            for det in zone_filtered:
                match = det.get("appearance_match")
                if match is True or isinstance(match, dict):
                    match_data = dict(match) if isinstance(match, dict) else {}
                    confidence = match_data.get("confidence", det.get("appearance_confidence"))
                    payload = {"detection": det, "match": match_data}
                    if confidence is not None:
                        payload["confidence"] = confidence
                    events.append(self._event(1, "Appearance Search", "high", f"Reviewed appearance target matched for {det.get('class', 'object')}", payload, False))
                    break

        if RULE_CAMERA_TAMPER in active:
            blur = float(detection_data.get("blur_score", 100) or 100)
            luminance = float(detection_data.get("luminance", 128) or 128)
            stdev = float(detection_data.get("stdev", 50) or 50)
            message = None
            if blur < self.config["tamper_blur_threshold"]:
                message = f"Camera view blurry/out-of-focus (score: {blur:.1f})"
            elif luminance < self.config["tamper_luminance_low"]:
                message = "Camera view blocked/completely dark"
            elif luminance > self.config["tamper_luminance_high"]:
                message = "Camera view overexposed/blinded"
            elif stdev < 5 and luminance > 50:
                message = "Static/low-information frame detected"
            elif motion_score > 150:
                message = "Excessive camera shaking/vibration"
            if message:
                events.append(self._event(2, "Camera Tamper", "critical", message, trigger_l3=True))

        if RULE_CHAIN_SNATCHING in active:
            bags = [item for item in zone_filtered if item.get("class") in {"handbag", "backpack", "suitcase"}]
            if any(person_count >= 2 and self._centroid_distance(bag["centroid"], person["centroid"]) < self.config["proximity_threshold"] and self._get_track_velocity(source_id, person.get("id")) > self.config["rapid_motion_threshold"] for bag in bags for person in persons):
                events.append(self._event(3, "Chain/Handbag Snatching", "critical", "Rapid motion near a carried bag — semantic verification required", trigger_l3=True))

        if RULE_CROWD_DETECTION in active and person_count >= self.config["crowd_threshold"]:
            events.append(self._event(4, "Crowd Detection", "medium", f"Crowd detected: {person_count} persons", {"count": person_count}, False))

        if RULE_EVE_TEASING in active and any(len(cluster) >= 3 for cluster in self._find_proximity_clusters(persons)):
            events.append(self._event(5, "Eve Teasing", "high", "Close-proximity cluster detected — harassment behavior verification required", trigger_l3=True))

        # Rules 6/7 are authoritative dedicated face detector outputs; they are
        # not synthesized from YOLO person boxes here.

        if RULE_GESTURE_DETECTION in active and any(self._get_track_velocity(source_id, person.get("id")) > 30 for person in persons):
            events.append(self._event(8, "Gesture Detection", "low", "Rapid body motion detected — gesture verification requested", trigger_l3=True))

        if RULE_GRAFFITI_VANDALISM in active:
            for person in persons:
                tid = person.get("id")
                if tid is not None and self._get_loiter_time(source_id, tid) > 20 and self._get_track_velocity(source_id, tid) < 10:
                    events.append(self._event(9, "Graffiti and Vandalism", "high", f"Stationary person (ID:{tid}) — vandalism verification requested", trigger_l3=True))
                    break

        if RULE_INTRUSION_DETECTION in active:
            active_ids = set()
            for person in [item for item in persons if item.get("zone_id")]:
                tid = person.get("id")
                if tid is None:
                    continue
                active_ids.add(tid)
                started = self.persistence_counters[source_id].setdefault(tid, now)
                duration = now - started
                if duration >= self.config["persistence_threshold"]:
                    events.append(self._event(10, "Intrusion Detection", "high", f"Person (ID:{tid}) persisted in {person.get('zone_name', 'restricted zone')} for {int(duration)}s", {"track_id": tid, "duration": duration, "zone": person.get("zone_name")}, True))
            for tid in list(self.persistence_counters[source_id]):
                if tid not in active_ids:
                    self.persistence_counters[source_id].pop(tid, None)

        if RULE_LAKSHMANREKHA_CROSSING in active:
            for crossing in self._check_line_crossings(source_id, persons, camera_zones):
                events.append(self._event(11, "Lakshmanrekha Crossing", "high", f"Person (ID:{crossing['track_id']}) crossed virtual line '{crossing['zone_name']}' ({crossing['direction']})", crossing, True))

        if RULE_LOITERING in active:
            for person in persons:
                tid = person.get("id")
                duration = self._get_loiter_time(source_id, tid)
                if duration > self.config["loitering_time_threshold"]:
                    events.append(self._event(12, "Loitering", "medium", f"Person (ID:{tid}) present for {int(duration)}s — behavioral verification requested", {"track_id": tid, "duration": duration}, True))
                    break

        if RULE_MOBILE_SNATCHING in active:
            phones = [item for item in zone_filtered if item.get("class") == "cell phone"]
            if any(person_count >= 2 and self._centroid_distance(phone["centroid"], person["centroid"]) < self.config["proximity_threshold"] and self._get_track_velocity(source_id, person.get("id")) > self.config["rapid_motion_threshold"] for phone in phones for person in persons):
                events.append(self._event(13, "Mobile Snatching", "critical", "Rapid motion near a mobile phone — snatching verification requested", trigger_l3=True))

        if RULE_OBJECT_CLASSIFICATION in active and zone_filtered:
            summary: Dict[str, int] = {}
            confidences = []
            for item in zone_filtered:
                label = item.get("class", "unknown")
                summary[label] = summary.get(label, 0) + 1
                try:
                    confidences.append(float(item.get("confidence", 0.0)))
                except (TypeError, ValueError):
                    pass
            events.append(self._event(14, "Object Classification", "low", "Objects: " + ", ".join(f"{key}:{value}" for key, value in summary.items()), {"classes": summary, "confidence": max(confidences) if confidences else None}, False))

        if RULE_PEOPLE_FIGHTING in active and person_count >= 2:
            for cluster in self._find_proximity_clusters(persons):
                rapid = sum(self._get_track_velocity(source_id, person.get("id")) > self.config["rapid_motion_threshold"] for person in cluster)
                if len(cluster) >= 2 and rapid >= 2:
                    events.append(self._event(15, "People Fighting", "critical", f"Aggressive-motion candidate: {len(cluster)} persons, {rapid} fast actors", {"cluster_size": len(cluster), "rapid_actors": rapid}, True))
                    break

        if RULE_PERSON_COLLAPSING in active:
            for person in persons:
                tid = person.get("id")
                if tid is not None and self._get_vertical_drop(source_id, tid) > self.config["collapse_vertical_threshold"] and self._get_track_velocity(source_id, tid) < 5:
                    events.append(self._event(16, "Person Collapsing", "critical", f"Rapid downward posture change for person (ID:{tid}) — collapse verification requested", {"track_id": tid}, True))
                    break

        if RULE_STRIKE_PROCESSION in active and person_count >= self.config["strike_threshold"] and self._check_directional_movement(source_id, persons):
            events.append(self._event(17, "Strike / Morcha / Procession", "high", f"Large group ({person_count} persons) moving in a coordinated direction", trigger_l3=True))

        if RULE_SUSPECTED_APPEARANCE in active and person_count > 0:
            events.append(self._event(18, "Suspected Appearance", "medium", f"{person_count} person(s) detected — objective behavior verification requested", trigger_l3=True))

        if RULE_UNATTENDED_OBJECT in active:
            for info in self._check_unattended_objects(source_id, objects, persons, now):
                events.append(self._event(19, "Unattended Object", "high", f"Unattended {info['class']} for {int(info['duration'])}s", info, True))

        if RULE_WOMEN_SURROUNDED in active and any(len(cluster) >= 4 for cluster in self._find_proximity_clusters(persons)):
            events.append(self._event(20, "Women Surrounded by Men", "critical", "Close surrounding/blocking cluster detected — vulnerability/distress verification required; no gender inference is used", trigger_l3=True))

        if RULE_ABDUCTION in active and person_count >= 2:
            x_margin, y_margin = frame_width * 0.10, frame_height * 0.10
            for person in persons:
                tid = person.get("id")
                cx, cy = person["centroid"]
                near_edge = cx < x_margin or cx > frame_width - x_margin or cy < y_margin or cy > frame_height - y_margin
                velocity = self._get_track_velocity(source_id, tid)
                if velocity > self.config["rapid_motion_threshold"] * 1.5 and near_edge:
                    events.append(self._event(21, "Abduction Detection", "critical", f"Rapid movement of person (ID:{tid}) near frame boundary — forced-removal verification required", {"track_id": tid, "velocity": velocity, "position": [cx, cy]}, True))
                    break

        if RULE_VEHICLE_MONITORING in active and vehicles:
            summary: Dict[str, int] = {}
            confidences = []
            for vehicle in vehicles:
                label = vehicle.get("class", "vehicle")
                summary[label] = summary.get(label, 0) + 1
                try:
                    confidences.append(float(vehicle.get("confidence", 0.0)))
                except (TypeError, ValueError):
                    pass
            events.append(self._event(22, "Vehicle Monitoring", "low", "Vehicles: " + ", ".join(f"{key}:{value}" for key, value in summary.items()), {"vehicles": summary, "confidence": max(confidences) if confidences else None}, False))

        if RULE_ZONE_MONITORING in active:
            summary: Dict[str, int] = {}
            for item in detections:
                name = item.get("zone_name")
                if name:
                    summary[name] = summary.get(name, 0) + 1
            for name, count in summary.items():
                events.append(self._event(23, "Zone Monitoring (Restricted Area)", "high", f"RESTRICTED ALERT: {count} object(s) detected inside {name}", {"zone": name, "count": count}, True))

        severity_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        deduped: Dict[str, dict] = {}
        for event in events:
            key = event["type"]
            if key not in deduped or severity_rank.get(event["severity"], 0) > severity_rank.get(deduped[key]["severity"], 0):
                deduped[key] = event
        final_events = list(deduped.values())
        for event in final_events:
            event["source_id"] = source_id
            data = event.setdefault("data", {})
            if isinstance(data, dict):
                data.setdefault("source_id", source_id)
            if not event.get("trigger_layer3"):
                self.trigger_alert_api(source_id, event)
        self.source_events[source_id] = {event["type"]: event for event in final_events}
        return final_events

    @staticmethod
    def _event(rule_id, event_type, severity, message, data=None, trigger_l3=False):
        event = {"id": rule_id, "type": event_type, "severity": severity, "message": message, "timestamp": datetime.now(timezone.utc).isoformat(), "trigger_layer3": trigger_l3}
        if data is not None:
            event["data"] = data
        return event

    def _ensure_source_state(self, source_id: str):
        self.frame_counts.setdefault(source_id, 0)
        self.track_histories.setdefault(source_id, {})
        self.track_first_seen.setdefault(source_id, {})
        self.track_last_seen.setdefault(source_id, {})
        self.track_classes.setdefault(source_id, {})
        self.source_events.setdefault(source_id, {})
        self.static_objects.setdefault(source_id, {})
        self.persistence_counters.setdefault(source_id, {})
        self.line_crossings.setdefault(source_id, {})
        self.heatmaps.setdefault(source_id, np.zeros((10, 10), dtype=np.float32))

    def _update_track_history(self, source_id, detections):
        history = self.track_histories[source_id]
        first_seen = self.track_first_seen[source_id]
        last_seen = self.track_last_seen[source_id]
        classes = self.track_classes[source_id]
        now = time.time()
        current_ids = set()
        for item in detections:
            tid = item.get("id")
            if tid is None:
                continue
            current_ids.add(tid)
            if tid not in history:
                history[tid] = deque(maxlen=30)
                first_seen[tid] = now
            history[tid].append(item["centroid"])
            last_seen[tid] = now
            classes[tid] = item.get("class", "object")
        stale_after = float(self.config["track_ttl_seconds"])
        for tid in [key for key, seen in last_seen.items() if key not in current_ids and now - seen > stale_after]:
            history.pop(tid, None)
            first_seen.pop(tid, None)
            last_seen.pop(tid, None)
            classes.pop(tid, None)
            self.persistence_counters[source_id].pop(tid, None)
            for crossing_key in list(self.line_crossings[source_id]):
                if crossing_key.startswith(f"{tid}_"):
                    self.line_crossings[source_id].pop(crossing_key, None)

    def _get_track_velocity(self, source_id, track_id):
        if track_id is None:
            return 0.0
        history = self.track_histories.get(source_id, {}).get(track_id)
        if not history or len(history) < 2:
            return 0.0
        first, second = history[-2], history[-1]
        return self._centroid_distance(first, second)

    def _get_vertical_drop(self, source_id, track_id):
        history = self.track_histories.get(source_id, {}).get(track_id) if track_id is not None else None
        return float(history[-1][1] - history[-5][1]) if history and len(history) >= 5 else 0.0

    def _get_loiter_time(self, source_id, track_id):
        started = self.track_first_seen.get(source_id, {}).get(track_id) if track_id is not None else None
        return max(0.0, time.time() - started) if started is not None else 0.0

    def _find_proximity_clusters(self, persons):
        if len(persons) < 2:
            return []
        threshold = self.config["proximity_threshold"]
        unvisited = set(range(len(persons)))
        clusters = []
        while unvisited:
            seed = unvisited.pop()
            cluster_indices = {seed}
            frontier = [seed]
            while frontier:
                current = frontier.pop()
                neighbors = [idx for idx in list(unvisited) if self._centroid_distance(persons[current]["centroid"], persons[idx]["centroid"]) < threshold]
                for idx in neighbors:
                    unvisited.remove(idx)
                    cluster_indices.add(idx)
                    frontier.append(idx)
            if len(cluster_indices) >= 2:
                clusters.append([persons[idx] for idx in cluster_indices])
        return clusters

    def _check_directional_movement(self, source_id, persons):
        directions = []
        for person in persons:
            history = self.track_histories.get(source_id, {}).get(person.get("id"))
            if history and len(history) >= 3:
                dx, dy = history[-1][0] - history[-3][0], history[-1][1] - history[-3][1]
                if abs(dx) > 5 or abs(dy) > 5:
                    directions.append(np.arctan2(dy, dx))
        if len(directions) < 5:
            return False
        mean = np.arctan2(np.mean(np.sin(directions)), np.mean(np.cos(directions)))
        aligned = sum(abs(np.arctan2(np.sin(direction - mean), np.cos(direction - mean))) < np.pi / 4 for direction in directions)
        return aligned >= len(directions) * 0.6

    def _check_line_crossings(self, source_id, persons, zones):
        crossings = []
        state = self.line_crossings[source_id]
        for zone in zones:
            zone_id = zone.get("id")
            if zone_id is None:
                continue
            for person in persons:
                tid = person.get("id")
                if tid is None:
                    continue
                norm = person.get("norm_centroid")
                if not norm:
                    continue
                nx, ny = norm
                if zone.get("type") == "circle":
                    center = zone.get("center", [0.5, 0.5])
                    distance = np.sqrt((nx - center[0]) ** 2 + (ny - center[1]) ** 2)
                    side = 1 if distance <= float(zone.get("radius", 0.1)) else -1
                else:
                    polygon = zone.get("polygon", [])
                    if len(polygon) < 2:
                        continue
                    x1, y1 = polygon[0]
                    x2, y2 = polygon[1]
                    side = 1 if (x2 - x1) * (ny - y1) - (y2 - y1) * (nx - x1) > 0 else -1
                key = f"{tid}_{zone_id}"
                previous = state.get(key)
                if previous is not None and previous != side:
                    crossings.append({"track_id": tid, "zone_id": zone_id, "zone_name": zone.get("name", "Zone"), "direction": "entry" if side == 1 else "exit"})
                state[key] = side
        return crossings

    def _check_unattended_objects(self, source_id, objects, persons, now):
        static = self.static_objects[source_id]
        threshold = self.config["proximity_threshold"] * 2
        current_ids = set()
        unattended = []
        for obj in objects:
            tid = obj.get("id")
            if tid is None:
                continue
            current_ids.add(tid)
            if any(self._centroid_distance(obj["centroid"], person["centroid"]) < threshold for person in persons):
                static.pop(tid, None)
                continue
            record = static.setdefault(tid, {"pos": obj["centroid"], "first_seen": now, "class": obj.get("class", "object")})
            duration = now - record["first_seen"]
            if duration > self.config["unattended_object_time"]:
                unattended.append({"track_id": tid, "class": obj.get("class", "object"), "duration": duration, "position": obj["centroid"]})
        for tid in list(static):
            if tid not in current_ids:
                static.pop(tid, None)
        return unattended

    def _update_heatmap(self, source_id, detections, frame_width=1920.0, frame_height=1080.0):
        heatmap = self.heatmaps[source_id]
        heatmap *= 0.9
        for item in detections:
            norm = item.get("norm_centroid")
            if norm and len(norm) >= 2:
                nx, ny = float(norm[0]), float(norm[1])
            else:
                cx, cy = item["centroid"]
                nx, ny = cx / frame_width, cy / frame_height
            gx, gy = max(0, min(int(nx * 10), 9)), max(0, min(int(ny * 10), 9))
            heatmap[gy, gx] += 1
        self.heatmaps[source_id] = np.clip(heatmap, 0, 50)

    def get_active_events(self, source_id: str):
        return list(self.source_events.get(source_id, {}).values())

    def clear_source_data(self, source_id: str):
        for store in (self.frame_counts, self.track_histories, self.track_first_seen, self.track_last_seen, self.track_classes, self.source_events, self.static_objects, self.line_crossings, self.persistence_counters, self.heatmaps):
            store.pop(source_id, None)
        try:
            from services.yolo26_engine import yolo26_engine
            yolo26_engine.reset_stream(source_id)
        except Exception:
            pass

    @staticmethod
    def _event_confidence(event: dict):
        deep = event.get("deep_reasoning") if isinstance(event, dict) else None
        if isinstance(deep, dict):
            try:
                return max(0.0, min(1.0, float(deep.get("confidence_score"))))
            except (TypeError, ValueError):
                pass
        data = event.get("data") if isinstance(event, dict) else None
        if isinstance(data, dict):
            try:
                return max(0.0, min(1.0, float(data.get("confidence"))))
            except (TypeError, ValueError):
                pass
        return None

    def trigger_alert_api(self, source_id: str, event: dict):
        if not source_id or not isinstance(event, dict):
            return False
        try:
            from routes.events import find_recent_event, save_event_records, update_event_record
            rule_type = str(event.get("type", "Unknown Event"))
            rule_id = event.get("id")
            try:
                rule_id = int(rule_id) if rule_id is not None else None
            except (TypeError, ValueError):
                rule_id = None
            if rule_id and rule_id not in self.get_active_rules_for_source(source_id):
                return False

            with self._alert_lock:
                if find_recent_event(rule_type, source_id, self.config["alert_dedupe_seconds"]):
                    return False
                event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
                category = self._category_for_rule(rule_type)
                confidence = self._event_confidence(event)
                record = {
                    "event_id": event_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "rule_name": rule_type,
                    "camera_name": source_id,
                    "camera_id": source_id,
                    "location": "Main Location",
                    "priority": event.get("priority", event.get("severity", "high")),
                    "duration": 30,
                    "status": "Active",
                    "category": category,
                    "confidence": confidence,
                    "confidence_source": "gemma" if isinstance(event.get("deep_reasoning"), dict) else "detector" if confidence is not None else "unscored",
                    "acknowledged": False,
                    "message": event.get("message", ""),
                    "video_proof_url": f"/api/augment/events/proofs/{event_id}.mp4",
                }
                if not save_event_records([record]):
                    return False
            self._start_proof_recording(event_id, source_id, update_event_record)
            logger.info("Persisted VMS event %s %s camera=%s", event_id, rule_type, source_id)
            return True
        except Exception as exc:
            logger.exception("Error persisting alert: %s", exc)
            return False

    @staticmethod
    def _category_for_rule(rule_type: str) -> str:
        if rule_type in {"Face Capture", "Face Recognition", "Appearance Search"}:
            return "Face Analytics"
        if rule_type == "Vehicle Monitoring":
            return "Vehicle Analytics"
        if rule_type in {"People Fighting", "Mobile Snatching", "Chain/Handbag Snatching", "Eve Teasing", "Women Surrounded by Men", "Abduction Detection"}:
            return "Crime Detection"
        if rule_type in {"Crowd Detection", "Person Collapsing", "Strike / Morcha / Procession"}:
            return "Crowd & Public Safety"
        return "Security Analytics"

    def _start_proof_recording(self, event_id: str, source_id: str, update_event_record):
        def worker():
            import subprocess
            from pathlib import Path
            rtsp_url = None
            try:
                camera_config_path = os.path.join(os.path.dirname(__file__), "..", "data", "camera_configuration.json")
                if os.path.exists(camera_config_path):
                    with open(camera_config_path, "r", encoding="utf-8") as handle:
                        camera_data = json.load(handle)
                    for cameras in camera_data.values() if isinstance(camera_data, dict) else []:
                        if not isinstance(cameras, dict):
                            continue
                        for camera_ip, url in cameras.items():
                            if camera_ip in source_id or source_id in camera_ip:
                                rtsp_url = url
                                break
                        if rtsp_url:
                            break
                if not rtsp_url:
                    update_event_record(event_id, {"video_proof_url": None})
                    return
                proofs = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "proofs")))
                proofs.mkdir(parents=True, exist_ok=True)
                output = proofs / f"{event_id}.mp4"
                command = ["ffmpeg", "-y", "-rtsp_transport", "tcp", "-i", rtsp_url, "-t", "30", "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "1000k", "-an", "-movflags", "frag_keyframe+empty_moov", str(output)]
                result = subprocess.run(command, timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                if result.returncode != 0 or not output.exists() or output.stat().st_size <= 10240:
                    try:
                        if output.exists():
                            output.unlink()
                    except OSError:
                        pass
                    update_event_record(event_id, {"video_proof_url": None})
            except Exception as exc:
                logger.warning("Proof recording failed for %s: %s", event_id, exc)
                try:
                    update_event_record(event_id, {"video_proof_url": None})
                except Exception:
                    pass
        threading.Thread(target=worker, daemon=True, name=f"proof-{event_id}").start()


pattern_engine = PatternEngine()
