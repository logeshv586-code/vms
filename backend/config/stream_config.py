"""
Stream configuration settings for RTSP connections
This file contains configurable parameters for improving stream stability
"""

import os

class StreamConfig:
    """Configuration class for RTSP stream settings"""

    # Connection timeout settings (in seconds)
    RTSP_OPEN_TIMEOUT = int(os.environ.get("RTSP_OPEN_TIMEOUT", "45"))  # Time to wait for initial connection
    RTSP_READ_TIMEOUT = int(os.environ.get("RTSP_READ_TIMEOUT", "90"))  # Time to wait for frame reads

    # Reconnection settings
    MAX_RECONNECT_ATTEMPTS = int(os.environ.get("MAX_RECONNECT_ATTEMPTS", "10"))
    RECONNECT_BASE_DELAY = int(os.environ.get("RECONNECT_BASE_DELAY", "2"))  # Base delay for exponential backoff
    MAX_RECONNECT_DELAY = int(os.environ.get("MAX_RECONNECT_DELAY", "60"))  # Maximum delay between reconnections

    # Frame handling settings
    MAX_FRAME_RETRIES = int(os.environ.get("MAX_FRAME_RETRIES", "5"))
    FRAME_TIMEOUT_THRESHOLD = int(os.environ.get("FRAME_TIMEOUT_THRESHOLD", "60"))  # Seconds without frames before reconnect

    # Buffer settings
    BUFFER_SIZE_STABLE = int(os.environ.get("BUFFER_SIZE_STABLE", "3"))  # Buffer size for stable connections
    BUFFER_SIZE_UNSTABLE = int(os.environ.get("BUFFER_SIZE_UNSTABLE", "4"))  # Buffer size for unstable connections

    # Frame rate settings
    TARGET_FPS_STABLE = int(os.environ.get("TARGET_FPS_STABLE", "24"))  # FPS for stable connections
    TARGET_FPS_UNSTABLE = int(os.environ.get("TARGET_FPS_UNSTABLE", "15"))  # FPS for unstable connections

    # Health check settings
    HEALTH_CHECK_INTERVAL = int(os.environ.get("HEALTH_CHECK_INTERVAL", "30"))  # Seconds between health checks
    CONNECTION_TEST_FRAMES = int(os.environ.get("CONNECTION_TEST_FRAMES", "5"))  # Number of frames to test on connection
    MIN_SUCCESSFUL_TEST_FRAMES = int(os.environ.get("MIN_SUCCESSFUL_TEST_FRAMES", "3"))  # Minimum successful test frames

    # Error handling settings
    TIMEOUT_ERROR_DELAY = int(os.environ.get("TIMEOUT_ERROR_DELAY", "15"))  # Delay after timeout errors
    GENERAL_ERROR_DELAY = int(os.environ.get("GENERAL_ERROR_DELAY", "30"))  # Delay after general errors
    CRITICAL_ERROR_DELAY = int(os.environ.get("CRITICAL_ERROR_DELAY", "300"))  # Delay after critical errors (5 minutes)

    # Connection method configurations
    CONNECTION_METHODS = [
        {
            'name': 'TCP with extended timeouts',
            'url_suffix': '?tcp',
            'timeout_open_ms': RTSP_OPEN_TIMEOUT * 1000,
            'timeout_read_ms': RTSP_READ_TIMEOUT * 1000,
            'buffer_size': BUFFER_SIZE_STABLE
        },
        {
            'name': 'Original URL with standard timeouts',
            'url_suffix': '',
            'timeout_open_ms': (RTSP_OPEN_TIMEOUT - 10) * 1000,
            'timeout_read_ms': (RTSP_READ_TIMEOUT - 15) * 1000,
            'buffer_size': BUFFER_SIZE_STABLE - 1
        },
        {
            'name': 'TCP with maximum timeouts',
            'url_suffix': '',
            'timeout_open_ms': RTSP_OPEN_TIMEOUT * 1000,
            'timeout_read_ms': RTSP_READ_TIMEOUT * 1000,
            'buffer_size': BUFFER_SIZE_UNSTABLE
        },
        {
            'name': 'UDP fallback',
            'url_suffix': '?udp',
            'timeout_open_ms': (RTSP_OPEN_TIMEOUT - 20) * 1000,
            'timeout_read_ms': (RTSP_READ_TIMEOUT - 30) * 1000,
            'buffer_size': BUFFER_SIZE_STABLE - 1
        }
    ]

    @classmethod
    def get_connection_method(cls, index):
        """Get connection method configuration by index"""
        if 0 <= index < len(cls.CONNECTION_METHODS):
            return cls.CONNECTION_METHODS[index]
        return None

    @classmethod
    def get_all_connection_methods(cls):
        """Get all connection method configurations"""
        return cls.CONNECTION_METHODS

    @classmethod
    def print_config(cls):
        """Print current configuration for debugging"""
        print("=== Stream Configuration ===")
        print(f"RTSP_OPEN_TIMEOUT: {cls.RTSP_OPEN_TIMEOUT}s")
        print(f"RTSP_READ_TIMEOUT: {cls.RTSP_READ_TIMEOUT}s")
        print(f"MAX_RECONNECT_ATTEMPTS: {cls.MAX_RECONNECT_ATTEMPTS}")
        print(f"MAX_FRAME_RETRIES: {cls.MAX_FRAME_RETRIES}")
        print(f"FRAME_TIMEOUT_THRESHOLD: {cls.FRAME_TIMEOUT_THRESHOLD}s")
        print(f"BUFFER_SIZE_STABLE: {cls.BUFFER_SIZE_STABLE}")
        print(f"TARGET_FPS_STABLE: {cls.TARGET_FPS_STABLE}")
        print(f"HEALTH_CHECK_INTERVAL: {cls.HEALTH_CHECK_INTERVAL}s")
        print("============================")

# Create a global instance for easy access
stream_config = StreamConfig()
