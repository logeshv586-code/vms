import os
import cv2
import torch
import numpy as np
from datetime import datetime
from ultralytics import YOLO
from pathlib import Path
import logging
from typing import List, Dict, Optional, Tuple
import json
import warnings

# Configure torch to allow loading YOLO models
try:
    from ultralytics.nn.tasks import DetectionModel
    import torch.nn.modules.container
    import torch.nn.modules.conv
    import torch.nn.modules.batchnorm
    import torch.nn.modules.activation
    import torch.nn.modules.pooling
    import torch.nn.modules.linear
    import torch.nn.modules.dropout
    import torch.nn.modules.upsampling

    # Add all necessary torch modules for YOLO model loading
    safe_globals = [
        DetectionModel,
        torch.nn.modules.container.Sequential,
        torch.nn.modules.container.ModuleList,
        torch.nn.modules.conv.Conv2d,
        torch.nn.modules.batchnorm.BatchNorm2d,
        torch.nn.modules.activation.SiLU,
        torch.nn.modules.pooling.MaxPool2d,
        torch.nn.modules.linear.Linear,
        torch.nn.modules.dropout.Dropout,
        torch.nn.modules.upsampling.Upsample,
    ]
    torch.serialization.add_safe_globals(safe_globals)
except ImportError:
    # Fallback for older versions
    pass

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppearanceSearchEngine:
    """Engine for searching persons and objects in recorded videos using YOLO"""
    
    def __init__(self, model_path: str = "../yolov8n.pt", recordings_base_path: str = "../recordings"):
        """
        Initialize the appearance search engine
        
        Args:
            model_path: Path to the YOLO model file
            recordings_base_path: Base path where recordings are stored
        """
        self.model_path = Path(model_path)
        self.recordings_base_path = Path(recordings_base_path)
        self.yolo_model = None
        self.appearance_data_path = Path("../appearance_data")
        
        # Ensure appearance data directory exists
        self.appearance_data_path.mkdir(exist_ok=True)
        
        # Load YOLO model
        self._load_yolo_model()
        
        # YOLO class names for objects we can search
        self.searchable_objects = [
            'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck',
            'boat', 'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench',
            'bird', 'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra',
            'giraffe', 'backpack', 'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee',
            'skis', 'snowboard', 'sports ball', 'kite', 'baseball bat', 'baseball glove',
            'skateboard', 'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
            'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple', 'sandwich', 'orange',
            'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair', 'couch',
            'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
            'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink',
            'refrigerator', 'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier',
            'toothbrush'
        ]
    
    def _load_yolo_model(self):
        """Load the YOLO model"""
        try:
            if not self.model_path.exists():
                logger.error(f"YOLO model not found at {self.model_path}")
                raise FileNotFoundError(f"YOLO model not found at {self.model_path}")

            # Suppress warnings and configure torch for YOLO model loading
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                # Load YOLO model with proper configuration
                try:
                    from ultralytics.nn.tasks import DetectionModel
                    import torch.nn.modules.container
                    import torch.nn.modules.conv
                    import torch.nn.modules.batchnorm
                    import torch.nn.modules.activation
                    import torch.nn.modules.pooling
                    import torch.nn.modules.linear
                    import torch.nn.modules.dropout
                    import torch.nn.modules.upsampling

                    # Add all necessary torch modules for YOLO model loading
                    safe_globals = [
                        DetectionModel,
                        torch.nn.modules.container.Sequential,
                        torch.nn.modules.container.ModuleList,
                        torch.nn.modules.conv.Conv2d,
                        torch.nn.modules.batchnorm.BatchNorm2d,
                        torch.nn.modules.activation.SiLU,
                        torch.nn.modules.pooling.MaxPool2d,
                        torch.nn.modules.linear.Linear,
                        torch.nn.modules.dropout.Dropout,
                        torch.nn.modules.upsampling.Upsample,
                    ]
                    torch.serialization.add_safe_globals(safe_globals)
                except ImportError:
                    pass
                self.yolo_model = YOLO(str(self.model_path))

            logger.info(f"YOLO model loaded successfully from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def get_searchable_objects(self) -> List[str]:
        """Get list of objects that can be searched"""
        return self.searchable_objects
    
    def save_search_image(self, image_data: bytes, filename: str) -> str:
        """
        Save uploaded search image to appearance_data folder
        
        Args:
            image_data: Binary image data
            filename: Original filename
            
        Returns:
            Path to saved image
        """
        try:
            # Create unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_ext = Path(filename).suffix
            unique_filename = f"search_{timestamp}{file_ext}"
            
            save_path = self.appearance_data_path / unique_filename
            
            with open(save_path, 'wb') as f:
                f.write(image_data)
            
            logger.info(f"Search image saved to {save_path}")
            return str(save_path)
        except Exception as e:
            logger.error(f"Failed to save search image: {e}")
            raise
    
    def search_object_in_videos(self, object_name: str, video_dir: Optional[str] = None) -> List[Dict]:
        """
        Search for a specific object in recorded videos

        Args:
            object_name: Name of object to search for
            video_dir: Specific video directory to search in (optional)

        Returns:
            List of detection results with first detection per video and thumbnails
        """
        results = []

        if object_name.lower() not in [obj.lower() for obj in self.searchable_objects]:
            logger.warning(f"Object '{object_name}' not in searchable objects list")
            return results

        search_dirs = []
        if video_dir:
            search_dirs = [self.recordings_base_path / video_dir]
        else:
            # Search all recording directories
            search_dirs = [d for d in self.recordings_base_path.iterdir() if d.is_dir()]

        for stream_dir in search_dirs:
            if not stream_dir.exists():
                continue

            logger.info(f"Searching for '{object_name}' in {stream_dir.name}")

            # Get all video files in the directory
            video_files = list(stream_dir.glob("*.mp4")) + list(stream_dir.glob("*.avi")) + list(stream_dir.glob("*.mkv"))

            for video_file in video_files:
                # Get only first detection per video with thumbnail
                first_detection = self._get_first_detection_with_thumbnail(video_file, object_name, "object")
                if first_detection:
                    results.append(first_detection)

        return results
    
    def search_person_in_videos(self, target_image_path: str, video_dir: Optional[str] = None) -> List[Dict]:
        """
        Search for a person using reference image in recorded videos

        Args:
            target_image_path: Path to reference image of person
            video_dir: Specific video directory to search in (optional)

        Returns:
            List of detection results with first detection per video and thumbnails
        """
        results = []

        # For now, we'll use YOLO person detection only
        # Face recognition with DLIB can be added later if needed
        search_dirs = []
        if video_dir:
            search_dirs = [self.recordings_base_path / video_dir]
        else:
            # Search all recording directories
            search_dirs = [d for d in self.recordings_base_path.iterdir() if d.is_dir()]

        for stream_dir in search_dirs:
            if not stream_dir.exists():
                continue

            logger.info(f"Searching for person in {stream_dir.name}")

            # Get all video files in the directory
            video_files = list(stream_dir.glob("*.mp4")) + list(stream_dir.glob("*.avi")) + list(stream_dir.glob("*.mkv"))

            for video_file in video_files:
                # Get only first detection per video with thumbnail
                first_detection = self._get_first_detection_with_thumbnail(video_file, "person", "person")
                if first_detection:
                    results.append(first_detection)

        return results

    def _get_first_detection_with_thumbnail(self, video_path: Path, search_target: str, search_type: str) -> Optional[Dict]:
        """
        Get the first detection in a video and capture thumbnail

        Args:
            video_path: Path to video file
            search_target: Object name or "person"
            search_type: "object" or "person"

        Returns:
            First detection with thumbnail or None if no detection found
        """
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                logger.warning(f"Could not open video: {video_path}")
                return None

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            frame_num = 0
            sample_rate = 30  # Sample every 30th frame for faster processing

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Sample frames to reduce processing time
                if frame_num % sample_rate == 0:
                    timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                    timestamp_str = self._ms_to_timestamp(timestamp_ms)

                    # Run YOLO detection
                    results = self.yolo_model(frame, verbose=False)

                    for result in results:
                        if result.boxes is not None:
                            for box in result.boxes:
                                cls_id = int(box.cls[0])
                                label = self.yolo_model.names[cls_id]
                                confidence = float(box.conf[0])

                                # Check if this matches our search target
                                if label.lower() == search_target.lower() and confidence > 0.5:
                                    x1, y1, x2, y2 = map(int, box.xyxy[0])

                                    # Capture thumbnail of the detection
                                    thumbnail_path = self._save_detection_thumbnail(
                                        frame, x1, y1, x2, y2, video_path, timestamp_ms
                                    )

                                    detection = {
                                        "video_path": str(video_path),
                                        "video_name": video_path.name,
                                        "stream_id": video_path.parent.name,
                                        "timestamp": timestamp_str,
                                        "timestamp_ms": timestamp_ms,
                                        "frame_number": frame_num,
                                        "confidence": confidence,
                                        "bbox": [x1, y1, x2, y2],
                                        "search_type": search_type,
                                        "search_target": search_target,
                                        "thumbnail_path": thumbnail_path
                                    }

                                    cap.release()
                                    return detection

                frame_num += 1

            cap.release()
            return None

        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
            return None

    def _save_detection_thumbnail(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int,
                                video_path: Path, timestamp_ms: float) -> str:
        """
        Save a thumbnail image of the detection

        Args:
            frame: Video frame
            x1, y1, x2, y2: Bounding box coordinates
            video_path: Path to source video
            timestamp_ms: Timestamp in milliseconds

        Returns:
            Path to saved thumbnail
        """
        try:
            # Create thumbnails directory
            thumbnails_dir = self.appearance_data_path / "thumbnails"
            thumbnails_dir.mkdir(exist_ok=True)

            # Expand bounding box slightly for better context
            height, width = frame.shape[:2]
            padding = 20
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - padding)
            x2 = min(width, x2 + padding)
            y2 = min(height, y2 + padding)

            # Extract the detection region
            detection_crop = frame[y1:y2, x1:x2]

            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_name = video_path.stem
            thumbnail_filename = f"{video_name}_{timestamp}_{int(timestamp_ms)}.jpg"
            thumbnail_path = thumbnails_dir / thumbnail_filename

            # Save the thumbnail
            cv2.imwrite(str(thumbnail_path), detection_crop)

            logger.info(f"Saved detection thumbnail: {thumbnail_path}")
            return str(thumbnail_path)

        except Exception as e:
            logger.error(f"Error saving thumbnail: {e}")
            return ""

    def _search_in_single_video(self, video_path: Path, search_target: str, search_type: str) -> List[Dict]:
        """
        Search for target in a single video file
        
        Args:
            video_path: Path to video file
            search_target: Object name or "person"
            search_type: "object" or "person"
            
        Returns:
            List of detections in this video
        """
        detections = []
        
        try:
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                logger.warning(f"Could not open video: {video_path}")
                return detections
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0
            
            frame_num = 0
            sample_rate = 30  # Sample every 30th frame for faster processing
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Sample frames to reduce processing time
                if frame_num % sample_rate == 0:
                    timestamp_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                    timestamp_str = self._ms_to_timestamp(timestamp_ms)
                    
                    # Run YOLO detection
                    results = self.yolo_model(frame, verbose=False)
                    
                    for result in results:
                        if result.boxes is not None:
                            for box in result.boxes:
                                cls_id = int(box.cls[0])
                                label = self.yolo_model.names[cls_id]
                                confidence = float(box.conf[0])
                                
                                # Check if this matches our search target
                                if label.lower() == search_target.lower() and confidence > 0.5:
                                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                                    
                                    detection = {
                                        "video_path": str(video_path),
                                        "video_name": video_path.name,
                                        "stream_id": video_path.parent.name,
                                        "timestamp": timestamp_str,
                                        "timestamp_ms": timestamp_ms,
                                        "frame_number": frame_num,
                                        "confidence": confidence,
                                        "bbox": [x1, y1, x2, y2],
                                        "search_type": search_type,
                                        "search_target": search_target
                                    }
                                    detections.append(detection)
                
                frame_num += 1
            
            cap.release()
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
        
        return detections
    
    def _ms_to_timestamp(self, ms: float) -> str:
        """Convert milliseconds to HH:MM:SS format"""
        seconds = int(ms / 1000)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def get_available_streams(self) -> List[Dict]:
        """Get list of available recording streams"""
        streams = []
        
        for stream_dir in self.recordings_base_path.iterdir():
            if stream_dir.is_dir():
                video_files = list(stream_dir.glob("*.mp4")) + list(stream_dir.glob("*.avi")) + list(stream_dir.glob("*.mkv"))
                
                streams.append({
                    "stream_id": stream_dir.name,
                    "video_count": len(video_files),
                    "latest_video": max(video_files, key=lambda f: f.stat().st_mtime).name if video_files else None
                })
        
        return streams
