import json
import os
import logging
import time
from datetime import datetime
from collections import deque
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Paths to the rule configurations (Root level)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
CAMERA_RULES_PATH = os.path.join(ROOT_DIR, "camera_rules.json")
EVENTS_CONFIG_PATH = os.path.join(ROOT_DIR, "events_configuration.json")
CAMERA_ZONES_PATH = os.path.join(ROOT_DIR, "backend/data/camera_zones.json")

# ─── RULE ID CONSTANTS ───
RULE_APPEARANCE_SEARCH       = 1
RULE_CAMERA_TAMPER           = 2
RULE_CHAIN_SNATCHING         = 3
RULE_CROWD_DETECTION         = 4
RULE_EVE_TEASING             = 5
RULE_FACE_CAPTURE            = 6
RULE_FACE_RECOGNITION        = 7
RULE_GESTURE_DETECTION       = 8
RULE_GRAFFITI_VANDALISM      = 9
RULE_INTRUSION_DETECTION     = 10
RULE_LAKSHMANREKHA_CROSSING  = 11
RULE_LOITERING               = 12
RULE_MOBILE_SNATCHING        = 13
RULE_OBJECT_CLASSIFICATION   = 14
RULE_PEOPLE_FIGHTING         = 15
RULE_PERSON_COLLAPSING       = 16
RULE_STRIKE_PROCESSION       = 17
RULE_SUSPECTED_APPEARANCE    = 18
RULE_UNATTENDED_OBJECT       = 19
RULE_WOMEN_SURROUNDED        = 20
RULE_ABDUCTION               = 21
RULE_VEHICLE_MONITORING      = 22
RULE_ZONE_MONITORING         = 23


class PatternEngine:
    """Layer 2 Detection Engine — Full 23-Rule Suite
    
    Analyzes YOLO26 detections using heuristics and triggers Layer 3 (Gemma)
    for complex behavioral events that require vision-language reasoning.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PatternEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.frame_counts = {}
        
        # Thresholds
        self.config = {
            "crowd_threshold": 20,
            "strike_threshold": 10,
            "loitering_time_threshold": 30,       # seconds
            "rapid_motion_threshold": 50,          # pixels/frame
            "collapse_vertical_threshold": 80,     # vertical pixel drop
            "proximity_threshold": 120,            # pixels between centroids
            "unattended_object_time": 60,          # seconds object static w/o person (increased for better stability)
            "persistence_threshold": 3,            # frames/seconds in zone before intrusion alert
            "tamper_blur_threshold": 30,           # Laplacian variance below this means focused blur/spray
            "tamper_luminance_low": 20,            # Dark/covered camera
            "tamper_luminance_high": 240,          # Blinded by flashlight
        }
        
        # Per-source state
        self.track_histories = {}       # {source: {track_id: deque of centroids}}
        self.track_first_seen = {}      # {source: {track_id: timestamp}}
        self.track_classes = {}         # {source: {track_id: class_name}}
        self.source_events = {}         # {source: {event_type: event_dict}}
        self.static_objects = {}        # {source: {track_id: {pos, first_seen}}}
        self.persistence_counters = {}  # {source: {track_id: entry_time}} 
        
        # Rule & Zone state
        self.active_rules = {}          # {camera_id: [rule_ids]}
        self.zones = {}                 # {camera_id: {zones: [...]}}
        self.global_rules = []
        self.line_crossings = {}        # {source: {track_id: last_side}}
        self.heatmaps = {}              # {source: 10x10 occupancy grid}
        
        self._load_configurations()
        self._initialized = True
        logger.info(f"PatternEngine initialized — 23-Rule Suite (loaded {len(self.active_rules)} camera mappings)")

    def _load_configurations(self):
        """Load global rules, camera rule mappings, and zone definitions"""
        try:
            if os.path.exists(EVENTS_CONFIG_PATH):
                with open(EVENTS_CONFIG_PATH, "r") as f:
                    self.global_rules = json.load(f).get("rules", [])
            
            if os.path.exists(CAMERA_RULES_PATH):
                with open(CAMERA_RULES_PATH, "r") as f:
                    self.active_rules = json.load(f).get("camera_rules", {})

            if os.path.exists(CAMERA_ZONES_PATH):
                with open(CAMERA_ZONES_PATH, "r") as f:
                    self.zones = json.load(f)
            
            logger.debug(f"PatternEngine configs loaded: {len(self.active_rules)} cameras mapped")
        except Exception as e:
            logger.error(f"Error loading PatternEngine configuration: {e}")

    def reload_config(self):
        """Reload global rules, camera rule mappings, and zone definitions"""
        self._load_configurations()
        logger.info("PatternEngine configuration reloaded")

    def get_active_rules_for_source(self, source_id: str) -> set:
        """Get set of active rule IDs for a given source"""
        if not source_id:
            return set()
        
        def normalize_id(id_str):
            if not id_str: return ""
            clean = id_str.lower().replace("camera-", "").replace("camera_", "")
            for char in ['-', '_', '.', ' ']:
                clean = clean.replace(char, "")
            return clean

        norm_source = normalize_id(source_id)
        globally_enabled = {r["id"] for r in self.global_rules if r.get("enabled", False)}
        
        assigned_rules = set()
        for k, v in self.active_rules.items():
            if normalize_id(k) == norm_source:
                assigned_rules.update(v)
                
        return set(rid for rid in assigned_rules if rid in globally_enabled)

    def has_active_rules(self, source_id: str) -> bool:
        """Check if a source has any globally enabled active rules"""
        return len(self.get_active_rules_for_source(source_id)) > 0

    # ─── GEOMETRY HELPERS ────────────────────────────────────────────

    def is_point_in_zone(self, point, zone):
        """Check if point is inside the zone (supports polygon and circle)"""
        zone_type = zone.get("type", "polygon")
        
        if zone_type == "circle":
            center = zone.get("center", [0.5, 0.5])
            radius = zone.get("radius", 0.1)
            return self.is_point_in_circle(point, center, radius)
        else:
            # Default to polygon (ray-casting)
            polygon = zone.get("polygon", [])
            if not polygon:
                return False
            x, y = point
            n = len(polygon)
            inside = False
            p1x, p1y = polygon[0]
            for i in range(1, n + 1):
                p2x, p2y = polygon[i % n]
                if y > min(p1y, p2y):
                    if y <= max(p1y, p2y):
                        if x <= max(p1x, p2x):
                            if p1y != p2y:
                                xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                                if p1x == p2x or x <= xints:
                                    inside = not inside
                p1x, p1y = p2x, p2y
            return inside

    def is_point_in_circle(self, point, center, radius):
        """Check if point is within circle radius (Euclidean distance)"""
        dist = np.sqrt((point[0] - center[0])**2 + (point[1] - center[1])**2)
        return dist <= radius

    def _centroid_distance(self, c1, c2):
        """Euclidean distance between two centroids"""
        return np.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2)

    def _get_persons(self, detections):
        """Filter to person detections only"""
        return [d for d in detections if d["class"] == "person"]

    def _get_vehicles(self, detections):
        """Filter to vehicle detections"""
        return [d for d in detections if d["class"] in ("car", "truck", "bus", "motorcycle", "bicycle")]

    def _get_objects(self, detections):
        """Filter to non-person, non-vehicle objects (bags, suitcases, etc.)"""
        persons_vehicles = {"person", "car", "truck", "bus", "motorcycle", "bicycle"}
        return [d for d in detections if d["class"] not in persons_vehicles]

    # ─── MAIN ENTRY POINT ────────────────────────────────────────────

    def process_detections(self, source_id: str, detection_data: dict):
        """
        Main Layer 2 analysis — runs all enabled rules for this camera.
        
        Args:
            source_id: Camera stream ID (e.g. "Eagle_192.168.4.243")
            detection_data: {"detections": [...], "counts": {...}, "motion_score": float}
        """
        self._load_configurations()
        
        detections = detection_data.get("detections", [])
        counts = detection_data.get("counts", {})
        motion_score = detection_data.get("motion_score", 0)
        
        def normalize_id(id_str):
            if not id_str: return ""
        # Determine active rules for this camera
        active = self.get_active_rules_for_source(source_id)
        norm_source = source_id.lower().replace("camera-", "").replace("camera_", "")
        
        # Init per-source state
        if source_id not in self.track_histories:
            self.track_histories[source_id] = {}
            self.frame_counts[source_id] = 0
            
        self.frame_counts[source_id] += 1
        
        if self.frame_counts[source_id] % 30 == 0:
            logger.info(f"PatternEngine [{norm_source}] - Active rules: {active}")
        if source_id not in self.track_first_seen:
            self.track_first_seen[source_id] = {}
        if source_id not in self.track_classes:
            self.track_classes[source_id] = {}
        if source_id not in self.source_events:
            self.source_events[source_id] = {}
        if source_id not in self.static_objects:
            self.static_objects[source_id] = {}
        if source_id not in self.line_crossings:
            self.line_crossings[source_id] = {}
        if source_id not in self.persistence_counters:
            self.persistence_counters[source_id] = {}
        if source_id not in self.heatmaps:
            self.heatmaps[source_id] = np.zeros((10, 10))
            
        self._update_track_history(source_id, detections)
        self._update_heatmap(source_id, detections)
        
        # Get zone info
        zones_norm = {normalize_id(k): v for k, v in self.zones.items()}
        camera_meta = zones_norm.get(norm_source, {"zones": []})
        camera_zones = camera_meta.get("zones", [])
        
        if self.frame_counts[source_id] % 30 == 0:
            logger.info(f"PatternEngine [{norm_source}] - Loaded {len(camera_zones)} zones")
        
        # Spatial filtering — tag detections with zone info
        for det in detections:
            centroid = det["centroid"]
            # Use pre-computed norm_centroid from YOLO engine or fallback
            norm_centroid = det.get("norm_centroid")
            if not norm_centroid:
                bbox = det.get("bbox", [0, 0, 1920, 1080])
                frame_w = max(bbox[2], 1920)
                frame_h = max(bbox[3], 1080)
                norm_centroid = [centroid[0] / frame_w, centroid[1] / frame_h]
            
            for zone in camera_zones:
                if self.is_point_in_zone(norm_centroid, zone):
                    det["zone_id"] = zone["id"]
                    det["zone_name"] = zone["name"]
                    break
        
        # If Zone Monitoring is active, filter to zone-only detections
        if RULE_ZONE_MONITORING in active:
            zone_filtered = [d for d in detections if d.get("zone_id")]
        else:
            zone_filtered = detections
        
        persons = self._get_persons(zone_filtered)
        vehicles = self._get_vehicles(zone_filtered)
        objects = self._get_objects(zone_filtered)
        person_count = len(persons)
        now = time.time()
        
        events = []
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 1: Appearance Search
        # ═══════════════════════════════════════════════════════════════
        if RULE_APPEARANCE_SEARCH in active:
            for det in zone_filtered:
                if det["class"] in ("person", "car", "motorcycle", "bus", "truck"):
                    events.append(self._event(1, "Appearance Search", "low",
                        f"Detected {det['class']} (ID:{det.get('id','?')})", 
                        data=det, trigger_l3=False))
                    break  # Only report once per frame to reduce noise
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 2: Camera Tamper
        # ═══════════════════════════════════════════════════════════════
        # ═══════════════════════════════════════════════════════════════
        # RULE 2: Camera Tamper
        # ═══════════════════════════════════════════════════════════════
        if RULE_CAMERA_TAMPER in active:
            blur_score = detection_data.get("blur_score", 100)
            luminance = detection_data.get("luminance", 128)
            stdev = detection_data.get("stdev", 50)
            
            tamper_msg = None
            if blur_score < self.config["tamper_blur_threshold"]:
                tamper_msg = f"Camera view blury/out-of-focus (score: {blur_score:.1f})"
            elif luminance < self.config["tamper_luminance_low"]:
                tamper_msg = "Camera view blocked/completely dark"
            elif luminance > self.config["tamper_luminance_high"]:
                tamper_msg = "Camera view overexposed/blinded"
            elif stdev < 5 and luminance > 50: # Grey/static frame
                tamper_msg = "Static/frozen frame detected"
            elif motion_score > 150:
                tamper_msg = "Excessive camera shaking/vibration"

            if tamper_msg:
                events.append(self._event(2, "Camera Tamper", "critical", tamper_msg, trigger_l3=True))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 3: Chain/Handbag Snatching
        # ═══════════════════════════════════════════════════════════════
        if RULE_CHAIN_SNATCHING in active:
            bags = [d for d in zone_filtered if d["class"] in ("handbag", "backpack", "suitcase")]
            if bags and person_count >= 2:
                # Check if any person is moving rapidly near a bag
                for bag in bags:
                    for person in persons:
                        dist = self._centroid_distance(bag["centroid"], person["centroid"])
                        velocity = self._get_track_velocity(source_id, person.get("id"))
                        if dist < self.config["proximity_threshold"] and velocity > self.config["rapid_motion_threshold"]:
                            events.append(self._event(3, "Chain/Handbag Snatching", "critical",
                                f"Rapid motion near {bag['class']} — possible snatching",
                                trigger_l3=True))
                            break
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 4: Crowd Detection
        # ═══════════════════════════════════════════════════════════════
        if RULE_CROWD_DETECTION in active:
            if person_count >= self.config["crowd_threshold"]:
                heatmap_data = self.heatmaps[source_id].tolist()
                events.append(self._event(4, "Crowd Detection", "medium",
                    f"Crowd detected: {person_count} persons",
                    data={"count": person_count, "heatmap": heatmap_data}, trigger_l3=False))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 5: Eve Teasing
        # ═══════════════════════════════════════════════════════════════
        if RULE_EVE_TEASING in active:
            if person_count >= 3:
                clusters = self._find_proximity_clusters(persons)
                for cluster in clusters:
                    if len(cluster) >= 3:
                        events.append(self._event(5, "Eve Teasing", "high",
                            f"Close proximity cluster of {len(cluster)} persons detected",
                            trigger_l3=True))
                        break
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 6: Face Capture
        # ═══════════════════════════════════════════════════════════════
        if RULE_FACE_CAPTURE in active:
            if person_count > 0:
                events.append(self._event(6, "Face Capture", "low",
                    f"{person_count} face(s) available for capture",
                    data={"count": person_count}, trigger_l3=False))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 7: Face Recognition
        # ═══════════════════════════════════════════════════════════════
        if RULE_FACE_RECOGNITION in active:
            if person_count > 0:
                events.append(self._event(7, "Face Recognition", "low",
                    f"{person_count} person(s) in frame for recognition",
                    data={"count": person_count}, trigger_l3=False))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 8: Gesture Detection
        # ═══════════════════════════════════════════════════════════════
        if RULE_GESTURE_DETECTION in active:
            # YOLO can detect persons; Gemma analyzes gestures
            rapid_persons = [p for p in persons if self._get_track_velocity(source_id, p.get("id")) > 30]
            if rapid_persons:
                events.append(self._event(8, "Gesture Detection", "low",
                    f"Active motion from {len(rapid_persons)} person(s) — gesture analysis requested",
                    trigger_l3=True))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 9: Graffiti and Vandalism Detection
        # ═══════════════════════════════════════════════════════════════
        if RULE_GRAFFITI_VANDALISM in active:
            # Person stationary for extended time + high motion score = possible vandalism
            for person in persons:
                tid = person.get("id")
                if tid and self._get_loiter_time(source_id, tid) > 20:
                    velocity = self._get_track_velocity(source_id, tid)
                    if velocity < 10:  # Stationary
                        events.append(self._event(9, "Graffiti and Vandalism", "high",
                            f"Stationary person (ID:{tid}) for extended period — possible vandalism",
                            trigger_l3=True))
                        break
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 10: Intrusion Detection
        # ═══════════════════════════════════════════════════════════════
        if RULE_INTRUSION_DETECTION in active:
            intruders = [d for d in persons if d.get("zone_id")]
            active_intruder_ids = set()
            
            for intruder in intruders:
                tid = intruder.get("id")
                if tid is None: continue
                active_intruder_ids.add(tid)
                
                # Check persistence
                if tid not in self.persistence_counters[source_id]:
                    self.persistence_counters[source_id][tid] = now
                else:
                    duration = now - self.persistence_counters[source_id][tid]
                    if duration >= self.config["persistence_threshold"]:
                        events.append(self._event(10, "Intrusion Detection", "high",
                            f"Person (ID:{tid}) persisted in {intruder.get('zone_name', 'restricted zone')} for {int(duration)}s",
                            data={"track_id": tid, "duration": duration, "zone": intruder.get("zone_name")}, 
                            trigger_l3=True))
            
            # Cleanup persistence counters for tracks no longer in zones
            stale_p = [tid for tid in self.persistence_counters[source_id] if tid not in active_intruder_ids]
            for tid in stale_p:
                del self.persistence_counters[source_id][tid]
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 11: Lakshmanrekha Crossing (Virtual Line)
        # ═══════════════════════════════════════════════════════════════
        if RULE_LAKSHMANREKHA_CROSSING in active:
            crossings = self._check_line_crossings(source_id, persons, camera_zones)
            if crossings:
                for crossing in crossings:
                    events.append(self._event(11, "Lakshmanrekha Crossing", "high",
                        f"Person (ID:{crossing['track_id']}) crossed virtual line '{crossing['zone_name']}'",
                        trigger_l3=True))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 12: Loitering
        # ═══════════════════════════════════════════════════════════════
        if RULE_LOITERING in active:
            for person in persons:
                tid = person.get("id")
                loiter_time = self._get_loiter_time(source_id, tid)
                if loiter_time > self.config["loitering_time_threshold"]:
                    events.append(self._event(12, "Loitering", "medium",
                        f"Person (ID:{tid}) loitering for {int(loiter_time)}s - behavioral intent analysis requested",
                        data={"track_id": tid, "duration": loiter_time}, trigger_l3=True))
                    break  # One loitering alert at a time
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 13: Mobile Snatching
        # ═══════════════════════════════════════════════════════════════
        if RULE_MOBILE_SNATCHING in active:
            phones = [d for d in zone_filtered if d["class"] == "cell phone"]
            if phones and person_count >= 2:
                for phone in phones:
                    for person in persons:
                        dist = self._centroid_distance(phone["centroid"], person["centroid"])
                        velocity = self._get_track_velocity(source_id, person.get("id"))
                        if dist < self.config["proximity_threshold"] and velocity > self.config["rapid_motion_threshold"]:
                            events.append(self._event(13, "Mobile Snatching", "critical",
                                f"Rapid motion near mobile phone — possible snatching",
                                trigger_l3=True))
                            break
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 14: Object Classification
        # ═══════════════════════════════════════════════════════════════
        if RULE_OBJECT_CLASSIFICATION in active:
            if zone_filtered:
                class_summary = {}
                for d in zone_filtered:
                    class_summary[d["class"]] = class_summary.get(d["class"], 0) + 1
                summary_str = ", ".join(f"{k}:{v}" for k, v in class_summary.items())
                events.append(self._event(14, "Object Classification", "low",
                    f"Objects: {summary_str}",
                    data={"classes": class_summary}, trigger_l3=False))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 15: People Fighting
        # ═══════════════════════════════════════════════════════════════
        if RULE_PEOPLE_FIGHTING in active:
            if person_count >= 2:
                clusters = self._find_proximity_clusters(persons)
                for cluster in clusters:
                    if len(cluster) >= 2:
                        # Check for aggressive motion within the cluster
                        rapid_count = 0
                        for p in cluster:
                            tid = p.get("id")
                            vel = self._get_track_velocity(source_id, tid)
                            if vel > self.config["rapid_motion_threshold"]:
                                rapid_count += 1
                        
                        if rapid_count >= 2:
                            events.append(self._event(15, "People Fighting", "critical",
                                f"Physical altercation suspected: {len(cluster)} persons in close proximity with aggressive motion",
                                data={"cluster_size": len(cluster), "rapid_actors": rapid_count},
                                trigger_l3=True))
                            break
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 16: Person Collapsing
        # ═══════════════════════════════════════════════════════════════
        if RULE_PERSON_COLLAPSING in active:
            for person in persons:
                tid = person.get("id")
                if tid:
                    v_drop = self._get_vertical_drop(source_id, tid)
                    velocity = self._get_track_velocity(source_id, tid)
                    
                    # Suden vertical drop followed by inactivity (low velocity)
                    if v_drop > self.config["collapse_vertical_threshold"] and velocity < 5:
                        events.append(self._event(16, "Person Collapsing", "critical",
                            f"Medical Emergency: Person (ID:{tid}) sudden vertical drop detected ({int(v_drop)}px) with inactivity",
                            data={"track_id": tid, "drop": v_drop, "residual_motion": velocity},
                            trigger_l3=True))
                        break
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 17: Strike / Morcha / Procession
        # ═══════════════════════════════════════════════════════════════
        if RULE_STRIKE_PROCESSION in active:
            if person_count >= self.config["strike_threshold"]:
                # Check if many people are moving in the same direction
                directional = self._check_directional_movement(source_id, persons)
                if directional:
                    events.append(self._event(17, "Strike / Morcha / Procession", "high",
                        f"Large group ({person_count} persons) moving in coordinated direction",
                        trigger_l3=True))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 18: Suspected Appearance
        # ═══════════════════════════════════════════════════════════════
        if RULE_SUSPECTED_APPEARANCE in active:
            if person_count > 0:
                events.append(self._event(18, "Suspected Appearance", "medium",
                    f"{person_count} person(s) detected — appearance analysis available",
                    trigger_l3=True))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 19: Unattended Object
        # ═══════════════════════════════════════════════════════════════
        if RULE_UNATTENDED_OBJECT in active:
            unattended = self._check_unattended_objects(source_id, objects, persons, now)
            for obj_info in unattended:
                events.append(self._event(19, "Unattended Object", "high",
                    f"Unattended {obj_info['class']} for {int(obj_info['duration'])}s",
                    data=obj_info, trigger_l3=True))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 20: Women Surrounded by Men
        # ═══════════════════════════════════════════════════════════════
        if RULE_WOMEN_SURROUNDED in active:
            if person_count >= 4:
                clusters = self._find_proximity_clusters(persons)
                for cluster in clusters:
                    if len(cluster) >= 4:
                        events.append(self._event(20, "Women Surrounded by Men", "critical",
                            f"Cluster of {len(cluster)} persons in close proximity — vulnerability risk",
                            trigger_l3=True))
                        break
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 21: Women/Infant Abduction
        # ═══════════════════════════════════════════════════════════════
        if RULE_ABDUCTION in active:
            if person_count >= 2:
                for person in persons:
                    tid = person.get("id")
                    velocity = self._get_track_velocity(source_id, tid)
                    cx, cy = person["centroid"]
                    
                    # Forced movement towards exit or frame edge with high velocity
                    # Assuming 1920x1080 resolution for normalized edge detection
                    if velocity > self.config["rapid_motion_threshold"] * 1.5:
                        is_near_edge = cx < 200 or cx > 1720 or cy < 150 or cy > 930
                        if is_near_edge:
                            events.append(self._event(21, "Abduction Detection", "critical",
                                f"High-priority: Person (ID:{tid}) rapidly forced/moving towards frame boundary",
                                data={"track_id": tid, "velocity": velocity, "position": [cx, cy]},
                                trigger_l3=True))
                            break
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 22: Vehicle Monitoring
        # ═══════════════════════════════════════════════════════════════
        if RULE_VEHICLE_MONITORING in active:
            if vehicles:
                v_summary = {}
                for v in vehicles:
                    v_summary[v["class"]] = v_summary.get(v["class"], 0) + 1
                summary_str = ", ".join(f"{k}:{v}" for k, v in v_summary.items())
                events.append(self._event(22, "Vehicle Monitoring", "low",
                    f"Vehicles: {summary_str}",
                    data={"vehicles": v_summary}, trigger_l3=False))
        
        # ═══════════════════════════════════════════════════════════════
        # RULE 23: Zone Monitoring
        # ═══════════════════════════════════════════════════════════════
        if RULE_ZONE_MONITORING in active:
            zone_detections = [d for d in detections if d.get("zone_id")]
            if zone_detections:
                zone_summary = {}
                for d in zone_detections:
                    zn = d.get("zone_name", "Unknown")
                    zone_summary[zn] = zone_summary.get(zn, 0) + 1
                for zone_name, count in zone_summary.items():
                    events.append(self._event(23, "Zone Monitoring (Restricted Area)", "high",
                        f"RESTRICTED ALERT: {count} object(s) detected inside {zone_name}",
                        data={"zone": zone_name, "count": count}, trigger_l3=True))
        
        # Deduplicate by type (keep highest severity)
        deduped = {}
        severity_rank = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        for evt in events:
            key = evt["type"]
            if key not in deduped or severity_rank.get(evt["severity"], 0) > severity_rank.get(deduped[key]["severity"], 0):
                deduped[key] = evt
        
        final_events = list(deduped.values())
        self.source_events[source_id] = {e["type"]: e for e in final_events}
        return final_events

    # ─── EVENT FACTORY ────────────────────────────────────────────────

    def _event(self, rule_id, event_type, severity, message, data=None, trigger_l3=False):
        """Create a standardized event dict"""
        evt = {
            "id": rule_id,
            "type": event_type,
            "severity": severity,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "trigger_layer3": trigger_l3,
        }
        if data:
            evt["data"] = data
        return evt

    # ─── TRACKING HELPERS ─────────────────────────────────────────────

    def _update_track_history(self, source_id, detections):
        """Update sliding window of centroids and timestamps for each track_id"""
        history = self.track_histories[source_id]
        first_seen = self.track_first_seen[source_id]
        classes = self.track_classes[source_id]
        now = time.time()
        
        for det in detections:
            tid = det.get("id")
            if tid is None:
                continue
            if tid not in history:
                history[tid] = deque(maxlen=30)
                first_seen[tid] = now
            history[tid].append(det["centroid"])
            classes[tid] = det["class"]

    def _get_track_velocity(self, source_id, track_id):
        """Get pixel velocity of a tracked object (distance between last 2 positions)"""
        if track_id is None:
            return 0
        history = self.track_histories.get(source_id, {}).get(track_id)
        if not history or len(history) < 2:
            return 0
        p1, p2 = history[-2], history[-1]
        return np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

    def _get_vertical_drop(self, source_id, track_id):
        """Get downward Y movement over recent frames (positive = dropping)"""
        if track_id is None:
            return 0
        history = self.track_histories.get(source_id, {}).get(track_id)
        if not history or len(history) < 5:
            return 0
        # Compare Y of 5 frames ago to current (Y increases downward in image)
        return history[-1][1] - history[-5][1]

    def _get_loiter_time(self, source_id, track_id):
        """How long a track has been visible (seconds)"""
        if track_id is None:
            return 0
        first = self.track_first_seen.get(source_id, {}).get(track_id)
        if first is None:
            return 0
        return time.time() - first

    # ─── PROXIMITY & CLUSTER ANALYSIS ─────────────────────────────────

    def _find_proximity_clusters(self, persons):
        """Find groups of persons within proximity_threshold of each other"""
        if len(persons) < 2:
            return []
        
        threshold = self.config["proximity_threshold"]
        visited = set()
        clusters = []
        
        for i, p1 in enumerate(persons):
            if i in visited:
                continue
            cluster = [p1]
            visited.add(i)
            for j, p2 in enumerate(persons):
                if j in visited:
                    continue
                if self._centroid_distance(p1["centroid"], p2["centroid"]) < threshold:
                    cluster.append(p2)
                    visited.add(j)
            if len(cluster) >= 2:
                clusters.append(cluster)
        
        return clusters

    # ─── DIRECTIONAL MOVEMENT ─────────────────────────────────────────

    def _check_directional_movement(self, source_id, persons):
        """Check if multiple persons are moving in roughly the same direction"""
        if len(persons) < 5:
            return False
        
        directions = []
        for p in persons:
            tid = p.get("id")
            history = self.track_histories.get(source_id, {}).get(tid)
            if history and len(history) >= 3:
                dx = history[-1][0] - history[-3][0]
                dy = history[-1][1] - history[-3][1]
                if abs(dx) > 5 or abs(dy) > 5:
                    angle = np.arctan2(dy, dx)
                    directions.append(angle)
        
        if len(directions) < 5:
            return False
        
        # Check if most directions are within 45 degrees of each other
        mean_dir = np.mean(directions)
        aligned = sum(1 for d in directions if abs(d - mean_dir) < np.pi/4)
        return aligned >= len(directions) * 0.6

    # ─── LINE CROSSING ────────────────────────────────────────────────

    def _check_line_crossings(self, source_id, persons, zones):
        """Check if any person crossed a virtual line defined by a zone edge"""
        crossings = []
        lc = self.line_crossings[source_id]
        
        for zone in zones:
            for person in persons:
                tid = person.get("id")
                if tid is None:
                    continue
                    
                cx, cy = person["centroid"]
                # Use pre-computed norm_centroid from YOLO engine or fallback
                ncx, ncy = person.get("norm_centroid", [cx / 1920, cy / 1080])
                
                # Determine which side of the line/boundary the point is on
                if zone.get("type") == "circle":
                    # For circles, "side" is whether inside or outside
                    center = zone.get("center", [0.5, 0.5])
                    radius = zone.get("radius", 0.1)
                    dist = np.sqrt((ncx - center[0])**2 + (ncy - center[1])**2)
                    current_side = 1 if dist <= radius else -1
                else:
                    # For polygons, use the first edge as the virtual line
                    poly = zone.get("polygon", [])
                    if len(poly) < 2:
                        continue
                    lx1, ly1 = poly[0]
                    lx2, ly2 = poly[1]
                    side = (lx2 - lx1) * (ncy - ly1) - (ly2 - ly1) * (ncx - lx1)
                    current_side = 1 if side > 0 else -1
                
                key = f"{tid}_{zone['id']}"
                if key in lc:
                    if lc[key] != current_side:
                        crossings.append({
                            "track_id": tid,
                            "zone_id": zone["id"],
                            "zone_name": zone["name"],
                            "direction": "entry" if current_side == 1 else "exit"
                        })
                lc[key] = current_side
        
        return crossings

    # ─── UNATTENDED OBJECT ────────────────────────────────────────────

    def _check_unattended_objects(self, source_id, objects, persons, now):
        """Track objects that remain static without a person nearby"""
        static = self.static_objects[source_id]
        threshold = self.config["proximity_threshold"] * 2  # Wider radius for "ownership"
        unattended = []
        
        current_obj_ids = set()
        for obj in objects:
            tid = obj.get("id")
            if tid is None:
                continue
            current_obj_ids.add(tid)
            
            # Check if any person is nearby
            person_nearby = any(
                self._centroid_distance(obj["centroid"], p["centroid"]) < threshold
                for p in persons
            )
            
            if not person_nearby:
                if tid not in static:
                    static[tid] = {"pos": obj["centroid"], "first_seen": now, "class": obj["class"]}
                else:
                    duration = now - static[tid]["first_seen"]
                    if duration > self.config["unattended_object_time"]:
                        unattended.append({
                            "track_id": tid,
                            "class": obj["class"],
                            "duration": duration,
                            "position": obj["centroid"],
                        })
            else:
                # Person nearby — reset timer
                if tid in static:
                    del static[tid]
        
        # Cleanup stale entries
        stale_ids = [tid for tid in static if tid not in current_obj_ids]
        for tid in stale_ids:
            del static[tid]
        
        return unattended

    # ─── PUBLIC API ───────────────────────────────────────────────────

    def get_active_events(self, source_id: str):
        """Return currently active events for a specific source"""
        return list(self.source_events.get(source_id, {}).values())
    
    def _update_heatmap(self, source_id, detections):
        """Update 10x10 occupancy grid for crowd density analysis"""
        heatmap = self.heatmaps[source_id]
        # Decay existing heatmap slightly to show temporal density
        heatmap *= 0.9
        
        for det in detections:
            cx, cy = det["centroid"]
            # Normalize to 0-9 index
            # Assuming 1920x1080 if not specified, or just using fractional if YOLO provided it
            # Detection data from yolo26_engine uses pixel coordinates
            gx = min(int(cx / 192), 9)
            gy = min(int(cy / 108), 9)
            heatmap[gy, gx] += 1
            
        # Clip to max value to prevent overflow
        self.heatmaps[source_id] = np.clip(heatmap, 0, 50)

    def clear_source_data(self, source_id: str):
        """Cleanup memory when a stream is closed"""
        stores = (self.track_histories, self.track_first_seen, self.track_classes,
                  self.source_events, self.static_objects, self.line_crossings,
                  self.persistence_counters, self.heatmaps)
        for store in stores:
            if source_id in store:
                del store[source_id]

    def trigger_alert_api(self, source_id: str, event: dict):
        """
        Trigger the central Alert API for a confirmed security detection.
        Writes the event to event_records.json and records an MP4 video proof.
        """
        logger.info(f"🚨 [ALERT API] Triggered for {source_id}: {event['type']} - {event['message']}")
        
        try:
            from routes.events import get_event_records, save_event_records
            import uuid
            from datetime import datetime
            import threading
            import subprocess
            from pathlib import Path
            import os
            import sys
            
            records = get_event_records()
            rule_type = event.get("type", "Unknown Event")
            
            # Debounce: check if an event for this rule on this camera was generated within the last 5 minutes (300 seconds).
            already_active = False
            now = datetime.now()
            for r in reversed(records):
                if r.get("rule_name") == rule_type and r.get("camera_id") == source_id:
                    created_at_str = r.get("created_at")
                    if created_at_str:
                        try:
                            created_time = datetime.fromisoformat(created_at_str)
                            if (now - created_time).total_seconds() < 300:
                                already_active = True
                                break
                        except:
                            pass
            
            # Check if rule is enabled for this camera specifically
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
                "Graffiti / Vandalism": 9,
                "Intrusion Detection": 10,
                "Lakshmanrekha Crossing": 11,
                "Loitering": 12,
                "Mobile Snatching": 13,
                "Object Classification": 14,
                "People Fighting": 15,
                "Person Collapsing": 16,
                "Strike / Morcha / Hartal / Procession": 17,
                "Strike / Procession": 17,
                "Suspected Appearance": 18,
                "Unattended Object": 19,
                "Women Surrounded by Men": 20,
                "Women Surrounded": 20,
                "Women/Infant Abduction": 21,
                "Abduction Detection": 21,
                "Vehicle Monitoring": 22,
                "Zone Monitoring": 23,
            }
            rule_id = rule_name_to_id.get(rule_type)
            active_rules_for_cam = self.get_active_rules_for_source(source_id)
            if rule_id and rule_id not in active_rules_for_cam:
                logger.info(f"Rule '{rule_type}' (ID:{rule_id}) is NOT enabled for camera '{source_id}'. Skipping event generation.")
                return

            # Check if the rule is enabled in global configuration
            EVENTS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "events_configuration.json") if 'WORKSPACE_ROOT' in locals() else os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "events_configuration.json"))
            rule_enabled = True
            try:
                if os.path.exists(EVENTS_CONFIG_PATH):
                    with open(EVENTS_CONFIG_PATH, "r") as f:
                        import json
                        config = json.load(f)
                        for rule in config.get("rules", []):
                            if rule.get("name") == rule_type:
                                rule_enabled = rule.get("enabled", True)
                                break
            except Exception as e:
                logger.error(f"Error checking event config: {e}")
                
            if not rule_enabled:
                logger.info(f"Rule '{rule_type}' is disabled in configuration. Skipping event generation.")
                return
            
            if already_active:
                return
                
            # Generate a truly unique ID for this new event occurrence
            event_id_str = f"EVT-{uuid.uuid4().hex[:8].upper()}"
            
            # Determine category based on rule type
            category = "Security Analytics"
            if rule_type in ["Face Capture", "Face Recognition", "Appearance Search"]:
                category = "Face Analytics"
            elif rule_type in ["Vehicle Monitoring"]:
                category = "Vehicle Analytics"
            elif rule_type in ["People Fighting", "Mobile Snatching", "Chain/Handbag Snatching", "Eve Teasing", "Women Surrounded by Men", "Women/Infant Abduction"]:
                category = "Crime Detection"
            elif rule_type in ["Crowd Detection", "Person Collapsing", "Strike / Morcha / Hartal / Procession"]:
                category = "Crowd & Public Safety"
                
            new_record = {
                "event_id": event_id_str,
                "created_at": datetime.now().isoformat(),
                "rule_name": rule_type,
                "camera_name": source_id,
                "camera_id": source_id,
                "location": "Main Location",
                "priority": event.get("priority", "High"),
                "duration": 30,
                "status": "Active",
                "category": category,
                "confidence": 0.95,
                "acknowledged": False,
                "message": event.get("message", ""),
                "video_proof_url": f"/api/augment/events/proofs/{event_id_str}.mp4"
            }
            
            records.append(new_record)
            save_event_records(records)
            
            def record_proof(eid, sid):
                try:
                    # Get RTSP URL from camera configuration safely
                    import json
                    rtsp_url = None
                    camera_config_path = os.path.join(os.path.dirname(__file__), "..", "data", "camera_configuration.json")
                    if os.path.exists(camera_config_path):
                        with open(camera_config_path, "r") as f:
                            cam_data = json.load(f)
                            # Iterate through collections to find the camera by IP/ID
                            for collection, cameras in cam_data.items():
                                if isinstance(cameras, dict):
                                    for cam_ip, url in cameras.items():
                                        if cam_ip in sid or sid in cam_ip:
                                            rtsp_url = url
                                            break
                                if rtsp_url:
                                    break
                    
                    if not rtsp_url:
                        logger.warning(f"Could not find RTSP URL for stream {sid} to record proof.")
                        # Clear video_proof_url since no video will be captured
                        rec_list = get_event_records()
                        for r in rec_list:
                            if r.get("event_id") == eid:
                                r["video_proof_url"] = None
                                break
                        save_event_records(rec_list)
                        return
                        
                    proofs_dir = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "proofs")))
                    proofs_dir.mkdir(parents=True, exist_ok=True)
                    
                    output_file = proofs_dir / f"{eid}.mp4"
                    
                    logger.info(f"🎥 Recording video proof for event {eid} to {output_file}")
                    
                    # FFmpeg command to capture 30 seconds for the event
                    cmd = [
                        "ffmpeg", "-y",
                        "-rtsp_transport", "tcp",
                        "-i", rtsp_url,
                        "-t", "30",
                        "-c:v", "libx264",
                        "-preset", "ultrafast",
                        "-b:v", "1000k",
                        "-an", # No audio
                        "-movflags", "frag_keyframe+empty_moov",
                        str(output_file)
                    ]
                    
                    subprocess.run(cmd, timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    # Verify video proof file exists and is not empty (> 10KB)
                    if output_file.exists() and output_file.stat().st_size > 10240:
                        logger.info(f"✅ Video proof recorded successfully ({output_file.stat().st_size} bytes): {output_file}")
                    else:
                        logger.warning(f"⚠️ Video proof recording failed or empty for {eid}. Removing empty file.")
                        if output_file.exists():
                            try: output_file.unlink()
                            except: pass
                        # Clear video_proof_url so no empty video is stored/shown
                        rec_list = get_event_records()
                        for r in rec_list:
                            if r.get("event_id") == eid:
                                r["video_proof_url"] = None
                                break
                        save_event_records(rec_list)

                except Exception as e:
                    logger.error(f"❌ Failed to record video proof: {e}")
                    rec_list = get_event_records()
                    for r in rec_list:
                        if r.get("event_id") == eid:
                            r["video_proof_url"] = None
                            break
                    save_event_records(rec_list)

            # Spawn FFmpeg in background
            threading.Thread(target=record_proof, args=(event_id_str, source_id), daemon=True).start()
            
        except Exception as e:
            logger.error(f"Error persisting alert to events system: {e}")

    # ─── PUBLIC API ───────────────────────────────────────────────────
pattern_engine = PatternEngine()
