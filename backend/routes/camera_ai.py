"""REST API for persisted per-camera AI preferences."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.camera_ai_preferences import (
    get_all_preferences,
    get_camera_ai_preferences,
    set_camera_ai_preferences,
)

router = APIRouter(prefix="/api/camera-ai", tags=["camera_ai"])


class CameraAIPreferencesUpdate(BaseModel):
    enabled: Optional[bool] = None
    confidence: Optional[float] = None
    iou: Optional[float] = None
    tracker: Optional[str] = None
    skip_frames: Optional[int] = None
    ai_fps: Optional[float] = None
    evidence_pre_seconds: Optional[float] = None
    evidence_post_seconds: Optional[float] = None


@router.get("")
async def get_all_camera_ai_preferences():
    return {"success": True, "data": get_all_preferences()}


@router.get("/{camera_id:path}")
async def get_camera_ai(camera_id: str):
    return {"success": True, "data": get_camera_ai_preferences(camera_id)}


@router.put("/{camera_id:path}")
async def update_camera_ai(camera_id: str, request: CameraAIPreferencesUpdate):
    try:
        payload = request.model_dump(exclude_unset=True) if hasattr(request, "model_dump") else request.dict(exclude_unset=True)
        saved = set_camera_ai_preferences(camera_id, payload)
        return {"success": True, "data": saved, "message": f"AI preferences updated for {camera_id}"}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update AI preferences: {exc}") from exc
