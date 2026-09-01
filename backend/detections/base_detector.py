import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np

logger = logging.getLogger(__name__)

class BaseDetector(ABC):
    """
    Standard Base class for all 23+ intelligent video analytic detectors.
    Ensures consistent lifecycle, inference pipeline, and event output structure.
    """
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.is_enabled = self.config.get("enabled", True)
        self.confidence_threshold = self.config.get("confidence_threshold", 0.5)
        self.model = None
        
        logger.info(f"Initializing video analytic detector: {self.name}")
        self.load_model()
        
    @abstractmethod
    def load_model(self) -> None:
        """
        Loads the underlying machine learning model, weights, or configuration.
        To be implemented by specific detectors.
        """
        pass
        
    @abstractmethod
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Executes inference or OpenCV analytical rules on the input frame.
        
        Args:
            frame: Input video frame (numpy.ndarray)
            **kwargs: Extra parameters like stream_id, timestamp, bounding boxes, etc.
            
        Returns:
            Dict containing:
                "triggered": bool - Whether the event rule was triggered
                "detections": List[Dict] - Bounding boxes, labels, confidence scores
                "metadata": Dict - Specialized analytics metadata specific to this detector
                "event_type": str - Event classification label
        """
        return {
            "triggered": False,
            "detections": [],
            "metadata": {},
            "event_type": self.name
        }
        
    def get_name(self) -> str:
        """Returns the name of the detector"""
        return self.name
        
    def enable(self) -> None:
        """Enables the detector"""
        self.is_enabled = True
        logger.info(f"Detector {self.name} has been enabled.")
        
    def disable(self) -> None:
        """Disables the detector"""
        self.is_enabled = False
        logger.info(f"Detector {self.name} has been disabled.")
