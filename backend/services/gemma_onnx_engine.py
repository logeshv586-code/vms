import logging
import os
import time
from typing import Any, Dict, List

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image
from transformers import AutoProcessor, AutoTokenizer

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "models", "paligemma.onnx")
)


class GemmaONNXEngine:
    """Optional Tier-2 PaliGemma ONNX region analyzer.

    The engine is deliberately strict: a plain logits-only ONNX graph is not treated as a
    generated caption. PaliGemma is autoregressive, so a usable export must return generated
    token IDs (or be replaced by a proper generation runtime). This prevents one-pass argmax
    logits from being presented to operators as real semantic reasoning.
    """

    def __init__(self, model_path=None, processor_id=None):
        self.model_path = os.path.abspath(
            model_path or os.getenv("VMS_PALIGEMMA_ONNX_PATH", _DEFAULT_MODEL_PATH)
        )
        self.processor_id = processor_id or os.getenv(
            "VMS_PALIGEMMA_PROCESSOR", "google/paligemma-3b-pt-224"
        )
        self.session = None
        self.processor = None
        self.tokenizer = None
        self.initialized = False
        self.provider = None
        self.last_error = None
        self.input_names = set()

        if not os.path.exists(self.model_path):
            self.last_error = f"PaliGemma ONNX model not found: {self.model_path}"
            logger.info(self.last_error)
            return

        try:
            available = set(ort.get_available_providers())
            providers = []
            if "CUDAExecutionProvider" in available:
                providers.append("CUDAExecutionProvider")
            providers.append("CPUExecutionProvider")

            self.session = ort.InferenceSession(self.model_path, providers=providers)
            self.provider = self.session.get_providers()[0] if self.session.get_providers() else None
            self.input_names = {item.name for item in self.session.get_inputs()}

            local_only = os.getenv("VMS_GEMMA_PROCESSOR_LOCAL_ONLY", "false").lower() == "true"
            self.processor = AutoProcessor.from_pretrained(
                self.processor_id,
                local_files_only=local_only,
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.processor_id,
                local_files_only=local_only,
            )

            required = {"input_ids", "pixel_values"}
            missing = required - self.input_names
            if missing:
                raise RuntimeError(f"ONNX graph missing required inputs: {sorted(missing)}")

            self.initialized = True
            logger.info(
                "PaliGemma ONNX initialized: path=%s provider=%s inputs=%s",
                self.model_path,
                self.provider,
                sorted(self.input_names),
            )
        except Exception as exc:
            self.last_error = str(exc)
            self.session = None
            self.initialized = False
            logger.exception("Failed to initialize PaliGemma ONNX engine: %s", exc)

    @property
    def available(self) -> bool:
        return self.initialized and self.session is not None

    def analyze_regions(self, frame, regions, task_type="caption") -> List[Dict[str, Any]]:
        if not self.available:
            reason = self.last_error or "PaliGemma ONNX engine is not initialized"
            return [
                {"region": region, "error": reason, "task": task_type, "available": False}
                for region in regions
            ]

        results = []
        height, width = frame.shape[:2]
        for region in regions:
            try:
                box = region.get("box", [])
                if len(box) != 4:
                    raise ValueError("Region has no valid bbox")
                x1, y1, x2, y2 = [int(float(v)) for v in box]
                x1, x2 = max(0, x1), min(width, x2)
                y1, y2 = max(0, y1), min(height, y2)
                if x2 <= x1 or y2 <= y1:
                    raise ValueError("Region bbox is empty after clamping")

                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    raise ValueError("Region crop is empty")

                prompt = self._prompt(task_type, str(region.get("label", "object")))
                output_text, latency_ms = self._infer(crop, prompt)
                results.append(
                    {
                        "region": region,
                        "analysis": output_text,
                        "task": task_type,
                        "available": True,
                        "latency_ms": latency_ms,
                    }
                )
            except Exception as exc:
                logger.debug("PaliGemma region analysis failed: %s", exc)
                results.append(
                    {
                        "region": region,
                        "error": str(exc),
                        "task": task_type,
                        "available": True,
                    }
                )
        return results

    @staticmethod
    def _prompt(task_type: str, label: str) -> str:
        if task_type == "caption":
            return f"Describe only the visible {label}: appearance, color, and observable state."
        if task_type == "ocr":
            return "Read only clearly visible text. If no text is readable, answer: no readable text."
        if task_type == "verify":
            return f"Is a {label} clearly visible? Answer yes or no and briefly state the visual evidence."
        if task_type == "context":
            return f"Describe only the observable action of the {label}. Do not infer intent."
        raise ValueError(f"Unsupported task_type: {task_type}")

    def _infer(self, crop, prompt):
        pil_img = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        inputs = self.processor(text=prompt, images=pil_img, return_tensors="np")

        onnx_inputs = {}
        for name in self.input_names:
            if name not in inputs:
                continue
            value = inputs[name]
            if name in {"input_ids", "attention_mask", "token_type_ids"}:
                value = value.astype(np.int64)
            elif name == "pixel_values":
                value = value.astype(np.float32)
            onnx_inputs[name] = value

        required = {"input_ids", "pixel_values"}
        missing = required - set(onnx_inputs)
        if missing:
            raise RuntimeError(f"Processor did not provide required ONNX inputs: {sorted(missing)}")

        started = time.perf_counter()
        outputs = self.session.run(None, onnx_inputs)
        latency_ms = (time.perf_counter() - started) * 1000.0
        if not outputs:
            raise RuntimeError("ONNX graph returned no outputs")

        generated = np.asarray(outputs[0])
        # A rank-3 float tensor is normally token logits [batch, sequence, vocabulary].
        # One argmax pass is NOT autoregressive generation, so do not turn it into a fake caption.
        if generated.ndim == 3 and np.issubdtype(generated.dtype, np.floating):
            raise RuntimeError(
                "PaliGemma ONNX graph returns logits only. Export/use an autoregressive generation graph "
                "or the local GGUF Gemma backend; logits-only output is not accepted as semantic validation."
            )

        if generated.ndim == 1:
            generated = generated[None, :]
        if generated.ndim != 2:
            raise RuntimeError(f"Unsupported ONNX output shape for generated token IDs: {generated.shape}")

        if not np.issubdtype(generated.dtype, np.integer):
            generated = generated.astype(np.int64)
        decoded = self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0].strip()
        if not decoded:
            raise RuntimeError("PaliGemma ONNX returned an empty generated response")
        return decoded, latency_ms

    def get_status(self):
        return {
            "initialized": self.initialized,
            "available": self.available,
            "model_path": self.model_path,
            "processor": self.processor_id,
            "provider": self.provider,
            "last_error": self.last_error,
        }


gemma_onnx_engine = GemmaONNXEngine()
