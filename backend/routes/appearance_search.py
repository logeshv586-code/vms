from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Form
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional, List
import logging
import sys
import os
from pathlib import Path

# Add the Event_Detections directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Event_Detections'))

try:
    from appearance_search import AppearanceSearchEngine
except ImportError as e:
    logging.error(f"Failed to import AppearanceSearchEngine: {e}")
    AppearanceSearchEngine = None

router = APIRouter(prefix="/api/appearance-search", tags=["appearance-search"])
logger = logging.getLogger(__name__)

# Global search engine instance
search_engine = None

def get_search_engine():
    """Get or create the search engine instance"""
    global search_engine
    if search_engine is None and AppearanceSearchEngine is not None:
        try:
            # Paths relative to the routes directory
            model_path = os.path.join(os.path.dirname(__file__), '..', 'yolov8n.pt')
            recordings_path = os.path.join(os.path.dirname(__file__), '..', 'recordings')
            search_engine = AppearanceSearchEngine(model_path, recordings_path)
            logger.info("Appearance search engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize appearance search engine: {e}")
            search_engine = None
    return search_engine

@router.get("/health")
async def health_check():
    """Health check for appearance search service"""
    engine = get_search_engine()
    if engine is None:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "message": "Appearance search engine not available"}
        )
    
    return {"status": "healthy", "message": "Appearance search service is running"}

@router.get("/searchable-objects")
async def get_searchable_objects():
    """Get list of objects that can be searched"""
    engine = get_search_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Appearance search engine not available")
    
    try:
        objects = engine.get_searchable_objects()
        return {"objects": objects}
    except Exception as e:
        logger.error(f"Error getting searchable objects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/available-streams")
async def get_available_streams():
    """Get list of available recording streams"""
    engine = get_search_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Appearance search engine not available")
    
    try:
        streams = engine.get_available_streams()
        return {"streams": streams}
    except Exception as e:
        logger.error(f"Error getting available streams: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-image")
async def upload_search_image(file: UploadFile = File(...)):
    """Upload an image for person search"""
    engine = get_search_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Appearance search engine not available")
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Validate file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(status_code=400, detail="File size too large (max 10MB)")
    
    try:
        # Save the uploaded image
        saved_path = engine.save_search_image(file_content, file.filename)
        
        return {
            "success": True,
            "message": "Image uploaded successfully",
            "image_path": saved_path,
            "filename": file.filename
        }
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search-object")
async def search_object(
    object_name: str = Form(...),
    stream_id: Optional[str] = Form(None)
):
    """Search for a specific object in recorded videos"""
    engine = get_search_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Appearance search engine not available")
    
    try:
        logger.info(f"Starting object search for '{object_name}' in stream: {stream_id or 'all streams'}")
        
        # Perform the search
        results = engine.search_object_in_videos(object_name, stream_id)
        
        logger.info(f"Object search completed. Found {len(results)} detections")
        
        return {
            "success": True,
            "search_type": "object",
            "search_target": object_name,
            "stream_id": stream_id,
            "total_detections": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Error searching for object: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search-person")
async def search_person(
    image_path: str = Form(...),
    stream_id: Optional[str] = Form(None)
):
    """Search for a person using uploaded reference image"""
    engine = get_search_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Appearance search engine not available")
    
    try:
        logger.info(f"Starting person search with image: {image_path} in stream: {stream_id or 'all streams'}")
        
        # Verify the image path exists
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Reference image not found")
        
        # Perform the search
        results = engine.search_person_in_videos(image_path, stream_id)
        
        logger.info(f"Person search completed. Found {len(results)} detections")
        
        return {
            "success": True,
            "search_type": "person",
            "reference_image": image_path,
            "stream_id": stream_id,
            "total_detections": len(results),
            "results": results
        }
    except Exception as e:
        logger.error(f"Error searching for person: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search-results/{search_id}")
async def get_search_results(search_id: str):
    """Get cached search results (for future implementation)"""
    # This endpoint can be implemented later for caching search results
    # and providing progress updates for long-running searches
    return {"message": "Search results caching not yet implemented"}

@router.get("/thumbnail/{filename}")
async def get_thumbnail(filename: str):
    """Serve detection thumbnail images"""
    engine = get_search_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Appearance search engine not available")

    try:
        # Construct thumbnail path
        thumbnails_dir = Path(engine.appearance_data_path) / "thumbnails"
        thumbnail_path = thumbnails_dir / filename

        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail not found")

        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/jpeg",
            filename=filename
        )
    except Exception as e:
        logger.error(f"Error serving thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear-cache")
async def clear_search_cache():
    """Clear cached search data and uploaded images"""
    engine = get_search_engine()
    if engine is None:
        raise HTTPException(status_code=503, detail="Appearance search engine not available")

    try:
        # Clear uploaded images from appearance_data folder
        appearance_data_path = Path(engine.appearance_data_path)
        deleted_count = 0

        for file_path in appearance_data_path.glob("search_*"):
            if file_path.is_file():
                file_path.unlink()
                deleted_count += 1

        # Clear thumbnails
        thumbnails_dir = appearance_data_path / "thumbnails"
        if thumbnails_dir.exists():
            for file_path in thumbnails_dir.glob("*.jpg"):
                if file_path.is_file():
                    file_path.unlink()
                    deleted_count += 1

        return {
            "success": True,
            "message": f"Cleared {deleted_count} cached files"
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))
