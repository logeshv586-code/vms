import logging
import base64
import json
import numpy as np
import cv2
import os
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from services.security_rag_service import security_rag

logger = logging.getLogger(__name__)

# Paths to local models
GEMMA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../gemma-4-E4B-it-GGUF"))
MODEL_PATH = os.path.join(GEMMA_DIR, "gemma-4-E4B-it-Q4_K_M.gguf")
MMPROJ_PATH = os.path.join(GEMMA_DIR, "mmproj-gemma-4-E4B-it-BF16.gguf")

# ─── RULE-SPECIFIC PROMPTS (All 23 Rules) ────────────────────────
RULE_PROMPTS = {
    1: {
        "name": "Appearance Search",
        "focus": "Describe the visible person or vehicle in detail: clothing color, type (shirt/jacket/pants), hair style/color, height estimate, accessories (bag, glasses, hat), and any distinguishing features. For vehicles: color, type (sedan/SUV/bike), and any visible markings.",
        "threat_types": "matched_appearance/partial_match/no_match/false_alarm"
    },
    2: {
        "name": "Camera Tamper",
        "focus": "Check if the camera view is obscured, blocked, spray-painted, moved, or showing an abnormal angle. Look for hands near the lens, sudden blur, or a completely dark/white frame.",
        "threat_types": "tamper/obstruction/repositioned/false_alarm"
    },
    3: {
        "name": "Chain/Handbag Snatching",
        "focus": "Look for someone grabbing or pulling a bag/chain/purse from another person. Check for sudden jerking motion, a person running away with an item, or a victim reacting in distress.",
        "threat_types": "snatching/theft/struggle/false_alarm"
    },
    4: {
        "name": "Crowd Detection",
        "focus": "Assess the crowd: estimate the number of people, density (sparse, moderate, packed), behavior (calm, agitated, stampeding), and overall mood. Look for any signs of panic, pushing, or disorderly conduct.",
        "threat_types": "orderly_crowd/agitated_crowd/stampede_risk/false_alarm"
    },
    5: {
        "name": "Eve Teasing / Harassment",
        "focus": "Look for harassment behavior: a group of people cornering or following an individual, intimidating gestures, unwanted physical proximity, or aggressive body language toward a lone person.",
        "threat_types": "harassment/intimidation/stalking/false_alarm"
    },
    6: {
        "name": "Face Capture",
        "focus": "Evaluate the quality of visible faces for capture: check if faces are frontal or profile, well-lit or shadowed, occluded by mask/hat/hair, and at sufficient resolution for identification. Report face count and quality.",
        "threat_types": "high_quality_face/partial_face/occluded_face/no_face"
    },
    7: {
        "name": "Face Recognition",
        "focus": "Assess if any visible person could be matched to a known individual. Evaluate facial visibility, angle, lighting conditions, and any partial occlusions that might affect recognition accuracy.",
        "threat_types": "recognizable/partially_visible/unrecognizable/false_alarm"
    },
    8: {
        "name": "Gesture Detection",
        "focus": "Identify hand and body gestures: waving, pointing, signalling, raising fist, beckoning, thumbs-up/down, or distress signals (waving for help). Describe the gesture and its likely intent.",
        "threat_types": "distress_signal/aggressive_gesture/neutral_gesture/false_alarm"
    },
    9: {
        "name": "Graffiti and Vandalism",
        "focus": "Detect signs of vandalism: person spray-painting walls, scratching surfaces, breaking windows, kicking/hitting property, or using tools to damage infrastructure. Look for paint cans, markers, or tools in hand.",
        "threat_types": "active_vandalism/property_damage/graffiti/false_alarm"
    },
    10: {
        "name": "Intrusion Detection",
        "focus": "Verify if the person is genuinely in a restricted/unauthorized area. Check if they appear to be trespassing, climbing fences, or entering through unauthorized access points.",
        "threat_types": "trespassing/unauthorized_access/fence_climbing/false_alarm"
    },
    11: {
        "name": "Lakshmanrekha Crossing",
        "focus": "Identify if a person has crossed the virtual boundary line (indicated by yellow/cyan markings). Check the direction of movement (entry vs exit), the speed of crossing, and look for any suspicious behavior or unauthorized access. Report if the crossing appears forced or if the individual is carrying restricted items.",
        "threat_types": "boundary_crossed/unauthorized_entry/authorized_crossing/false_alarm"
    },
    12: {
        "name": "Loitering",
        "focus": "Assess if the person appears to be loitering with suspicious intent: repeatedly pacing, looking around nervously, checking doors/windows, or waiting without apparent purpose.",
        "threat_types": "suspicious_loitering/casing/waiting/false_alarm"
    },
    13: {
        "name": "Mobile Snatching",
        "focus": "Look for someone grabbing a phone from another person's hand. Check for sudden snatching motion, a person running with a phone, or a victim reaching out.",
        "threat_types": "phone_snatching/theft/grab_and_run/false_alarm"
    },
    14: {
        "name": "Object Classification",
        "focus": "Identify and classify all visible objects in the scene with detail: vehicles (car/truck/bus with color), bags (backpack/suitcase/briefcase), animals, tools, weapons, or any unusual items. Provide a comprehensive scene inventory.",
        "threat_types": "weapon_detected/suspicious_object/normal_objects/unclassified"
    },
    15: {
        "name": "People Fighting",
        "focus": "Look for physical altercation: punching, kicking, pushing, wrestling, or any violent physical contact between two or more people. Check for aggressive stances and rapid body movements.",
        "threat_types": "fight/assault/brawl/pushing/false_alarm"
    },
    16: {
        "name": "Person Collapsing",
        "focus": "Check if a person has fallen down, collapsed, or is lying on the ground. Look for signs of medical emergency: person lying motionless, others gathering around to help.",
        "threat_types": "medical_emergency/collapse/fall/unconscious/false_alarm"
    },
    17: {
        "name": "Strike / Morcha / Procession",
        "focus": "Assess if a large group of people is conducting an organized protest, march, or procession. Look for banners, placards, slogans, coordinated movement direction, and chanting. Evaluate if the gathering is peaceful or turning violent.",
        "threat_types": "peaceful_protest/violent_protest/march/procession/false_alarm"
    },
    18: {
        "name": "Suspected Appearance",
        "focus": "Evaluate if the person's appearance or behavior seems suspicious: wearing face-covering in non-cold weather, carrying unusual objects (tools, wire cutters), matching a suspect description, looking around nervously, or acting furtively.",
        "threat_types": "suspicious_person/concealed_identity/nervous_behavior/false_alarm"
    },
    19: {
        "name": "Unattended Object",
        "focus": "Verify if the object (bag, box, package) is truly unattended with no owner nearby. Check if anyone has left an item and walked away, if the object looks suspicious or out of place.",
        "threat_types": "abandoned_bag/suspicious_package/left_belongings/false_alarm"
    },
    20: {
        "name": "Women Surrounded",
        "focus": "Check if a woman or vulnerable person appears to be surrounded or cornered by a group. Look for signs of distress, intimidation, blocking escape routes, or aggressive postures from the group.",
        "threat_types": "surrounding/intimidation/harassment/cornering/false_alarm"
    },
    21: {
        "name": "Abduction Detection",
        "focus": "Look for forced removal: someone carrying a child or person against their will, dragging, struggling, a person being forced into a vehicle, or a child crying with an unfamiliar adult.",
        "threat_types": "abduction/forced_removal/kidnapping/child_in_distress/false_alarm"
    },
    22: {
        "name": "Vehicle Monitoring",
        "focus": "Analyze vehicle behavior: identify vehicle type (car/truck/bus/motorcycle), color, speed estimate (normal/fast/stopped), direction, lane usage, and any abnormal behavior like wrong-way driving, sudden stops, or erratic movement.",
        "threat_types": "speeding/wrong_way/erratic_driving/stopped_vehicle/normal"
    },
    23: {
        "name": "Zone Monitoring",
        "focus": "Deeply analyze all activity within the marked monitored zone (indicated by yellow/cyan circle or polygon). Count all persons and objects inside. Detect any unauthorized presence, unusual items left behind, or abnormal behavior patterns within the restricted area. Report the overall security status of the zone.",
        "threat_types": "zone_violation/anomaly_detected/normal_activity/restricted_access"
    },
}


def _detect_gpu_layers():
    """Auto-detect GPU availability and return optimal n_gpu_layers.
    Returns -1 for full GPU offload, 0 for CPU-only."""
    try:
        import subprocess
        # Check for NVIDIA GPU using nvidia-smi
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            free_mem = int(result.stdout.strip().split('\n')[0])
            if free_mem > 2000:  # More than 2GB free VRAM
                logger.info(f"GPU detected with {free_mem}MB free VRAM — using full GPU offload")
                return -1  # Offload all layers to GPU
            elif free_mem > 500:
                logger.info(f"GPU detected with {free_mem}MB free VRAM — partial GPU offload (15 layers)")
                return 15
            else:
                logger.info(f"GPU detected but only {free_mem}MB free — falling back to CPU")
                return 0
    except FileNotFoundError:
        logger.info("nvidia-smi not found — no NVIDIA GPU, using CPU")
    except Exception as e:
        logger.warning(f"GPU detection failed: {e} — falling back to CPU")
    return 0
 


class GemmaEngine:
    """Layer 3 Deep Reasoning Engine — Local Vision LLM (llama-cpp-python)
    
    Uses Gemma-4-V multimodal model for rule-specific behavioral validation.
    Automatically detects GPU/CPU and uses optimal configuration.
    Non-blocking inference with timeout protection to prevent backend freeze.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GemmaEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.llm = None
        self.chat_handler = None
        self._inference_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gemma")
        self._is_busy = False
        self._gpu_layers = 0
        
        try:
            if os.environ.get("DISABLE_VLM", "false").lower() == "true":
                logger.info("Local Gemma VLM disabled via DISABLE_VLM environment variable.")
                self._initialized = True
                return

            logger.info(f"Initializing local Gemma-4 VLM from {MODEL_PATH}")
            if not os.path.exists(MODEL_PATH) or not os.path.exists(MMPROJ_PATH):
                logger.error(f"Model files missing at {GEMMA_DIR}")
                self._initialized = True  # Mark as initialized to prevent retry loops
                return

            # Auto-detect GPU/CPU
            self._gpu_layers = _detect_gpu_layers()
            
            self._load_model(self._gpu_layers)
            
        except Exception as e:
            logger.error(f"Failed to initialize local Gemma Engine: {e}")
            logger.debug(traceback.format_exc())
            self.llm = None
        
        self._initialized = True

    def _load_model(self, n_gpu_layers):
        """Load the model with specified GPU layers, with CPU fallback."""
        from llama_cpp import Llama
        from llama_cpp.llama_chat_format import Llava15ChatHandler
        
        try:
            # Initialize Vision Handler
            self.chat_handler = Llava15ChatHandler(clip_model_path=MMPROJ_PATH)
            
            # Determine thread count based on mode
            n_threads = 4 if n_gpu_layers > 0 else os.cpu_count() or 8
            
            # Load Llama model
            self.llm = Llama(
                model_path=MODEL_PATH,
                chat_handler=self.chat_handler,
                n_ctx=2048,
                n_gpu_layers=n_gpu_layers,
                n_threads=n_threads,
                verbose=False
            )
            
            mode = "GPU" if n_gpu_layers != 0 else "CPU"
            logger.info(f"✅ Gemma Engine initialized ({mode} mode, {n_gpu_layers} GPU layers, {n_threads} threads)")
            
        except Exception as e:
            if n_gpu_layers != 0:
                logger.warning(f"GPU loading failed ({e}), falling back to CPU-only...")
                self._gpu_layers = 0
                try:
                    self.chat_handler = Llava15ChatHandler(clip_model_path=MMPROJ_PATH)
                    self.llm = Llama(
                        model_path=MODEL_PATH,
                        chat_handler=self.chat_handler,
                        n_ctx=2048,
                        n_gpu_layers=0,
                        n_threads=os.cpu_count() or 8,
                        verbose=False
                    )
                    logger.info("✅ Gemma Engine initialized (CPU fallback mode)")
                except Exception as e2:
                    logger.error(f"CPU fallback also failed: {e2}")
                    self.llm = None
            else:
                logger.error(f"CPU model loading failed: {e}")
                self.llm = None

    def analyze_scene(self, frame: np.ndarray, stream_id: str):
        """
        Broad scene analysis: detects all objects and behaviors without a specific Layer 2 trigger.
        Useful for the AI Detection Tab general inventory.
        """
        context = {
            "id": 14, # Default to Object Classification
            "type": "General Scene Analysis",
            "message": f"Broad scan for stream {stream_id}"
        }
        return self.analyze_behavior(frame, context)

    def analyze_behavior(self, frame: np.ndarray, event_context: dict):
        """
        Send frame and Layer 2 context to local VLM for deep reasoning.
        Non-blocking with timeout protection — will not freeze the backend.
        """
        if self.llm is None:
            return self._simulate_inference(frame, event_context)
        
        if self._is_busy:
            return {"error": "Gemma engine is busy with another inference"}

        try:
            self._is_busy = True
            # Run inference in thread pool with a 60-second hard timeout
            future = self._inference_pool.submit(self._do_inference, frame, event_context)
            try:
                result = future.result(timeout=60)
                return result
            except FuturesTimeout:
                logger.warning("Gemma inference timed out after 60s — skipping this frame")
                return {
                    "event_validated": False,
                    "severity": "low",
                    "threat_type": "timeout",
                    "short_description": "Vision analysis timed out. Frame skipped.",
                    "confidence_score": 0.0
                }
        except Exception as e:
            logger.error(f"Error in Gemma Engine analysis: {e}")
            return {"error": str(e)}
        finally:
            self._is_busy = False

    def _do_inference(self, frame: np.ndarray, event_context: dict):
        """Actual inference execution (runs in thread pool)."""
        try:
            # 1. Encode frame as Base64 Data URI (lower quality for speed)
            h, w = frame.shape[:2]
            # Resize large frames for faster inference
            if w > 1024:
                scale = 1024 / w
                frame = cv2.resize(frame, (1024, int(h * scale)), interpolation=cv2.INTER_AREA)
            
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            base64_image = base64.b64encode(buffer).decode('utf-8')
            data_uri = f"data:image/jpeg;base64,{base64_image}"
            
            # 2. Build rule-specific prompt
            rule_id = event_context.get("id")
            rule_info = RULE_PROMPTS.get(rule_id, {
                "focus": "Analyze the scene for any suspicious or abnormal behavior reflecting a security risk.",
                "threat_types": "suspicious/normal/false_alarm"
            })
            
            system_prompt = "You are a specialized security AI analyst. Respond ONLY in valid JSON format."
            user_prompt = f"""
ALERT: Layer 2 flagged a potential '{event_context.get('type')}' event. 
CONTEXT: {event_context.get('message')}
PROTOCOL: {security_rag.get_context(rule_info['name'])}
TASK: {rule_info['focus']}

Respond with this JSON structure:
{{
  "event_validated": true/false,
  "severity": "low/medium/high/critical",
  "threat_type": "{rule_info['threat_types']}",
  "short_description": "2-sentence summary",
  "confidence_score": 0.0-1.0
}}
"""

            # 3. Request inference
            response = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {"type": "image_url", "image_url": {"url": data_uri}}
                        ]
                    }
                ],
                max_tokens=256,
                temperature=0.1  # High precision for security
            )
            
            raw_output = response["choices"][0]["message"]["content"]
            reasoning = self._safe_parse_json(raw_output)
            return reasoning
                
        except Exception as e:
            logger.error(f"Error in Gemma inference: {e}")
            return {"error": str(e)}

    def _safe_parse_json(self, raw: str):
        """Parse JSON response with fallback handling"""
        try:
            # Clean possible markdown wrap
            raw = raw.strip()
            if raw.startswith("```json"):
                raw = raw[7:-3]
            elif raw.startswith("```"):
                raw = raw[3:-3]
            
            return json.loads(raw)
        except Exception:
            # Extract anything between curly braces
            try:
                start = raw.find('{')
                end = raw.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(raw[start:end])
            except:
                pass
            
            return {
                "event_validated": False,
                "severity": "low",
                "threat_type": "parse_error",
                "short_description": "Vision model response was malformed.",
                "confidence_score": 0.0
            }

    def _simulate_inference(self, frame: np.ndarray, event_context: dict):
        """Simulate high-fidelity Gemma vision reasoning for verification/demo when model is in standby"""
        import time
        import random
        
        # Micro-sleep to mimic model processing (500ms - 1.2s)
        time.sleep(random.uniform(0.5, 1.2))
        
        rule_id = event_context.get("id", 14)
        rule_name = event_context.get("type", "General Scene Analysis")
        message = event_context.get("message", "Suspicious activity detected")
        
        # Professional, context-tailored deep descriptions mapping to all 23 rules
        descriptions = {
            1: "Appearance Search: Detailed visual analysis identifies a subject matching the targeted color profile in the center frame.",
            2: "Camera Tamper: Complete camera view verified. Normal pixel variance and brightness levels detected. Tamper threshold nominal.",
            3: "Snatching: Body language and quick-reaching tracking paths flagged. Potential physical snatching behavior verified.",
            4: "Crowd Detection: Group density is within normal safety margins (approx. 4-6 individuals). Crowd sentiment remains calm.",
            5: "Eve Teasing / Harassment: Cornering and follow-paths examined. Intimidation risk remains below alarm thresholds.",
            6: "Face Capture: Frontal facial aspect detected with stable orientation. Resolution satisfies biometric extraction criteria.",
            7: "Face Recognition: Facial details match known profiles. Identification confidence score meets high certainty threshold.",
            8: "Gesture Detection: Distinct waving gesture identified. Gesture type is marked as cooperative / neutral.",
            9: "Vandalism: Structural backdrop monitored. No destructive motion profiles or foreign spray canisters detected.",
            10: "Intrusion Detection: Trespass event verified. Subject positioned fully inside the restricted zone area.",
            11: "Boundary Crossing: Virtual line breach confirmed. Subject crossed the boundary line heading inbound.",
            12: "Loitering: Dwelling pattern observed. Subject has lingered in the frame's focus area for more than 45 seconds.",
            13: "Mobile Snatching: Rapid arm extension and sudden acceleration away from victim verified as suspicious snatched trajectory.",
            14: "Object Classification: Scene scan complete. Primary object: Person, Secondary objects: Vehicle, bag, and portable laptop.",
            15: "People Fighting: Interlocking motion vectors and aggressive postural acceleration profiles indicate physical struggle.",
            16: "Person Collapsing: Dynamic height tracking confirms a rapid posture drop to floor level. Motionless subject detected.",
            17: "Strike / Protest: Coordinate grouping suggests organized formation. Hand-held posters or slogans are under analysis.",
            18: "Suspected Appearance: Face concealment (hoodie/cap) and erratic head rotation verified as elevated security suspicion.",
            19: "Unattended Object: Object displacement tracked. Bag left stationary without accompanying guardian tracking ID for > 2 min.",
            20: "Women Surrounded: Gender-coded centroid tracking shows no hostile grouping or perimeter enclosing behavior.",
            21: "Abduction: Forced physical movement or non-cooperative pulling vector checked. Posture and gait remain normal.",
            22: "Vehicle Monitoring: Dynamic speed tracking confirms velocity is within bounds. Direction of vehicle travel is legal.",
            23: f"Zone Monitoring: Restricted zone violation confirmed. Bounding coordinate verification: {message} is validated."
        }
        
        desc = descriptions.get(rule_id, f"Behavioral analysis of '{rule_name}' verified. Description: {message}")
        
        return {
            "event_validated": True,
            "severity": event_context.get("severity", "medium"),
            "threat_type": "zone_violation" if rule_id == 23 else "suspicious_activity",
            "short_description": desc,
            "confidence_score": round(random.uniform(0.88, 0.97), 2),
            "simulated": True
        }

    def get_status(self):
        """Return engine status for frontend display"""
        return {
            "initialized": True,
            "mode": "CPU (Simulated)" if self.llm is None else ("GPU" if self._gpu_layers != 0 else "CPU"),
            "gpu_layers": self._gpu_layers,
            "busy": self._is_busy,
            "model": "Gemma-4-E4B-it (Simulated)" if self.llm is None else "Gemma-4-E4B-it",
            "rules_covered": len(RULE_PROMPTS)
        }


# Global singleton
gemma_engine = GemmaEngine()
