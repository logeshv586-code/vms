import logging
from typing import Dict, Any, List
import numpy as np
import cv2
from .base_detector import BaseDetector

logger = logging.getLogger(__name__)


class CameraTamperDetector(BaseDetector):
    """
    Detects camera tampering events including lens obstruction, intentional
    defocusing, abrupt scene changes, and physical displacement of the camera.
    Also tracks state to detect persons close to the camera lens hiding or
    obstructing the camera, and weapons closing in on the lens (breaking).

    Detection Strategy:
        1. Brightness Analysis — Monitors mean frame brightness to detect
           lens covering / spray attacks (sudden drop to near-zero) or
           blinding (spike to near-maximum).
        2. Blur Detection — Uses Laplacian variance to identify intentional
           defocusing. A sharp drop in the variance relative to the
           calibrated reference indicates a focus attack.
        3. Histogram Comparison — Compares the current frame's colour
           histogram against a stored reference frame using correlation.
           A low correlation score signals a scene change or physical
           displacement.
        4. Hiding Camera — Stateful detection tracking if a person is close to
           the camera lens and obscuring the camera (5-10s preliminary check,
           30s confirmed tamper).
        5. Weapon Closing In — Stateful detection tracking if a weapon (e.g. knife,
           hammer, etc.) is moving close to the camera, indicating physical damage.

    Kaggle Dataset Sourcing Suggestion:
        UCSD Anomaly Detection Dataset
        https://www.kaggle.com/datasets/ulisesreynoso/ucsd-anomaly-detection-dataset
    """

    # ------------------------------------------------------------------ #
    #  Tamper event sub-types
    # ------------------------------------------------------------------ #
    TAMPER_OBSTRUCTION = "lens_obstruction"
    TAMPER_BLINDING = "lens_blinding"
    TAMPER_DEFOCUS = "defocus"
    TAMPER_SCENE_CHANGE = "scene_change"
    TAMPER_HIDING = "hiding_camera"
    TAMPER_BREAKING = "camera_breaking"

    def __init__(self, config: Dict[str, Any] = None):
        # Internals initialised *before* super().__init__ calls load_model()
        self._reference_frame: np.ndarray | None = None
        self._reference_histogram: np.ndarray | None = None
        self._reference_laplacian_var: float = 0.0
        self._frame_count: int = 0
        
        # Stateful tracking variables
        self._last_person_near_time: float = 0.0
        self._tamper_start_time: float = 0.0

        super().__init__("camera_tamper", config)

    # ------------------------------------------------------------------ #
    #  Model / configuration loading
    # ------------------------------------------------------------------ #
    def load_model(self) -> None:
        """
        Loads standard thresholds and optional YOLO model for person/weapon detection.
        """
        self._brightness_low = self.config.get("brightness_low", 15.0)
        self._brightness_high = self.config.get("brightness_high", 240.0)
        self._blur_ratio_threshold = self.config.get("blur_ratio_threshold", 0.35)
        self._histogram_corr_threshold = self.config.get("histogram_corr_threshold", 0.40)
        self._reference_warmup_frames = self.config.get("reference_warmup_frames", 30)
        
        # Person and weapon closing-in thresholds
        self._person_near_ratio = self.config.get("person_near_ratio", 0.20)
        self._weapon_near_ratio = self.config.get("weapon_near_ratio", 0.05)
        self._person_detection_method = self.config.get("person_detection_method", "yolo")
        self._proximity_time_window = self.config.get("proximity_time_window", 15.0)  # seconds
        
        # Weapon class taxonomy
        self._weapon_classes = set(self.config.get("weapon_classes", [
            "knife", "scissors", "baseball bat", "hammer", "weapon", "sword", "gun", "pistol"
        ]))

        if self._person_detection_method == "yolo":
            try:
                from ultralytics import YOLO
                model_path = self.config.get("yolo_model_path", "yolov8n.pt")
                self.model = YOLO(model_path)
                logger.info("CameraTamperDetector: YOLO model loaded for person/weapon detection (%s).", model_path)
            except Exception as e:
                logger.warning("Could not load YOLO model for CameraTamperDetector: %s. Falling back to contour analysis.", e)
                self.model = None
                self._person_detection_method = "contour"
        else:
            self.model = None

        logger.info(
            "CameraTamperDetector configured — brightness=[%.1f, %.1f], "
            "blur_ratio=%.2f, hist_corr=%.2f, warmup=%d frames, detection_method=%s",
            self._brightness_low,
            self._brightness_high,
            self._blur_ratio_threshold,
            self._histogram_corr_threshold,
            self._reference_warmup_frames,
            self._person_detection_method,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _compute_brightness(gray: np.ndarray) -> float:
        """Return the mean pixel intensity of a grayscale frame."""
        return float(np.mean(gray))

    @staticmethod
    def _compute_laplacian_variance(gray: np.ndarray) -> float:
        """Higher value → sharper image.  Near-zero → severe blur."""
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    @staticmethod
    def _compute_histogram(frame_bgr: np.ndarray) -> np.ndarray:
        """Compute a normalised HSV hue-saturation histogram."""
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    def _update_reference(self, frame_bgr: np.ndarray, gray: np.ndarray) -> None:
        """Store the current frame as the reference baseline."""
        self._reference_frame = gray.copy()
        self._reference_histogram = self._compute_histogram(frame_bgr)
        self._reference_laplacian_var = self._compute_laplacian_variance(gray)

    # ------------------------------------------------------------------ #
    #  Main detection pipeline
    # ------------------------------------------------------------------ #
    def detect(self, frame: np.ndarray, **kwargs) -> Dict[str, Any]:
        """
        Analyse the incoming frame for signs of camera tampering.

        Args:
            frame: BGR video frame (np.ndarray).
            **kwargs:
                stream_id (str): Optional camera/stream identifier.
                timestamp (float): Optional epoch timestamp.
                external_detections (List[Dict]): Pre-computed object detections.

        Returns:
            Standardised detection dict.
        """
        if not self.is_enabled:
            return {
                "triggered": False,
                "detections": [],
                "metadata": {},
                "event_type": self.name,
            }

        import time
        timestamp = kwargs.get("timestamp", time.time())
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self._frame_count += 1

        # ---- Warm-up: build reference baseline ----------------------- #
        if self._frame_count <= self._reference_warmup_frames:
            if self._frame_count == self._reference_warmup_frames:
                self._update_reference(frame, gray)
                logger.info("CameraTamperDetector: reference frame captured at frame %d.", self._frame_count)
            return {
                "triggered": False,
                "detections": [],
                "metadata": {"status": "warming_up", "frames_remaining": self._reference_warmup_frames - self._frame_count},
                "event_type": self.name,
            }

        h_img, w_img = frame.shape[:2]
        frame_area = h_img * w_img

        # ---- Step 1: Detect Persons and Weapons ---------------------- #
        persons = []
        weapons = []
        external = kwargs.get("external_detections", [])
        
        for det in external:
            label = det.get("label", det.get("class", ""))
            bbox = det.get("bbox")
            if not bbox or len(bbox) != 4:
                continue
            conf = float(det.get("confidence", 1.0))
            if label == "person":
                persons.append({"bbox": bbox, "confidence": conf})
            elif label in self._weapon_classes:
                weapons.append({"bbox": bbox, "confidence": conf, "label": label})

        if not external:
            if self._person_detection_method == "yolo" and self.model is not None:
                results = self.model(frame, verbose=False)
                for r in results:
                    if r.boxes is not None:
                        for box in r.boxes:
                            cls_id = int(box.cls[0])
                            label = self.model.names[cls_id]
                            conf = float(box.conf[0])
                            if conf < self.confidence_threshold:
                                continue
                            bbox = box.xyxy[0].tolist()
                            if label == "person":
                                persons.append({"bbox": bbox, "confidence": conf})
                            elif label in self._weapon_classes:
                                weapons.append({"bbox": bbox, "confidence": conf, "label": label})
            else:
                # Fallback to contour-based person candidates (large blobs)
                blurred = cv2.GaussianBlur(gray, (11, 11), 0)
                thresh = cv2.adaptiveThreshold(
                    blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, 15, 4
                )
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
                closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
                contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if area < frame_area * 0.01:
                        continue
                    x, y, bw, bh = cv2.boundingRect(cnt)
                    aspect = bw / max(bh, 1)
                    if 0.3 < aspect < 0.8:
                        persons.append({"bbox": [x, y, x + bw, y + bh], "confidence": 0.5})

        # ---- Step 2: Check if Person is Near the Lens ---------------- #
        person_near = False
        for p in persons:
            px1, py1, px2, py2 = p["bbox"]
            p_area = (px2 - px1) * (py2 - py1)
            ratio = p_area / frame_area
            width_ratio = (px2 - px1) / w_img
            height_ratio = (py2 - py1) / h_img
            if ratio >= self._person_near_ratio or width_ratio > 0.45 or height_ratio > 0.45:
                person_near = True
                break

        if person_near:
            self._last_person_near_time = timestamp

        # ---- Step 3: Run Classical Tamper Analysis ------------------ #
        brightness = self._compute_brightness(gray)
        laplacian_var = self._compute_laplacian_variance(gray)
        correlation = 1.0
        
        classical_tamper_active = False

        if brightness < self._brightness_low or brightness > self._brightness_high:
            classical_tamper_active = True

        if self._reference_laplacian_var > 0:
            blur_ratio = laplacian_var / self._reference_laplacian_var
            if blur_ratio < self._blur_ratio_threshold:
                classical_tamper_active = True

        if self._reference_histogram is not None:
            current_hist = self._compute_histogram(frame)
            correlation = cv2.compareHist(self._reference_histogram, current_hist, cv2.HISTCMP_CORREL)
            if correlation < self._histogram_corr_threshold:
                classical_tamper_active = True

        # ---- Step 4: Stateful Hiding & Breaking Logic ---------------- #
        person_was_near_recently = (timestamp - self._last_person_near_time) <= self._proximity_time_window
        hiding_events: List[Dict[str, Any]] = []
        trigger_hiding = False

        if classical_tamper_active:
            if self._tamper_start_time > 0.0:
                tamper_duration = timestamp - self._tamper_start_time
            elif person_was_near_recently:
                self._tamper_start_time = timestamp
                tamper_duration = 0.0
            else:
                self._tamper_start_time = 0.0
                tamper_duration = 0.0
            
            if self._tamper_start_time > 0.0:
                if 5.0 <= tamper_duration <= 10.0:
                    trigger_hiding = True
                    hiding_events.append({
                        "type": self.TAMPER_HIDING,
                        "confidence": round(0.5 + 0.3 * ((tamper_duration - 5.0) / 5.0), 3),
                        "detail": f"Suspicious activity: Person hiding camera for {tamper_duration:.1f}s (5-10s range)"
                    })
                elif tamper_duration > 10.0:
                    if tamper_duration >= 30.0:
                        trigger_hiding = True
                        hiding_events.append({
                            "type": self.TAMPER_HIDING,
                            "confidence": 1.0,
                            "detail": f"Camera Tamper Detected: Person hiding camera confirmed after {tamper_duration:.1f}s"
                        })
                    else:
                        hiding_events.append({
                            "type": self.TAMPER_HIDING,
                            "confidence": round(0.1 + 0.3 * (tamper_duration / 30.0), 3),
                            "detail": f"Monitoring suspicious hiding: person near lens, duration {tamper_duration:.1f}s (checking up to 30s)"
                        })
        else:
            self._tamper_start_time = 0.0

        # Weapon closing-in (breaking) detection
        breaking_events: List[Dict[str, Any]] = []
        trigger_breaking = False
        
        for w_det in weapons:
            wx1, wy1, wx2, wy2 = w_det["bbox"]
            w_area = (wx2 - wx1) * (wy2 - wy1)
            w_ratio = w_area / frame_area
            w_label = w_det.get("label", "weapon")
            
            if w_ratio >= self._weapon_near_ratio:
                trigger_breaking = True
                breaking_events.append({
                    "type": self.TAMPER_BREAKING,
                    "confidence": round(w_det["confidence"], 3),
                    "detail": f"Weapon '{w_label}' detected close to camera lens (area ratio: {w_ratio:.2%}), indicating physical attack / breaking."
                })

        # ---- Step 5: Build Final Response ---------------------------- #
        tamper_events: List[Dict[str, Any]] = []

        if brightness < self._brightness_low:
            tamper_events.append({
                "type": self.TAMPER_OBSTRUCTION,
                "confidence": round(min(1.0, (self._brightness_low - brightness) / self._brightness_low), 3),
                "detail": f"Mean brightness {brightness:.1f} below threshold {self._brightness_low}",
            })
        elif brightness > self._brightness_high:
            tamper_events.append({
                "type": self.TAMPER_BLINDING,
                "confidence": round(min(1.0, (brightness - self._brightness_high) / (255 - self._brightness_high + 1e-6)), 3),
                "detail": f"Mean brightness {brightness:.1f} above threshold {self._brightness_high}",
            })

        if self._reference_laplacian_var > 0:
            blur_ratio = laplacian_var / self._reference_laplacian_var
            if blur_ratio < self._blur_ratio_threshold:
                tamper_events.append({
                    "type": self.TAMPER_DEFOCUS,
                    "confidence": round(min(1.0, 1.0 - blur_ratio), 3),
                    "detail": (
                        f"Laplacian variance {laplacian_var:.2f} is {blur_ratio:.2%} of "
                        f"reference {self._reference_laplacian_var:.2f}"
                    ),
                })

        if self._reference_histogram is not None:
            if correlation < self._histogram_corr_threshold:
                tamper_events.append({
                    "type": self.TAMPER_SCENE_CHANGE,
                    "confidence": round(min(1.0, 1.0 - correlation), 3),
                    "detail": f"Histogram correlation {correlation:.3f} below threshold {self._histogram_corr_threshold}",
                })

        # Suppress raw alerts if person was near or active session exists, deferring to stateful hiding alerts
        if person_was_near_recently or self._tamper_start_time > 0.0:
            tamper_events = []
 
        tamper_events.extend(hiding_events)
        tamper_events.extend(breaking_events)
 
        triggered = (len(tamper_events) > 0 and not person_was_near_recently and self._tamper_start_time == 0.0) or trigger_hiding or trigger_breaking

        detections = []
        for evt in tamper_events:
            if evt["type"] == self.TAMPER_HIDING and not trigger_hiding:
                continue
            if evt["type"] == self.TAMPER_BREAKING and not trigger_breaking:
                continue
            
            bbox = [0, 0, w_img, h_img]
            if evt["type"] == self.TAMPER_BREAKING and weapons:
                large_weapons = [w for w in weapons if ((w["bbox"][2] - w["bbox"][0]) * (w["bbox"][3] - w["bbox"][1]) / frame_area) >= self._weapon_near_ratio]
                if large_weapons:
                    bbox = large_weapons[0]["bbox"]

            detections.append({
                "label": evt["type"],
                "confidence": evt["confidence"],
                "bbox": bbox,
            })

        triggered = len(detections) > 0

        return {
            "triggered": triggered,
            "detections": detections,
            "metadata": {
                "brightness": round(brightness, 2),
                "laplacian_variance": round(laplacian_var, 2),
                "histogram_correlation": round(
                    correlation if self._reference_histogram is not None else -1.0, 3
                ),
                "tamper_events": tamper_events,
                "frame_index": self._frame_count,
                "person_near": person_near,
                "person_was_near_recently": person_was_near_recently,
                "tamper_duration": round(timestamp - self._tamper_start_time, 2) if self._tamper_start_time > 0.0 else 0.0
            },
            "event_type": self.name,
        }

