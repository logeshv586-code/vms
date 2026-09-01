import logging
import os
from typing import Dict, Any, List, Optional
import numpy as np
import cv2
from .base_detector import BaseDetector

# Try importing torch and torchvision for custom classifier
try:
    import torch
    import torch.nn as nn
    import torchvision.transforms as transforms
    from torchvision import models as tv_models
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False


logger = logging.getLogger(__name__)


class GraffitiAndVandalismDetector(BaseDetector):
    """
    Detects graffiti and vandalism events including spray-painting walls,
    writing/scratching surfaces, and pasting poster wallpapers.

    Detection Strategy:
        1. Person Tracking & Proximity: Monitors the position and duration of
           person instances to identify individuals stationary near walls or boundaries.
        2. Localized Motion Analysis: Computes dense optical flow (Farneback)
           in the upper/mid portion of the person's bounding box (hand/arm region).
           High flow energy combined with a stationary body centroid suggests painting/spraying.
        3. Object association: Checks for relevant objects in proximity to the person
           (e.g., generic objects representing paint canisters or markers, like COCO 'bottle').
        4. Stateful Alerts:
           - Stage 1: Suspicious Proximity (< 5s). Triggered = False.
           - Stage 2: Possible Spraying / Writing (5s to 15s). Triggered = False (warning level).
           - Stage 3: Confirmed Graffiti / Vandalism (>= 15s). Triggered = True.

    Kaggle Dataset Sourcing Suggestion:
        Vandalism Detection Dataset
        https://www.kaggle.com/datasets/mostafamohamed67/vandalism-detection-dataset
    """

    # Vandalism event sub-types
    VANDALISM_PROXIMITY = "suspicious_proximity"
    VANDALISM_POSSIBLE = "possible_graffiti"
    VANDALISM_CONFIRMED = "confirmed_graffiti"

    def __init__(self, config: Dict[str, Any] = None):
        self._prev_gray: Optional[np.ndarray] = None
        self._track_first_seen: Dict[int, float] = {}
        self._track_centroids_history: Dict[int, np.ndarray] = {}
        
        # Stateful timing tracker for active vandalism events
        self._vandalism_start_time: float = 0.0
        self._last_vandalism_time: float = 0.0
        
        # Classifier placeholders
        self.classifier_model = None
        self.classifier_transform = None
        self._use_classifier = False
        
        super().__init__("graffiti_and_vandalism", config)

    # ------------------------------------------------------------------ #
    #  Model / configuration loading
    # ------------------------------------------------------------------ #
    def load_model(self) -> None:
        """
        Loads configurations and optional YOLO model for detection.
        """
        self._loiter_threshold = self.config.get("loitering_time_threshold", 15.0)  # seconds
        self._velocity_threshold = self.config.get("velocity_threshold", 8.0)  # pixels/frame
        self._flow_energy_threshold = self.config.get("flow_energy_threshold", 5.0)  # flow magnitude
        self._canister_proximity = self.config.get("canister_proximity", 120.0)  # pixels
        self._stage_2_window = self.config.get("stage_2_window", 5.0)  # seconds
        self._stage_3_window = self.config.get("stage_3_window", 15.0)  # seconds

        # Canister/Tool class taxonomy (representing spray can/brush/bottle)
        self._canister_classes = set(self.config.get("canister_classes", [
            "bottle", "cup", "can", "spray", "marker"
        ]))

        # --- Custom ResNet Classifier Model ---
        self._use_classifier = False
        self.classifier_model = None

        if _TORCH_AVAILABLE and self.config.get("use_classifier", True):
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            classifier_path = self.config.get(
                "classifier_model_path",
                os.path.join(backend_dir, "models", "detections", "graffiti_and_vandalism", "graffiti_vandalism_model.pt")
            )

            if os.path.exists(classifier_path):
                try:
                    logger.info(f"Loading ResNet18 classifier from {classifier_path}...")
                    model = tv_models.resnet18(weights=None)
                    num_ftrs = model.fc.in_features
                    model.fc = nn.Linear(num_ftrs, 3)

                    # Load weights
                    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
                    state_dict = torch.load(classifier_path, map_location=device)
                    model.load_state_dict(state_dict)
                    model = model.to(device)
                    model.eval()

                    self.classifier_model = model
                    self.classifier_device = device
                    self._use_classifier = True

                    # Preprocessing transforms (matches validation transforms in train_graffiti_vandalism.py)
                    self.classifier_transform = transforms.Compose([
                        transforms.ToPILImage(),
                        transforms.Resize((224, 224)),
                        transforms.ToTensor(),
                        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
                    ])
                    logger.info("ResNet18 classifier model loaded successfully for GraffitiAndVandalismDetector.")
                except Exception as e:
                    logger.warning(f"Could not load custom ResNet classifier: {e}")
            else:
                logger.info(f"Custom classifier model not found at {classifier_path}. Detector will use rule-based heuristics only.")

        try:
            from ultralytics import YOLO
            model_path = self.config.get("model_path", "yolov8n.pt")
            self.model = YOLO(model_path)
            self._use_yolo = True
            logger.info("YOLOv8 model loaded for GraffitiAndVandalismDetector.")
        except Exception as e:
            logger.warning("Could not load YOLO model for GraffitiAndVandalismDetector: %s.", e)
            self.model = None
            self._use_yolo = False

        logger.info(
            "GraffitiAndVandalismDetector configured — loiter_threshold=%.1fs, "
            "velocity_threshold=%.1f, flow_threshold=%.1f, stage2=%.1fs, stage3=%.1fs, use_classifier=%s",
            self._loiter_threshold,
            self._velocity_threshold,
            self._flow_energy_threshold,
            self._stage_2_window,
            self._stage_3_window,
            self._use_classifier
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
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

    def _compute_box_upper_motion(self, box: List[int], flow_mag: Optional[np.ndarray], h: int, w: int) -> float:
        """Compute optical flow motion energy in the upper half of the box (arm/hand region)."""
        if flow_mag is None:
            return 0.0
        x1, y1, x2, y2 = box
        height = y2 - y1
        y2_upper = int(y1 + 0.55 * height)  # upper-to-mid body
        x1c, y1c = max(0, x1), max(0, y1)
        x2c, y2c = min(w, x2), min(h, y2_upper)
        if x2c <= x1c or y2c <= y1c:
            return 0.0
        return float(np.mean(flow_mag[y1c:y2c, x1c:x2c]))

    def _centroid_distance(self, c1, c2):
        return np.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2)

    # ------------------------------------------------------------------ #
    #  Main detection pipeline
    # ------------------------------------------------------------------ #
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse a single frame for graffiti/vandalism/spraying with stateful checks.

        Args:
            frame: BGR video frame (H x W x 3).
            **kwargs:
                external_detections (List[Dict]): Upstream object detections.
                timestamp (float): Current frame timestamp in seconds.

        Returns:
            Standardised detection dict.
        """
        if not self.is_enabled:
            return {
                "triggered": False,
                "detections": [],
                "metadata": {},
                "event_type": self.name
            }

        import time
        timestamp = kwargs.get("timestamp", time.time())
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = frame.shape[:2]
        
        # 1. Parse Detections
        persons = []
        canisters = []
        external = kwargs.get("external_detections", [])
        
        if external:
            for det in external:
                label = det.get("label", det.get("class", ""))
                bbox = det.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                conf = float(det.get("confidence", 1.0))
                # Resolve tracking ID if missing
                tid = det.get("id")
                
                if label == "person":
                    persons.append({"bbox": bbox, "id": tid, "confidence": conf})
                elif label in self._canister_classes:
                    canisters.append({"bbox": bbox, "label": label, "confidence": conf})
        else:
            # Fallback to YOLO inference if no external detections are passed
            if self._use_yolo and self.model is not None:
                results = self.model.track(frame, persist=True, verbose=False)
                for r in results:
                    if r.boxes is not None:
                        for box in r.boxes:
                            cls_id = int(box.cls[0])
                            label = self.model.names[cls_id]
                            conf = float(box.conf[0])
                            if conf < self.confidence_threshold:
                                continue
                            bbox = box.xyxy[0].tolist()
                            tid = int(box.id[0]) if (box.id is not None) else None
                            if label == "person":
                                persons.append({"bbox": bbox, "id": tid, "confidence": conf})
                            elif label in self._canister_classes:
                                canisters.append({"bbox": bbox, "label": label, "confidence": conf})

        # Calculate dense optical flow
        flow_mag = self._compute_optical_flow(gray)

        active_vandalism_detected = False
        vandalism_details = []
        person_near_wall = False
        
        for person in persons:
            bbox = person["bbox"]
            tid = person.get("id", 1)  # Fallback to 1 if no tracking ID available
            
            # Compute person centroid
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            curr_centroid = np.array([cx, cy])
            
            # 1. Track Loitering Duration
            if tid not in self._track_first_seen:
                self._track_first_seen[tid] = timestamp
            loiter_time = timestamp - self._track_first_seen[tid]
            
            # 2. Track Velocity (Stationary verification)
            if tid in self._track_centroids_history:
                velocity = float(np.linalg.norm(curr_centroid - self._track_centroids_history[tid]))
            else:
                velocity = 0.0
            self._track_centroids_history[tid] = curr_centroid

            # 3. Arm/Hand Motion Analysis (Optical Flow)
            upper_motion = self._compute_box_upper_motion(bbox, flow_mag, h, w)
            
            # 4. Canister association
            has_canister_nearby = False
            associated_canister = None
            for can in canisters:
                cb = can["bbox"]
                ccx = (cb[0] + cb[2]) / 2.0
                ccy = (cb[1] + cb[3]) / 2.0
                dist = self._centroid_distance((cx, cy), (ccx, ccy))
                if dist <= self._canister_proximity:
                    has_canister_nearby = True
                    associated_canister = can
                    break

            # Run Custom ResNet Classifier on the person crop if enabled
            classifier_vandalism_detected = False
            classifier_label = "normal"
            classifier_conf = 0.0
            
            if self._use_classifier and self.classifier_model is not None:
                try:
                    # Bounding box coordinates
                    x1, y1, x2, y2 = map(int, bbox)
                    # Clamp to frame boundary
                    x1_c = max(0, x1)
                    y1_c = max(0, y1)
                    x2_c = min(w, x2)
                    y2_c = min(h, y2)
                    
                    if x2_c > x1_c and y2_c > y1_c:
                        person_crop = frame[y1_c:y2_c, x1_c:x2_c]
                        if person_crop.size > 0:
                            # Convert BGR to RGB
                            crop_rgb = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
                            # Preprocess
                            tensor_img = self.classifier_transform(crop_rgb).unsqueeze(0).to(self.classifier_device)
                            # Run inference
                            with torch.no_grad():
                                outputs = self.classifier_model(tensor_img)
                                probabilities = torch.softmax(outputs, dim=1)
                                conf, pred_idx = torch.max(probabilities, 1)
                                conf = float(conf.item())
                                pred_idx = int(pred_idx.item())
                                
                                # Class map: 0: graffiti, 1: normal, 2: vandalism (alphabetical)
                                class_names = ["graffiti", "normal", "vandalism"]
                                classifier_label = class_names[pred_idx]
                                classifier_conf = conf
                                
                                # If predicted class is graffiti or vandalism and confidence exceeds threshold
                                if classifier_label in ["graffiti", "vandalism"] and conf >= self.confidence_threshold:
                                    classifier_vandalism_detected = True
                                    logger.info(f"Classifier flagged person ID {tid} as '{classifier_label}' (conf: {conf:.2f})")
                except Exception as e:
                    logger.warning(f"Error running classifier on person crop: {e}")

            # Criteria for vandalism indicators:
            # - Stationary (velocity < threshold) or loitering near structure (> loiter_threshold)
            # - Active arm/hand motion (flow > energy threshold)
            # - (Optional but strong) holding a canister/marker nearby
            is_stationary = velocity < self._velocity_threshold
            has_active_motion = upper_motion > self._flow_energy_threshold
            
            is_suspicious_heuristic = is_stationary and (has_active_motion or (loiter_time > self._loiter_threshold and has_canister_nearby))
            is_suspicious_classifier = classifier_vandalism_detected
            
            if is_suspicious_heuristic or is_suspicious_classifier:
                active_vandalism_detected = True
                person_near_wall = True
                vandalism_details.append({
                    "track_id": tid,
                    "duration": round(loiter_time, 2),
                    "upper_motion": round(upper_motion, 2),
                    "has_canister": has_canister_nearby,
                    "canister_label": associated_canister["label"] if associated_canister else None,
                    "bbox": bbox,
                    "classifier_flagged": is_suspicious_classifier,
                    "classifier_label": classifier_label,
                    "classifier_confidence": round(classifier_conf, 2)
                })

        # Stateful Timeline-based Alert Evaluator
        triggered = False
        alert_events = []
        
        if active_vandalism_detected:
            if self._vandalism_start_time == 0.0:
                self._vandalism_start_time = timestamp
            
            elapsed = timestamp - self._vandalism_start_time
            self._last_vandalism_time = timestamp
            
            if elapsed >= self._stage_3_window:
                # Confirmed alert level
                triggered = True
                alert_events.append({
                    "type": self.VANDALISM_CONFIRMED,
                    "confidence": 0.95,
                    "detail": f"Vandalism Alert: Person actively spraying or writing on wall for {elapsed:.1f}s (confirmed)."
                })
            elif elapsed >= self._stage_2_window:
                # Warning level
                alert_events.append({
                    "type": self.VANDALISM_POSSIBLE,
                    "confidence": round(0.5 + 0.3 * (elapsed / self._stage_3_window), 2),
                    "detail": f"Vandalism Warning: Suspicious painting/writing motion near wall for {elapsed:.1f}s."
                })
            else:
                # Proximity / preliminary loitering level
                alert_events.append({
                    "type": self.VANDALISM_PROXIMITY,
                    "confidence": 0.30,
                    "detail": f"Monitoring: Person loitering close to wall with potential tool, elapsed {elapsed:.1f}s."
                })
        else:
            # Decaying/cooling down stateful timer if no vandalism seen for 3.0 seconds
            if self._vandalism_start_time > 0.0 and (timestamp - self._last_vandalism_time > 3.0):
                self._vandalism_start_time = 0.0

        detections = []
        for evt in alert_events:
            # Only trigger bounding box overlay if warning (Stage 2) or confirmed (Stage 3) is active
            if evt["type"] in (self.VANDALISM_POSSIBLE, self.VANDALISM_CONFIRMED):
                for detail in vandalism_details:
                    detections.append({
                        "label": evt["type"],
                        "confidence": evt["confidence"],
                        "bbox": detail["bbox"]
                    })

        # Save current frame as previous for next call
        self._prev_gray = gray

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "active_vandalism": active_vandalism_detected,
                "person_near_wall": person_near_wall,
                "vandalism_duration": round(timestamp - self._vandalism_start_time, 2) if self._vandalism_start_time > 0.0 else 0.0,
                "vandalism_details": vandalism_details,
                "alert_events": alert_events
            },
            "event_type": self.name
        }
