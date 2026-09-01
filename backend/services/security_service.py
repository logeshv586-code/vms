"""
Eagle VMS Security Service
Implements core security controls:
- Bcrypt password hashing
- JWT authentication & session token management
- Account lockout & login rate limiting
- AES-256-GCM credential encryption at rest
- Structured audit logging
- Input validation (path traversal, RTSP URLs, filename sanitization)
"""

import os
import re
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

# ── Load Security Configuration ─────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "4kZ9mP7xW2qL8vY1nR5kT0sA3bC6dE9fG2hJ5mL8nP1rS4tU7vX0yZ3aB6cD9eF2gH5jK8mN1pQ4rT7uW0zY3aB6c")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_HOURS", "8"))
JWT_REFRESH_TOKEN_EXPIRE_HOURS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_HOURS", "24"))
VMS_MASTER_KEY = os.getenv("VMS_MASTER_KEY", "k9F3mP7zW2qL8vY1nR5kT0sA3bC6dE9fG2hJ5mL8nP1B")
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))

# ── Audit Log Setup ──────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BACKEND_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_LOG_PATH = LOGS_DIR / "audit.log"

# ── State Containers ────────────────────────────────────────────────────────
# Revoked tokens (in-memory token blacklist for immediate revocation on logout)
REVOKED_TOKENS: Dict[str, float] = {}

# Failed login attempt tracking: {username_or_ip: [timestamp1, timestamp2, ...]}
FAILED_ATTEMPTS: Dict[str, List[float]] = {}


# ── Audit Logging ────────────────────────────────────────────────────────────
def log_audit(event_type: str, username: Optional[str] = None, ip_address: Optional[str] = None, details: Optional[Dict[str, Any]] = None, status: str = "SUCCESS"):
    """
    Log a structured security event to backend/logs/audit.log.
    """
    try:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "username": username or "anonymous",
            "ip_address": ip_address or "unknown",
            "status": status,
            "details": details or {}
        }
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to audit log: {e}")


# ── Bcrypt Password Hashing ─────────────────────────────────────────────────
def is_bcrypt_hash(value: str) -> bool:
    """Check if a string is a bcrypt hash ($2a$, $2b$, or $2y$)."""
    if not value or not isinstance(value, str):
        return False
    return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt with cost factor 12."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(password: str, hashed_or_plain: str) -> bool:
    """
    Verify password against bcrypt hash or legacy plaintext password.
    """
    if not hashed_or_plain:
        return False
    if is_bcrypt_hash(hashed_or_plain):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed_or_plain.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error checking bcrypt password: {e}")
            return False
    # Legacy fallback check (will be transparently upgraded on load/login)
    return password == hashed_or_plain


# ── Rate Limiting & Account Lockout ─────────────────────────────────────────
def check_account_lockout(key: str) -> Tuple[bool, int]:
    """
    Check if an account or IP is currently locked out.
    Returns: (is_locked, remaining_lockout_seconds)
    """
    now = time.time()
    attempts = FAILED_ATTEMPTS.get(key, [])
    
    # Filter attempts within the lockout window
    recent_attempts = [t for t in attempts if now - t < LOGIN_LOCKOUT_SECONDS]
    FAILED_ATTEMPTS[key] = recent_attempts
    
    if len(recent_attempts) >= LOGIN_MAX_ATTEMPTS:
        oldest_relevant = recent_attempts[0]
        remaining = int(LOGIN_LOCKOUT_SECONDS - (now - oldest_relevant))
        return True, max(1, remaining)
        
    return False, 0

def record_failed_login(key: str, username: str, ip: str = "unknown"):
    """Record a failed login attempt and log audit event."""
    now = time.time()
    attempts = FAILED_ATTEMPTS.get(key, [])
    attempts.append(now)
    FAILED_ATTEMPTS[key] = attempts
    
    recent_count = len([t for t in attempts if now - t < LOGIN_LOCKOUT_SECONDS])
    
    if recent_count >= LOGIN_MAX_ATTEMPTS:
        log_audit(
            event_type="ACCOUNT_LOCKED",
            username=username,
            ip_address=ip,
            details={"attempts": recent_count, "lockout_seconds": LOGIN_LOCKOUT_SECONDS},
            status="LOCKED"
        )
    else:
        log_audit(
            event_type="LOGIN_FAILED",
            username=username,
            ip_address=ip,
            details={"failed_attempts": recent_count, "max_allowed": LOGIN_MAX_ATTEMPTS},
            status="FAILURE"
        )

def reset_failed_logins(key: str):
    """Clear failed login attempts counter on successful login."""
    if key in FAILED_ATTEMPTS:
        del FAILED_ATTEMPTS[key]


import uuid

# Unique identifier for the current running backend process instance
SERVER_BOOT_ID = str(uuid.uuid4())

def get_server_boot_id() -> str:
    """Return the unique boot ID for the currently running backend instance."""
    return SERVER_BOOT_ID

# ── JWT Authentication ───────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    """Create a signed JWT access token (8 hour expiration by default)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "boot_id": SERVER_BOOT_ID
    })
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """Create a signed JWT refresh token (24 hour expiration by default)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_REFRESH_TOKEN_EXPIRE_HOURS)
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "boot_id": SERVER_BOOT_ID
    })
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token, ensuring it was issued by the current backend instance."""
    if is_token_revoked(token):
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        # Reject token if issued by a previous backend run
        if payload.get("boot_id") != SERVER_BOOT_ID:
            logger.info("Token boot_id mismatch (backend was closed/restarted). Token rejected.")
            return None
        return payload
    except jwt.PyJWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None

def revoke_token(token: str):
    """Revoke a token immediately (used on logout)."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
        exp = payload.get("exp", time.time() + 86400)
        REVOKED_TOKENS[token] = exp
    except Exception as e:
        logger.warning(f"Could not parse token for revocation: {e}")

def is_token_revoked(token: str) -> bool:
    """Check if token is in the revocation blacklist."""
    now = time.time()
    # Cleanup expired tokens from blacklist periodically
    expired = [t for t, exp in REVOKED_TOKENS.items() if exp < now]
    for t in expired:
        del REVOKED_TOKENS[t]
        
    return token in REVOKED_TOKENS


# ── AES-256-GCM Credential Encryption ───────────────────────────────────────
def _get_aes_key() -> bytes:
    """Derive 256-bit key from VMS_MASTER_KEY using HKDF."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"eagle_vms_salt",
        info=b"camera_credential_encryption",
    )
    return hkdf.derive(VMS_MASTER_KEY.encode("utf-8"))

def encrypt_credential(plaintext: str) -> str:
    """
    Encrypt camera RTSP credential using AES-256-GCM.
    Returns string in format enc:gcm:<nonce_hex>:<ciphertext_hex>
    """
    if not plaintext:
        return ""
    if plaintext.startswith("enc:gcm:"):
        return plaintext  # Already encrypted
        
    key = _get_aes_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return f"enc:gcm:{nonce.hex()}:{ciphertext.hex()}"

def decrypt_credential(encrypted_str: str) -> str:
    """
    Decrypt camera RTSP credential encrypted with AES-256-GCM.
    Returns plaintext string. If not encrypted, returns original string.
    """
    if not encrypted_str or not isinstance(encrypted_str, str):
        return encrypted_str or ""
    if not encrypted_str.startswith("enc:gcm:"):
        return encrypted_str  # Plaintext string
        
    try:
        parts = encrypted_str.split(":")
        if len(parts) != 4:
            return encrypted_str
        nonce = bytes.fromhex(parts[2])
        ciphertext = bytes.fromhex(parts[3])
        key = _get_aes_key()
        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception as e:
        logger.error(f"Error decrypting credential: {e}")
        return encrypted_str


# ── Input Validation & Sanitization ─────────────────────────────────────────
def sanitize_path(base_dir: str, file_path: str) -> Optional[Path]:
    """
    Prevent path traversal by verifying target path resides within base_dir.
    Returns Path object if safe, None if path traversal attempt detected.
    """
    try:
        base = Path(base_dir).resolve()
        target = (base / file_path).resolve()
        if base in target.parents or target == base:
            return target
        logger.warning(f"Path traversal blocked: {file_path} attempting to leave {base_dir}")
        return None
    except Exception as e:
        logger.error(f"Error sanitizing path: {e}")
        return None

def validate_rtsp_url(url: str) -> bool:
    """Validate RTSP URL pattern."""
    if not url or not isinstance(url, str):
        return False
    rtsp_pattern = r"^rtsp://([a-zA-Z0-9_.~%-]+(:[a-zA-Z0-9_.~%-]+)?@)?[a-zA-Z0-9._%-]+(:[0-9]+)?(/.*)?$"
    return bool(re.match(rtsp_pattern, url))

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent command injection / directory traversal."""
    if not filename:
        return "unnamed"
    # Remove directory separators and illegal characters
    cleaned = os.path.basename(filename)
    cleaned = re.sub(r"[^\w\-. ]", "_", cleaned)
    return cleaned
