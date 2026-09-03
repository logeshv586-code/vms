"""Runtime security helpers for the local VMS backend.

The VMS commonly handles credential-bearing RTSP URLs. These helpers keep credentials out of
logs and API payloads while preserving enough host/path information for diagnostics. The module
also hardens the legacy FastAPI bootstrap by replacing wildcard CORS origins with an explicit
local/UI allow-list without requiring every existing entry point to duplicate the policy.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_USERINFO_RE = re.compile(r"(?i)\b((?:rtsp|rtsps|http|https)://)([^/@\s]+)@")
_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key)=)([^&#\s]+)"
)
_DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "null",
)


def sanitize_text(value: Any) -> Any:
    """Redact credential-bearing URL userinfo and common secret query parameters."""
    if not isinstance(value, str):
        return value
    text = _USERINFO_RE.sub(r"\1***:***@", value)
    return _QUERY_SECRET_RE.sub(r"\1***", text)


def redact_url(value: Any) -> Any:
    """Return a diagnostics-safe URL without username/password or secret query values."""
    if not isinstance(value, str) or "://" not in value:
        return sanitize_text(value)

    try:
        parts = urlsplit(value)
        if not parts.scheme or not parts.netloc:
            return sanitize_text(value)

        host = parts.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if parts.port:
            host = f"{host}:{parts.port}"
        if parts.username is not None or parts.password is not None:
            host = f"***:***@{host}"

        redacted_query = []
        for key, item in parse_qsl(parts.query, keep_blank_values=True):
            if key.lower() in {
                "password", "passwd", "pwd", "token", "secret", "api_key", "apikey",
                "access_key", "accesskey",
            }:
                item = "***"
            redacted_query.append((key, item))
        return urlunsplit((parts.scheme, host, parts.path, urlencode(redacted_query), parts.fragment))
    except Exception:
        return sanitize_text(value)


def sanitize_payload(value: Any) -> Any:
    """Recursively redact URLs/secrets from diagnostics and API response structures."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            lower = str(key).lower()
            if lower in {"password", "passwd", "pwd", "token", "secret", "api_key", "apikey"}:
                result[key] = "***"
            else:
                result[key] = sanitize_payload(item)
        return result
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_payload(item) for item in value)
    if isinstance(value, str):
        return redact_url(value) if "://" in value else sanitize_text(value)
    return value


def get_allowed_origins(extra: Iterable[str] | None = None) -> list[str]:
    """Return explicit local/UI CORS origins, optionally extended by VMS_CORS_ORIGINS."""
    configured = os.getenv("VMS_CORS_ORIGINS", "")
    origins = list(_DEFAULT_CORS_ORIGINS)
    if configured:
        origins.extend(item.strip() for item in configured.split(",") if item.strip())
    if extra:
        origins.extend(str(item).strip() for item in extra if str(item).strip())

    deduped = []
    for origin in origins:
        if origin == "*" or origin in deduped:
            continue
        deduped.append(origin)
    return deduped


def install_cors_guard() -> None:
    """Harden legacy CORSMiddleware registrations that still pass allow_origins=['*']."""
    try:
        from starlette.middleware.cors import CORSMiddleware
    except Exception:
        return

    current = CORSMiddleware.__init__
    if getattr(current, "_vms_cors_guard", False):
        return

    original = current

    def secure_init(
        self,
        app,
        allow_origins=(),
        allow_methods=("GET",),
        allow_headers=(),
        allow_credentials=False,
        allow_origin_regex=None,
        expose_headers=(),
        max_age=600,
    ):
        origins = list(allow_origins or [])
        if "*" in origins:
            origins = get_allowed_origins()
        return original(
            self,
            app,
            allow_origins=origins,
            allow_methods=allow_methods,
            allow_headers=allow_headers,
            allow_credentials=allow_credentials,
            allow_origin_regex=allow_origin_regex,
            expose_headers=expose_headers,
            max_age=max_age,
        )

    secure_init._vms_cors_guard = True
    CORSMiddleware.__init__ = secure_init


def install_json_redaction() -> None:
    """Redact secrets from all Starlette/FastAPI JSON responses before serialization."""
    try:
        from starlette.responses import JSONResponse
    except Exception:
        return

    current = JSONResponse.render
    if getattr(current, "_vms_json_redaction", False):
        return

    original = current

    def secure_render(self, content):
        return original(self, sanitize_payload(content))

    secure_render._vms_json_redaction = True
    JSONResponse.render = secure_render


def install_log_redaction() -> None:
    """Install one process-wide LogRecord factory that redacts credentials before handlers run."""
    current = logging.getLogRecordFactory()
    if getattr(current, "_vms_redacting_factory", False):
        return

    previous = current

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.msg = sanitize_text(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(sanitize_payload(item) for item in record.args)
        elif isinstance(record.args, dict):
            record.args = sanitize_payload(record.args)
        return record

    factory._vms_redacting_factory = True
    logging.setLogRecordFactory(factory)


__all__ = [
    "get_allowed_origins",
    "install_cors_guard",
    "install_json_redaction",
    "install_log_redaction",
    "redact_url",
    "sanitize_payload",
    "sanitize_text",
]
