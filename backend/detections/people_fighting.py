import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import deque
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class PeopleFightingDetector(BaseDetector):
    """
    Detects physical fights and violence between persons in video frames.
    Implements a Multi-Stage Violence Scoring Engine and Play-Fighting Play Filter.

    Detection Strategy:
        1. Person Tracking: Uses ByteTrack tracking IDs (or centroid matching fallback)
           to track individuals and monitor interactions over time.
        2. Multi-Stage Scoring: Evaluates pairwise interaction scores:
           - Proximity Score (pairwise distance)
           - Motion Score (optical flow energy)
           - Overlap Score (box IoU)
           - Upper Body Motion (focuses on punch/shove gestures)
           - Acceleration Score (sudden speed/motion changes)
        3. Timeline Analysis & Filtering:
           - Level 1: Suspicious Interaction (< 5s). Triggered = False.
           - Level 2: Aggressive Escalation (5s to 30s). Triggered = False (suppresses play fights).
           - Level 3: Confirmed Violence (30s to 60s). Triggered = True.
           - Level 4: Severe Assault / Ground Assault (>= 60s, or standing person kicking lying person). Triggered = True.

    Kaggle Dataset Sourcing Suggestions:
        - RWF-2000 (Real World Fighting) Dataset
        - Hockey Fight Dataset
        - Surveillance Fight Detection Dataset
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._prev_gray: Optional[np.ndarray] = None
        self._motion_history: deque = deque(maxlen=30)
        
        # Stateful tracking history
        self._active_interactions: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self._track_centroids_history: Dict[int, np.ndarray] = {}
        self._last_person_centroids: Dict[int, np.ndarray] = {}
        self._next_track_id: int = 1
        
        super().__init__("people_fighting", config)

    # ------------------------------------------------------------------
    # Model Loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """
        Loads YOLOv8 model for person tracking, or HOG fallback.
        """
        self._proximity_threshold = self.config.get("proximity_threshold", 150)
        self._overlap_iou_threshold = self.config.get("overlap_iou_threshold", 0.15)
        self._motion_energy_threshold = self.config.get("motion_energy_threshold", 8.0)
        self._fight_score_threshold = self.config.get("fight_score_threshold", 0.50)
        self._play_fighting_window = self.config.get("play_fighting_window", 30.0) # wait 30s to confirm

        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            self._use_yolo = True
            logger.info("YOLOv8 model loaded for PeopleFightingDetector.")
        except Exception as e:
            logger.warning(
                f"YOLO unavailable ({e}); falling back to HOG person detector."
            )
            self.model = cv2.HOGDescriptor()
            self.model.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._use_yolo = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse a single frame for fighting / violence with stateful scoring.

        Args:
            frame: BGR video frame (H × W × 3).
            **kwargs:
                person_boxes (List[List[int]]): Pre-computed bounding boxes.
                external_detections (List[Dict]): Upstream object detections.
                timestamp (float): Frame timestamp in seconds.

        Returns:
            Standardised detection dict.
        """
        if not self.is_enabled:
            return self._empty_result()

        import time
        timestamp = kwargs.get("timestamp", time.time())
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]
        frame_area = h * w

        # --- 1. Parse Person Detections ---
        raw_boxes = kwargs.get("person_boxes")
        external_detections = kwargs.get("external_detections")
        
        persons = []
        if external_detections:
            for det in external_detections:
                label = det.get("label", det.get("class", ""))
                if label == "person":
                    bbox = det.get("bbox")
                    if bbox and len(bbox) == 4:
                        persons.append({
                            "bbox": [int(v) for v in bbox],
                            "id": det.get("id"),
                            "confidence": float(det.get("confidence", 1.0))
                        })
        elif raw_boxes:
            for idx, box in enumerate(raw_boxes):
                persons.append({
                    "bbox": box,
                    "id": None,
                    "confidence": 1.0
                })
        else:
            persons = self._detect_persons_local(frame)

        # Resolve tracking IDs if they are missing
        self._resolve_tracker_ids(persons)

        # --- 2. Dense optical flow ---
        flow_mag = self._compute_optical_flow(gray)

        # --- 3. Per-person motion energy (total & upper body) ---
        person_energies = {}
        person_upper_energies = {}
        current_velocities = {}

        for p in persons:
            pid = p["id"]
            bbox = p["bbox"]
            
            # Total body motion
            person_energies[pid] = self._compute_box_motion(bbox, flow_mag, h, w)
            # Upper body motion (punches/shoves)
            person_upper_energies[pid] = self._compute_upper_body_motion(bbox, flow_mag, h, w)
            
            # Velocity / Acceleration tracking
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            curr_centroid = np.array([cx, cy])
            if pid in self._track_centroids_history:
                velocity = float(np.linalg.norm(curr_centroid - self._track_centroids_history[pid]))
            else:
                velocity = 0.0
            current_velocities[pid] = velocity
            self._track_centroids_history[pid] = curr_centroid

        # --- 4. Pair-wise fight scoring & ground assault heuristics ---
        n = len(persons)
        current_active_keys = set()

        for i in range(n):
            for j in range(i + 1, n):
                p_i = persons[i]
                p_j = persons[j]
                id_i, id_j = p_i["id"], p_j["id"]
                pair_key = (min(id_i, id_j), max(id_i, id_j))
                
                box_a = p_i["bbox"]
                box_b = p_j["bbox"]
                
                centroid_i = np.array([(box_a[0] + box_a[2]) / 2.0, (box_a[1] + box_a[3]) / 2.0])
                centroid_j = np.array([(box_b[0] + box_b[2]) / 2.0, (box_b[1] + box_b[3]) / 2.0])
                dist = float(np.linalg.norm(centroid_i - centroid_j))

                # Scores
                proximity_score = max(0.0, 1.0 - dist / self._proximity_threshold)
                avg_energy = (person_energies.get(id_i, 0.0) + person_energies.get(id_j, 0.0)) / 2.0
                motion_score = min(1.0, avg_energy / self._motion_energy_threshold)
                
                iou = self._iou(box_a, box_b)
                overlap_score = min(1.0, iou / self._overlap_iou_threshold) if self._overlap_iou_threshold > 0 else 0.0
                
                avg_upper = (person_upper_energies.get(id_i, 0.0) + person_upper_energies.get(id_j, 0.0)) / 2.0
                upper_body_score = min(1.0, avg_upper / self._motion_energy_threshold)
                
                max_vel = max(current_velocities.get(id_i, 0.0), current_velocities.get(id_j, 0.0))
                acceleration_score = min(1.0, max_vel / 20.0)

                # Combined multi-stage violence score
                combined = (
                    0.20 * proximity_score
                    + 0.20 * motion_score
                    + 0.20 * overlap_score
                    + 0.20 * upper_body_score
                    + 0.20 * acceleration_score
                )

                # Ground assault detection check
                ground_assault_detected = False
                w_a, h_a = box_a[2] - box_a[0], box_a[3] - box_a[1]
                w_b, h_b = box_b[2] - box_b[0], box_b[3] - box_b[1]
                is_a_lying = w_a > 1.4 * h_a
                is_b_lying = w_b > 1.4 * h_b
                is_a_standing = h_a > 1.2 * w_a
                is_b_standing = h_b > 1.2 * w_b

                if (is_a_lying and is_b_standing) or (is_b_lying and is_a_standing):
                    standing_id = id_j if is_b_standing else id_i
                    # Only flag if standing person is actively moving
                    if person_energies.get(standing_id, 0.0) > 4.0 and dist < self._proximity_threshold:
                        ground_assault_detected = True

                if combined >= self._fight_score_threshold:
                    current_active_keys.add(pair_key)
                    if pair_key not in self._active_interactions:
                        self._active_interactions[pair_key] = {
                            "start_time": timestamp,
                            "last_seen_time": timestamp,
                            "max_score": combined,
                            "ground_assault_count": 1 if ground_assault_detected else 0
                        }
                    else:
                        rec = self._active_interactions[pair_key]
                        rec["last_seen_time"] = timestamp
                        rec["max_score"] = max(rec["max_score"], combined)
                        if ground_assault_detected:
                            rec["ground_assault_count"] += 1

        # Decaying / cleaning up stale interactions
        stale_pairs = []
        for pair_key, rec in list(self._active_interactions.items()):
            if timestamp - rec["last_seen_time"] > 3.0:
                stale_pairs.append(pair_key)
        for pk in stale_pairs:
            self._active_interactions.pop(pk, None)

        # --- 5. Timeline-based stages & triggers ---
        triggered = False
        detections: List[Dict[str, Any]] = []

        for pair_key, rec in self._active_interactions.items():
            duration = timestamp - rec["start_time"]

            if rec["ground_assault_count"] >= 5:
                level = 4
                level_str = "ground_assault (Level 4)"
                level_severity = "critical"
            elif duration >= 60.0:
                level = 4
                level_str = "severe_assault (Level 4)"
                level_severity = "critical"
            elif duration >= self._play_fighting_window:
                level = 3
                level_str = "confirmed_violence (Level 3)"
                level_severity = "high"
            elif duration >= 5.0:
                level = 2
                level_str = "aggressive_escalation (Level 2)"
                level_severity = "medium"
            else:
                level = 1
                level_str = "suspicious_interaction (Level 1)"
                level_severity = "low"

            if level >= 3:
                triggered = True

            id_a, id_b = pair_key
            box_a = next((p["bbox"] for p in persons if p["id"] == id_a), None)
            box_b = next((p["bbox"] for p in persons if p["id"] == id_b), None)

            if box_a and box_b:
                merged_box = self._merge_boxes(box_a, box_b)
                detections.append({
                    "bbox": merged_box,
                    "confidence": round(float(rec["max_score"]), 3),
                    "label": f"fight_{level_str.split(' ')[0]}",
                    "level": level,
                    "level_name": level_str,
                    "severity": level_severity,
                    "duration": round(duration, 2),
                    "person_boxes": [box_a, box_b]
                })

        # Store previous frame state
        self._prev_gray = gray
        avg_energy = float(np.mean(list(person_energies.values()))) if person_energies else 0.0
        self._motion_history.append(avg_energy)

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "persons_detected": len(persons),
                "active_interactions": len(self._active_interactions),
                "avg_motion_energy": round(avg_energy, 2),
                "interaction_details": [
                    {
                        "pair": k,
                        "duration": round(timestamp - v["start_time"], 2),
                        "ground_assault": v["ground_assault_count"] >= 5,
                        "max_score": round(v["max_score"], 3)
                    }
                    for k, v in self._active_interactions.items()
                ]
            },
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _empty_result(self) -> Dict[str, Any]:
        return {
            "triggered": False,
            "detections": [],
            "metadata": {},
            "event_type": self.name,
        }

    def _detect_persons_local(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        persons = []
        if self._use_yolo and self.model is not None:
            try:
                results = self.model.track(frame, persist=True, verbose=False)
            except Exception:
                results = self.model(frame, verbose=False)
                
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        label = self.model.names[cls_id]
                        conf = float(box.conf[0])
                        if label == "person" and conf >= self.confidence_threshold:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            track_id = int(box.id[0]) if (box.id is not None) else None
                            persons.append({
                                "bbox": [x1, y1, x2, y2],
                                "id": track_id,
                                "confidence": conf
                            })
        else:
            rects, _ = self.model.detectMultiScale(
                frame, winStride=(8, 8), padding=(4, 4), scale=1.05
            )
            for (x, y, bw, bh) in rects:
                persons.append({
                    "bbox": [int(x), int(y), int(x + bw), int(y + bh)],
                    "id": None,
                    "confidence": 0.5
                })
        return persons

    def _resolve_tracker_ids(self, persons: List[Dict[str, Any]]):
        """Simple centroid distance matching for fallback tracking."""
        updated_centroids = {}
        for p in persons:
            bbox = p["bbox"]
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            centroid = np.array([cx, cy])
            
            if p.get("id") is not None:
                updated_centroids[p["id"]] = centroid
                continue
                
            matched_id = None
            min_dist = 80.0
            for tid, last_centroid in self._last_person_centroids.items():
                dist = float(np.linalg.norm(centroid - last_centroid))
                if dist < min_dist:
                    min_dist = dist
                    matched_id = tid
                    
            if matched_id is not None:
                p["id"] = matched_id
                self._last_person_centroids.pop(matched_id, None)
            else:
                p["id"] = self._next_track_id
                self._next_track_id += 1
                
            updated_centroids[p["id"]] = centroid
            
        self._last_person_centroids = updated_centroids

    def _compute_optical_flow(self, gray: np.ndarray) -> Optional[np.ndarray]:
        """Compute dense Farneback optical-flow magnitude map."""
        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            return None
        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray, gray,
            None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        return mag

    def _compute_box_motion(self, box: List[int], flow_mag: Optional[np.ndarray], h: int, w: int) -> float:
        if flow_mag is None:
            return 0.0
        x1, y1, x2, y2 = box
        x1c, y1c = max(0, x1), max(0, y1)
        x2c, y2c = min(w, x2), min(h, y2)
        if x2c <= x1c or y2c <= y1c:
            return 0.0
        return float(np.mean(flow_mag[y1c:y2c, x1c:x2c]))

    def _compute_upper_body_motion(self, box: List[int], flow_mag: Optional[np.ndarray], h: int, w: int) -> float:
        if flow_mag is None:
            return 0.0
        x1, y1, x2, y2 = box
        height = y2 - y1
        y2_upper = int(y1 + 0.40 * height)
        x1c, y1c = max(0, x1), max(0, y1)
        x2c, y2c = min(w, x2), min(h, y2_upper)
        if x2c <= x1c or y2c <= y1c:
            return 0.0
        return float(np.mean(flow_mag[y1c:y2c, x1c:x2c]))

    def _iou(self, box_a: List[int], box_b: List[int]) -> float:
        xa = max(box_a[0], box_b[0])
        ya = max(box_a[1], box_b[1])
        xb = min(box_a[2], box_b[2])
        yb = min(box_a[3], box_b[3])
        inter = max(0, xb - xa) * max(0, yb - ya)
        area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
        area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _merge_boxes(box_a: List[int], box_b: List[int]) -> List[int]:
        return [
            min(box_a[0], box_b[0]),
            min(box_a[1], box_b[1]),
            max(box_a[2], box_b[2]),
            max(box_a[3], box_b[3]),
        ]
