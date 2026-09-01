import logging
import numpy as np
import cv2
import os
import time
import onnxruntime as ort
from transformers import AutoProcessor, AutoTokenizer
from PIL import Image

logger = logging.getLogger(__name__)

class GemmaONNXEngine:
    """
    Tier 2 Semantic Engine — PaliGemma optimized with ONNX Runtime.
    Handles semantic verification, captioning, and OCR on region proposals.
    """
    
    def __init__(self, model_path=None, processor_id="google/paligemma-3b-pt-224"):
        self.model_path = model_path or os.path.join("backend", "models", "paligemma.onnx")
        self.session = None
        self.processor = None
        self.tokenizer = None
        self.initialized = False
        
        try:
            if not os.path.exists(self.model_path):
                logger.warning(f"PaliGemma ONNX model not found at {self.model_path}. Engine will stay in standby.")
                return

            # Initialize ONNX session with CPU optimization
            # Note: We can add CUDAExecutionProvider if GPU is available
            providers = ['CPUExecutionProvider']
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            
            # Load processor and tokenizer from HF
            self.processor = AutoProcessor.from_pretrained(processor_id)
            self.tokenizer = AutoTokenizer.from_pretrained(processor_id)
            
            self.initialized = True
            logger.info("✅ Gemma ONNX Engine initialized successfully on CPU")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemma ONNX Engine: {e}")

    def analyze_regions(self, frame, regions, task_type="caption"):
        """
        Process multiple region proposals in a batch.
        Regions is a list of dicts: {"box": [x1, y1, x2, y2], "label": "person"}
        """
        if not self.initialized:
            return [{"error": "Engine not initialized"}] * len(regions)

        results = []
        for region in regions:
            try:
                x1, y1, x2, y2 = region["box"]
                crop = frame[int(y1):int(y2), int(x1):int(x2)]
                
                if crop.size == 0:
                    results.append({"error": "Empty crop"})
                    continue

                # Prepare prompt based on task
                if task_type == "caption":
                    prompt = f"Describe the {region.get('label', 'object')} in detail, focusing on color and appearance."
                elif task_type == "ocr":
                    prompt = "ocr"
                elif task_type == "verify":
                    prompt = f"Is there a {region.get('label', 'object')} in this image? answer yes or no."
                elif task_type == "context":
                    prompt = f"What is the {region.get('label', 'object')} doing? describe behavior."
                else:
                    prompt = "describe the scene"

                # Inference
                output_text = self._infer(crop, prompt)
                
                results.append({
                    "region": region,
                    "analysis": output_text,
                    "task": task_type
                })
            except Exception as e:
                logger.error(f"Error analyzing region: {e}")
                results.append({"error": str(e)})

        return results

    def _infer(self, crop, prompt):
        """Internal inference logic for PaliGemma ONNX"""
        # 1. Preprocess
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        inputs = self.processor(text=prompt, images=pil_img, return_tensors="np")

        # 2. Run ONNX Session
        # Input names depend on how the model was exported. 
        # Standard PaliGemma exports usually have 'input_ids', 'pixel_values'
        onnx_inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "pixel_values": inputs["pixel_values"].astype(np.float32)
        }
        
        # Add attention_mask if present
        if "attention_mask" in inputs:
            onnx_inputs["attention_mask"] = inputs["attention_mask"].astype(np.int64)

        start_time = time.time()
        outputs = self.session.run(None, onnx_inputs)
        latency = (time.time() - start_time) * 1000
        
        # 3. Post-process (De-tokenize)
        # Assuming the model returns logits or token IDs directly
        # If it's a full seq2seq export, the output might be the generated IDs
        generated_ids = outputs[0]
        
        # Simple argmax if it returns logits
        if len(generated_ids.shape) == 3:
            generated_ids = np.argmax(generated_ids, axis=-1)
            
        decoded = self.tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
        
        logger.debug(f"Inference latency: {latency:.2f}ms")
        return decoded.strip()

# Global Instance
gemma_onnx_engine = GemmaONNXEngine()
