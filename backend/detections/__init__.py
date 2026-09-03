"""VMS detector registry with explicit runtime capability health.

The package contains a mixture of specialized detectors and Layer-2 rules.  A
missing optional detector must never make the whole application un-importable,
but it also must never be silently advertised as healthy.  This registry keeps
one source of truth for what was requested, what actually imported, and why an
optional capability is unavailable.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DetectorSpec:
    key: str
    candidates: Tuple[Tuple[str, str], ...]
    required: bool = False
    aliases: Tuple[str, ...] = ()
    description: str = ""


# Prefer the real module names that exist in this repository.  Legacy module
# names are kept only as fallbacks so older deployments can still start.
DETECTOR_SPECS: Tuple[DetectorSpec, ...] = (
    DetectorSpec("appearance_search", ((".appearance_search", "AppearanceSearchDetector"),), description="Appearance similarity search"),
    DetectorSpec("object_detection", ((".object_detection", "ObjectDetectionDetector"),), required=True, aliases=("object",)),
    DetectorSpec("vehicle_monitoring", ((".vehicle_monitoring", "VehicleMonitoringDetector"),), aliases=("vehicle",)),
    DetectorSpec("addiction_detection", ((".addiction_detection", "AddictionDetectionDetector"),), aliases=("addiction",)),
    DetectorSpec("camera_tamper", ((".camera_tamper", "CameraTamperDetector"), (".camera_tamper", "CameraTamperDetectionDetector"), (".tampering_detection", "TamperingDetectionDetector")), aliases=("tampering_detection",)),
    DetectorSpec("chain_snatching", ((".chain_snatching", "ChainSnatchingDetector"), (".chain_snatching", "ChainSnatchingDetectionDetector"))),
    DetectorSpec("crowd_detection", ((".crowd_detection", "CrowdDetectionDetector"), (".crowd_detection", "CrowdDetector"))),
    DetectorSpec("eavesdropping", ((".eavesdropping", "EavesdroppingDetector"),)),
    DetectorSpec("face_capture", ((".face_capture", "FaceCaptureDetector"),), required=True),
    DetectorSpec("face_recognition", ((".face_recognition", "FaceRecognitionDetector"),), required=True),
    DetectorSpec("graffiti_and_vandalism", ((".graffiti_and_vandalism", "GraffitiAndVandalismDetector"), (".graffiti_and_vandalism", "GraffitiDetector")), aliases=("graffiti_detection",)),
    DetectorSpec("intrusion_detection", ((".intrusion_detection", "IntrusionDetectionDetector"), (".intrusion_detection", "IntrusionDetector")), aliases=("intrusion",)),
    DetectorSpec("line_crossing", ((".lakshman_rekha", "LakshmanRekhaDetector"), (".lakshman_rekha", "LakshmanRekhaCrossingDetector"), (".line_crossing", "LineCrossingDetector")), aliases=("lakshman_rekha",)),
    DetectorSpec("loitering_detection", ((".loitering", "LoiteringDetector"), (".loitering", "LoiteringDetectionDetector"), (".loitering_detection", "LoiteringDetectionDetector")), aliases=("loitering",)),
    DetectorSpec("mobile_snatching", ((".mobile_snatching", "MobileSnatchingDetector"), (".mobile_snatching", "MobileSnatchingDetectionDetector"))),
    DetectorSpec("person_collapse", ((".people_collapse", "PeopleCollapseDetector"), (".people_collapse", "PersonCollapseDetector"), (".fall_detection", "FallDetectionDetector")), aliases=("fall_detection",)),
    DetectorSpec("fight_detection", ((".people_fighting", "PeopleFightingDetector"), (".fight_detection", "FightDetectionDetector")), aliases=("people_fighting",)),
    DetectorSpec("sign_language", ((".sign_language", "SignLanguageDetector"),), required=True, aliases=("gesture_detection",)),
    DetectorSpec("strike", ((".strike", "StrikeDetector"), (".strike", "StrikeDetectionDetector"))),
    DetectorSpec("suspect_appearance", ((".suspect_appearance", "SuspectAppearanceDetector"), (".suspect_appearance", "SuspectedAppearanceDetector"))),
    DetectorSpec("unattended_object", ((".unattended_object", "UnattendedObjectDetector"), (".abandoned_object", "AbandonedObjectDetector")), aliases=("abandoned_object", "unattended_baggage")),
    DetectorSpec("women_surrounded", ((".women_surrounded", "WomenSurroundedDetector"), (".women_surrounded", "WomenSurroundedDetectionDetector"))),
    DetectorSpec("hand_gesture_classifier", ((".hand_gesture_classifier", "HandGestureClassifier"), (".hand_gesture_classifier", "HandGestureClassifierDetector"))),
)


DETECTOR_REGISTRY: Dict[str, Type] = {}
DETECTOR_HEALTH: Dict[str, Dict[str, Any]] = {}


def _load_spec(spec: DetectorSpec) -> Optional[Type]:
    errors: List[str] = []
    loaded_cls: Optional[Type] = None
    loaded_module: Optional[str] = None
    loaded_class: Optional[str] = None

    for module_path, class_name in spec.candidates:
        try:
            module = importlib.import_module(module_path, package=__name__)
            candidate = getattr(module, class_name)
            loaded_cls = candidate
            loaded_module = module.__name__
            loaded_class = class_name
            break
        except Exception as exc:  # optional capabilities may legitimately be absent
            errors.append(f"{module_path}:{class_name}: {type(exc).__name__}: {exc}")

    health = {
        "key": spec.key,
        "available": loaded_cls is not None,
        "required": spec.required,
        "module": loaded_module,
        "class": loaded_class,
        "aliases": list(spec.aliases),
        "description": spec.description,
        "errors": errors if loaded_cls is None else [],
    }
    DETECTOR_HEALTH[spec.key] = health

    if loaded_cls is None:
        log = logger.error if spec.required else logger.warning
        log("Detector '%s' unavailable: %s", spec.key, " | ".join(errors) or "no candidates")
        return None

    DETECTOR_REGISTRY[spec.key] = loaded_cls
    for alias in spec.aliases:
        DETECTOR_REGISTRY[alias] = loaded_cls
    return loaded_cls


_LOADED: Dict[str, Optional[Type]] = {spec.key: _load_spec(spec) for spec in DETECTOR_SPECS}

# Compatibility class exports used by older modules.  They intentionally map
# to None when the capability is unavailable instead of crashing package import.
AppearanceSearchDetector = _LOADED.get("appearance_search")
ObjectDetectionDetector = _LOADED.get("object_detection")
VehicleMonitoringDetector = _LOADED.get("vehicle_monitoring")
AddictionDetectionDetector = _LOADED.get("addiction_detection")
FaceCaptureDetector = _LOADED.get("face_capture")
FaceRecognitionDetector = _LOADED.get("face_recognition")
SignLanguageDetector = _LOADED.get("sign_language")
IntrusionDetectionDetector = _LOADED.get("intrusion_detection")
CrowdDetectionDetector = _LOADED.get("crowd_detection")
GraffitiAndVandalismDetector = _LOADED.get("graffiti_and_vandalism")
LoiteringDetectionDetector = _LOADED.get("loitering_detection")
FightDetectionDetector = _LOADED.get("fight_detection")
AbandonedObjectDetector = _LOADED.get("unattended_object")
LineCrossingDetector = _LOADED.get("line_crossing")
TamperingDetectionDetector = _LOADED.get("camera_tamper")
FallDetectionDetector = _LOADED.get("person_collapse")


def get_all_detectors(include_aliases: bool = False) -> Dict[str, Type]:
    """Return available detector classes.

    By default only canonical keys are returned.  ``include_aliases=True`` is
    provided for legacy callers that expect old registry names.
    """
    if include_aliases:
        return dict(DETECTOR_REGISTRY)
    canonical = {spec.key for spec in DETECTOR_SPECS}
    return {key: value for key, value in DETECTOR_REGISTRY.items() if key in canonical}


def get_detector_health() -> Dict[str, Dict[str, Any]]:
    """Return a JSON-serialisable startup capability report."""
    return {key: dict(value) for key, value in DETECTOR_HEALTH.items()}


def get_unavailable_detectors(required_only: bool = False) -> Dict[str, Dict[str, Any]]:
    return {
        key: dict(value)
        for key, value in DETECTOR_HEALTH.items()
        if not value["available"] and (not required_only or value["required"])
    }


def assert_required_detectors() -> None:
    """Raise when a detector marked required failed to import.

    Production launchers can call this explicitly.  Importing the package
    itself remains resilient so maintenance/configuration screens still work.
    """
    missing = get_unavailable_detectors(required_only=True)
    if missing:
        details = "; ".join(
            f"{key}: {' | '.join(meta.get('errors', []))}" for key, meta in missing.items()
        )
        raise RuntimeError(f"Required VMS detectors are unavailable: {details}")


def create_detector(name: str, config: Optional[Dict[str, Any]] = None):
    cls = DETECTOR_REGISTRY.get(name)
    if cls is None:
        health = DETECTOR_HEALTH.get(name)
        if health:
            reason = " | ".join(health.get("errors", [])) or "unavailable"
            raise ValueError(f"Detector '{name}' is configured but unavailable: {reason}")
        available = ", ".join(sorted(get_all_detectors().keys()))
        raise ValueError(f"Unknown detector '{name}'. Available detectors: {available}")
    return cls(config=config or {})


logger.info(
    "VMS detector capabilities: %d/%d canonical detectors available",
    len(get_all_detectors()),
    len(DETECTOR_SPECS),
)

__all__ = [
    "DETECTOR_REGISTRY",
    "DETECTOR_HEALTH",
    "DETECTOR_SPECS",
    "get_all_detectors",
    "get_detector_health",
    "get_unavailable_detectors",
    "assert_required_detectors",
    "create_detector",
    "AppearanceSearchDetector",
    "ObjectDetectionDetector",
    "VehicleMonitoringDetector",
    "AddictionDetectionDetector",
    "FaceCaptureDetector",
    "FaceRecognitionDetector",
    "SignLanguageDetector",
    "IntrusionDetectionDetector",
    "CrowdDetectionDetector",
    "GraffitiAndVandalismDetector",
    "LoiteringDetectionDetector",
    "FightDetectionDetector",
    "AbandonedObjectDetector",
    "LineCrossingDetector",
    "TamperingDetectionDetector",
    "FallDetectionDetector",
]
