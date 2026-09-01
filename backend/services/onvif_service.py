"""
ONVIF Service for Camera Resolution Configuration
Handles ONVIF protocol communication with IP cameras for resolution management
"""

import logging
import asyncio as _real_asyncio
import inspect
from typing import Dict, List, Optional, Tuple
from onvif import ONVIFCamera
from zeep.exceptions import Fault
import time


async def _smart_call(func, *args, **kwargs):
    """Call func, awaiting the result if it is a coroutine."""
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    result = func(*args, **kwargs)
    if inspect.iscoroutine(result):
        return await result
    return result


logger = logging.getLogger(__name__)

# Keep a reference so the rest of the file can use asyncio normally
asyncio = _real_asyncio


class ONVIFService:
    """Service for managing camera settings via ONVIF protocol"""

    def __init__(self):
        self.camera_connections = {}  # Cache for camera connections
        self.connection_timeout = 30  # seconds

    async def _create_and_attach_service(self, cam, service_name: str):
        """
        Call cam.create_<service_name>_service(), await if needed,
        and attach the returned object as cam.<service_name> so that
        downstream code like cam.devicemgmt.X / cam.media.X works.
        """
        creator = getattr(cam, f"create_{service_name}_service")
        svc = await _smart_call(creator)
        setattr(cam, service_name, svc)
        return svc

    async def connect_camera(self, ip: str, username: str, password: str, port: int = 80) -> Optional[ONVIFCamera]:
        """
        Establish connection to ONVIF camera

        Args:
            ip: Camera IP address
            username: ONVIF username
            password: ONVIF password
            port: ONVIF port (default 80)

        Returns:
            ONVIFCamera instance or None if connection fails
        """
        connection_key = f"{ip}:{port}"

        # Check if we have a cached connection
        if connection_key in self.camera_connections:
            try:
                # Test if connection is still valid
                cam = self.camera_connections[connection_key]
                await asyncio.wait_for(
                    _smart_call(cam.devicemgmt.GetDeviceInformation),
                    timeout=5
                )
                return cam
            except Exception:
                # Connection is stale, remove from cache
                del self.camera_connections[connection_key]

        try:
            logger.info(f"Connecting to ONVIF camera at {ip}:{port}")

            # Create new camera connection
            cam = ONVIFCamera(ip, port, username, password)

            # Initialize xaddrs (required for async onvif-zeep)
            await asyncio.wait_for(
                _smart_call(cam.update_xaddrs),
                timeout=self.connection_timeout
            )

            # Create devicemgmt service and attach it to cam
            await asyncio.wait_for(
                self._create_and_attach_service(cam, "devicemgmt"),
                timeout=self.connection_timeout
            )

            # Test connection
            device_info = await asyncio.wait_for(
                _smart_call(cam.devicemgmt.GetDeviceInformation),
                timeout=10
            )

            logger.info(f"Connected to camera: {device_info.Manufacturer} {device_info.Model}")

            # Cache the connection
            self.camera_connections[connection_key] = cam

            return cam

        except asyncio.TimeoutError:
            logger.error(f"Timeout connecting to camera {ip}:{port}")
            return None
        except Exception as e:
            logger.error(f"Failed to connect to camera {ip}:{port}: {str(e)}")
            return None


    async def get_video_profiles(self, ip: str, username: str, password: str, port: int = 80) -> List[Dict]:
        """
        Get available video profiles from camera

        Returns:
            List of video profile dictionaries
        """
        cam = await self.connect_camera(ip, username, password, port)
        if not cam:
            raise Exception(f"Failed to connect to camera {ip}")

        try:
            # Create media service
            await self._create_and_attach_service(cam, "media")

            # Get profiles
            profiles = await asyncio.wait_for(
                _smart_call(cam.media.GetProfiles),
                timeout=10
            )

            profile_list = []
            for profile in profiles:
                if hasattr(profile, 'VideoEncoderConfiguration') and profile.VideoEncoderConfiguration:
                    config = profile.VideoEncoderConfiguration
                    profile_info = {
                        'token': profile.token,
                        'name': profile.Name,
                        'encoding': config.Encoding if hasattr(config, 'Encoding') else 'Unknown',
                        'resolution': {
                            'width': config.Resolution.Width if hasattr(config, 'Resolution') else 0,
                            'height': config.Resolution.Height if hasattr(config, 'Resolution') else 0
                        },
                        'frame_rate': config.RateControl.FrameRateLimit if hasattr(config, 'RateControl') and hasattr(config.RateControl, 'FrameRateLimit') else 0,
                        'bitrate': config.RateControl.BitrateLimit if hasattr(config, 'RateControl') and hasattr(config.RateControl, 'BitrateLimit') else 0
                    }
                    profile_list.append(profile_info)

            return profile_list

        except Exception as e:
            logger.error(f"Failed to get video profiles from {ip}: {str(e)}")
            raise Exception(f"Failed to get video profiles: {str(e)}")

    async def get_current_resolution(self, ip: str, username: str, password: str, port: int = 80) -> Optional[Tuple[int, int]]:
        """
        Get current resolution of the camera's main profile

        Returns:
            Tuple of (width, height) or None if failed
        """
        try:
            profiles = await self.get_video_profiles(ip, username, password, port)
            if profiles:
                # Return resolution of first profile (usually main stream)
                resolution = profiles[0]['resolution']
                return (resolution['width'], resolution['height'])
            return None
        except Exception as e:
            logger.error(f"Failed to get current resolution from {ip}: {str(e)}")
            return None

    async def set_camera_resolution(self, ip: str, username: str, password: str, width: int, height: int,
                                  port: int = 80, profile_token: str = None, frame_rate: int = 15,
                                  bitrate: int = 1024) -> bool:
        """
        Set camera resolution using ONVIF protocol

        Args:
            ip: Camera IP address
            username: ONVIF username
            password: ONVIF password
            width: Target width
            height: Target height
            port: ONVIF port
            profile_token: Specific profile token (uses first if None)
            frame_rate: Frame rate limit
            bitrate: Bitrate limit in Kbps

        Returns:
            True if successful, False otherwise
        """
        cam = await self.connect_camera(ip, username, password, port)
        if not cam:
            return False

        try:
            # Create media service
            await self._create_and_attach_service(cam, "media")

            # First, check if the resolution is supported
            try:
                supported_resolutions = await self.get_supported_resolutions(ip, username, password, port)
                resolution_supported = any(
                    res[0] == width and res[1] == height
                    for res in supported_resolutions
                )
                if not resolution_supported:
                    logger.warning(f"Resolution {width}x{height} may not be supported by camera {ip}")
            except Exception as e:
                logger.warning(f"Could not verify supported resolutions: {e}")

            # First, check if the resolution is supported
            try:
                supported_resolutions = await self.get_supported_resolutions(ip, username, password, port)
                resolution_supported = any(
                    res[0] == width and res[1] == height
                    for res in supported_resolutions
                )
                if not resolution_supported:
                    logger.warning(f"Resolution {width}x{height} may not be supported by camera {ip}")
            except Exception as e:
                logger.warning(f"Could not verify supported resolutions: {e}")

            # Get profiles if token not specified
            if not profile_token:
                profiles = await asyncio.wait_for(
                    _smart_call(cam.media.GetProfiles),
                    timeout=10
                )
                if not profiles:
                    raise Exception("No profiles found")
                profile_token = profiles[0].token

            # Get profiles to find the correct configuration token
            profiles = await asyncio.wait_for(
                _smart_call(cam.media.GetProfiles),
                timeout=10
            )

            # Find the profile with video encoder configuration
            target_profile = None
            for profile in profiles:
                if hasattr(profile, 'VideoEncoderConfiguration') and profile.VideoEncoderConfiguration:
                    if not profile_token or profile.token == profile_token:
                        target_profile = profile
                        break

            if not target_profile:
                raise Exception("No suitable video encoder profile found")

            # Get the video encoder configuration token
            video_config_token = target_profile.VideoEncoderConfiguration.token

            # Get current configuration using the correct token
            current_config = await asyncio.wait_for(
                _smart_call(cam.media.GetVideoEncoderConfiguration, video_config_token),
                timeout=10
            )

            logger.info(f"Current config for {ip}: {current_config.Resolution.Width}x{current_config.Resolution.Height}")

            # Modify the existing configuration directly
            current_config.Resolution.Width = width
            current_config.Resolution.Height = height

            logger.info(f"Setting resolution for {ip}: {width}x{height}")

            # Update rate control if available
            if hasattr(current_config, 'RateControl') and current_config.RateControl:
                current_config.RateControl.FrameRateLimit = frame_rate
                current_config.RateControl.BitrateLimit = bitrate
                current_config.RateControl.EncodingInterval = 1

            # Create the SetVideoEncoderConfiguration request properly
            set_request = cam.media.create_type('SetVideoEncoderConfiguration')
            set_request.Configuration = current_config
            set_request.ForcePersistence = True

            # Apply configuration
            logger.info(f"Applying configuration to {ip}: {width}x{height}")
            await asyncio.wait_for(
                _smart_call(cam.media.SetVideoEncoderConfiguration, set_request),
                timeout=15
            )

            # Verify the change was applied
            try:
                verification_config = await asyncio.wait_for(
                    _smart_call(cam.media.GetVideoEncoderConfiguration, current_config.token),
                    timeout=10
                )
                actual_width = verification_config.Resolution.Width
                actual_height = verification_config.Resolution.Height
                logger.info(f"Verification: Camera {ip} now has resolution {actual_width}x{actual_height}")
            except Exception as verify_error:
                logger.warning(f"Could not verify resolution change for {ip}: {verify_error}")

            logger.info(f"Successfully set resolution {width}x{height} for camera {ip}")
            return True

        except Fault as e:
            logger.error(f"ONVIF fault setting resolution for {ip}: {str(e)}")
            # Try alternative method
            return await self._try_alternative_resolution_method(cam, ip, width, height, frame_rate, bitrate)
        except Exception as e:
            logger.error(f"Failed to set resolution for {ip}: {str(e)}")
            # Try alternative method
            return await self._try_alternative_resolution_method(cam, ip, width, height, frame_rate, bitrate)

    async def get_supported_resolutions(self, ip: str, username: str, password: str, port: int = 80) -> List[Tuple[int, int]]:
        """
        Get list of supported resolutions from camera

        Returns:
            List of (width, height) tuples
        """
        cam = await self.connect_camera(ip, username, password, port)
        if not cam:
            return []

        try:
            # Create media service
            await self._create_and_attach_service(cam, "media")

            # Get video encoder configuration options
            profiles = await asyncio.wait_for(
                _smart_call(cam.media.GetProfiles),
                timeout=10
            )

            if not profiles:
                return []

            # Get configuration options for first profile
            options_request = cam.media.create_type('GetVideoEncoderConfigurationOptions')
            options_request.ProfileToken = profiles[0].token

            options = await asyncio.wait_for(
                _smart_call(cam.media.GetVideoEncoderConfigurationOptions, options_request),
                timeout=10
            )

            resolutions = []
            if hasattr(options, 'H264') and options.H264 and hasattr(options.H264, 'ResolutionsAvailable'):
                for res in options.H264.ResolutionsAvailable:
                    resolutions.append((res.Width, res.Height))

            # If no specific resolutions found, return common ones
            if not resolutions:
                resolutions = [
                    (1920, 1080),  # 1080p
                    (1280, 720),   # 720p
                    (640, 480),    # VGA
                    (320, 240)     # QVGA
                ]

            return resolutions

        except Exception as e:
            logger.error(f"Failed to get supported resolutions from {ip}: {str(e)}")
            # Return common resolutions as fallback
            return [
                (1920, 1080),  # 1080p
                (1280, 720),   # 720p
                (640, 480),    # VGA
                (320, 240)     # QVGA
            ]

    def _get_resolution_variations(self, width: int, height: int):
        """Get different resolution format variations that cameras might expect"""
        variations = [
            (width, height),  # Standard format
        ]

        # Some cameras might have slightly different supported resolutions
        if width == 1920 and height == 1080:
            variations.extend([(1920, 1088), (1920, 1072)])  # Some cameras use these variants
        elif width == 1280 and height == 720:
            variations.extend([(1280, 704), (1280, 736)])   # Some cameras use these variants

        return variations

    async def _try_alternative_resolution_method(self, cam, ip: str, width: int, height: int, frame_rate: int, bitrate: int) -> bool:
        """
        Alternative method for setting resolution using configuration options
        """
        try:
            logger.info(f"Trying alternative resolution method for {ip}")

            # Get profiles
            profiles = await asyncio.wait_for(
                _smart_call(cam.media.GetProfiles),
                timeout=10
            )

            if not profiles:
                return False

            # Use first profile
            profile = profiles[0]

            # Get configuration options
            options_request = cam.media.create_type('GetVideoEncoderConfigurationOptions')
            options_request.ProfileToken = profile.token

            options = await asyncio.wait_for(
                _smart_call(cam.media.GetVideoEncoderConfigurationOptions, options_request),
                timeout=10
            )

            # Check if resolution is in available options
            available_resolutions = []
            if hasattr(options, 'H264') and options.H264 and hasattr(options.H264, 'ResolutionsAvailable'):
                available_resolutions = [(res.Width, res.Height) for res in options.H264.ResolutionsAvailable]

            logger.info(f"Available resolutions for {ip}: {available_resolutions}")

            # Try different resolution variations
            resolution_variations = self._get_resolution_variations(width, height)
            target_width, target_height = width, height

            for var_width, var_height in resolution_variations:
                if (var_width, var_height) in available_resolutions:
                    target_width, target_height = var_width, var_height
                    logger.info(f"Using resolution variation: {target_width}x{target_height}")
                    break
            else:
                logger.error(f"No suitable resolution found for {width}x{height}. Available: {available_resolutions}")
                return False

            # Try to modify the profile directly
            if hasattr(profile, 'VideoEncoderConfiguration') and profile.VideoEncoderConfiguration:
                config = profile.VideoEncoderConfiguration
                config.Resolution.Width = target_width
                config.Resolution.Height = target_height

                logger.info(f"Alternative method: setting {target_width}x{target_height} for {ip}")

                if hasattr(config, 'RateControl') and config.RateControl:
                    config.RateControl.FrameRateLimit = frame_rate
                    config.RateControl.BitrateLimit = bitrate

                # Create proper request with ForcePersistence
                set_request = cam.media.create_type('SetVideoEncoderConfiguration')
                set_request.Configuration = config
                set_request.ForcePersistence = True

                # Try to set the modified configuration
                await asyncio.wait_for(
                    _smart_call(cam.media.SetVideoEncoderConfiguration, set_request),
                    timeout=15
                )

                logger.info(f"Alternative method succeeded for {ip}: {width}x{height}")
                return True

            return False

        except Exception as e:
            logger.error(f"Alternative resolution method failed for {ip}: {str(e)}")
            # Try one more method - direct configuration modification
            return await self._try_direct_config_method(cam, ip, width, height, frame_rate, bitrate)

    async def _try_direct_config_method(self, cam, ip: str, width: int, height: int, frame_rate: int, bitrate: int) -> bool:
        """
        Direct configuration method - modifies existing config in place
        """
        try:
            logger.info(f"Trying direct configuration method for {ip}")

            # Get all profiles
            profiles = await asyncio.wait_for(
                _smart_call(cam.media.GetProfiles),
                timeout=10
            )

            for profile in profiles:
                if hasattr(profile, 'VideoEncoderConfiguration') and profile.VideoEncoderConfiguration:
                    config_token = profile.VideoEncoderConfiguration.token

                    # Get the current configuration
                    current_config = await asyncio.wait_for(
                        _smart_call(cam.media.GetVideoEncoderConfiguration, config_token),
                        timeout=10
                    )

                    # Modify resolution directly
                    current_config.Resolution.Width = width
                    current_config.Resolution.Height = height

                    # Update rate control if available
                    if hasattr(current_config, 'RateControl') and current_config.RateControl:
                        current_config.RateControl.FrameRateLimit = frame_rate
                        current_config.RateControl.BitrateLimit = bitrate

                    # Create proper request with ForcePersistence
                    set_request = cam.media.create_type('SetVideoEncoderConfiguration')
                    set_request.Configuration = current_config
                    set_request.ForcePersistence = True

                    # Try to set it back
                    await asyncio.wait_for(
                        _smart_call(cam.media.SetVideoEncoderConfiguration, set_request),
                        timeout=15
                    )

                    logger.info(f"Direct config method succeeded for {ip}: {width}x{height}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Direct config method failed for {ip}: {str(e)}")
            return False

    def disconnect_camera(self, ip: str, port: int = 80):
        """Disconnect and remove camera from cache"""
        connection_key = f"{ip}:{port}"
        if connection_key in self.camera_connections:
            del self.camera_connections[connection_key]
            logger.info(f"Disconnected camera {ip}:{port}")

    async def get_current_stream_settings(self, ip: str, username: str, password: str, port: int = 80) -> Optional[Dict]:
        """
        Get current stream settings from camera

        Returns:
            Dictionary with current stream settings or None if failed
        """
        try:
            profiles = await self.get_video_profiles(ip, username, password, port)
            if profiles:
                # Get settings from first profile (usually main stream)
                profile = profiles[0]

                # Map encoding to proper format for UI consistency
                encoding = profile.get('encoding', 'H.264')
                if encoding.upper() in ['H264', 'H.264']:
                    video_encoding = 'H.264'
                elif encoding.upper() in ['H265', 'H.265', 'HEVC']:
                    video_encoding = 'H.265'
                else:
                    # Default to H.264 for unknown encodings
                    video_encoding = 'H.264'

                # Determine video quality based on bitrate
                bitrate = profile.get('bitrate', 2048)
                if bitrate <= 1024:
                    video_quality = 'low'
                elif bitrate <= 4096:
                    video_quality = 'medium'
                else:
                    video_quality = 'high'

                # Determine bitrate type (most cameras use variable by default)
                bitrate_type = 'variable'  # Most modern cameras default to variable bitrate

                return {
                    "streamType": "main",  # Default to main stream
                    "videoType": "video",  # Default to video stream
                    "bitrateType": bitrate_type,
                    "videoQuality": video_quality,
                    "frameRate": profile.get('frame_rate', 25),
                    "maxBitrate": bitrate,
                    "videoEncoding": video_encoding,
                    "h265Plus": "off",  # Default to off (requires specific detection)
                    "profile": "main",  # Default to main profile
                    "iFrameInterval": 50,  # Default to 50 (requires specific ONVIF call to get actual value)
                    "svc": "off",  # Default to off (requires specific detection)
                    "smoothing": 50  # Default to 50 (camera-specific setting)
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get current stream settings from {ip}: {str(e)}")
            return None

    async def get_supported_stream_settings(self, ip: str, username: str, password: str, port: int = 80) -> Dict:
        """
        Get supported stream settings from camera

        Returns:
            Dictionary with supported stream settings options
        """
        try:
            cam = await self.connect_camera(ip, username, password, port)
            if not cam:
                return self._get_default_supported_settings()

            # Create media service
            await self._create_and_attach_service(cam, "media")

            # Get profiles
            profiles = await asyncio.wait_for(
                _smart_call(cam.media.GetProfiles),
                timeout=10
            )

            if not profiles:
                return self._get_default_supported_settings()

            # Get configuration options for first profile
            options_request = cam.media.create_type('GetVideoEncoderConfigurationOptions')
            options_request.ProfileToken = profiles[0].token

            options = await asyncio.wait_for(
                _smart_call(cam.media.GetVideoEncoderConfigurationOptions, options_request),
                timeout=10
            )

            # Extract supported settings from ONVIF options
            supported_settings = self._get_default_supported_settings()

            # Try to get actual supported values from camera
            if hasattr(options, 'H264') and options.H264:
                h264_options = options.H264

                # Frame rates - Use Hikvision standard frame rates
                if hasattr(h264_options, 'FrameRateRange') and h264_options.FrameRateRange:
                    frame_rates = []
                    min_rate = h264_options.FrameRateRange.Min
                    max_rate = h264_options.FrameRateRange.Max
                    # Use Hikvision frame rate options, including fractional rates if min_rate is low enough
                    hikvision_rates = []

                    # Add fractional rates if camera supports very low frame rates
                    if min_rate <= 0.5:
                        hikvision_rates.extend([
                            ("1/16", 0.0625), ("1/8", 0.125), ("1/4", 0.25), ("1/2", 0.5)
                        ])

                    # Add standard integer rates
                    hikvision_rates.extend([
                        (1, 1), (2, 2), (4, 4), (6, 6), (8, 8), (10, 10), (12, 12),
                        (15, 15), (16, 16), (18, 18), (20, 20), (22, 22), (25, 25)
                    ])

                    for label, rate_value in hikvision_rates:
                        if min_rate <= rate_value <= max_rate:
                            frame_rates.append({"value": label, "label": str(label)})
                    if frame_rates:
                        supported_settings["frameRates"] = frame_rates

                # Bitrates
                if hasattr(h264_options, 'BitrateRange') and h264_options.BitrateRange:
                    bitrates = []
                    min_bitrate = h264_options.BitrateRange.Min
                    max_bitrate = h264_options.BitrateRange.Max
                    # Generate common bitrates within range
                    for bitrate in [512, 1024, 2048, 4096, 8192]:
                        if min_bitrate <= bitrate <= max_bitrate:
                            bitrates.append({"value": bitrate, "label": f"{bitrate} Kbps"})
                    if bitrates:
                        supported_settings["maxBitrates"] = bitrates

            return supported_settings

        except Exception as e:
            logger.error(f"Failed to get supported stream settings from {ip}: {str(e)}")
            return self._get_default_supported_settings()

    def _get_default_supported_settings(self) -> Dict:
        """Get default supported stream settings when camera doesn't provide specific options"""
        return {
            "streamTypes": [
                {"value": "main", "label": "Main Stream (Normal)"},
                {"value": "sub", "label": "Sub-Stream"}
            ],
            "videoTypes": [
                {"value": "video", "label": "Video Stream"},
                {"value": "video_audio", "label": "Video&Audio"}
            ],
            "bitrateTypes": [
                {"value": "constant", "label": "Constant"},
                {"value": "variable", "label": "Variable"}
            ],
            "videoQualities": [
                {"value": "low", "label": "Low"},
                {"value": "medium", "label": "Medium"},
                {"value": "high", "label": "High"}
            ],
            "frameRates": [
                {"value": "1/16", "label": "1/16"},
                {"value": "1/8", "label": "1/8"},
                {"value": "1/4", "label": "1/4"},
                {"value": "1/2", "label": "1/2"},
                {"value": 1, "label": "1"},
                {"value": 2, "label": "2"},
                {"value": 4, "label": "4"},
                {"value": 6, "label": "6"},
                {"value": 8, "label": "8"},
                {"value": 10, "label": "10"},
                {"value": 12, "label": "12"},
                {"value": 15, "label": "15"},
                {"value": 16, "label": "16"},
                {"value": 18, "label": "18"},
                {"value": 20, "label": "20"},
                {"value": 22, "label": "22"},
                {"value": 25, "label": "25"}
            ],
            "maxBitrates": [
                {"value": 256, "label": "256"},
                {"value": 512, "label": "512"},
                {"value": 1024, "label": "1024"},
                {"value": 2048, "label": "2048"},
                {"value": 3072, "label": "3072"},
                {"value": 4096, "label": "4096"},
                {"value": 5144, "label": "5144"},
                {"value": 8192, "label": "8192"}
            ],
            "videoEncodings": [
                {"value": "H.264", "label": "H.264"},
                {"value": "H.265", "label": "H.265"}
            ],
            "profiles": [
                {"value": "basic", "label": "Basic Profile"},
                {"value": "main", "label": "Main Profile"},
                {"value": "high", "label": "High Profile"}
            ]
        }

    async def set_camera_stream_settings(self, ip: str, username: str, password: str, port: int = 80,
                                       stream_type: str = None, video_type: str = None,
                                       bitrate_type: str = None, video_quality: str = None,
                                       frame_rate: int = None, max_bitrate: int = None,
                                       video_encoding: str = None, profile: str = None,
                                       i_frame_interval: int = None) -> Dict:
        """
        Set camera stream settings using ONVIF protocol

        Args:
            ip: Camera IP address
            username: ONVIF username
            password: ONVIF password
            port: ONVIF port
            stream_type: Stream type (main/sub)
            video_type: Video type (video/audio)
            bitrate_type: Bitrate type (variable/constant)
            video_quality: Video quality (low/medium/high/ultra)
            frame_rate: Frame rate limit
            max_bitrate: Maximum bitrate in Kbps
            video_encoding: Video encoding (H.264/H.265)
            profile: Encoding profile (baseline/main/high)
            i_frame_interval: I-frame interval

        Returns:
            Dictionary with detailed results for each setting
        """
        # Initialize results dictionary
        results = {
            "success": False,
            "settings_applied": {},
            "settings_failed": {},
            "message": "",
            "total_attempted": 0,
            "total_succeeded": 0,
            "total_failed": 0
        }

        cam = await self.connect_camera(ip, username, password, port)
        if not cam:
            results["message"] = f"Failed to connect to camera {ip}"
            return results

        try:
            # Create media service
            await self._create_and_attach_service(cam, "media")

            # Get profiles
            profiles = await asyncio.wait_for(
                _smart_call(cam.media.GetProfiles),
                timeout=10
            )

            if not profiles:
                results["message"] = f"No profiles found for camera {ip}"
                return results

            # Get video encoder configuration
            video_config_token = None
            for profile in profiles:
                if hasattr(profile, 'VideoEncoderConfiguration') and profile.VideoEncoderConfiguration:
                    video_config_token = profile.VideoEncoderConfiguration.token
                    break

            if not video_config_token:
                results["message"] = f"No video encoder configuration found for camera {ip}"
                return results

            # Get current configuration
            current_config = await asyncio.wait_for(
                _smart_call(cam.media.GetVideoEncoderConfiguration, video_config_token),
                timeout=10
            )

            # Track which settings to attempt
            settings_to_apply = {}

            # Prepare settings that can be set via ONVIF
            if frame_rate is not None:
                settings_to_apply["frameRate"] = frame_rate
                results["total_attempted"] += 1

            if max_bitrate is not None:
                settings_to_apply["maxBitrate"] = max_bitrate
                results["total_attempted"] += 1

            if video_encoding is not None:
                settings_to_apply["videoEncoding"] = video_encoding
                results["total_attempted"] += 1

            if i_frame_interval is not None:
                settings_to_apply["iFrameInterval"] = i_frame_interval
                results["total_attempted"] += 1

            # Mark unsupported settings as not attempted (but inform user)
            unsupported_settings = []
            if stream_type is not None:
                unsupported_settings.append("streamType")
            if video_type is not None:
                unsupported_settings.append("videoType")
            if bitrate_type is not None:
                unsupported_settings.append("bitrateType")
            if video_quality is not None:
                unsupported_settings.append("videoQuality")
            if profile is not None:
                unsupported_settings.append("profile")

            # Apply each setting individually
            config_modified = False

            # Set frame rate
            if "frameRate" in settings_to_apply:
                try:
                    if hasattr(current_config, 'RateControl') and current_config.RateControl:
                        current_config.RateControl.FrameRateLimit = settings_to_apply["frameRate"]
                        results["settings_applied"]["frameRate"] = settings_to_apply["frameRate"]
                        results["total_succeeded"] += 1
                        config_modified = True
                        logger.info(f"Frame rate set to {settings_to_apply['frameRate']} for camera {ip}")
                    else:
                        results["settings_failed"]["frameRate"] = "Camera does not support frame rate control via ONVIF"
                        results["total_failed"] += 1
                except Exception as e:
                    results["settings_failed"]["frameRate"] = f"Error setting frame rate: {str(e)}"
                    results["total_failed"] += 1

            # Set bitrate
            if "maxBitrate" in settings_to_apply:
                try:
                    if hasattr(current_config, 'RateControl') and current_config.RateControl:
                        current_config.RateControl.BitrateLimit = settings_to_apply["maxBitrate"]
                        results["settings_applied"]["maxBitrate"] = settings_to_apply["maxBitrate"]
                        results["total_succeeded"] += 1
                        config_modified = True
                        logger.info(f"Bitrate set to {settings_to_apply['maxBitrate']} for camera {ip}")
                    else:
                        results["settings_failed"]["maxBitrate"] = "Camera does not support bitrate control via ONVIF"
                        results["total_failed"] += 1
                except Exception as e:
                    results["settings_failed"]["maxBitrate"] = f"Error setting bitrate: {str(e)}"
                    results["total_failed"] += 1

            # Set video encoding
            if "videoEncoding" in settings_to_apply:
                try:
                    if hasattr(current_config, 'Encoding'):
                        # Normalize video encoding value to standard format
                        encoding_value = settings_to_apply["videoEncoding"]

                        # Handle different input formats and normalize to ONVIF standard
                        if encoding_value.lower() in ['h264', 'h.264', '0']:
                            normalized_encoding = 'H264'
                        elif encoding_value.lower() in ['h265', 'h.265', 'hevc', '1']:
                            normalized_encoding = 'H265'
                        elif encoding_value in ['H.264']:
                            normalized_encoding = 'H264'
                        elif encoding_value in ['H.265']:
                            normalized_encoding = 'H265'
                        else:
                            results["settings_failed"]["videoEncoding"] = f"Unsupported encoding: {encoding_value}"
                            results["total_failed"] += 1
                            logger.warning(f"Unsupported video encoding format: {encoding_value}")
                            normalized_encoding = None

                        if normalized_encoding:
                            current_config.Encoding = normalized_encoding
                            results["settings_applied"]["videoEncoding"] = encoding_value  # Return original format for UI consistency
                            results["total_succeeded"] += 1
                            config_modified = True
                            logger.info(f"Video encoding set to {normalized_encoding} (from {encoding_value}) for camera {ip}")
                    else:
                        results["settings_failed"]["videoEncoding"] = "Camera does not support encoding change via ONVIF"
                        results["total_failed"] += 1
                except Exception as e:
                    results["settings_failed"]["videoEncoding"] = f"Error setting video encoding: {str(e)}"
                    results["total_failed"] += 1

            # Set I-frame interval
            if "iFrameInterval" in settings_to_apply:
                try:
                    if hasattr(current_config, 'RateControl') and current_config.RateControl:
                        current_config.RateControl.EncodingInterval = settings_to_apply["iFrameInterval"]
                        results["settings_applied"]["iFrameInterval"] = settings_to_apply["iFrameInterval"]
                        results["total_succeeded"] += 1
                        config_modified = True
                        logger.info(f"I-frame interval set to {settings_to_apply['iFrameInterval']} for camera {ip}")
                    else:
                        results["settings_failed"]["iFrameInterval"] = "Camera does not support I-frame interval control via ONVIF"
                        results["total_failed"] += 1
                except Exception as e:
                    results["settings_failed"]["iFrameInterval"] = f"Error setting I-frame interval: {str(e)}"
                    results["total_failed"] += 1

            # Apply configuration if any settings were modified
            if config_modified:
                logger.info(f"Attempting to apply configuration for {ip} with {len(results['settings_applied'])} settings")
                config_applied = await self._apply_configuration_with_fallback(cam, current_config, ip, results)
                logger.info(f"Configuration application result for {ip}: {config_applied}")
                if not config_applied:
                    # If applying the configuration fails, mark all attempted settings as failed
                    for setting in list(results["settings_applied"].keys()):
                        error_msg = f"Configuration rejected by camera. Hikvision cameras often have ONVIF limitations - try using the camera's web interface for these settings: {', '.join(results['settings_applied'].keys())}"
                        results["settings_failed"][setting] = error_msg
                        results["total_failed"] += 1
                        del results["settings_applied"][setting]
                    results["total_succeeded"] = 0

            # Add information about unsupported settings with Hikvision-specific guidance
            for setting in unsupported_settings:
                if setting in ["streamType", "videoType", "bitrateType", "videoQuality", "profile"]:
                    results["settings_failed"][setting] = f"Setting '{setting}' requires Hikvision web interface. ONVIF doesn't sync these settings properly with Hikvision cameras. Use camera web interface at http://{ip}"
                else:
                    results["settings_failed"][setting] = "Setting not supported via ONVIF (camera-specific web interface required)"
                results["total_failed"] += 1

            # Determine overall success
            if results["total_succeeded"] > 0:
                results["success"] = True
                if results["total_failed"] > 0:
                    results["message"] = f"Partially successful: {results['total_succeeded']} settings applied, {results['total_failed']} failed"
                else:
                    results["message"] = f"All {results['total_succeeded']} settings applied successfully"
            else:
                results["success"] = False
                results["message"] = f"No settings could be applied. {results['total_failed']} settings failed"

            return results

        except Exception as e:
            logger.error(f"Failed to set stream settings for {ip}: {str(e)}")
            results["message"] = f"Error during stream settings operation: {str(e)}"
            return results

    async def _apply_configuration_with_fallback(self, cam, current_config, ip: str, results: Dict) -> bool:
        """
        Apply ONVIF configuration with Hikvision-specific fallback methods

        Args:
            cam: ONVIF camera instance
            current_config: Video encoder configuration to apply
            ip: Camera IP address
            results: Results dictionary to track success/failure

        Returns:
            True if configuration was applied successfully, False otherwise
        """
        try:
            # Method 1: Try with ForcePersistence=True (standard ONVIF)
            logger.info(f"Attempting standard ONVIF configuration for {ip}")
            set_request = cam.media.create_type('SetVideoEncoderConfiguration')
            set_request.Configuration = current_config
            set_request.ForcePersistence = True

            await asyncio.wait_for(
                _smart_call(cam.media.SetVideoEncoderConfiguration, set_request),
                timeout=15
            )
            logger.info(f"Standard ONVIF configuration successfully applied to camera {ip}")
            return True

        except Exception as e1:
            logger.warning(f"Standard ONVIF method failed for {ip}: {str(e1)}")

            # Method 2: Try without ForcePersistence (Hikvision compatibility)
            try:
                logger.info(f"Attempting Hikvision-compatible ONVIF configuration for {ip}")
                set_request = cam.media.create_type('SetVideoEncoderConfiguration')
                set_request.Configuration = current_config
                # Don't set ForcePersistence for Hikvision cameras

                await asyncio.wait_for(
                    _smart_call(cam.media.SetVideoEncoderConfiguration, set_request),
                    timeout=15
                )
                logger.info(f"Hikvision-compatible ONVIF configuration successfully applied to camera {ip}")
                return True

            except Exception as e2:
                logger.warning(f"Hikvision-compatible ONVIF method failed for {ip}: {str(e2)}")

                # Method 3: Try applying settings one by one (individual parameter method)
                try:
                    logger.info(f"Attempting individual parameter method for {ip}")
                    return await self._apply_individual_parameters(cam, current_config, ip)

                except Exception as e3:
                    logger.error(f"All ONVIF configuration methods failed for {ip}. Standard: {str(e1)}, Hikvision: {str(e2)}, Individual: {str(e3)}")
                    return False

    async def _apply_individual_parameters(self, cam, config, ip: str) -> bool:
        """
        Try to apply configuration parameters individually
        This method attempts to set each parameter separately to identify which ones work
        """
        try:
            # Get the original configuration first
            original_config = await asyncio.wait_for(
                _smart_call(cam.media.GetVideoEncoderConfiguration, config.token),
                timeout=10
            )

            success_count = 0

            # Try to apply frame rate only
            if hasattr(config, 'RateControl') and config.RateControl and hasattr(original_config, 'RateControl') and original_config.RateControl:
                try:
                    temp_config = original_config
                    if hasattr(config.RateControl, 'FrameRateLimit'):
                        temp_config.RateControl.FrameRateLimit = config.RateControl.FrameRateLimit

                        set_request = cam.media.create_type('SetVideoEncoderConfiguration')
                        set_request.Configuration = temp_config

                        await asyncio.wait_for(
                            _smart_call(cam.media.SetVideoEncoderConfiguration, set_request),
                            timeout=10
                        )
                        success_count += 1
                        logger.info(f"Frame rate applied individually for {ip}")
                except Exception as e:
                    logger.warning(f"Individual frame rate setting failed for {ip}: {str(e)}")

            # Try to apply bitrate only
            if hasattr(config, 'RateControl') and config.RateControl and hasattr(original_config, 'RateControl') and original_config.RateControl:
                try:
                    temp_config = await asyncio.wait_for(
                        _smart_call(cam.media.GetVideoEncoderConfiguration, config.token),
                        timeout=10
                    )
                    if hasattr(config.RateControl, 'BitrateLimit'):
                        temp_config.RateControl.BitrateLimit = config.RateControl.BitrateLimit

                        set_request = cam.media.create_type('SetVideoEncoderConfiguration')
                        set_request.Configuration = temp_config

                        await asyncio.wait_for(
                            _smart_call(cam.media.SetVideoEncoderConfiguration, set_request),
                            timeout=10
                        )
                        success_count += 1
                        logger.info(f"Bitrate applied individually for {ip}")
                except Exception as e:
                    logger.warning(f"Individual bitrate setting failed for {ip}: {str(e)}")

            return success_count > 0

        except Exception as e:
            logger.error(f"Individual parameter method failed for {ip}: {str(e)}")
            return False

# Global instance
onvif_service = ONVIFService()