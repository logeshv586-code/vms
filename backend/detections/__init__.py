"""
VMS Detection Modules Package
==============================

Central registry for all 22 video analytic detector classes.

Provides:
    - ``DETECTOR_REGISTRY``   – Dict mapping detector name → class.
    - ``get_all_detectors()`` – Returns the full registry dict.
    - ``create_detector()``   – Factory that instantiates a detector by name.
"""

import logging
from typing import Dict, Any, Optional, Type

logger = logging.getLogger(__name__)

# ── Detector Imports ────────────────────────────────────────────────────────
# Each import is wrapped individually so that a missing module file does NOT
# prevent the rest of the package from loading.  Any import that fails is
# logged as a warning and the corresponding entry is simply omitted from the
# registry.

_IMPORT_MAP: Dict[str, tuple] = {}  # populated below

def _safe_import(module_path: str, class_name: str) -> Optional[Type]:
    """Import *class_name* from *module_path*, returning None on failure."""
    try:
        import importlib
        mod = importlib.import_module(module_path, package=__name__)
        return getattr(mod, class_name)
    except Exception as exc:
        logger.warning("Could not import %s from %s: %s", class_name, module_path, exc)
        return None


# ── 1. Appearance Search ─────────────────────────────────────────────
from .appearance_search import AppearanceSearchDetector

# ── 2. Object Detection ─────────────────────────────────────────────
from .object_detection import ObjectDetectionDetector

# ── 3. Vehicle Monitoring ────────────────────────────────────────────
from .vehicle_monitoring import VehicleMonitoringDetector

# ── 4. Addiction Detection ───────────────────────────────────────────
from .addiction_detection import AddictionDetectionDetector

# ── 5. Face Capture ───────────────────────────────────────────────
from .face_capture import FaceCaptureDetector

# ── 6. Face Recognition ─────────────────────────────────────────────
from .face_recognition import FaceRecognitionDetector

# ── 7. Sign Language / Hand Gesture ─────────────────────────────────
from .sign_language import SignLanguageDetector

# ── 5-22. Remaining detectors (safe-imported) ──────────────────────────────
# These modules may or may not exist yet.  safe_import ensures the package
# still loads even when some detector files are not yet created.

FaceDetectionDetector          = _safe_import(".face_detection",          "FaceDetectionDetector")
MotionDetectionDetector        = _safe_import(".motion_detection",        "MotionDetectionDetector")
IntrusionDetectionDetector     = _safe_import(".intrusion_detection",     "IntrusionDetectionDetector")
CrowdDetectionDetector         = _safe_import(".crowd_detection",         "CrowdDetectionDetector")
FireSmokeDetectionDetector     = _safe_import(".fire_smoke_detection",    "FireSmokeDetectionDetector")
AbandonedObjectDetector        = _safe_import(".abandoned_object",        "AbandonedObjectDetector")
LoiteringDetectionDetector     = _safe_import(".loitering_detection",     "LoiteringDetectionDetector")
FallDetectionDetector          = _safe_import(".fall_detection",          "FallDetectionDetector")
PPEDetectionDetector           = _safe_import(".ppe_detection",           "PPEDetectionDetector")
WeaponDetectionDetector        = _safe_import(".weapon_detection",        "WeaponDetectionDetector")
AnimalDetectionDetector        = _safe_import(".animal_detection",        "AnimalDetectionDetector")
TrafficViolationDetector       = _safe_import(".traffic_violation",       "TrafficViolationDetector")
TamperingDetectionDetector     = _safe_import(".tampering_detection",     "TamperingDetectionDetector")
LineCrossingDetector           = _safe_import(".line_crossing",           "LineCrossingDetector")
FightDetectionDetector         = _safe_import(".fight_detection",         "FightDetectionDetector")
UnattendedBaggageDetector      = _safe_import(".unattended_baggage",      "UnattendedBaggageDetector")
LicensePlateDetector           = _safe_import(".license_plate",           "LicensePlateDetector")
GenderAgeDetector              = _safe_import(".gender_age_detection",    "GenderAgeDetector")
GraffitiAndVandalismDetector   = _safe_import(".graffiti_and_vandalism",   "GraffitiAndVandalismDetector")


# ── Registry Construction ──────────────────────────────────────────────────

# All 22 detectors with their canonical registry keys
_ALL_DETECTORS = {
    # Always-available (direct imports)
    "appearance_search":    AppearanceSearchDetector,
    "object_detection":     ObjectDetectionDetector,
    "vehicle_monitoring":   VehicleMonitoringDetector,
    "addiction_detection":  AddictionDetectionDetector,
    "face_capture":         FaceCaptureDetector,
    "face_recognition":     FaceRecognitionDetector,
    "sign_language":        SignLanguageDetector,

    # Safe-imported (may be None until the file is created)
    "face_detection":       FaceDetectionDetector,
    "motion_detection":     MotionDetectionDetector,
    "intrusion_detection":  IntrusionDetectionDetector,
    "crowd_detection":      CrowdDetectionDetector,
    "fire_smoke_detection": FireSmokeDetectionDetector,
    "abandoned_object":     AbandonedObjectDetector,
    "loitering_detection":  LoiteringDetectionDetector,
    "fall_detection":       FallDetectionDetector,
    "ppe_detection":        PPEDetectionDetector,
    "weapon_detection":     WeaponDetectionDetector,
    "animal_detection":     AnimalDetectionDetector,
    "traffic_violation":    TrafficViolationDetector,
    "tampering_detection":  TamperingDetectionDetector,
    "line_crossing":        LineCrossingDetector,
    "fight_detection":      FightDetectionDetector,
    "unattended_baggage":   UnattendedBaggageDetector,
    "license_plate":        LicensePlateDetector,
    "gender_age_detection": GenderAgeDetector,
    "graffiti_and_vandalism": GraffitiAndVandalismDetector,
}

# Build the live registry – only entries that imported successfully
DETECTOR_REGISTRY: Dict[str, Type] = {
    name: cls for name, cls in _ALL_DETECTORS.items() if cls is not None
}

logger.info(
    "Detector registry initialised: %d / %d detectors available.",
    len(DETECTOR_REGISTRY),
    len(_ALL_DETECTORS),
)


# ── Public API ──────────────────────────────────────────────────────────────

def get_all_detectors() -> Dict[str, Type]:
    """
    Return the full detector registry.

    Returns:
        Dict mapping detector name strings to their detector classes.
        Only detectors whose module files exist and imported successfully
        are included.
    """
    return DETECTOR_REGISTRY


def create_detector(name: str, config: Dict[str, Any] = None):
    """
    Factory function: instantiate a detector by its registry name.

    Args:
        name:   Canonical detector name (e.g. ``"object_detection"``).
        config: Optional configuration dict forwarded to the detector.

    Returns:
        An instance of the requested detector.

    Raises:
        ValueError: If *name* is not found in the registry.
    """
    cls = DETECTOR_REGISTRY.get(name)
    if cls is None:
        available = ", ".join(sorted(DETECTOR_REGISTRY.keys()))
        raise ValueError(
            f"Unknown detector '{name}'. Available detectors: {available}"
        )
    logger.info("Creating detector instance: %s", name)
    return cls(config=config)


# ── __all__ ─────────────────────────────────────────────────────────────────

__all__ = [
    # Registry & helpers
    "DETECTOR_REGISTRY",
    "get_all_detectors",
    "create_detector",

    # Detector classes (all 22)
    "AppearanceSearchDetector",
    "ObjectDetectionDetector",
    "VehicleMonitoringDetector",
    "AddictionDetectionDetector",
    "FaceDetectionDetector",
    "MotionDetectionDetector",
    "IntrusionDetectionDetector",
    "CrowdDetectionDetector",
    "FireSmokeDetectionDetector",
    "AbandonedObjectDetector",
    "LoiteringDetectionDetector",
    "FallDetectionDetector",
    "PPEDetectionDetector",
    "WeaponDetectionDetector",
    "AnimalDetectionDetector",
    "TrafficViolationDetector",
    "TamperingDetectionDetector",
    "LineCrossingDetector",
    "FightDetectionDetector",
    "UnattendedBaggageDetector",
    "LicensePlateDetector",
    "GenderAgeDetector",
    "GraffitiAndVandalismDetector",
]

