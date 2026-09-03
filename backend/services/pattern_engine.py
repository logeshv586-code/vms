import json
import logging
import os
import time
from collections import deque
from datetime import datetime
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
    """Layer-2 temporal/spatial analysis for the 23 configured VMS rules.

    YOLO/tracking owns detections and geometry. This layer produces deterministic candidates.
    Complex behavioral candidates are verified by Layer 3 before the alert API is called.
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

        self._load_configurations(force=True)
        self._initialized = True
        logger.info(
            "PatternEngine initialized — 23-rule suite (%d camera mappings)",
            len(self.active_rules),
        )

    @staticmethod
    def _normalize_id(value: Optional[str]) -> str:
        """Normalize camera IDs consistently across rule and zone configuration files."""
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
        """Hot-reload configs only when files change instead of doing disk I/O every frame."""
        signature = tuple(
            self._file_signature(path)
            for path in (EVENTS_CONFIG_PATH, CAMERA_RULES_PATH, CAMERA_ZONES_PATH)
        )
        if not force and signature == self._config_signature:
            return

        try:
            if os.path.exists(EVENTS_CONFIG_PATH):
                with open(EVENTS_CONFIG_PATH, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    self.global_rules = data.get("rules", []) if isinstance(data, dict) else []
            else:
                self.global_rules = []

            if os.path.exists(CAMERA_RULES_PATH):
                with open(CAMERA_RULES_PATH, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    self.active_rules = data.get("camera_rules", {}) if isinstance(data, dict) else {}
            else:
                self.active_rules = {}

            if os.path.exists(CAMERA_ZONES_PATH):
                with open(CAMERA_ZONES_PATH, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    self.zones = data if isinstance(data, dict) else {}
            else:
                self.zones = {}

            self._config_signature = signature
            logger.debug("PatternEngine configs reloaded: %d camera mappings", len(self.active_rules))
        except Exception as exc:
            logger.error("Error loading PatternEngine configuration: %s", exc)

    def reload_config(self):
        self._load_configurations(force=True)
        logger.info("PatternEngine configuration reloaded")

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

        assigned_rules = set()
        for camera_id, rule_ids in self.active_rules.items():
            if self._normalize_id(camera_id) != norm_source:
                continue
            for rule_id in rule_ids or []:
                try:
                    assigned_rules.add(int(rule_id))
                except (TypeError, ValueError):
                    continue
        return assigned_rules & globally_enabled

    def has_active_rules(self, source_id: str) -> bool:
        return bool(self.get_active_rules_for_source(source_id))

    def _zones_for_source(self, source_id: str) -> List[dict]:
        norm_source = self._normalize_id(source_id)
        for camera_id, meta in self.zones.items():
            if self._normalize_id(camera_id) == norm_source and isinstance(meta, dict):
                zones = meta.get("zones", [])
                return zones if isinstance(zones, list) else []
        return []

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def is_point_in_zone(self, point, zone):
        if not point or not isinstance(zone, dict):
            return False
        if zone.get("type", "polygon") == "circle":
            return self.is_point_in_circle(
                point,
                zone.get("center", [0.5, 0.5]),
                zone.get("radius", 0.1),
            )

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
    def _centroid_distance(c1, c2):
        return np.sqrt((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2)

    @staticmethod
    def _get_persons(detections):
        return [d for d in detections if d.get("class") == "person"]

    @staticmethod
    def _get_vehicles(detections):
        classes = {"car", "truck", "bus", "motorcycle", "bicycle"}
        return [d for d in detections if d.get("class") in classes]

    @staticmethod
    def _get_objects(detections):
        excluded = {"person", "car", "truck", "bus", "motorcycle", "bicycle"}
        return [d for d in detections if d.get("class") not in excluded]

    # ------------------------------------------------------------------
    # Main Layer-2 pass
    # ------------------------------------------------------------------

    def process_detections(self, source_id: str, detection_data: dict):
        self._load_configurations()
        if not source_id or not isinstance(detection_data, dict):
            return []

        detections = [
            d for d in detection_data.get("detections", [])
            if isinstance(d, dict) and d.get("class") and d.get("centroid")
        ]
        motion_score = float(detection_data.get("motion_score", 0) or 0)
        frame_width = max(1.0, float(detection_data.get("frame_width", 1920) or 1920))
        frame_height = max(1.0, float(detection_data.get("frame_height", 1080) or 1080))

        active = self.get_active_rules_for_source(source_id)
        norm_source = self._normalize_id(source_id)
        self._ensure_source_state(source_id)
        self.frame_counts[source_id] += 1

        self._update_track_history(source_id, detections)
        self._update_heatmap(source_id, detections, frame_width, frame_height)

        camera_zones = self._zones_for_source(source_id)
        if self.frame_counts[source_id] % 30 == 0:
            logger.info(
                "PatternEngine [%s] active_rules=%s zones=%d",
                norm_source,
                sorted(active),
                len(camera_zones),
            )

        # Always recalculate membership so a track leaving a zone does not retain stale tags.
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

        zone_filtered = (
            [d for d in detections if d.get("zone_id")]
            if RULE_ZONE_MONITORING in active
            else detections
        )
        persons = self._get_persons(zone_filtered)
        vehicles = self._get_vehicles(zone_filtered)
        objects = self._get_objects(zone_filtered)
        person_count = len(persons)
        now = time.time()
        events = []

        if RULE_APPEARANCE_SEARCH in active:
            for det in zone_filtered:
                if det.get("class") in {"person", "car", "motorcycle", "bus", "truck"}:
                    events.append(self._event(
                        1,
                        "Appearance Search",
                        "low",
                        f"Detected {det['class']} (ID:{det.get('id', '?')})",
                        data=det,
                        trigger_l3=False,
                    ))
                    break

        if RULE_CAMERA_TAMPER in active:
            blur_score = float(detection_data.get("blur_score", 100) or 100)
            luminance = float(detection_data.get("luminance", 128) or 128)
            stdev = float(detection_data.get("stdev", 50) or 50)
            tamper_msg = None
            if blur_score < self.config["tamper_blur_threshold"]:
                tamper_msg = f"Camera view blurry/out-of-focus (score: {blur_score:.1f})"
            elif luminance < self.config["tamper_luminance_low"]:
                tamper_msg = "Camera view blocked/completely dark"
            elif luminance > self.config["tamper_luminance_high"]:
                tamper_msg = "Camera view overexposed/blinded"
            elif stdev < 5 and luminance > 50:
                tamper_msg = "Static/low-information frame detected"
            elif motion_score > 150:
                tamper_msg = "Excessive camera shaking/vibration"
            if tamper_msg:
                events.append(self._event(2, "Camera Tamper", "critical", tamper_msg, trigger_l3=True))

        if RULE_CHAIN_SNATCHING in active:
            bags = [d for d in zone_filtered if d.get("class") in {"handbag", "backpack", "suitcase"}]
            for bag in bags:
                for person in persons:
                    distance = self._centroid_distance(bag["centroid"], person["centroid"])
                    velocity = self._get_track_velocity(source_id, person.get("id"))
                    if person_count >= 2 and distance < self.config["proximity_threshold"] and velocity > self.config["rapid_motion_threshold"]:
                        events.append(self._event(
                            3,
                            "Chain/Handbag Snatching",
                            "critical",
                            f"Rapid motion near {bag['class']} — possible snatching",
                            trigger_l3=True,
                        ))
                        break

        if RULE_CROWD_DETECTION in active and person_count >= self.config["crowd_threshold"]:
            events.append(self._event(
                4,
                "Crowd Detection",
                "medium",
                f"Crowd detected: {person_count} persons",
                data={"count": person_count, "heatmap": self.heatmaps[source_id].tolist()},
                trigger_l3=False,
            ))

        if RULE_EVE_TEASING in active and person_count >= 3:
            for cluster in self._find_proximity_clusters(persons):
                if len(cluster) >= 3:
                    events.append(self._event(
                        5,
                        "Eve Teasing",
                        "high",
                        f"Close proximity cluster of {len(cluster)} persons detected; semantic verification required",
                        trigger_l3=True,
                    ))
                    break

        # Rules 6 and 7 are intentionally not synthesized from YOLO person boxes. main.py runs
        # FaceCaptureDetector and FaceRecognitionDetector separately; those detectors are the
        # authoritative sources for face presence and identity/watchlist results.

        if RULE_GESTURE_DETECTION in active:
            rapid_persons = [
                person for person in persons
                if self._get_track_velocity(source_id, person.get("id")) > 30
            ]
            if rapid_persons:
                events.append(self._event(
                    8,
                    "Gesture Detection",
                    "low",
                    f"Active motion from {len(rapid_persons)} person(s) — gesture verification requested",
                    trigger_l3=True,
                ))

        if RULE_GRAFFITI_VANDALISM in active:
            for person in persons:
                track_id = person.get("id")
                if track_id is None:
                    continue
                if self._get_loiter_time(source_id, track_id) > 20 and self._get_track_velocity(source_id, track_id) < 10:
                    events.append(self._event(
                        9,
                        "Graffiti and Vandalism",
                        "high",
                        f"Stationary person (ID:{track_id}) for extended period — vandalism verification requested",
                        trigger_l3=True,
                    ))
                    break

        if RULE_INTRUSION_DETECTION in active:
            intruders = [d for d in persons if d.get("zone_id")]
            active_intruder_ids = set()
            for intruder in intruders:
                track_id = intruder.get("id")
                if track_id is None:
                    continue
                active_intruder_ids.add(track_id)
                if track_id not in self.persistence_counters[source_id]:
                    self.persistence_counters[source_id][track_id] = now
                    continue
                duration = now - self.persistence_counters[source_id][track_id]
                if duration >= self.config["persistence_threshold"]:
                    events.append(self._event(
                        10,
                        "Intrusion Detection",
                        "high",
                        f"Person (ID:{track_id}) persisted in {intruder.get('zone_name', 'restricted zone')} for {int(duration)}s",
                        data={"track_id": track_id, "duration": duration, "zone": intruder.get("zone_name")},
                        trigger_l3=True,
                    ))
            for track_id in list(self.persistence_counters[source_id]):
                if track_id not in active_intruder_ids:
                    self.persistence_counters[source_id].pop(track_id, None)

        if RULE_LAKSHMANREKHA_CROSSING in active:
            for crossing in self._check_line_crossings(source_id, persons, camera_zones):
                events.append(self._event(
                    11,
                    "Lakshmanrekha Crossing",
                    "high",
                    f"Person (ID:{crossing['track_id']}) crossed virtual line '{crossing['zone_name']}' ({crossing['direction']})",
                    data=crossing,
                    trigger_l3=True,
                ))

        if RULE_LOITERING in active:
            for person in persons:
                track_id = person.get("id")
                loiter_time = self._get_loiter_time(source_id, track_id)
                if loiter_time > self.config["loitering_time_threshold"]:
                    events.append(self._event(
                        12,
                        "Loitering",
                        "medium",
                        f"Person (ID:{track_id}) present for {int(loiter_time)}s — behavioral verification requested",
                        data={"track_id": track_id, "duration": loiter_time},
                        trigger_l3=True,
                    ))
                    break

        if RULE_MOBILE_SNATCHING in active:
            phones = [d for d in zone_filtered if d.get("class") == "cell phone"]
            for phone in phones:
                for person in persons:
                    distance = self._centroid_distance(phone["centroid"], person["centroid"])
                    velocity = self._get_track_velocity(source_id, person.get("id"))
                    if person_count >= 2 and distance < self.config["proximity_threshold"] and velocity > self.config["rapid_motion_threshold"]:
                        events.append(self._event(
                            13,
                            "Mobile Snatching",
                            "critical",
                            "Rapid motion near a mobile phone — snatching verification requested",
                            trigger_l3=True,
                        ))
                        break

        if RULE_OBJECT_CLASSIFICATION in active and zone_filtered:
            class_summary = {}
            confidences = []
            for detection in zone_filtered:
                label = detection.get("class", "unknown")
                class_summary[label] = class_summary.get(label, 0) + 1
                try:
                    confidences.append(float(detection.get("confidence", 0.0)))
                except (TypeError, ValueError):
                    pass
            summary = ", ".join(f"{name}:{count}" for name, count in class_summary.items())
            events.append(self._event(
                14,
                "Object Classification",
                "low",
                f"Objects: {summary}",
                data={"classes": class_summary, "confidence": max(confidences) if confidences else None},
                trigger_l3=False,
            ))

        if RULE_PEOPLE_FIGHTING in active and person_count >= 2:
            for cluster in self._find_proximity_clusters(persons):
                rapid_count = sum(
                    1 for person in cluster
                    if self._get_track_velocity(source_id, person.get("id")) > self.config["rapid_motion_threshold"]
                )
                if len(cluster) >= 2 and rapid_count >= 2:
                    events.append(self._event(
                        15,
                        "People Fighting",
                        "critical",
                        f"Close-proximity aggressive-motion candidate: {len(cluster)} persons, {rapid_count} fast actors",
                        data={"cluster_size": len(cluster), "rapid_actors": rapid_count},
                        trigger_l3=True,
                    ))
                    break

        if RULE_PERSON_COLLAPSING in active:
            for person in persons:
                track_id = person.get("id")
                if track_id is None:
                    continue
                vertical_drop = self._get_vertical_drop(source_id, track_id)
                velocity = self._get_track_velocity(source_id, track_id)
                if vertical_drop > self.config["collapse_vertical_threshold"] and velocity < 5:
                    events.append(self._event(
                        16,
                        "Person Collapsing",
                        "critical",
                        f"Rapid downward posture change for person (ID:{track_id}); collapse verification requested",
                        data={"track_id": track_id, "drop": vertical_drop, "residual_motion": velocity},
                        trigger_l3=True,
                    ))
                    break

        if RULE_STRIKE_PROCESSION in active and person_count >= self.config["strike_threshold"]:
            if self._check_directional_movement(source_id, persons):
                events.append(self._event(
                    17,
                    "Strike / Morcha / Procession",
                    "high",
                    f"Large group ({person_count} persons) moving in a coordinated direction",
                    trigger_l3=True,
                ))

        if RULE_SUSPECTED_APPEARANCE in active and person_count > 0:
            events.append(self._event(
                18,
                "Suspected Appearance",
                "medium",
                f"{person_count} person(s) detected — objective appearance/behavior verification requested",
                trigger_l3=True,
            ))

        if RULE_UNATTENDED_OBJECT in active:
            for object_info in self._check_unattended_objects(source_id, objects, persons, now):
                events.append(self._event(
                    19,
                    "Unattended Object",
                    "high",
                    f"Unattended {object_info['class']} for {int(object_info['duration'])}s",
                    data=object_info,
                    trigger_l3=True,
                ))

        if RULE_WOMEN_SURROUNDED in active and person_count >= 4:
            for cluster in self._find_proximity_clusters(persons):
                if len(cluster) >= 4:
                    events.append(self._event(
                        20,
                        "Women Surrounded by Men",
                        "critical",
                        f"Cluster of {len(cluster)} persons in close proximity — vulnerability verification required",
                        trigger_l3=True,
                    ))
                    break

        if RULE_ABDUCTION in active and person_count >= 2:
            x_margin = frame_width * 0.10
            y_margin = frame_height * 0.10
            for person in persons:
                track_id = person.get("id")
                velocity = self._get_track_velocity(source_id, track_id)
                cx, cy = person["centroid"]
                near_edge = (
                    cx < x_margin
                    or cx > frame_width - x_margin
                    or cy < y_margin
                    or cy > frame_height - y_margin
                )
                if velocity > self.config["rapid_motion_threshold"] * 1.5 and near_edge:
                    events.append(self._event(
                        21,
                        "Abduction Detection",
                        "critical",
                        f"Rapid movement of person (ID:{track_id}) near frame boundary — forced-removal verification requested",
                        data={"track_id": track_id, "velocity": velocity, "position": [cx, cy]},
                        trigger_l3=True,
                    ))
                    break

        if RULE_VEHICLE_MONITORING in active and vehicles:
            vehicle_summary = {}
            confidences = []
            for vehicle in vehicles:
                label = vehicle.get("class", "vehicle")
                vehicle_summary[label] = vehicle_summary.get(label, 0) + 1
                try:
                    confidences.append(float(vehicle.get("confidence", 0.0)))
                except (TypeError, ValueError):
                    pass
            summary = ", ".join(f"{name}:{count}" for name, count in vehicle_summary.items())
            events.append(self._event(
                22,
                "Vehicle Monitoring",
                "low",
                f"Vehicles: {summary}",
                data={"vehicles": vehicle_summary, "confidence": max(confidences) if confidences else None},
                trigger_l3=False,
            ))

        if RULE_ZONE_MONITORING in active:
            zone_summary = {}
            for detection in detections:
                zone_name = detection.get("zone_name")
                if zone_name:
                    zone_summary[zone_name] = zone_summary.get(zone_name, 0) + 1
            for zone_name, count in zone_summary.items():
                events.append(self._event(
                    23,
                    "Zone Monitoring (Restricted Area)",
                    "high",
                    f"RESTRICTED ALERT: {count} object(s) detected inside {zone_name}",
                    data={"zone": zone_name, "count": count},
                    trigger_l3=True,
                ))

        severity_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        deduped = {}
        for event in events:
            key = event["type"]
            if key not in deduped or severity_rank.get(event["severity"], 0) > severity_rank.get(deduped[key]["severity"], 0):
                deduped[key] = event

        final_events = list(deduped.values())
        self.source_events[source_id] = {event["type"]: event for event in final_events}
        return final_events

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

    @staticmethod
    def _event(rule_id, event_type, severity, message, data=None, trigger_l3=False):
        event = {
            "id": rule_id,
            "type": event_type,
            "severity": severity,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "trigger_layer3": trigger_l3,
        }
        if data is not None:
            event["data"] = data
        return event

    # ------------------------------------------------------------------
    # Temporal helpers
    # ------------------------------------------------------------------

    def _update_track_history(self, source_id, detections):
        history = self.track_histories[source_id]
        first_seen = self.track_first_seen[source_id]
        last_seen = self.track_last_seen[source_id]
        classes = self.track_classes[source_id]
        now = time.time()
        current_ids = set()

        for detection in detections:
            track_id = detection.get("id")
            if track_id is None:
                continue
            current_ids.add(track_id)
            if track_id not in history:
                history[track_id] = deque(maxlen=30)
                first_seen[track_id] = now
            history[track_id].append(detection["centroid"])
            last_seen[track_id] = now
            classes[track_id] = detection.get("class", "object")

        stale_after = float(self.config["track_ttl_seconds"])
        stale_ids = [
            track_id
            for track_id, seen_at in last_seen.items()
            if track_id not in current_ids and now - seen_at > stale_after
        ]
        for track_id in stale_ids:
            history.pop(track_id, None)
            first_seen.pop(track_id, None)
            last_seen.pop(track_id, None)
            classes.pop(track_id, None)
            self.persistence_counters[source_id].pop(track_id, None)
            for crossing_key in list(self.line_crossings[source_id]):
                if crossing_key.startswith(f"{track_id}_"):
                    self.line_crossings[source_id].pop(crossing_key, None)

    def _get_track_velocity(self, source_id, track_id):
        if track_id is None:
            return 0.0
        history = self.track_histories.get(source_id, {}).get(track_id)
        if not history or len(history) < 2:
            return 0.0
        first, second = history[-2], history[-1]
        return float(np.sqrt((second[0] - first[0]) ** 2 + (second[1] - first[1]) ** 2))

    def _get_vertical_drop(self, source_id, track_id):
        if track_id is None:
            return 0.0
        history = self.track_histories.get(source_id, {}).get(track_id)
        if not history or len(history) < 5:
            return 0.0
        return float(history[-1][1] - history[-5][1])

    def _get_loiter_time(self, source_id, track_id):
        if track_id is None:
            return 0.0
        first_seen = self.track_first_seen.get(source_id, {}).get(track_id)
        if first_seen is None:
            return 0.0
        return max(0.0, time.time() - first_seen)

    def _find_proximity_clusters(self, persons):
        if len(persons) < 2:
            return []
        visited = set()
        clusters = []
        threshold = self.config["proximity_threshold"]
        for index, first in enumerate(persons):
            if index in visited:
                continue
            cluster = [first]
            visited.add(index)
            for other_index, second in enumerate(persons):
                if other_index in visited:
                    continue
                if self._centroid_distance(first["centroid"], second["centroid"]) < threshold:
                    cluster.append(second)
                    visited.add(other_index)
            if len(cluster) >= 2:
                clusters.append(cluster)
        return clusters

    def _check_directional_movement(self, source_id, persons):
        if len(persons) < 5:
            return False
        directions = []
        for person in persons:
            history = self.track_histories.get(source_id, {}).get(person.get("id"))
            if history and len(history) >= 3:
                dx = history[-1][0] - history[-3][0]
                dy = history[-1][1] - history[-3][1]
                if abs(dx) > 5 or abs(dy) > 5:
                    directions.append(np.arctan2(dy, dx))
        if len(directions) < 5:
            return False
        # Circular mean is more robust around the -pi/pi boundary than plain arithmetic mean.
        mean_angle = np.arctan2(np.mean(np.sin(directions)), np.mean(np.cos(directions)))
        aligned = 0
        for direction in directions:
            delta = np.arctan2(np.sin(direction - mean_angle), np.cos(direction - mean_angle))
            if abs(delta) < np.pi / 4:
                aligned += 1
        return aligned >= len(directions) * 0.6

    def _check_line_crossings(self, source_id, persons, zones):
        crossings = []
        state = self.line_crossings[source_id]
        for zone in zones:
            zone_id = zone.get("id")
            zone_name = zone.get("name", "Zone")
            if zone_id is None:
                continue
            for person in persons:
                track_id = person.get("id")
                if track_id is None:
                    continue
                cx, cy = person["centroid"]
                ncx, ncy = person.get("norm_centroid", [cx / 1920.0, cy / 1080.0])

                if zone.get("type") == "circle":
                    center = zone.get("center", [0.5, 0.5])
                    radius = float(zone.get("radius", 0.1))
                    distance = np.sqrt((ncx - center[0]) ** 2 + (ncy - center[1]) ** 2)
                    current_side = 1 if distance <= radius else -1
                else:
                    polygon = zone.get("polygon", [])
                    if len(polygon) < 2:
                        continue
                    x1, y1 = polygon[0]
                    x2, y2 = polygon[1]
                    side = (x2 - x1) * (ncy - y1) - (y2 - y1) * (ncx - x1)
                    current_side = 1 if side > 0 else -1

                key = f"{track_id}_{zone_id}"
                previous_side = state.get(key)
                if previous_side is not None and previous_side != current_side:
                    crossings.append({
                        "track_id": track_id,
                        "zone_id": zone_id,
                        "zone_name": zone_name,
                        "direction": "entry" if current_side == 1 else "exit",
                    })
                state[key] = current_side
        return crossings

    def _check_unattended_objects(self, source_id, objects, persons, now):
        static = self.static_objects[source_id]
        threshold = self.config["proximity_threshold"] * 2
        unattended = []
        current_object_ids = set()

        for obj in objects:
            track_id = obj.get("id")
            if track_id is None:
                continue
            current_object_ids.add(track_id)
            person_nearby = any(
                self._centroid_distance(obj["centroid"], person["centroid"]) < threshold
                for person in persons
            )
            if person_nearby:
                static.pop(track_id, None)
                continue

            if track_id not in static:
                static[track_id] = {
                    "pos": obj["centroid"],
                    "first_seen": now,
                    "class": obj.get("class", "object"),
                }
                continue

            duration = now - static[track_id]["first_seen"]
            if duration > self.config["unattended_object_time"]:
                unattended.append({
                    "track_id": track_id,
                    "class": obj.get("class", "object"),
                    "duration": duration,
                    "position": obj["centroid"],
                })

        for track_id in list(static):
            if track_id not in current_object_ids:
                static.pop(track_id, None)
        return unattended

    def _update_heatmap(self, source_id, detections, frame_width=1920.0, frame_height=1080.0):
        heatmap = self.heatmaps[source_id]
        heatmap *= 0.9
        for detection in detections:
            norm = detection.get("norm_centroid")
            if norm and len(norm) >= 2:
                nx, ny = float(norm[0]), float(norm[1])
            else:
                cx, cy = detection["centroid"]
                nx, ny = cx / frame_width, cy / frame_height
            gx = max(0, min(int(nx * 10), 9))
            gy = max(0, min(int(ny * 10), 9))
            heatmap[gy, gx] += 1
        self.heatmaps[source_id] = np.clip(heatmap, 0, 50)

    # ------------------------------------------------------------------
    # Public state / alert API
    # ------------------------------------------------------------------

    def get_active_events(self, source_id: str):
        return list(self.source_events.get(source_id, {}).values())

    def clear_source_data(self, source_id: str):
        stores = (
            self.frame_counts,
            self.track_histories,
            self.track_first_seen,
            self.track_last_seen,
            self.track_classes,
            self.source_events,
            self.static_objects,
            self.line_crossings,
            self.persistence_counters,
            self.heatmaps,
        )
        for store in stores:
            store.pop(source_id, None)

    @staticmethod
    def _event_confidence(event: dict):
        """Return measured confidence when available; never invent a 95% score."""
        deep = event.get("deep_reasoning") if isinstance(event, dict) else None
        if isinstance(deep, dict):
            try:
                value = float(deep.get("confidence_score"))
                return max(0.0, min(1.0, value))
            except (TypeError, ValueError):
                pass

        data = event.get("data") if isinstance(event, dict) else None
        if isinstance(data, dict):
            try:
                value = float(data.get("confidence"))
                return max(0.0, min(1.0, value))
            except (TypeError, ValueError):
                pass
        return None

    def trigger_alert_api(self, source_id: str, event: dict):
        """Persist a confirmed event and start best-effort video proof capture."""
        logger.info(
            "[ALERT API] %s: %s - %s",
            source_id,
            event.get("type"),
            event.get("message"),
        )

        try:
            import subprocess
            import threading
            import uuid
            from pathlib import Path

            from routes.events import get_event_records, save_event_records

            records = get_event_records()
            rule_type = event.get("type", "Unknown Event")
            now = datetime.now()

            for record in reversed(records):
                if record.get("rule_name") != rule_type or record.get("camera_id") != source_id:
                    continue
                created_at = record.get("created_at")
                if not created_at:
                    continue
                try:
                    if (now - datetime.fromisoformat(created_at)).total_seconds() < 300:
                        return
                except Exception:
                    continue

            rule_name_to_id = {
                "Appearance Search": 1,
                "Camera Tamper": 2,
                "Chain/Handbag Snatching": 3,
                "Crowd Detection": 4,
                "Eve Teasing": 5,
                "Face Capture": 6,
                "Face Recognition": 7,
                "Gesture Detection": 8,
                "Graffiti and Vandalism Detection": 9,
                "Graffiti and Vandalism": 9,
                "Graffiti / Vandalism": 9,
                "Intrusion Detection": 10,
                "Lakshmanrekha Crossing": 11,
                "Loitering": 12,
                "Mobile Snatching": 13,
                "Object Classification": 14,
                "People Fighting": 15,
                "Person Collapsing": 16,
                "Strike / Morcha / Hartal / Procession": 17,
                "Strike / Morcha / Procession": 17,
                "Strike / Procession": 17,
                "Suspected Appearance": 18,
                "Unattended Object": 19,
                "Women Surrounded by Men": 20,
                "Women Surrounded": 20,
                "Women/Infant Abduction": 21,
                "Abduction Detection": 21,
                "Vehicle Monitoring": 22,
                "Zone Monitoring": 23,
                "Zone Monitoring (Restricted Area)": 23,
            }
            rule_id = rule_name_to_id.get(rule_type)
            if rule_id and rule_id not in self.get_active_rules_for_source(source_id):
                logger.info(
                    "Rule '%s' (ID:%s) is not enabled for camera '%s'; skipping event",
                    rule_type,
                    rule_id,
                    source_id,
                )
                return

            global_rule_enabled = True
            try:
                with open(EVENTS_CONFIG_PATH, "r", encoding="utf-8") as handle:
                    config = json.load(handle)
                for rule in config.get("rules", []):
                    if rule.get("id") == rule_id or rule.get("name") == rule_type:
                        global_rule_enabled = bool(rule.get("enabled", True))
                        break
            except Exception as exc:
                logger.debug("Could not re-check event config before persistence: %s", exc)

            if not global_rule_enabled:
                return

            event_id = f"EVT-{uuid.uuid4().hex[:8].upper()}"
            category = "Security Analytics"
            if rule_type in {"Face Capture", "Face Recognition", "Appearance Search"}:
                category = "Face Analytics"
            elif rule_type == "Vehicle Monitoring":
                category = "Vehicle Analytics"
            elif rule_type in {
                "People Fighting",
                "Mobile Snatching",
                "Chain/Handbag Snatching",
                "Eve Teasing",
                "Women Surrounded by Men",
                "Women/Infant Abduction",
                "Abduction Detection",
            }:
                category = "Crime Detection"
            elif rule_type in {
                "Crowd Detection",
                "Person Collapsing",
                "Strike / Morcha / Hartal / Procession",
                "Strike / Morcha / Procession",
            }:
                category = "Crowd & Public Safety"

            record = {
                "event_id": event_id,
                "created_at": datetime.now().isoformat(),
                "rule_name": rule_type,
                "camera_name": source_id,
                "camera_id": source_id,
                "location": "Main Location",
                "priority": event.get("priority", event.get("severity", "High")),
                "duration": 30,
                "status": "Active",
                "category": category,
                "confidence": self._event_confidence(event),
                "confidence_source": "gemma" if isinstance(event.get("deep_reasoning"), dict) else "detector" if self._event_confidence(event) is not None else "unscored",
                "acknowledged": False,
                "message": event.get("message", ""),
                "video_proof_url": f"/api/augment/events/proofs/{event_id}.mp4",
            }
            records.append(record)
            save_event_records(records)

            def record_proof(eid, sid):
                try:
                    rtsp_url = None
                    camera_config_path = os.path.join(
                        os.path.dirname(__file__), "..", "data", "camera_configuration.json"
                    )
                    if os.path.exists(camera_config_path):
                        with open(camera_config_path, "r", encoding="utf-8") as handle:
                            camera_data = json.load(handle)
                        for cameras in camera_data.values() if isinstance(camera_data, dict) else []:
                            if not isinstance(cameras, dict):
                                continue
                            for camera_ip, url in cameras.items():
                                if camera_ip in sid or sid in camera_ip:
                                    rtsp_url = url
                                    break
                            if rtsp_url:
                                break

                    if not rtsp_url:
                        self._clear_proof_url(eid, get_event_records, save_event_records)
                        return

                    proofs_dir = Path(
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "proofs"))
                    )
                    proofs_dir.mkdir(parents=True, exist_ok=True)
                    output_file = proofs_dir / f"{eid}.mp4"
                    command = [
                        "ffmpeg",
                        "-y",
                        "-rtsp_transport",
                        "tcp",
                        "-i",
                        rtsp_url,
                        "-t",
                        "30",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "ultrafast",
                        "-b:v",
                        "1000k",
                        "-an",
                        "-movflags",
                        "frag_keyframe+empty_moov",
                        str(output_file),
                    ]
                    subprocess.run(
                        command,
                        timeout=45,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    if not output_file.exists() or output_file.stat().st_size <= 10240:
                        try:
                            if output_file.exists():
                                output_file.unlink()
                        except Exception:
                            pass
                        self._clear_proof_url(eid, get_event_records, save_event_records)
                except Exception as exc:
                    logger.error("Failed to record event proof %s: %s", eid, exc)
                    self._clear_proof_url(eid, get_event_records, save_event_records)

            threading.Thread(target=record_proof, args=(event_id, source_id), daemon=True).start()
        except Exception as exc:
            logger.error("Error persisting alert to events system: %s", exc)

    @staticmethod
    def _clear_proof_url(event_id, get_event_records, save_event_records):
        try:
            records = get_event_records()
            for record in records:
                if record.get("event_id") == event_id:
                    record["video_proof_url"] = None
                    break
            save_event_records(records)
        except Exception:
            pass


pattern_engine = PatternEngine()
