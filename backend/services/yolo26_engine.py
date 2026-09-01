import cv2
import numpy as np
from ultralytics import YOLO
import logging
import os
import json
from datetime import datetime

# Paths
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
CAMERA_ZONES_PATH = os.path.join(DATA_DIR, "camera_zones.json")

logger = logging.getLogger(__name__)

class YOLO26Engine:
    """Detection and Tracking Engine using YOLO26 and ByteTrack"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(YOLO26Engine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        try:
            # Initialize YOLO26 Nano model
            self.model = YOLO("yolo26n.pt")
            self.model.to('cpu')
            self.zones_config = {}
            self._load_zones()
            # Frame skipping logic
            self.frame_count = 0
            self.skip_n_frames = 1 
            self.last_annotated = None
            self.last_metadata = {"detections": [], "counts": {}}
            self.prev_gray = None
            logger.info("YOLO26 Nano optimized for CPU with Persistence")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to load YOLO26 model: {e}")
            raise

    def _load_zones(self):
        """Load zone polygons from the configuration file"""
        try:
            if os.path.exists(CAMERA_ZONES_PATH):
                with open(CAMERA_ZONES_PATH, "r") as f:
                    self.zones_config = json.load(f)
        except Exception as e:
            logger.error(f"Error loading zones in YOLO engine: {e}")

    def reload_config(self):
        """Reload configuration from disk"""
        self._load_zones()
        logger.info("YOLO26Engine configuration reloaded")

    def process_frame(self, frame: np.ndarray, persist: bool = True, stream_id: str = None):
        """
        Process a single frame for detection and tracking with Zone awareness
        """
        if frame is None:
            return None, []
            
        h, w = frame.shape[:2]
        self._load_zones() # Hot-reload zones

        try:
            # Frame Skipping logic for CPU
            self.frame_count += 1
            if persist and self.frame_count % (self.skip_n_frames + 1) != 0:
                # Return PREVIOUS annotated frame for visual consistency (No flicker)
                # But we draw current zones for metadata accuracy
                display_frame = self.last_annotated if self.last_annotated is not None else frame.copy()
                return display_frame, {**self.last_metadata, "skipped": True}

            # Run inference
            results = self.model.track(
                frame, 
                persist=persist, 
                tracker="bytetrack.yaml", 
                verbose=False,
                conf=0.25 # Balanced confidence for CPU
            )
            
            result = results[0]
            # Use custom marking instead of generic result.plot()
            annotated_frame = frame.copy()
            
            # --- Draw Zones ---
            if stream_id and stream_id in self.zones_config:
                camera_zones = self.zones_config[stream_id].get("zones", [])
                for zone in camera_zones:
                    color = (0, 255, 255) # Yellow/Cyan for zones
                    thickness = 2
                    
                    if zone.get("type") == "circle":
                        center = zone.get("center", [0.5, 0.5])
                        radius = zone.get("radius", 0.1)
                        # Convert normalized to pixel coordinates
                        cx, cy = int(center[0] * w), int(center[1] * h)
                        # Radius is trickier with aspect ratio, using width-based scale
                        r_pix = int(radius * w) 
                        cv2.circle(annotated_frame, (cx, cy), r_pix, color, thickness)
                        cv2.putText(annotated_frame, zone["name"], (cx - r_pix, cy - r_pix - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                    else:
                        # Default to polygon
                        poly = zone.get("polygon", [])
                        if poly:
                            pts = np.array([[int(p[0] * w), int(p[1] * h)] for p in poly], np.int32)
                            pts = pts.reshape((-1, 1, 2))
                            cv2.polylines(annotated_frame, [pts], isClosed=True, color=color, thickness=thickness)
                            cv2.putText(annotated_frame, zone["name"], (pts[0][0][0], pts[0][0][1] - 10),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # Extract metadata and draw Intelligent Marking
            detections = []
            counts = {}
            if result.boxes:
                for box in result.boxes:
                    track_id = int(box.id[0]) if box.id is not None else None
                    cls_id = int(box.cls[0])
                    label = self.model.names[cls_id]
                    confidence = float(box.conf[0])
                    xyxy = box.xyxy[0].tolist()
                    cx = (xyxy[0] + xyxy[2]) / 2
                    cy = (xyxy[1] + xyxy[3]) / 2
                    
                    # --- Intelligent Visual Marking ---
                    color = (0, 255, 0) # Default Green
                    if label == "person": color = (0, 212, 255) # Sleek Cyan for Security
                    
                    # Draw sleeker bounding box
                    x1, y1, x2, y2 = map(int, xyxy)
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                    
                    # Add premium label
                    label_text = f"{label} {track_id}" if track_id else label
                    cv2.putText(annotated_frame, label_text, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
                    # -----------------------------------

                    detections.append({
                        "id": track_id, "class": label, "class_id": cls_id,
                        "confidence": confidence, "bbox": xyxy, 
                        "norm_bbox": [xyxy[0]/w, xyxy[1]/h, xyxy[2]/w, xyxy[3]/h],
                        "centroid": [cx, cy],
                        "norm_centroid": [cx / w, cy / h],
                        "timestamp": datetime.now().isoformat()
                    })

                    counts[label] = counts.get(label, 0) + 1
            
            # --- Tamper Metrics ---
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # 1. Blur Detection (Laplacian Variance)
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # 2. Luminance & Exposure (Mean/Std)
            mean_brightness = np.mean(gray)
            std_brightness = np.std(gray)
            
            # 3. Motion Score (Temporal difference)
            motion_score = 0
            if self.prev_gray is not None and self.prev_gray.shape == gray.shape:
                diff = cv2.absdiff(gray, self.prev_gray)
                motion_score = np.mean(diff)
            self.prev_gray = gray

            # Save state for skipped frames
            self.last_annotated = annotated_frame
            self.last_metadata = {
                "detections": detections, 
                "counts": counts, 
                "motion_score": float(motion_score),
                "blur_score": float(blur_score),
                "luminance": float(mean_brightness),
                "stdev": float(std_brightness)
            }

            return annotated_frame, self.last_metadata
            
        except Exception as e:
            logger.error(f"Error processing frame in YOLO26Engine: {e}")
            return frame, {"detections": [], "counts": {}, "motion_score": 0, "blur_score": 0}

    def get_annotated_frame_only(self, frame: np.ndarray):
        """Optimized path for just visual output"""
        annotated_frame, _ = self.process_frame(frame)
        return annotated_frame

# Singleton instance
yolo26_engine = YOLO26Engine()
