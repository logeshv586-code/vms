from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
import os
import logging
from typing import List, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the workspace root directory
WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ANALYTICS_CONFIG_PATH = os.path.join(WORKSPACE_ROOT, "analytics_configuration.json")

# Create router
router = APIRouter(prefix="/api/augment", tags=["analytics"])

# Define models
class AnalyticsServer(BaseModel):
    id: Optional[int] = None
    ip: str
    name: str

class AnalyticsResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    message: Optional[str] = None
    error: Optional[str] = None

# Helper function to load analytics configuration
def load_analytics_config():
    try:
        if not os.path.exists(ANALYTICS_CONFIG_PATH):
            # Create default configuration if it doesn't exist
            default_config = {
                "servers": []
            }
            with open(ANALYTICS_CONFIG_PATH, "w") as f:
                json.dump(default_config, f, indent=2)
            return default_config

        with open(ANALYTICS_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading analytics configuration: {str(e)}")
        return {"servers": []}

# Helper function to save analytics configuration
def save_analytics_config(config):
    try:
        with open(ANALYTICS_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving analytics configuration: {str(e)}")
        return False

# Get all servers
@router.get("/servers")
async def get_servers():
    try:
        config = load_analytics_config()
        return {
            "success": True,
            "data": config["servers"],
            "message": "Servers retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting servers: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to retrieve servers: {str(e)}"
        }

# Add a new server
@router.post("/servers")
async def add_server(server: AnalyticsServer):
    try:
        config = load_analytics_config()
        servers = config["servers"]

        # Generate new ID
        new_id = 1
        if servers:
            new_id = max(server["id"] for server in servers) + 1

        # Create new server
        new_server = {
            "id": new_id,
            "ip": server.ip,
            "name": server.name
        }

        # Add to list
        servers.append(new_server)

        # Save configuration
        if save_analytics_config(config):
            return {
                "success": True,
                "data": new_server,
                "message": "Server added successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        logger.error(f"Error adding server: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to add server: {str(e)}"
        }

# Update a server
@router.put("/servers/{server_id}")
async def update_server(server_id: int, server: AnalyticsServer):
    try:
        config = load_analytics_config()
        servers = config["servers"]

        # Find server by ID
        server_index = next((i for i, s in enumerate(servers) if s["id"] == server_id), None)
        if server_index is None:
            return {
                "success": False,
                "error": f"Server with ID {server_id} not found"
            }

        # Update server
        servers[server_index] = {
            "id": server_id,
            "ip": server.ip,
            "name": server.name
        }

        # Save configuration
        if save_analytics_config(config):
            return {
                "success": True,
                "data": servers[server_index],
                "message": "Server updated successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        logger.error(f"Error updating server: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to update server: {str(e)}"
        }

# Delete a server
@router.delete("/servers/{server_id}")
async def delete_server(server_id: int):
    try:
        config = load_analytics_config()
        servers = config["servers"]

        # Find server by ID
        server_index = next((i for i, s in enumerate(servers) if s["id"] == server_id), None)
        if server_index is None:
            return {
                "success": False,
                "error": f"Server with ID {server_id} not found"
            }

        # Remove server
        deleted_server = servers.pop(server_index)

        # Save configuration
        if save_analytics_config(config):
            return {
                "success": True,
                "data": deleted_server,
                "message": "Server deleted successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        logger.error(f"Error deleting server: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to delete server: {str(e)}"
        }
