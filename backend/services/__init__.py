# Services package initialization
# Importing any backend service installs process-wide safety before camera URLs are emitted and
# before FastAPI materializes its middleware stack.
from .security_runtime import install_cors_guard, install_json_redaction, install_log_redaction

install_log_redaction()
install_json_redaction()
install_cors_guard()
