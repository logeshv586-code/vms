from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import json
import os
import logging
import shutil
import re
import urllib.parse
from typing import List, Dict, Optional, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the backend directory
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CAMERA_JSON_PATH = os.path.join(BACKEND_DIR, "data/camera_configuration.json")

# Create router
router = APIRouter(prefix="/api/collections", tags=["collections"])

# Define models
class Camera(BaseModel):
    ip: str
    streamUrl: str

class Collection(BaseModel):
    name: str
    cameras: Optional[Dict[str, str]] = {}

class CollectionUpdate(BaseModel):
    name: str

class CameraAdd(BaseModel):
    ip: str
    streamUrl: str

class CameraRangeAdd(BaseModel):
    collection_name: str
    ip_start: str
    ip_end: Optional[str] = None
    camera_model: str
    username: str = ""
    password: str = ""
    port: str = "554"
    main_stream: str = ""
    analytic_stream: str = ""
    protocol: str = "rtsp"

# IP Validation Functions
def is_valid_ip_format(ip: str) -> bool:
    """Validate IPv4 address format"""
    regex = r'^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$'
    return bool(re.match(regex, ip))

def is_private_ip(ip: str) -> bool:
    """Check if IP address is within private network ranges"""
    if not is_valid_ip_format(ip):
        return False

    parts = list(map(int, ip.split('.')))
    first, second = parts[0], parts[1]

    # Class A private: 10.0.0.0 – 10.255.255.255
    if first == 10:
        return True

    # Class B private: 172.16.0.0 – 172.31.255.255
    if first == 172 and 16 <= second <= 31:
        return True

    # Class C private: 192.168.0.0 – 192.168.255.255
    if first == 192 and second == 168:
        return True

    return False

def validate_private_ip(ip: str) -> Dict[str, Any]:
    """Validate that an IP address is both valid format and within private ranges"""
    if not ip or not ip.strip():
        return {
            "isValid": False,
            "error": "IP address is required"
        }

    trimmed_ip = ip.strip()

    if not is_valid_ip_format(trimmed_ip):
        return {
            "isValid": False,
            "error": "Please enter a valid IP address format (e.g., 192.168.1.100)"
        }

    if not is_private_ip(trimmed_ip):
        return {
            "isValid": False,
            "error": "IP address must be within private network ranges:\n• 192.168.0.0 – 192.168.255.255 (most common)\n• 10.0.0.0 – 10.255.255.255\n• 172.16.0.0 – 172.31.255.255"
        }

    return {
        "isValid": True,
        "error": None
    }

def extract_ip_from_stream_url(stream_url: str) -> Optional[str]:
    """Extract IP address from a stream URL"""
    if not stream_url:
        return None

    try:
        parsed_url = urllib.parse.urlparse(stream_url)
        hostname = parsed_url.hostname

        # Check if hostname is an IP address (not a domain name)
        if hostname and is_valid_ip_format(hostname):
            return hostname

        return None
    except Exception:
        # If URL parsing fails, try to extract IP with regex
        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', stream_url)
        return ip_match.group(1) if ip_match else None

def extract_credentials_from_stream_url(stream_url: str) -> Dict[str, Optional[str]]:
    """Extract authentication credentials from a stream URL"""
    if not stream_url:
        return {"username": None, "password": None}

    try:
        parsed_url = urllib.parse.urlparse(stream_url)
        if parsed_url.username and parsed_url.password:
            return {
                "username": parsed_url.username,
                "password": parsed_url.password
            }
        return {"username": None, "password": None}
    except Exception:
        return {"username": None, "password": None}

def preserve_credentials_in_stream_url(new_stream_url: str, existing_stream_url: str) -> str:
    """
    Preserve existing credentials in a stream URL if new URL doesn't have them.

    This function will preserve credentials from the existing URL if:
    1. The new URL has no credentials
    2. The existing URL has credentials
    3. Both URLs are valid RTSP/HTTP URLs

    Note: This preserves credentials regardless of IP address to handle cases where
    the camera's stored IP might differ from the IP in the stream URL.
    """
    if not new_stream_url or not existing_stream_url:
        return new_stream_url

    try:
        # Extract credentials from both URLs
        new_credentials = extract_credentials_from_stream_url(new_stream_url)
        existing_credentials = extract_credentials_from_stream_url(existing_stream_url)

        # If new URL has no credentials but existing URL does, preserve existing credentials
        if (not new_credentials["username"] and not new_credentials["password"] and
            existing_credentials["username"] and existing_credentials["password"]):

            # Parse the new URL to reconstruct it with existing credentials
            parsed_new = urllib.parse.urlparse(new_stream_url)

            # Only proceed if we have a valid hostname
            if not parsed_new.hostname:
                return new_stream_url

            # Reconstruct URL with preserved credentials
            netloc = f"{existing_credentials['username']}:{existing_credentials['password']}@{parsed_new.hostname}"
            if parsed_new.port:
                netloc += f":{parsed_new.port}"

            preserved_url = urllib.parse.urlunparse((
                parsed_new.scheme,
                netloc,
                parsed_new.path,
                parsed_new.params,
                parsed_new.query,
                parsed_new.fragment
            ))

            logger.info(f"Preserved credentials in stream URL: {new_stream_url} -> {preserved_url}")
            return preserved_url

        # If new URL has credentials or existing URL has none, use new URL as-is
        return new_stream_url

    except Exception as e:
        logger.warning(f"Failed to preserve credentials in stream URL: {e}")
        return new_stream_url

def find_camera_by_ip_across_collections(camera_data: Dict, target_ip: str) -> Optional[Dict[str, str]]:
    """Find a camera by IP address across all collections"""
    for collection_name, cameras in camera_data.items():
        for existing_ip, existing_url in cameras.items():
            if existing_ip == target_ip:
                return {
                    "collection": collection_name,
                    "ip": existing_ip,
                    "streamUrl": existing_url
                }
    return None

def check_duplicate_camera(camera_data: Dict, new_ip: str, new_stream_url: str, exclude_collection: str = None, exclude_ip: str = None) -> Dict[str, Any]:
    """
    Check if a camera with the same IP address already exists across all collections.

    Enhanced logic prevents IP duplication by checking:
    1. Direct IP matches (camera key vs new IP)
    2. Stream URL IP matches (IP extracted from existing stream URLs vs new IP)
    3. Cross-stream URL IP matches (IP from existing stream URL vs IP from new stream URL)

    This ensures no two cameras can target the same physical device IP address.
    """

    # Extract IP from the new stream URL
    extracted_ip_from_new_url = extract_ip_from_stream_url(new_stream_url)

    # Collect all IPs we need to check for duplicates
    ips_to_check = []

    # Add the provided IP if valid
    if new_ip and is_valid_ip_format(new_ip):
        ips_to_check.append(new_ip)

    # Add the IP extracted from stream URL if valid and different
    if extracted_ip_from_new_url and is_valid_ip_format(extracted_ip_from_new_url):
        if extracted_ip_from_new_url not in ips_to_check:
            ips_to_check.append(extracted_ip_from_new_url)

    # If no valid IPs found, cannot proceed with duplicate checking
    if not ips_to_check:
        return {
            "isDuplicate": True,
            "error": "No valid IP address found in camera configuration",
            "type": "invalid_ip",
            "existingCollection": None
        }

    # Check for duplicate IP addresses across ALL collections
    for collection_name, cameras in camera_data.items():
        for existing_camera_ip, existing_stream_url in cameras.items():
            # Skip the specific camera we're updating (for update operations)
            if (exclude_collection and exclude_ip and
                collection_name == exclude_collection and existing_camera_ip == exclude_ip):
                continue

            # Collect all IPs associated with the existing camera
            existing_ips = []

            # Add the camera's stored IP key
            if existing_camera_ip and is_valid_ip_format(existing_camera_ip):
                existing_ips.append(existing_camera_ip)

            # Add IP extracted from the existing camera's stream URL
            existing_extracted_ip = extract_ip_from_stream_url(existing_stream_url)
            if existing_extracted_ip and is_valid_ip_format(existing_extracted_ip):
                if existing_extracted_ip not in existing_ips:
                    existing_ips.append(existing_extracted_ip)

            # Check if any of the new camera's IPs match any of the existing camera's IPs
            for new_check_ip in ips_to_check:
                for existing_check_ip in existing_ips:
                    if new_check_ip == existing_check_ip:
                        # Determine which IP caused the conflict for better error messaging
                        conflict_source = "camera IP" if new_check_ip == new_ip else "stream URL IP"
                        existing_source = "camera IP" if existing_check_ip == existing_camera_ip else "stream URL IP"

                        return {
                            "isDuplicate": True,
                            "error": f"Camera with IP address {new_check_ip} already exists in collection '{collection_name}'. Cannot add duplicate IP addresses.",
                            "type": "ip",
                            "existingCollection": collection_name,
                            "existingStreamUrl": existing_stream_url,
                            "conflictDetails": {
                                "conflictingIP": new_check_ip,
                                "newSource": conflict_source,
                                "existingSource": existing_source,
                                "existingCameraIP": existing_camera_ip
                            }
                        }

    return {
        "isDuplicate": False,
        "error": None
    }

def generate_ip_range(ip_start: str, ip_end: str = None) -> List[str]:
    """
    Generate a list of IP addresses from start to end.
    If ip_end is None, returns just the start IP.
    """
    if not ip_end:
        return [ip_start]

    try:
        # Split IP into parts
        start_parts = ip_start.split('.')

        # Validate start IP format
        if len(start_parts) != 4:
            raise ValueError("Invalid start IP format")

        # Handle different IP end formats
        base_ip = '.'.join(start_parts[:3])
        start_octet = int(start_parts[3])

        # If ip_end is just a number (last octet), use it directly
        if '.' not in ip_end:
            end_octet = int(ip_end)
        else:
            # If ip_end is a full IP, extract the last octet
            end_parts = ip_end.split('.')
            if len(end_parts) != 4:
                raise ValueError("Invalid end IP format")
            end_octet = int(end_parts[3])
            # Ensure the base IP matches
            if start_parts[:3] != end_parts[:3]:
                raise ValueError("IP range must have the same base (first 3 octets)")

        if start_octet > end_octet or start_octet < 1 or end_octet > 255:
            raise ValueError("Invalid IP range")

        return [f"{base_ip}.{i}" for i in range(start_octet, end_octet + 1)]

    except (ValueError, IndexError) as e:
        logger.error(f"Error generating IP range: {e}")
        return [ip_start]  # Fallback to single IP

def build_rtsp_url(ip: str, username: str, password: str, port: str, stream_path: str, protocol: str = "rtsp") -> str:
    """Build RTSP URL with credentials"""
    auth_part = f"{username}:{password}@" if username and password else ""
    port_part = f":{port}" if port and port != "554" else ""
    stream_part = f"/{stream_path}" if stream_path else ""

    return f"{protocol}://{auth_part}{ip}{port_part}{stream_part}"

def check_duplicate_camera_legacy(camera_data: Dict, new_ip: str, new_stream_url: str, exclude_collection: str = None, exclude_ip: str = None) -> Dict[str, Any]:
    """
    Legacy duplicate checking function that also checks for exact stream URL matches.
    Used for backward compatibility where exact URL matching is needed.
    """

    # Get the current camera's stream URL if we're excluding it (for updates)
    exclude_stream_url = None
    if exclude_collection and exclude_ip and exclude_collection in camera_data and exclude_ip in camera_data[exclude_collection]:
        exclude_stream_url = camera_data[exclude_collection][exclude_ip]

    for collection_name, cameras in camera_data.items():
        # Skip the collection we're updating (for update operations)
        if exclude_collection and collection_name == exclude_collection:
            for existing_ip, existing_url in cameras.items():
                # Skip the specific camera we're updating
                if exclude_ip and existing_ip == exclude_ip:
                    continue

                # Check for duplicate IP
                if existing_ip == new_ip:
                    return {
                        "isDuplicate": True,
                        "error": f"Camera with IP address {new_ip} already exists in collection '{collection_name}'. Cannot add duplicate IP addresses.",
                        "type": "ip",
                        "existingCollection": collection_name
                    }

                # Check for duplicate stream URL (but don't flag if it's the same camera's current URL)
                if existing_url == new_stream_url and existing_url != exclude_stream_url:
                    return {
                        "isDuplicate": True,
                        "error": f"Camera with stream URL '{new_stream_url}' already exists in collection '{collection_name}' and cannot be added",
                        "type": "url",
                        "existingCollection": collection_name
                    }
            continue

        # For other collections, check all cameras
        for existing_ip, existing_url in cameras.items():
            # Check for duplicate IP
            if existing_ip == new_ip:
                return {
                    "isDuplicate": True,
                    "error": f"Camera with IP address {new_ip} already exists in collection '{collection_name}'. Cannot add duplicate IP addresses.",
                    "type": "ip",
                    "existingCollection": collection_name
                }

            # Check for duplicate stream URL (but don't flag if it's the same camera's current URL)
            if existing_url == new_stream_url and existing_url != exclude_stream_url:
                return {
                    "isDuplicate": True,
                    "error": f"Camera with stream URL '{new_stream_url}' already exists in collection '{collection_name}' and cannot be added",
                    "type": "url",
                    "existingCollection": collection_name
                }

    return {
        "isDuplicate": False,
        "error": None
    }

# Helper function to ensure the camera configuration file exists
def ensure_camera_config():
    if not os.path.exists(CAMERA_JSON_PATH):
        logger.info(f"Creating new camera configuration file at {CAMERA_JSON_PATH}")
        with open(CAMERA_JSON_PATH, "w") as f:
            json.dump({}, f, indent=2)
    return CAMERA_JSON_PATH

# Helper function to read the camera configuration
def read_camera_config():
    ensure_camera_config()
    try:
        with open(CAMERA_JSON_PATH, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error parsing camera_configuration.json")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Malformed camera_configuration.json"
        )
    except Exception as e:
        logger.error(f"Error reading camera configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading camera configuration: {str(e)}"
        )

# Helper function to write the camera configuration
def write_camera_config(config):
    # Backup the old file
    if os.path.exists(CAMERA_JSON_PATH):
        backup_path = CAMERA_JSON_PATH + ".bak"
        try:
            shutil.copy2(CAMERA_JSON_PATH, backup_path)
            logger.debug(f"Created backup at: {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup camera_configuration.json: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to backup configuration file"
            )

    # Write to a temp file first
    temp_path = CAMERA_JSON_PATH + ".tmp"
    try:
        with open(temp_path, "w") as f:
            json.dump(config, f, indent=2)
        os.replace(temp_path, CAMERA_JSON_PATH)
        logger.debug(f"Wrote configuration to: {CAMERA_JSON_PATH}")
    except Exception as e:
        logger.error(f"Failed to write updated configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write updated configuration"
        )

# Get all collections
@router.get("/")
async def get_collections():
    try:
        camera_data = read_camera_config()
        collections = list(camera_data.keys())
        return {"collections": collections}
    except Exception as e:
        logger.error(f"Error getting collections: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Get a specific collection
@router.get("/{collection_name}")
async def get_collection(collection_name: str):
    try:
        camera_data = read_camera_config()

        if collection_name not in camera_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
            )

        return {
            "name": collection_name,
            "cameras": camera_data[collection_name]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Create a new collection
@router.post("/")
async def create_collection(collection: Collection):
    try:
        camera_data = read_camera_config()

        if collection.name in camera_data:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Collection '{collection.name}' already exists"
            )

        # Add the new collection
        camera_data[collection.name] = collection.cameras or {}

        # Save the updated configuration
        write_camera_config(camera_data)

        return {
            "message": f"Collection '{collection.name}' created successfully",
            "collection": {
                "name": collection.name,
                "cameras": camera_data[collection.name]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Update a collection (rename)
@router.put("/{collection_name}")
async def update_collection(collection_name: str, collection_update: CollectionUpdate):
    try:
        camera_data = read_camera_config()

        if collection_name not in camera_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
            )

        if collection_update.name in camera_data and collection_update.name != collection_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Collection '{collection_update.name}' already exists"
            )

        # Rename the collection
        camera_data[collection_update.name] = camera_data.pop(collection_name)

        # Save the updated configuration
        write_camera_config(camera_data)

        return {
            "message": f"Collection renamed from '{collection_name}' to '{collection_update.name}' successfully",
            "collection": {
                "name": collection_update.name,
                "cameras": camera_data[collection_update.name]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Delete a collection
@router.delete("/{collection_name}")
async def delete_collection(collection_name: str):
    try:
        camera_data = read_camera_config()

        if collection_name not in camera_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
            )

        # Remove the collection
        del camera_data[collection_name]

        # Save the updated configuration
        write_camera_config(camera_data)

        return {
            "message": f"Collection '{collection_name}' deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Add a camera to a collection
@router.post("/{collection_name}/cameras")
async def add_camera_to_collection(collection_name: str, camera: CameraAdd):
    try:
        camera_data = read_camera_config()

        if collection_name not in camera_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
            )

        # Validate IP address format and private range
        ip_validation = validate_private_ip(camera.ip)
        if not ip_validation["isValid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid IP address",
                    "message": ip_validation["error"],
                    "type": "validation"
                }
            )

        # Extract IP from stream URL and validate it as well
        extracted_ip = extract_ip_from_stream_url(camera.streamUrl)
        if extracted_ip:
            extracted_ip_validation = validate_private_ip(extracted_ip)
            if not extracted_ip_validation["isValid"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid IP address in stream URL",
                        "message": f"The IP address '{extracted_ip}' extracted from the stream URL is not valid: {extracted_ip_validation['error']}",
                        "type": "validation"
                    }
                )

        # Check for duplicate cameras
        duplicate_check = check_duplicate_camera(camera_data, camera.ip, camera.streamUrl)
        if duplicate_check["isDuplicate"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Duplicate camera",
                    "message": duplicate_check["error"],
                    "type": "duplicate",
                    "duplicateType": duplicate_check["type"],
                    "existingCollection": duplicate_check["existingCollection"]
                }
            )

        # Add the camera to the collection
        camera_data[collection_name][camera.ip] = camera.streamUrl

        # Save the updated configuration
        write_camera_config(camera_data)

        # Trigger stream restart for the new camera
        try:
            await restart_camera_stream(collection_name, camera.ip)
            logger.info(f"Successfully started stream for new camera {camera.ip} in collection {collection_name}")
        except Exception as stream_error:
            logger.warning(f"Camera added but failed to start stream: {stream_error}")

        return {
            "message": f"Camera '{camera.ip}' added to collection '{collection_name}' successfully",
            "camera": {
                "ip": camera.ip,
                "streamUrl": camera.streamUrl
            },
            "validation": {
                "ipValid": True,
                "streamUrlValid": True
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding camera to collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Update a camera in a collection
@router.put("/{collection_name}/cameras/{camera_ip}")
async def update_camera_in_collection(collection_name: str, camera_ip: str, camera: CameraAdd):
    try:
        camera_data = read_camera_config()

        if collection_name not in camera_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
            )

        if camera_ip not in camera_data[collection_name]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera '{camera_ip}' not found in collection '{collection_name}'"
            )

        # Store the old stream URL for comparison
        old_stream_url = camera_data[collection_name][camera_ip]

        # Preserve credentials from existing stream URL if new URL doesn't have them
        preserved_stream_url = preserve_credentials_in_stream_url(camera.streamUrl, old_stream_url)

        # Log credential preservation if it occurred
        if preserved_stream_url != camera.streamUrl:
            logger.info(f"Preserved credentials for camera {camera_ip}: {camera.streamUrl} -> {preserved_stream_url}")

        # Validate new IP address format and private range
        ip_validation = validate_private_ip(camera.ip)
        if not ip_validation["isValid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid IP address",
                    "message": ip_validation["error"],
                    "type": "validation"
                }
            )

        # Extract IP from stream URL and validate it as well
        extracted_ip = extract_ip_from_stream_url(preserved_stream_url)
        if extracted_ip:
            extracted_ip_validation = validate_private_ip(extracted_ip)
            if not extracted_ip_validation["isValid"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Invalid IP address in stream URL",
                        "message": f"The IP address '{extracted_ip}' extracted from the stream URL is not valid: {extracted_ip_validation['error']}",
                        "type": "validation"
                    }
                )

        # Check for duplicate cameras (excluding the current camera being updated)
        duplicate_check = check_duplicate_camera(
            camera_data,
            camera.ip,
            preserved_stream_url,
            exclude_collection=collection_name,
            exclude_ip=camera_ip
        )
        if duplicate_check["isDuplicate"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Duplicate camera",
                    "message": duplicate_check["error"],
                    "type": "duplicate",
                    "duplicateType": duplicate_check["type"],
                    "existingCollection": duplicate_check["existingCollection"]
                }
            )

        # Handle IP address change
        stream_restarted = False
        credentials_preserved = preserved_stream_url != camera.streamUrl

        if camera_ip != camera.ip:
            # IP address is changing - remove old entry and add new one
            del camera_data[collection_name][camera_ip]
            camera_data[collection_name][camera.ip] = preserved_stream_url

            # Stop old stream and start new one
            try:
                await stop_camera_stream(collection_name, camera_ip)
                await restart_camera_stream(collection_name, camera.ip)
                stream_restarted = True
                logger.info(f"Successfully restarted stream for camera IP change from {camera_ip} to {camera.ip}")
            except Exception as stream_error:
                logger.warning(f"Camera updated but failed to restart stream: {stream_error}")
        else:
            # IP address is the same, just update the stream URL
            camera_data[collection_name][camera_ip] = preserved_stream_url

            # Restart stream if URL changed (including credential preservation)
            if old_stream_url != preserved_stream_url:
                try:
                    await restart_camera_stream(collection_name, camera_ip)
                    stream_restarted = True
                    logger.info(f"Successfully restarted stream for camera {camera_ip} due to URL change")
                except Exception as stream_error:
                    logger.warning(f"Camera updated but failed to restart stream: {stream_error}")

        # Save the updated configuration
        write_camera_config(camera_data)

        return {
            "message": f"Camera updated in collection '{collection_name}' successfully",
            "camera": {
                "ip": camera.ip,
                "streamUrl": preserved_stream_url
            },
            "changes": {
                "ipChanged": camera_ip != camera.ip,
                "urlChanged": old_stream_url != preserved_stream_url,
                "streamRestarted": stream_restarted,
                "credentialsPreserved": credentials_preserved
            },
            "validation": {
                "ipValid": True,
                "streamUrlValid": True
            },
            "preservation": {
                "originalUrl": camera.streamUrl,
                "finalUrl": preserved_stream_url,
                "credentialsPreserved": credentials_preserved
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating camera in collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Remove a camera from a collection
@router.delete("/{collection_name}/cameras/{camera_ip}")
async def remove_camera_from_collection(collection_name: str, camera_ip: str):
    try:
        camera_data = read_camera_config()

        if collection_name not in camera_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
            )

        if camera_ip not in camera_data[collection_name]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Camera '{camera_ip}' not found in collection '{collection_name}'"
            )

        # Stop the camera stream before removing
        try:
            await stop_camera_stream(collection_name, camera_ip)
            logger.info(f"Successfully stopped stream for camera {camera_ip} before removal")
        except Exception as stream_error:
            logger.warning(f"Failed to stop stream before camera removal: {stream_error}")

        # Remove the camera from the collection
        del camera_data[collection_name][camera_ip]

        # Save the updated configuration
        write_camera_config(camera_data)

        return {
            "message": f"Camera '{camera_ip}' removed from collection '{collection_name}' successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing camera from collection: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Stream Management Functions
async def restart_camera_stream(collection_name: str, camera_ip: str):
    """Restart a camera stream by making a request to the main server"""
    import httpx

    try:
        # Use the restart stream endpoint from main.py
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:8000/restart-stream/{collection_name}/{camera_ip}")
            if response.status_code == 200:
                logger.info(f"Successfully restarted stream for {collection_name}/{camera_ip}")
                return response.json()
            else:
                logger.error(f"Failed to restart stream for {collection_name}/{camera_ip}: {response.text}")
                raise Exception(f"Stream restart failed with status {response.status_code}")
    except Exception as e:
        logger.error(f"Error restarting camera stream: {e}")
        raise

async def stop_camera_stream(collection_name: str, camera_ip: str):
    """Stop a camera stream by making a request to the main server"""
    import httpx

    try:
        stream_id = f"{collection_name}_{camera_ip}"
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"http://localhost:8000/api/stop_stream/{stream_id}")
            if response.status_code == 200:
                logger.info(f"Successfully stopped stream for {collection_name}/{camera_ip}")
                return response.json()
            else:
                logger.warning(f"Failed to stop stream for {collection_name}/{camera_ip}: {response.text}")
                # Don't raise exception for stop failures as it's not critical
    except Exception as e:
        logger.warning(f"Error stopping camera stream: {e}")
        # Don't raise exception for stop failures as it's not critical

# Validation Endpoints
@router.post("/validate-camera")
async def validate_camera_data(camera: CameraAdd, collection_name: Optional[str] = None, exclude_ip: Optional[str] = None):
    """Validate camera data without adding it to the database"""
    try:
        camera_data = read_camera_config()

        # Validate IP address format and private range
        ip_validation = validate_private_ip(camera.ip)
        if not ip_validation["isValid"]:
            return {
                "valid": False,
                "error": ip_validation["error"],
                "type": "ip_validation"
            }

        # Extract IP from stream URL and validate it as well
        extracted_ip = extract_ip_from_stream_url(camera.streamUrl)
        if extracted_ip:
            extracted_ip_validation = validate_private_ip(extracted_ip)
            if not extracted_ip_validation["isValid"]:
                return {
                    "valid": False,
                    "error": f"The IP address '{extracted_ip}' extracted from the stream URL is not valid: {extracted_ip_validation['error']}",
                    "type": "stream_url_validation"
                }

        # Check for duplicate cameras
        duplicate_check = check_duplicate_camera(
            camera_data,
            camera.ip,
            camera.streamUrl,
            exclude_collection=collection_name,
            exclude_ip=exclude_ip
        )
        if duplicate_check["isDuplicate"]:
            return {
                "valid": False,
                "error": duplicate_check["error"],
                "type": "duplicate",
                "duplicateType": duplicate_check["type"],
                "existingCollection": duplicate_check["existingCollection"]
            }

        return {
            "valid": True,
            "message": "Camera data is valid",
            "extractedIp": extracted_ip
        }
    except Exception as e:
        logger.error(f"Error validating camera data: {str(e)}")
        return {
            "valid": False,
            "error": f"Validation error: {str(e)}",
            "type": "server_error"
        }

# Smart IP Range Processing Endpoint
@router.post("/add-camera-range")
async def add_camera_range(camera_range: CameraRangeAdd):
    """
    Add multiple cameras from an IP range with intelligent duplicate handling.
    Skips duplicate IPs and continues processing the rest of the range.
    """
    try:
        camera_data = read_camera_config()

        # Validate collection exists
        if camera_range.collection_name not in camera_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{camera_range.collection_name}' not found"
            )

        # Generate IP range
        ip_list = generate_ip_range(camera_range.ip_start, camera_range.ip_end)

        # Results tracking
        results = {
            "total_ips": len(ip_list),
            "successful_cameras": [],
            "skipped_duplicates": [],
            "validation_errors": [],
            "processing_errors": []
        }

        # Process each IP in the range
        for current_ip in ip_list:
            try:
                # Validate IP format and private range
                ip_validation = validate_private_ip(current_ip)
                if not ip_validation["isValid"]:
                    results["validation_errors"].append({
                        "ip": current_ip,
                        "error": ip_validation["error"]
                    })
                    continue

                # Build RTSP URL with credential preservation logic
                main_stream_url = build_rtsp_url(
                    current_ip,
                    camera_range.username,
                    camera_range.password,
                    camera_range.port,
                    camera_range.main_stream,
                    camera_range.protocol
                )

                # Check for duplicates
                duplicate_check = check_duplicate_camera(camera_data, current_ip, main_stream_url)
                if duplicate_check["isDuplicate"]:
                    results["skipped_duplicates"].append({
                        "ip": current_ip,
                        "reason": duplicate_check["error"],
                        "existing_collection": duplicate_check["existingCollection"]
                    })
                    continue

                # Add camera to collection
                camera_data[camera_range.collection_name][current_ip] = main_stream_url

                # Generate camera name
                camera_name = f"{camera_range.camera_model} ({current_ip})" if len(ip_list) > 1 else camera_range.camera_model

                # Build analytic URL if provided
                analytic_url = ""
                if camera_range.analytic_stream:
                    analytic_url = build_rtsp_url(
                        current_ip,
                        camera_range.username,
                        camera_range.password,
                        camera_range.port,
                        camera_range.analytic_stream,
                        camera_range.protocol
                    )

                results["successful_cameras"].append({
                    "ip": current_ip,
                    "name": camera_name,
                    "stream_url": main_stream_url,
                    "analytic_url": analytic_url
                })

            except Exception as e:
                results["processing_errors"].append({
                    "ip": current_ip,
                    "error": str(e)
                })
                logger.error(f"Error processing camera {current_ip}: {str(e)}")

        # Save configuration if any cameras were added
        if results["successful_cameras"]:
            write_camera_config(camera_data)

            # Start streams for successfully added cameras
            for camera in results["successful_cameras"]:
                try:
                    await restart_camera_stream(camera_range.collection_name, camera["ip"])
                    logger.info(f"Successfully started stream for new camera {camera['ip']} in collection {camera_range.collection_name}")
                except Exception as stream_error:
                    logger.warning(f"Camera {camera['ip']} added but failed to start stream: {stream_error}")

        # Generate summary message
        summary_parts = []
        if results["successful_cameras"]:
            summary_parts.append(f"Successfully created {len(results['successful_cameras'])} cameras")
        if results["skipped_duplicates"]:
            summary_parts.append(f"Skipped {len(results['skipped_duplicates'])} duplicate IPs")
        if results["validation_errors"]:
            summary_parts.append(f"{len(results['validation_errors'])} validation errors")
        if results["processing_errors"]:
            summary_parts.append(f"{len(results['processing_errors'])} processing errors")

        summary = ". ".join(summary_parts) if summary_parts else "No cameras processed"

        return {
            "message": summary,
            "results": results,
            "collection_name": camera_range.collection_name
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_camera_range: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process camera range: {str(e)}"
        )
