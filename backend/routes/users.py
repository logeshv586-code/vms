from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
import json
import os
import logging
import re
from typing import List, Optional, Dict

from services.security_service import (
    hash_password,
    verify_password,
    is_bcrypt_hash,
    check_account_lockout,
    record_failed_login,
    reset_failed_logins,
    create_access_token,
    create_refresh_token,
    decode_token,
    revoke_token,
    log_audit,
    get_server_boot_id
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the backend directory
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
USERS_CONFIG_PATH = os.path.join(BACKEND_DIR, "data/users.json")

# Store the last modification time of the users.json file
last_modified_time = 0
# Store the cached configuration
cached_config = None

# Create router
router = APIRouter(prefix="/api/augment/users", tags=["users"])

# Define models
class UserPermissions(BaseModel):
    searchCameras: bool = False
    configureCameras: bool = False
    createSchedules: bool = False
    ptzControl: bool = False
    manageStorage: bool = False
    manageUser: bool = False
    actOnEvents: bool = False
    archivePlay: bool = False
    locationGroupConfig: bool = False
    clipDownload: bool = False
    reportDownload: bool = False
    unmaskedLivePlay: bool = False
    unmaskedArchivePlay: bool = False

class User(BaseModel):
    username: str
    password: str
    role: str
    permissions: UserPermissions
    created_by: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    permissions: Dict[str, bool]

class LoginRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    token: Optional[str] = None

class LoginResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None

# Helper function to load users configuration with auto bcrypt migration
def load_users_config():
    global last_modified_time, cached_config

    try:
        if not os.path.exists(USERS_CONFIG_PATH):
            logger.warning(f"Users configuration file not found at {USERS_CONFIG_PATH}")
            return {"users": []}

        current_modified_time = os.path.getmtime(USERS_CONFIG_PATH)

        if cached_config is not None and current_modified_time <= last_modified_time:
            return cached_config

        logger.info(f"Loading users configuration from {USERS_CONFIG_PATH} (modified at {current_modified_time})")
        with open(USERS_CONFIG_PATH, "r") as f:
            data = json.load(f)

            if isinstance(data, list):
                data = {"users": data}

            # Check if any user password requires auto bcrypt hashing migration
            needs_save = False
            for u in data.get("users", []):
                pwd = u.get("password", "")
                if pwd and not is_bcrypt_hash(pwd):
                    u["password"] = hash_password(pwd)
                    needs_save = True
                    logger.info(f"Migrated user '{u.get('username')}' password to bcrypt hash.")

            if needs_save:
                save_users_config(data)
                # reload modified time
                current_modified_time = os.path.getmtime(USERS_CONFIG_PATH)

            last_modified_time = current_modified_time
            cached_config = data
            return data
    except Exception as e:
        logger.error(f"Error loading users configuration: {str(e)}")
        return {"users": []}

# Helper function to save users configuration
def save_users_config(config):
    global last_modified_time, cached_config

    try:
        if isinstance(config, dict) and "users" in config:
            data_to_save = {"users": config["users"]}
        else:
            data_to_save = {"users": config}

        os.makedirs(os.path.dirname(USERS_CONFIG_PATH), exist_ok=True)

        with open(USERS_CONFIG_PATH, "w") as f:
            json.dump(data_to_save, f, indent=2)

        cached_config = None
        last_modified_time = 0
        return True
    except Exception as e:
        logger.error(f"Error saving users configuration: {str(e)}")
        return False

# Login endpoint
@router.post("/login")
async def login(login_data: LoginRequest, request: Request):
    try:
        client_ip = request.client.host if request.client else "unknown"
        lockout_key = f"{login_data.username.lower()}_{client_ip}"
        
        # 1. Rate limiting & Account lockout check
        is_locked, remaining_sec = check_account_lockout(lockout_key)
        if is_locked:
            minutes = max(1, remaining_sec // 60)
            log_audit(
                event_type="LOGIN_BLOCKED_LOCKOUT",
                username=login_data.username,
                ip_address=client_ip,
                details={"remaining_seconds": remaining_sec},
                status="BLOCKED"
            )
            return {
                "success": False,
                "error": f"Account locked due to 5 failed login attempts. Please try again after {minutes} minutes."
            }

        config = load_users_config()
        users = config.get("users", [])

        # Find user by username
        user = next((u for u in users if u["username"].lower() == login_data.username.lower()), None)

        if not user or not verify_password(login_data.password, user["password"]):
            # Record failed login attempt
            record_failed_login(lockout_key, login_data.username, client_ip)
            return {
                "success": False,
                "error": "Invalid username or password"
            }

        # Check role restriction if provided
        if login_data.role and user.get("role") != login_data.role:
            record_failed_login(lockout_key, login_data.username, client_ip)
            return {
                "success": False,
                "error": f"User exists but is not a {login_data.role}"
            }

        # Reset failed login count on successful auth
        reset_failed_logins(lockout_key)

        # Build payload & issue JWT access and refresh tokens
        user_data = {k: v for k, v in user.items() if k != "password"}
        current_boot_id = get_server_boot_id()

        token_payload = {
            "sub": str(user["id"]),
            "username": user["username"],
            "role": user["role"],
            "permissions": user.get("permissions", {})
        }
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        # Attach session metadata directly to user object
        import time as _time
        user_data["server_boot_id"] = current_boot_id
        user_data["access_token"] = access_token
        user_data["login_time"] = int(_time.time() * 1000)

        log_audit(
            event_type="LOGIN_SUCCESS",
            username=user["username"],
            ip_address=client_ip,
            details={"role": user["role"]},
            status="SUCCESS"
        )

        return {
            "success": True,
            "data": {
                "user": user_data,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "server_boot_id": current_boot_id
            },
            "message": "Login successful"
        }
    except Exception as e:
        logger.error(f"Error during login: {str(e)}")
        return {
            "success": False,
            "error": f"Login failed: {str(e)}"
        }

@router.get("/verify-session")
async def verify_session(server_boot_id: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """
    Verify if session is valid for the current backend instance.
    If backend restarted, server_boot_id will mismatch, invalidating the session.
    """
    active_boot_id = get_server_boot_id()

    if server_boot_id and server_boot_id != active_boot_id:
        return {
            "success": False,
            "valid": False,
            "reason": "Backend server restarted. Authentication required."
        }

    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        payload = decode_token(token)
        if not payload:
            return {
                "success": False,
                "valid": False,
                "reason": "Session token invalid or expired due to server restart."
            }

    if server_boot_id == active_boot_id:
        return {
            "success": True,
            "valid": True,
            "server_boot_id": active_boot_id
        }

    return {
        "success": False,
        "valid": False,
        "reason": "No valid session provided."
    }

@router.post("/refresh")
async def refresh_token(request_data: RefreshTokenRequest, request: Request):
    """Refresh JWT access token using valid refresh token."""
    client_ip = request.client.host if request.client else "unknown"
    payload = decode_token(request_data.refresh_token)
    
    if not payload or payload.get("type") != "refresh":
        log_audit("TOKEN_REFRESH_FAILED", ip_address=client_ip, status="FAILURE")
        return {"success": False, "error": "Invalid or expired refresh token"}

    token_payload = {
        "sub": payload.get("sub"),
        "username": payload.get("username"),
        "role": payload.get("role"),
        "permissions": payload.get("permissions", {})
    }
    new_access_token = create_access_token(token_payload)
    new_refresh_token = create_refresh_token(token_payload)
    
    # Revoke old refresh token (refresh token rotation)
    revoke_token(request_data.refresh_token)

    log_audit("TOKEN_REFRESH_SUCCESS", username=payload.get("username"), ip_address=client_ip, status="SUCCESS")

    return {
        "success": True,
        "data": {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    }

@router.post("/logout")
async def logout(logout_data: Optional[LogoutRequest] = None, authorization: Optional[str] = Header(None), request: Request = None):
    """Logout user and revoke tokens."""
    client_ip = request.client.host if (request and request.client) else "unknown"
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
    elif logout_data and logout_data.token:
        token = logout_data.token

    if token:
        payload = decode_token(token)
        username = payload.get("username") if payload else "unknown"
        revoke_token(token)
        log_audit("LOGOUT_SUCCESS", username=username, ip_address=client_ip, status="SUCCESS")

    return {"success": True, "message": "Logged out successfully"}

# Get all users
@router.get("")
async def get_users():
    try:
        config = load_users_config()
        # Remove passwords from response
        users = [{k: v for k, v in user.items() if k != "password"} for user in config["users"]]

        return {
            "success": True,
            "data": users,
            "message": "Users retrieved successfully"
        }
    except Exception as e:
        logger.error(f"Error getting users: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to retrieve users: {str(e)}"
        }

# Helper function to validate password
def validate_password(password, role):
    # Only validate for Admin and Supervisor roles
    if role in ["Admin", "Supervisor"]:
        # Password must be at least 8 characters long and include uppercase, lowercase, number, and special character
        pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).{8,}$"
        if not re.match(pattern, password):
            return False
    return True

# Create a new user
@router.post("")
async def create_user(user: User):
    try:
        config = load_users_config()
        users = config["users"]

        # Check if username already exists
        if any(u["username"] == user.username for u in users):
            return {
                "success": False,
                "error": f"Username '{user.username}' already exists"
            }

        # Validate password for Admin and Supervisor roles
        if not validate_password(user.password, user.role):
            return {
                "success": False,
                "error": "Password must be at least 8 characters long and include uppercase, lowercase, number, and special character"
            }

        # Generate new ID
        new_id = 1
        if users:
            new_id = max(u["id"] for u in users) + 1

        # Create new user with bcrypt hashed password
        hashed_pwd = hash_password(user.password)
        new_user = {
            "id": new_id,
            "username": user.username,
            "password": hashed_pwd,
            "role": user.role,
            "permissions": user.permissions.dict(),
            "created_by": user.created_by
        }

        # Add to list
        users.append(new_user)

        # Save configuration
        if save_users_config(config):
            log_audit(
                event_type="USER_CREATED",
                username=user.created_by or "system",
                details={"new_username": user.username, "role": user.role},
                status="SUCCESS"
            )
            # Remove password from response
            user_data = {k: v for k, v in new_user.items() if k != "password"}
            return {
                "success": True,
                "data": user_data,
                "message": "User created successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to create user: {str(e)}"
        }

# Update user permissions
@router.put("/{user_id}/permissions")
async def update_user_permissions(user_id: int, permissions: dict, current_user_id: Optional[int] = None, current_user_role: Optional[str] = None):
    try:
        config = load_users_config()
        users = config["users"]

        # Find user by ID
        user_index = next((i for i, u in enumerate(users) if u["id"] == user_id), None)
        if user_index is None:
            logger.warning(f"User with ID {user_id} not found")
            return {
                "success": False,
                "error": f"User with ID {user_id} not found"
            }

        # Log the received permissions for debugging
        logger.info(f"Updating permissions for user {user_id}: {permissions}")

        # Get the user to update
        user_to_update = users[user_index]

        # Check if permissions is nested (has a 'permissions' key)
        if 'permissions' in permissions:
            # Extract the inner permissions object
            permissions = permissions['permissions']

        # If current_user_id is provided, validate that the user has permission to make these changes
        if current_user_id and current_user_role:
            # Find the current user
            current_user = next((u for u in users if u["id"] == current_user_id), None)
            if not current_user:
                logger.warning(f"Current user with ID {current_user_id} not found")
                return {
                    "success": False,
                    "error": "Current user not found"
                }

            # If current user is Admin, they can only grant permissions they have
            if current_user_role == 'Admin' and user_to_update["role"] == 'Supervisor':
                logger.info(f"Validating Admin permissions for {current_user['username']}")

                # Check each permission being granted
                for perm_id, is_granted in permissions.items():
                    # If trying to grant a permission
                    if is_granted:
                        # Check if Admin has this permission
                        if not current_user["permissions"].get(perm_id, False):
                            logger.warning(f"Admin {current_user['username']} attempted to grant permission {perm_id} they don't have")
                            return {
                                "success": False,
                                "error": f"You cannot grant permission '{perm_id}' that you don't have yourself"
                            }

                        # Special case: Admin can't grant manageUser permission to Supervisors
                        if perm_id == 'manageUser':
                            logger.warning(f"Admin {current_user['username']} attempted to grant manageUser permission to Supervisor {user_to_update['username']}")
                            return {
                                "success": False,
                                "error": "Admins cannot grant 'Manage User' permission to Supervisors"
                            }

        # Update permissions
        users[user_index]["permissions"] = permissions

        # If we're updating an Admin's permissions, also update their Supervisors' permissions
        if user_to_update["role"] == "Admin":
            logger.info(f"Admin {user_to_update['username']} permissions changed, updating their Supervisors")

            # Find all Supervisors created by this Admin
            supervisors_updated = 0
            for i, user in enumerate(users):
                if user["role"] == "Supervisor" and user.get("created_by") == user_to_update["username"]:
                    logger.info(f"Checking Supervisor {user['username']} permissions")

                    # Create a copy of the Supervisor's permissions
                    updated_supervisor_permissions = user["permissions"].copy()
                    permissions_changed = False

                    # For each permission, if Admin lost it, Supervisor should lose it too
                    for perm_id, supervisor_has_perm in user["permissions"].items():
                        if supervisor_has_perm and not permissions.get(perm_id, False):
                            logger.info(f"Removing permission {perm_id} from Supervisor {user['username']}")
                            updated_supervisor_permissions[perm_id] = False
                            permissions_changed = True

                    # Update the Supervisor's permissions if needed
                    if permissions_changed:
                        users[i]["permissions"] = updated_supervisor_permissions
                        supervisors_updated += 1
                        logger.info(f"Updated Supervisor {user['username']} permissions")

            if supervisors_updated > 0:
                logger.info(f"Updated permissions for {supervisors_updated} Supervisors")

        # Save configuration
        if save_users_config(config):
            # Remove password from response
            user_data = {k: v for k, v in users[user_index].items() if k != "password"}
            logger.info(f"Successfully updated permissions for user {user_to_update['username']}")
            return {
                "success": True,
                "data": user_data,
                "message": "Permissions updated successfully"
            }
        else:
            logger.error("Failed to save configuration after updating permissions")
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        logger.error(f"Error updating permissions: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to update permissions: {str(e)}"
        }

# Helper function to determine if a user can delete another user
def can_delete_user(deleter, target_user):
    # Cannot delete self
    if deleter["id"] == target_user["id"]:
        return False

    # SuperAdmin can delete any Admin or Supervisor, but not other SuperAdmins
    if deleter["role"] == "SuperAdmin":
        return target_user["role"] != "SuperAdmin"

    # Admin can only delete Supervisors they created
    if deleter["role"] == "Admin":
        return (
            target_user["role"] == "Supervisor" and
            target_user.get("created_by") == deleter["username"]
        )

    # Supervisors cannot delete anyone
    return False

# Delete a user
@router.delete("/{user_id}")
async def delete_user(user_id: int, current_user_id: Optional[int] = None, current_user_role: Optional[str] = None, current_user_username: Optional[str] = None):
    try:
        logger.info(f"Attempting to delete user with ID: {user_id}")
        logger.info(f"Current user info - ID: {current_user_id}, Role: {current_user_role}, Username: {current_user_username}")

        config = load_users_config()
        users = config["users"]

        # Log the current users before deletion
        logger.info(f"Current users before deletion: {[u['username'] for u in users]}")

        # Find user by ID
        user_index = next((i for i, u in enumerate(users) if u["id"] == user_id), None)
        if user_index is None:
            logger.warning(f"User with ID {user_id} not found")
            return {
                "success": False,
                "error": f"User with ID {user_id} not found"
            }

        user_to_delete = users[user_index]
        logger.info(f"Found user to delete: {user_to_delete['username']} (ID: {user_to_delete['id']}, Role: {user_to_delete['role']})")

        # Check if it's the last SuperAdmin
        if user_to_delete["role"] == "SuperAdmin" and len([u for u in users if u["role"] == "SuperAdmin"]) <= 1:
            logger.warning("Cannot delete the last SuperAdmin user")
            return {
                "success": False,
                "error": "Cannot delete the last SuperAdmin user"
            }

        # Apply deletion rules if current user info is provided
        if current_user_id and current_user_role and current_user_username:
            # Find the current user
            current_user = next((u for u in users if u["id"] == current_user_id), None)
            if not current_user:
                logger.warning(f"Current user with ID {current_user_id} not found")
                return {
                    "success": False,
                    "error": "Current user not found"
                }

            # Check if the current user can delete the target user
            if not can_delete_user(current_user, user_to_delete):
                logger.warning(f"User {current_user['username']} does not have permission to delete {user_to_delete['username']}")
                return {
                    "success": False,
                    "error": "You do not have permission to delete this user"
                }

        # Remove user
        deleted_user = users.pop(user_index)
        logger.info(f"Removed user {deleted_user['username']} from users list")

        # Log the users after deletion
        logger.info(f"Users after deletion: {[u['username'] for u in users]}")

        # Save configuration
        if save_users_config(config):
            logger.info(f"Successfully saved configuration after deleting user {deleted_user['username']}")
            return {
                "success": True,
                "message": f"User '{deleted_user['username']}' deleted successfully"
            }
        else:
            logger.error("Failed to save configuration after user deletion")
            raise HTTPException(status_code=500, detail="Failed to save configuration")
    except Exception as e:
        logger.error(f"Error deleting user: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to delete user: {str(e)}"
        }

# Function to synchronize supervisor permissions with their admin's permissions
def synchronize_supervisor_permissions():
    try:
        logger.info("Synchronizing supervisor permissions with their admin's permissions")
        config = load_users_config()
        users = config["users"]

        # Create a dictionary of admins by username for quick lookup
        admins = {user["username"]: user for user in users if user["role"] == "Admin"}

        # Track supervisors that need updates
        supervisors_to_update = []

        # Check each supervisor
        for i, user in enumerate(users):
            if user["role"] == "Supervisor" and user.get("created_by") in admins:
                admin = admins[user["created_by"]]
                logger.info(f"Checking Supervisor {user['username']} created by Admin {admin['username']}")

                # Create a copy of the supervisor's permissions
                updated_permissions = user["permissions"].copy()
                permissions_changed = False

                # For each permission, if supervisor has it but admin doesn't, remove it
                for perm_id, has_perm in user["permissions"].items():
                    if has_perm and not admin["permissions"].get(perm_id, False):
                        logger.info(f"Removing permission {perm_id} from Supervisor {user['username']} (Admin {admin['username']} doesn't have it)")
                        updated_permissions[perm_id] = False
                        permissions_changed = True

                # Special case: manageUser should always be false for supervisors
                if updated_permissions.get("manageUser", False):
                    logger.info(f"Removing manageUser permission from Supervisor {user['username']}")
                    updated_permissions["manageUser"] = False
                    permissions_changed = True

                # If permissions changed, update the supervisor
                if permissions_changed:
                    users[i]["permissions"] = updated_permissions
                    supervisors_to_update.append(user["username"])

        # Save the configuration if any supervisors were updated
        if supervisors_to_update:
            logger.info(f"Updating permissions for supervisors: {supervisors_to_update}")
            if save_users_config(config):
                logger.info("Successfully synchronized supervisor permissions")
            else:
                logger.error("Failed to save configuration after synchronizing permissions")
        else:
            logger.info("No supervisor permissions needed to be synchronized")

    except Exception as e:
        logger.error(f"Error synchronizing supervisor permissions: {str(e)}")

# Run the synchronization when the module is loaded
synchronize_supervisor_permissions()
