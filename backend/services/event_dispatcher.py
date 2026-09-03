"""Canonical bridge from specialized/validated detections to the VMS event store.

Detectors should emit structured evidence and remain independent from FastAPI.
This small bridge converts only *confirmed* detector outputs into the existing
PatternEngine alert contract, which applies camera-rule checks, deduplication,
proof capture and persistence.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def dispatch_confirmed_event(
    source_id: str,
    event_type: str,
    severity: str,
    message: str,
    *,
    rule_id: Optional[int] = None,
    confidence: Optional[float] = None,
    data: Optional[Dict[str, Any]] = None,
    validation: Optional[Dict[str, Any]] = None,
) -> bool:
    """Persist one confirmed event through the central alert pipeline.

    Returns ``True`` when the dispatch call was accepted by the alert pipeline.
    The PatternEngine still owns rule-enable checks and the 5-minute event
    deduplication window, so callers can safely invoke this from realtime loops.
    """
    source = str(source_id or "").strip()
    if not source:
        logger.warning("Ignoring confirmed event '%s' without a source id", event_type)
        return False

    event: Dict[str, Any] = {
        "id": rule_id,
        "type": str(event_type or "Security Event"),
        "severity": str(severity or "medium").lower(),
        "message": str(message or "Confirmed security event"),
        "trigger_layer3": False,
        "validated": True,
        "source_id": source,
    }
    evidence = dict(data or {})
    if confidence is not None:
        try:
            evidence["confidence"] = max(0.0, min(1.0, float(confidence)))
        except (TypeError, ValueError):
            pass
    if evidence:
        event["data"] = evidence
    if isinstance(validation, dict):
        event["deep_reasoning"] = dict(validation)

    try:
        from services.pattern_engine import pattern_engine

        pattern_engine.trigger_alert_api(source, event)
        return True
    except Exception as exc:
        logger.exception("Failed to dispatch confirmed event '%s' for %s: %s", event_type, source, exc)
        return False


def dispatch_validated_layer3(source_id: str, event: Dict[str, Any], result: Dict[str, Any]) -> bool:
    """Dispatch a Layer-3 candidate only when the verifier explicitly validates it."""
    if not isinstance(result, dict) or result.get("event_validated") is not True:
        return False
    candidate = dict(event or {})
    candidate["deep_reasoning"] = dict(result)
    candidate["validated"] = True
    candidate["source_id"] = str(source_id or candidate.get("source_id") or "")
    try:
        from services.pattern_engine import pattern_engine

        pattern_engine.trigger_alert_api(candidate["source_id"], candidate)
        return True
    except Exception as exc:
        logger.exception("Failed to dispatch Layer-3 event for %s: %s", source_id, exc)
        return False
