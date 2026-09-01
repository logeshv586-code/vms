import logging
import numpy as np
import cv2
import os
import time
import onnxruntime as ort
from transformers import AutoTokenizer, AutoProcessor
from PIL import Image

logger = logging.getLogger(__name__)

class PaliGemmaONNXEngine:
    """
    High-Performance PaliGemma Engine optimized for CPU.
    Uses ONNX Runtime with OpenVINO or optimized CPU kernels.
    """
    
    def __init__(self, model_dir=None):
        self.model_dir = model_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "../models/paligemma_onnx"))
        self.session = None
        self.processor = None
        self.tokenizer = None
        self.initialized = False
        
        # Performance Settings
        self.providers = [
            'OpenVINOExecutionProvider', # Best for Intel CPU
            'CPUExecutionProvider'        # Optimized Fallback
        ]
        
        try:
            if not os.path.exists(self.model_dir):
                logger.warning(f"PaliGemma ONNX directory not found: {self.model_dir}")
                return

            # Note: A full PaliGemma ONNX model might be split into components
            # We'll look for a merged model or the decoder
            model_path = os.path.join(self.model_dir, "model.onnx")
            if not os.path.exists(model_path):
                logger.error(f"PaliGemma model file missing at {model_path}")
                return

            logger.info(f"Loading PaliGemma ONNX from {model_path}...")
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            self.session = ort.InferenceSession(model_path, sess_options, providers=self.providers)
            
            # Load tokenizer/processor from the same dir or HF
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
            self.processor = AutoProcessor.from_pretrained(self.model_dir)
            
            self.initialized = True
            logger.info(f"✅ PaliGemma ONNX Engine initialized (Providers: {self.session.get_providers()})")
            
        except Exception as e:
            logger.error(f"Failed to initialize PaliGemma Engine: {e}")

    def analyze_frame(self, frame: np.ndarray, prompt: str):
        """
        Fast inference on a single frame.
        """
        if not self.initialized:
            return {"error": "Engine not initialized"}
            
        try:
            start_time = time.time()
            
            # 1. Preprocess (Fast path)
            # Resize to model input size (usually 224x224 or 448x448)
            h, w = frame.shape[:2]
            # Convert to PIL for processor (or manual numpy)
            pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            
            inputs = self.processor(text=prompt, images=pil_img, return_tensors="np")
            
            # 2. Inference
            onnx_inputs = {
                "input_ids": inputs["input_ids"].astype(np.int64),
                "pixel_values": inputs["pixel_values"].astype(np.float32)
            }
            
            # Add attention_mask if the model expects it
            if "attention_mask" in inputs:
                onnx_inputs["attention_mask"] = inputs["attention_mask"].astype(np.int64)

            outputs = self.session.run(None, onnx_inputs)
            
            # 3. Post-process
            # Depending on export, we might get logits or generated IDs
            # Standard optimum export for vision-2-seq returns logits for the next token
            # This implementation assumes a merged decoder-only or simple generator
            logits = outputs[0]
            generated_ids = np.argmax(logits, axis=-1)
            
            decoded = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            latency = (time.time() - start_time) * 1000
            logger.debug(f"PaliGemma Inference: {latency:.2f}ms")
            
            return {
                "text": decoded.strip(),
                "latency_ms": latency
            }
            
        except Exception as e:
            logger.error(f"PaliGemma inference error: {e}")
            return {"error": str(e)}

    def detect_objects(self, frame: np.ndarray, labels=["person", "vehicle", "bag"]):
        """
        Specialized detection mode using PaliGemma's detect tokens.
        """
        prompt = f"detect {'; '.join(labels)}"
        result = self.analyze_frame(frame, prompt)
        
        if "error" in result:
            return result
            
        # PaliGemma returns detection tokens like <loc001><loc050> label
        # We'll need a parser for this.
        return self._parse_detections(result["text"], frame.shape[:2])

    def _parse_detections(self, text, shape):
        """Parse PaliGemma detection tokens into bounding boxes"""
        # Placeholder for regex-based parsing of <locXXXX> tokens
        # Implementation depends on the specific tokenizer vocabulary
        return {"raw_output": text, "detections": []}

# Global singleton
paligemma_engine = PaliGemmaONNXEngine()
