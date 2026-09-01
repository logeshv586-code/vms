import logging
import numpy as np
import time
from services.yolo26_engine import yolo26_engine
from services.gemma_onnx_engine import gemma_onnx_engine

logger = logging.getLogger(__name__)

class CascadedAIService:
    """
    Cascaded AI Pipeline:
    Tier 1: YOLO26 (Fast Detection + Tracking)
    Tier 2: Gemma/PaliGemma ONNX (Deep Semantic Analysis)
    """
    
    def __init__(self):
        self.yolo = yolo26_engine
        self.gemma = gemma_onnx_engine
        
    def process_frame(self, frame, stream_id=None, tasks=["caption"]):
        """
        Full cascaded pipeline execution
        """
        start_total = time.time()
        
        # --- Tier 1: Fast Detection ---
        annotated_frame, metadata = self.yolo.process_frame(frame, stream_id=stream_id)
        
        if metadata.get("skipped", False):
            return annotated_frame, metadata

        detections = metadata.get("detections", [])
        if not detections:
            return annotated_frame, metadata

        # --- Tier 2: Region Proposals & Semantic Analysis ---
        # We only process detections that have a high enough confidence or specific classes
        regions_to_analyze = []
        for det in detections:
            if det["class"] in ["person", "vehicle", "bag", "laptop"]:
                regions_to_analyze.append({
                    "box": det["bbox"],
                    "label": det["class"],
                    "id": det.get("id")
                })

        if regions_to_analyze and self.gemma.initialized:
            # Run deep analysis for each task requested
            for task in tasks:
                logger.info(f"Running Tier 2 task '{task}' on {len(regions_to_analyze)} regions")
                gemma_results = self.gemma.analyze_regions(frame, regions_to_analyze, task_type=task)
                
                # Merge Gemma results back into metadata
                for i, res in enumerate(gemma_results):
                    if i < len(detections):
                        # Matching by index since we passed regions_to_analyze in order
                        # A more robust match would use 'id'
                        target_id = res.get("region", {}).get("id")
                        for det in detections:
                            if det.get("id") == target_id:
                                det[f"gemma_{task}"] = res.get("analysis", "N/A")

        total_latency = (time.time() - start_total) * 1000
        metadata["total_latency_ms"] = total_latency
        metadata["tier2_active"] = self.gemma.initialized
        
        return annotated_frame, metadata

# Singleton instance
cascaded_ai_service = CascadedAIService()
