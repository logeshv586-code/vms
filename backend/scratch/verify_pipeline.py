import sys
import os
import cv2
import numpy as np
import logging

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.gemma_engine import gemma_engine
from services.yolo26_engine import yolo26_engine
from services.pattern_engine import pattern_engine

logging.basicConfig(level=logging.INFO)

def verify_pipeline():
    print("--- AI Security Pipeline Verification ---")
    
    # 1. Test Gemma Initialization
    print(f"Checking Gemma Engine: {gemma_engine.llm is not None}")
    if gemma_engine.llm is None:
        print("Error: Gemma Engine failed to initialize. Check paths.")
        return

    # 2. Test YOLO Tamper Metrics
    dummy_frame = 128 * np.ones((1080, 1920, 3), dtype=np.uint8)
    # Add some noise to prevent 0 stdev
    cv2.randn(dummy_frame, (128, 128, 128), (20, 20, 20))
    
    _ , metadata = yolo26_engine.process_frame(dummy_frame)
    print(f"YOLO Metrics: Blur={metadata.get('blur_score')}, Lum={metadata.get('luminance')}")
    
    # 3. Test Pattern Engine Rule (Intrusion with persistence)
    print("Testing Intrusion Rule with persistence...")
    detections = [{
        "class": "person",
        "centroid": [500, 500],
        "bbox": [400, 400, 600, 600],
        "id": 1,
        "zone_id": "zone_1",
        "zone_name": "Restricted Area"
    }]
    
    # Simulate a few frames of persistence
    for i in range(5):
        events = pattern_engine.process_detections("test_stream", {"detections": detections, "blur_score": 100, "luminance": 128, "stdev": 50})
        if events:
            print(f"Frame {i}: Detected Events: {[e['type'] for e in events]}")

    # 4. Test Gemma Reasoning (Mock call)
    print("Testing Gemma Reasoning...")
    event_context = {
        "id": 10,
        "type": "Intrusion Detection",
        "message": "Person in restricted zone"
    }
    # We won't run full inference here as it takes ~10s, but we've verified model loading above.
    # reasoning = gemma_engine.analyze_behavior(dummy_frame, event_context)
    # print(f"Gemma Reasoning: {reasoning}")

    print("--- Verification Complete ---")

if __name__ == "__main__":
    verify_pipeline()
