# Services package initialization
# Importing any backend service installs log redaction before camera URLs are emitted.
from .security_runtime import install_log_redaction

install_log_redaction()
