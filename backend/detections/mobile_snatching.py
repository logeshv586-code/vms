import logging
from typing import Dict, Any, List, Optional, Tuple
from collections import deque, defaultdict
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class MobileSnatchingDetector(BaseDetector):
    """
    Detects mobile-phone / object snatching events in video frames.

    Detection Strategy:
        1. Person & Phone Detection: Uses YOLO to detect persons and
           "cell phone" class objects. Falls back to contour-based small-
           rectangular-object detection near hand regions.
        2. Phone-Person Association: Associates each detected phone with
           the nearest person by bounding-box overlap or centroid proximity.
        3. Rapid Hand Motion: Computes optical flow within the hand/arm
           region (lower third of person bounding box on each side) to
           detect sudden jerking motions characteristic of snatching.
        4. Phone Transfer Detection: Tracks phone positions across frames.
           If a phone moves from one person's region to another's with
           high velocity (large displacement in few frames), a snatch is
           flagged.
        5. Velocity Anomaly: Measures phone-object displacement between
           frames. Normal phone use has low displacement; a snatch causes
           a spike in velocity that exceeds a configurable threshold.
        6. Temporal Confirmation: A snatch event must show the transfer
           pattern within a tight temporal window (< 1 second at 30 fps)
           to distinguish from handing over.

    Kaggle Dataset Sourcing Suggestions:
        - UCF Crime Dataset
        - COCO Dataset (for phone detection)
        - MOT Challenge Dataset (for person tracking)

    Config keys:
        model_path (str): Path to YOLOv8 weights. Default: "yolov8n.pt"
        phone_velocity_threshold (float): Minimum pixel displacement per
            frame to consider "rapid". Default: 40.0
        transfer_distance_threshold (int): Max distance from a person box
            for phone association. Default: 50
        snatch_window_frames (int): Max frames within which a transfer must
            complete. Default: 10
        hand_motion_threshold (float): Optical flow magnitude in hand region
            to flag. Default: 12.0
        temporal_window (int): Consecutive high-confidence frames to
            confirm. Default: 3
    """

    def __init__(self, config: Dict[str, Any] = None):
        self._prev_gray: Optional[np.ndarray] = None
        self._phone_tracks: Dict[int, deque] = defaultdict(
            lambda: deque(maxlen=30)
        )
        self._snatch_frame_count: int = 0
        self._frame_index: int = 0
        self._phone_id_counter: int = 0
        super().__init__("mobile_snatching", config)

    # ------------------------------------------------------------------
    # Model Loading
    # ------------------------------------------------------------------
    def load_model(self) -> None:
        """Load YOLOv8 for person + cell-phone detection, or fallback."""
        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            self._use_yolo = True
            logger.info("YOLOv8 model loaded for MobileSnatchingDetector.")
        except Exception as e:
            logger.warning(
                f"YOLO unavailable ({e}); falling back to contour-based detection."
            )
            self.model = None
            self._use_yolo = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse a frame for mobile-phone snatching events.

        Args:
            frame: BGR video frame (H × W × 3).
            **kwargs:
                person_boxes (List[List[int]]): Pre-computed person boxes.
                phone_boxes (List[List[int]]): Pre-computed phone boxes.
                timestamp (float): Frame timestamp.

        Returns:
            Standard detection dict.
        """
        if not self.is_enabled:
            return self._empty_result()

        self._frame_index += 1
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # --- 1. Detect persons and phones ---
        person_boxes = kwargs.get("person_boxes") or self._detect_persons(frame)
        phone_boxes = kwargs.get("phone_boxes") or self._detect_phones(frame, gray)

        # --- 2. Associate phones with nearest person ---
        associations = self._associate_phones_to_persons(phone_boxes, person_boxes)

        # --- 3. Track phones and detect transfers ---
        transfer_events = self._detect_transfers(
            phone_boxes, associations, person_boxes
        )

        # --- 4. Hand-region motion analysis ---
        hand_motion_events = self._analyse_hand_motion(
            gray, person_boxes, h, w
        )

        # --- 5. Combine signals ---
        snatch_events: List[Dict[str, Any]] = []
        phone_vel_thresh = self.config.get("phone_velocity_threshold", 40.0)

        for transfer in transfer_events:
            # Boost confidence if hand motion also detected
            hand_boost = 0.0
            for hm in hand_motion_events:
                if self._boxes_overlap(transfer["victim_box"], hm["person_box"]):
                    hand_boost = 0.15
                    break

            confidence = min(1.0, transfer["confidence"] + hand_boost)
            if confidence >= self.confidence_threshold:
                merged_box = self._merge_boxes(
                    transfer["victim_box"], transfer["snatcher_box"]
                )
                snatch_events.append({
                    "bbox": merged_box,
                    "confidence": round(confidence, 3),
                    "label": "mobile_snatching",
                    "phone_bbox": transfer["phone_box"],
                    "victim_box": transfer["victim_box"],
                    "snatcher_box": transfer["snatcher_box"],
                    "phone_velocity": round(transfer["velocity"], 1),
                })

        # --- 6. Temporal confirmation ---
        temporal_window = self.config.get("temporal_window", 3)
        if snatch_events:
            self._snatch_frame_count += 1
        else:
            self._snatch_frame_count = max(0, self._snatch_frame_count - 1)

        triggered = self._snatch_frame_count >= temporal_window

        self._prev_gray = gray

        return {
            "triggered": triggered,
            "detections": snatch_events,
            "metadata": {
                "persons_detected": len(person_boxes),
                "phones_detected": len(phone_boxes),
                "active_phone_tracks": len(self._phone_tracks),
                "transfer_events": len(transfer_events),
                "hand_motion_events": len(hand_motion_events),
                "consecutive_snatch_frames": self._snatch_frame_count,
                "frame_index": self._frame_index,
            },
            "event_type": self.name,
        }

    # ------------------------------------------------------------------
    # Internal: Detection
    # ------------------------------------------------------------------
    def _empty_result(self) -> Dict[str, Any]:
        return {
            "triggered": False,
            "detections": [],
            "metadata": {},
            "event_type": self.name,
        }

    def _detect_persons(self, frame: np.ndarray) -> List[List[int]]:
        boxes: List[List[int]] = []
        if self._use_yolo and self.model is not None:
            results = self.model(frame, verbose=False)
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        label = self.model.names[cls_id]
                        conf = float(box.conf[0])
                        if label == "person" and conf >= self.confidence_threshold:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            boxes.append([x1, y1, x2, y2])
        return boxes

    def _detect_phones(
        self, frame: np.ndarray, gray: np.ndarray
    ) -> List[List[int]]:
        """
        Detect cell phones using YOLO's 'cell phone' class or fallback
        contour-based detection for small rectangular objects.
        """
        phones: List[List[int]] = []

        if self._use_yolo and self.model is not None:
            results = self.model(frame, verbose=False)
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        cls_id = int(box.cls[0])
                        label = self.model.names[cls_id]
                        conf = float(box.conf[0])
                        if label == "cell phone" and conf >= 0.3:
                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            phones.append([x1, y1, x2, y2])
            return phones

        # Fallback: detect small, bright, rectangular contours
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 80, 200)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 500 < area < 8000:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect = ch / max(cw, 1)
                # Phone-like aspect ratio: taller than wide, small
                if 1.3 < aspect < 2.8:
                    phones.append([x, y, x + cw, y + ch])
        return phones

    # ------------------------------------------------------------------
    # Internal: Association & Tracking
    # ------------------------------------------------------------------
    @staticmethod
    def _centroid(box: List[int]) -> np.ndarray:
        return np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])

    def _associate_phones_to_persons(
        self,
        phone_boxes: List[List[int]],
        person_boxes: List[List[int]],
    ) -> List[Optional[int]]:
        """
        For each phone, find the nearest person. Returns a list of person
        indices (or None if no person is close enough).
        """
        transfer_dist = self.config.get("transfer_distance_threshold", 50)
        associations: List[Optional[int]] = []

        for pbox in phone_boxes:
            pc = self._centroid(pbox)
            best_idx: Optional[int] = None
            best_dist = float("inf")
            for pi, person_box in enumerate(person_boxes):
                # Check if phone centroid is inside person box (expanded slightly)
                px1, py1, px2, py2 = person_box
                margin = transfer_dist
                if (px1 - margin <= pc[0] <= px2 + margin and
                        py1 - margin <= pc[1] <= py2 + margin):
                    person_c = self._centroid(person_box)
                    dist = float(np.linalg.norm(pc - person_c))
                    if dist < best_dist:
                        best_dist = dist
                        best_idx = pi
            associations.append(best_idx)
        return associations

    def _detect_transfers(
        self,
        phone_boxes: List[List[int]],
        associations: List[Optional[int]],
        person_boxes: List[List[int]],
    ) -> List[Dict[str, Any]]:
        """
        Track phone positions and detect transfer from one person to another.
        """
        vel_thresh = self.config.get("phone_velocity_threshold", 40.0)
        snatch_window = self.config.get("snatch_window_frames", 10)
        transfer_events: List[Dict[str, Any]] = []

        for pi, (pbox, owner_idx) in enumerate(zip(phone_boxes, associations)):
            phone_c = self._centroid(pbox)
            track_id = self._match_phone_track(phone_c)

            observation = {
                "frame": self._frame_index,
                "centroid": phone_c,
                "bbox": pbox,
                "owner_idx": owner_idx,
            }
            self._phone_tracks[track_id].append(observation)
            track = self._phone_tracks[track_id]

            if len(track) < 2:
                continue

            # Compute velocity (displacement from previous frame)
            prev = track[-2]
            displacement = float(np.linalg.norm(phone_c - prev["centroid"]))
            velocity = displacement  # per frame

            # Check for owner change within the snatch window
            prev_owner = prev["owner_idx"]
            if (
                prev_owner is not None
                and owner_idx is not None
                and prev_owner != owner_idx
                and velocity >= vel_thresh
            ):
                # Look back to confirm rapid transition
                frames_since_owner_change = self._frame_index - prev["frame"]
                if frames_since_owner_change <= snatch_window:
                    confidence = min(1.0, velocity / (vel_thresh * 2))
                    transfer_events.append({
                        "phone_box": pbox,
                        "victim_box": person_boxes[prev_owner],
                        "snatcher_box": person_boxes[owner_idx],
                        "velocity": velocity,
                        "confidence": confidence,
                    })

        return transfer_events

    def _match_phone_track(self, centroid: np.ndarray) -> int:
        """Match a phone centroid to an existing track or create a new one."""
        match_thresh = 60.0
        best_id: Optional[int] = None
        best_dist = float("inf")

        for tid, track in self._phone_tracks.items():
            if not track:
                continue
            last_c = track[-1]["centroid"]
            dist = float(np.linalg.norm(centroid - last_c))
            if dist < best_dist and dist < match_thresh:
                best_dist = dist
                best_id = tid

        if best_id is not None:
            return best_id

        self._phone_id_counter += 1
        return self._phone_id_counter

    # ------------------------------------------------------------------
    # Internal: Hand Motion Analysis
    # ------------------------------------------------------------------
    def _analyse_hand_motion(
        self,
        gray: np.ndarray,
        person_boxes: List[List[int]],
        h: int,
        w: int,
    ) -> List[Dict[str, Any]]:
        """
        Compute optical flow in the hand/arm region of each person
        (lower-third on left and right sides of the bounding box).
        """
        hand_thresh = self.config.get("hand_motion_threshold", 12.0)
        events: List[Dict[str, Any]] = []

        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            return events

        flow = cv2.calcOpticalFlowFarneback(
            self._prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        for i, box in enumerate(person_boxes):
            x1, y1, x2, y2 = box
            bw = x2 - x1
            bh = y2 - y1

            # Hand region: lower 40% of person box, left and right thirds
            hand_y1 = max(0, y1 + int(bh * 0.5))
            hand_y2 = min(h, y2)

            # Left hand region
            lx1, lx2 = max(0, x1), min(w, x1 + int(bw * 0.35))
            # Right hand region
            rx1, rx2 = max(0, x2 - int(bw * 0.35)), min(w, x2)

            regions = [
                mag[hand_y1:hand_y2, lx1:lx2],
                mag[hand_y1:hand_y2, rx1:rx2],
            ]

            max_hand_motion = 0.0
            for roi in regions:
                if roi.size > 0:
                    max_hand_motion = max(max_hand_motion, float(np.mean(roi)))

            if max_hand_motion >= hand_thresh:
                events.append({
                    "person_idx": i,
                    "person_box": box,
                    "hand_motion_energy": round(max_hand_motion, 2),
                })

        return events

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _boxes_overlap(box_a: List[int], box_b: List[int]) -> bool:
        """Check if two boxes overlap at all."""
        return not (
            box_a[2] < box_b[0]
            or box_a[0] > box_b[2]
            or box_a[3] < box_b[1]
            or box_a[1] > box_b[3]
        )

    @staticmethod
    def _merge_boxes(box_a: List[int], box_b: List[int]) -> List[int]:
        return [
            min(box_a[0], box_b[0]),
            min(box_a[1], box_b[1]),
            max(box_a[2], box_b[2]),
            max(box_a[3], box_b[3]),
        ]

    def reset_tracks(self) -> None:
        """Clear all phone tracking state."""
        self._phone_tracks.clear()
        self._snatch_frame_count = 0
        self._frame_index = 0
        self._phone_id_counter = 0
        logger.info("MobileSnatchingDetector tracks have been reset.")
