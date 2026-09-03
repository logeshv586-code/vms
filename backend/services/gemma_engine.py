import base64
import json
import logging
import os
import subprocess
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any, Dict

import cv2
import numpy as np

try:
    from services.security_rag_service import security_rag
except Exception:
    security_rag = None

logger = logging.getLogger(__name__)

# Existing repository defaults remain supported, but deployments can override both files.
_DEFAULT_GEMMA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../gemma-4-E4B-it-GGUF")
)
MODEL_PATH = os.getenv(
    "VMS_GEMMA_MODEL_PATH",
    os.path.join(_DEFAULT_GEMMA_DIR, "gemma-4-E4B-it-Q4_K_M.gguf"),
)
MMPROJ_PATH = os.getenv(
    "VMS_GEMMA_MMPROJ_PATH",
    os.path.join(_DEFAULT_GEMMA_DIR, "mmproj-gemma-4-E4B-it-BF16.gguf"),
)

# Compact, security-focused prompts. Layer 2 supplies geometry/temporal evidence; the VLM is
# a verifier, not the source of truth for line crossing, speed, dwell time, or identity.
RULE_PROMPTS = {
    1: ("Appearance Search", "Describe visible appearance features only. Do not claim identity unless the supplied evidence explicitly contains an identity match."),
    2: ("Camera Tamper", "Check for obstruction, severe blur, darkness/overexposure, or a clearly displaced camera view."),
    3: ("Chain/Handbag Snatching", "Look for visible grabbing/pulling of a carried item plus victim reaction. Do not infer theft from proximity alone."),
    4: ("Crowd Detection", "Describe visible crowd density and agitation. Use the supplied numeric person count as authoritative."),
    5: ("Harassment", "Look for observable cornering, blocking, following, intimidation, or unwanted physical contact. Avoid inferring protected attributes."),
    6: ("Face Capture", "Assess face visibility, frontal angle, occlusion, lighting, and image quality. Do not identify a person."),
    7: ("Face Recognition", "Assess whether the face is suitable for recognition. Do not invent a name or match."),
    8: ("Gesture Detection", "Describe visible hand/body gestures and whether they resemble a distress or aggressive signal."),
    9: ("Graffiti/Vandalism", "Look for observable property damage, marking, breaking, kicking, or tool use."),
    10: ("Intrusion", "Verify visible presence and behavior; treat configured zone membership from Layer 2 as authoritative."),
    11: ("Boundary Crossing", "Describe the person's visible motion/context; treat geometric line-crossing evidence from Layer 2 as authoritative."),
    12: ("Loitering", "Describe behavior consistent with waiting/pacing; treat Layer 2 dwell duration as authoritative."),
    13: ("Mobile Snatching", "Look for a visible phone grab plus immediate separation/escape behavior. Do not infer theft from hand proximity alone."),
    14: ("Object Classification", "Describe visible objects and scene context. Never invent objects that are not visible."),
    15: ("People Fighting", "Look for repeated punching, kicking, grappling, forceful pushing, or aggressive physical contact."),
    16: ("Person Collapsing", "Look for a visible fall/collapse or person lying down; do not diagnose a medical condition."),
    17: ("Procession/Protest", "Describe visible organized group movement, banners/placards, and agitation without inferring political affiliation."),
    18: ("Suspected Appearance", "Describe objective visible appearance/behavior only. Do not classify a person as suspicious based on demographic traits."),
    19: ("Unattended Object", "Check whether a visible bag/package appears separated from nearby people; treat Layer 2 unattended duration as authoritative."),
    20: ("Person Surrounded", "Look for a person physically surrounded, blocked, cornered, or showing visible distress; do not infer gender."),
    21: ("Forced Removal", "Look for dragging, forced carrying, visible struggle, or forced entry into a vehicle. Do not infer relationship or intent without evidence."),
    22: ("Vehicle Monitoring", "Describe vehicle type and visible behavior; treat tracker-derived speed/direction as authoritative."),
    23: ("Zone Monitoring", "Describe visible activity in the configured zone; treat Layer 2 zone membership/counts as authoritative."),
}


def _unavailable_result(reason: str) -> Dict[str, Any]:
    return {
        "event_validated": False,
        "available": False,
        "severity": "unknown",
        "threat_type": "model_unavailable",
        "short_description": reason,
        "confidence_score": 0.0,
        "simulated": False,
    }


def _detect_gpu_layers() -> int:
    configured = os.getenv("VMS_GEMMA_GPU_LAYERS")
    if configured is not None:
        try:
            return int(configured)
        except ValueError:
            logger.warning("Invalid VMS_GEMMA_GPU_LAYERS=%r; auto-detecting", configured)

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            free_mb = int(result.stdout.strip().splitlines()[0])
            if free_mb >= 2500:
                return -1
            if free_mb >= 1000:
                return 15
    except Exception:
        pass
    return 0


class GemmaEngine:
    """Local multimodal Gemma/GGUF verifier with fail-closed production behavior."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.llm = None
        self.chat_handler = None
        self._inference_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemma")
        self._inference_lock = threading.Lock()
        self._gpu_layers = 0
        self._disabled = os.getenv("DISABLE_VLM", "false").lower() == "true"
        self._last_error = None
        self.timeout_seconds = max(5, int(os.getenv("VMS_GEMMA_TIMEOUT_SECONDS", "45")))

        if self._disabled:
            logger.info("Local Gemma VLM disabled via DISABLE_VLM")
            self._initialized = True
            return

        if not os.path.exists(MODEL_PATH) or not os.path.exists(MMPROJ_PATH):
            self._last_error = (
                f"Gemma vision model files are missing. model={MODEL_PATH}, mmproj={MMPROJ_PATH}"
            )
            logger.warning(self._last_error)
            self._initialized = True
            return

        try:
            self._gpu_layers = _detect_gpu_layers()
            self._load_model(self._gpu_layers)
        except Exception as exc:
            self._last_error = str(exc)
            logger.error("Failed to initialize Gemma VLM: %s", exc)
            logger.debug(traceback.format_exc())
            self.llm = None

        self._initialized = True

    @property
    def available(self) -> bool:
        return self.llm is not None

    def _load_model(self, n_gpu_layers: int):
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Llava15ChatHandler

        def build(gpu_layers: int):
            handler = Llava15ChatHandler(clip_model_path=MMPROJ_PATH)
            model = Llama(
                model_path=MODEL_PATH,
                chat_handler=handler,
                n_ctx=max(1024, int(os.getenv("VMS_GEMMA_CONTEXT", "2048"))),
                n_gpu_layers=gpu_layers,
                n_threads=max(1, int(os.getenv("VMS_GEMMA_THREADS", str(os.cpu_count() or 8)))),
                verbose=False,
            )
            return model, handler

        try:
            self.llm, self.chat_handler = build(n_gpu_layers)
            logger.info("Gemma VLM initialized with n_gpu_layers=%s", n_gpu_layers)
        except Exception as first_error:
            if n_gpu_layers == 0:
                raise
            logger.warning("Gemma GPU load failed; retrying on CPU: %s", first_error)
            self._gpu_layers = 0
            self.llm, self.chat_handler = build(0)
            logger.info("Gemma VLM initialized with CPU fallback")

    def analyze_scene(self, frame: np.ndarray, stream_id: str):
        return self.analyze_behavior(
            frame,
            {
                "id": 14,
                "type": "General Scene Analysis",
                "message": f"Broad scene verification for stream {stream_id}",
            },
        )

    def analyze_behavior(self, frame: np.ndarray, event_context: dict):
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return {
                **_unavailable_result("No valid frame was supplied to the vision verifier."),
                "threat_type": "invalid_frame",
            }

        if not self.available:
            reason = self._last_error or (
                "Gemma vision verification is disabled."
                if self._disabled
                else "Gemma vision model is not loaded."
            )
            return _unavailable_result(reason)

        # Only one llama.cpp vision request at a time. Do not queue old CCTV frames behind newer frames.
        if not self._inference_lock.acquire(blocking=False):
            return {
                "event_validated": False,
                "available": True,
                "severity": "unknown",
                "threat_type": "busy",
                "short_description": "Gemma verifier is busy; this frame was skipped.",
                "confidence_score": 0.0,
                "simulated": False,
            }

        try:
            future = self._inference_pool.submit(self._do_inference, frame.copy(), dict(event_context or {}))
            try:
                result = future.result(timeout=self.timeout_seconds)
                result.setdefault("available", True)
                result.setdefault("simulated", False)
                return result
            except FuturesTimeout:
                future.cancel()
                logger.warning("Gemma inference exceeded %ss", self.timeout_seconds)
                return {
                    "event_validated": False,
                    "available": True,
                    "severity": "unknown",
                    "threat_type": "timeout",
                    "short_description": "Gemma vision verification timed out; event was not validated.",
                    "confidence_score": 0.0,
                    "simulated": False,
                }
        except Exception as exc:
            logger.exception("Gemma analysis failed: %s", exc)
            return {
                "event_validated": False,
                "available": True,
                "severity": "unknown",
                "threat_type": "inference_error",
                "short_description": str(exc),
                "confidence_score": 0.0,
                "simulated": False,
            }
        finally:
            self._inference_lock.release()

    def _do_inference(self, frame: np.ndarray, event_context: dict):
        h, w = frame.shape[:2]
        max_width = max(320, int(os.getenv("VMS_GEMMA_MAX_WIDTH", "1024")))
        if w > max_width:
            scale = max_width / float(w)
            frame = cv2.resize(frame, (max_width, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)

        jpeg_quality = max(35, min(95, int(os.getenv("VMS_GEMMA_JPEG_QUALITY", "70"))))
        ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not ok:
            raise RuntimeError("Could not encode frame for Gemma")
        data_uri = "data:image/jpeg;base64," + base64.b64encode(buffer).decode("ascii")

        rule_id = int(event_context.get("id", 14) or 14)
        rule_name, focus = RULE_PROMPTS.get(
            rule_id,
            ("Security Event", "Verify only the observable evidence in the frame; do not invent missing facts."),
        )
        layer2_message = str(event_context.get("message", "No Layer 2 context provided"))
        layer2_severity = str(event_context.get("severity", "unknown"))
        rag_context = ""
        if security_rag is not None:
            try:
                rag_context = str(security_rag.get_context(rule_name) or "")[:1800]
            except Exception:
                rag_context = ""

        prompt = f"""You are a CCTV event verifier. Validate only what is supported by the image and supplied Layer 2 evidence.
Never fabricate identity, duration, speed, direction, zone membership, object possession, intent, demographic traits, or unseen actions.
If evidence is ambiguous, set event_validated=false and lower confidence.

Rule: {rule_name}
Layer 2 message: {layer2_message}
Layer 2 severity: {layer2_severity}
Verification focus: {focus}
Operational context: {rag_context}

Return ONLY one JSON object with exactly these fields:
{{
  "event_validated": true,
  "severity": "low|medium|high|critical|unknown",
  "threat_type": "short_machine_label",
  "short_description": "observable evidence summary",
  "confidence_score": 0.0
}}
"""

        response = self.llm.create_chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            max_tokens=256,
            temperature=0.0,
        )
        raw = response["choices"][0]["message"]["content"]
        return self._safe_parse_json(raw)

    @staticmethod
    def _safe_parse_json(raw: str) -> Dict[str, Any]:
        text = str(raw or "").strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            parsed = json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                return {
                    "event_validated": False,
                    "available": True,
                    "severity": "unknown",
                    "threat_type": "parse_error",
                    "short_description": "Gemma returned a malformed response; event was not validated.",
                    "confidence_score": 0.0,
                    "simulated": False,
                }
            try:
                parsed = json.loads(text[start:end])
            except Exception:
                return {
                    "event_validated": False,
                    "available": True,
                    "severity": "unknown",
                    "threat_type": "parse_error",
                    "short_description": "Gemma returned a malformed response; event was not validated.",
                    "confidence_score": 0.0,
                    "simulated": False,
                }

        confidence = parsed.get("confidence_score", 0.0)
        try:
            confidence = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            confidence = 0.0

        severity = str(parsed.get("severity", "unknown")).lower()
        if severity not in {"low", "medium", "high", "critical", "unknown"}:
            severity = "unknown"

        return {
            "event_validated": parsed.get("event_validated") is True,
            "available": True,
            "severity": severity,
            "threat_type": str(parsed.get("threat_type", "unknown"))[:80],
            "short_description": str(parsed.get("short_description", ""))[:600],
            "confidence_score": confidence,
            "simulated": False,
        }

    def get_status(self):
        if self._disabled:
            mode = "disabled"
        elif self.available:
            mode = "gpu" if self._gpu_layers != 0 else "cpu"
        else:
            mode = "unavailable"

        return {
            "initialized": self._initialized,
            "available": self.available,
            "status": "active" if self.available else mode,
            "mode": mode,
            "gpu_layers": self._gpu_layers,
            "busy": self._inference_lock.locked(),
            "model": os.path.basename(MODEL_PATH),
            "model_path": MODEL_PATH,
            "mmproj_path": MMPROJ_PATH,
            "rules_covered": len(RULE_PROMPTS),
            "simulated": False,
            "last_error": self._last_error,
        }


# Global singleton
gemma_engine = GemmaEngine()
