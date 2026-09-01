import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

/**
 * Camera Settings API service for ONVIF camera configuration
 */
class CameraSettingsApi {
  /**
   * Test ONVIF connection to a camera
   * @param {Object} credentials - Camera credentials
   * @returns {Promise<Object>} Connection test result
   */
  async testOnvifConnection(credentials) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/test-onvif-connection`, credentials, {
        timeout: 30000, // 30 second timeout for ONVIF connection
      });
      return response.data;
    } catch (error) {
      console.error('Error testing ONVIF connection:', error);
      throw error;
    }
  }

  /**
   * Get video profiles from camera
   * @param {string} cameraIp - Camera IP address
   * @param {string} username - ONVIF username
   * @param {string} password - ONVIF password
   * @param {number} port - ONVIF port (default 80)
   * @returns {Promise<Object>} Video profiles data
   */
  async getCameraProfiles(cameraIp, username, password, port = 80) {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/camera/${cameraIp}/profiles`, {
        params: { username, password, port },
        timeout: 20000,
      });
      return response.data;
    } catch (error) {
      console.error('Error getting camera profiles:', error);
      throw error;
    }
  }

  /**
   * Get current resolution of camera
   * @param {string} cameraIp - Camera IP address
   * @param {string} username - ONVIF username
   * @param {string} password - ONVIF password
   * @param {number} port - ONVIF port (default 80)
   * @returns {Promise<Object>} Current resolution data
   */
  async getCurrentResolution(cameraIp, username, password, port = 80) {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/camera/${cameraIp}/current-resolution`, {
        params: { username, password, port },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      console.error('Error getting current resolution:', error);
      throw error;
    }
  }

  /**
   * Get supported resolutions from camera
   * @param {string} cameraIp - Camera IP address
   * @param {string} username - ONVIF username
   * @param {string} password - ONVIF password
   * @param {number} port - ONVIF port (default 80)
   * @returns {Promise<Object>} Supported resolutions data
   */
  async getSupportedResolutions(cameraIp, username, password, port = 80) {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/camera/${cameraIp}/supported-resolutions`, {
        params: { username, password, port },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      console.error('Error getting supported resolutions:', error);
      throw error;
    }
  }

  /**
   * Set camera resolution via ONVIF
   * @param {Object} resolutionRequest - Resolution change request
   * @returns {Promise<Object>} Resolution change result
   */
  async setCameraResolution(resolutionRequest) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/camera/set-resolution`, resolutionRequest, {
        timeout: 30000, // 30 second timeout for resolution change
      });
      return response.data;
    } catch (error) {
      console.error('Error setting camera resolution:', error);
      throw error;
    }
  }

  /**
   * Get current stream settings from camera
   * @param {string} cameraIp - Camera IP address
   * @param {string} username - ONVIF username
   * @param {string} password - ONVIF password
   * @param {number} port - ONVIF port (default 80)
   * @returns {Promise<Object>} Current stream settings data
   */
  async getCurrentStreamSettings(cameraIp, username, password, port = 80) {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/camera/${cameraIp}/current-stream-settings`, {
        params: { username, password, port },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      console.error('Error getting current stream settings:', error);
      throw error;
    }
  }

  /**
   * Get supported stream settings from camera
   * @param {string} cameraIp - Camera IP address
   * @param {string} username - ONVIF username
   * @param {string} password - ONVIF password
   * @param {number} port - ONVIF port (default 80)
   * @returns {Promise<Object>} Supported stream settings data
   */
  async getSupportedStreamSettings(cameraIp, username, password, port = 80) {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/camera/${cameraIp}/supported-stream-settings`, {
        params: { username, password, port },
        timeout: 15000,
      });
      return response.data;
    } catch (error) {
      console.error('Error getting supported stream settings:', error);
      throw error;
    }
  }

  /**
   * Set camera stream settings via ONVIF
   * @param {Object} streamSettingsRequest - Stream settings change request
   * @returns {Promise<Object>} Stream settings change result
   */
  async setCameraStreamSettings(streamSettingsRequest) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/camera/set-stream-settings`, streamSettingsRequest, {
        timeout: 30000, // 30 second timeout for stream settings change
      });
      return response.data;
    } catch (error) {
      console.error('Error setting camera stream settings:', error);
      throw error;
    }
  }

  /**
   * Get all camera settings
   * @returns {Promise<Object>} All camera settings
   */
  async getCameraSettings() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/camera-settings`);
      return response.data;
    } catch (error) {
      console.error('Error getting camera settings:', error);
      throw error;
    }
  }

  /**
   * Update settings for a specific camera
   * @param {string} cameraIp - Camera IP address
   * @param {Object} settings - Settings to update
   * @returns {Promise<Object>} Update result
   */
  async updateCameraSettings(cameraIp, settings) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/camera-settings/${cameraIp}`, settings);
      return response.data;
    } catch (error) {
      console.error('Error updating camera settings:', error);
      throw error;
    }
  }

  /**
   * Disconnect camera and clear cache
   * @param {string} cameraIp - Camera IP address
   * @param {number} port - ONVIF port (default 80)
   * @returns {Promise<Object>} Disconnect result
   */
  async disconnectCamera(cameraIp, port = 80) {
    try {
      const response = await axios.delete(`${API_BASE_URL}/api/camera/${cameraIp}/disconnect`, {
        params: { port },
      });
      return response.data;
    } catch (error) {
      console.error('Error disconnecting camera:', error);
      throw error;
    }
  }

  /**
   * Get common resolution presets
   * @returns {Promise<Object>} Common resolutions
   */
  async getCommonResolutions() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/common-resolutions`);
      return response.data;
    } catch (error) {
      console.error('Error getting common resolutions:', error);
      throw error;
    }
  }

  /**
   * Extract camera IP from RTSP URL
   * @param {string} rtspUrl - RTSP URL
   * @returns {string|null} Extracted IP address
   */
  extractIpFromRtspUrl(rtspUrl) {
    try {
      // Match IP address pattern in RTSP URL
      const ipMatch = rtspUrl.match(/(?:rtsp:\/\/(?:[^@]+@)?)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/);
      return ipMatch ? ipMatch[1] : null;
    } catch (error) {
      console.error('Error extracting IP from RTSP URL:', error);
      return null;
    }
  }

  /**
   * Parse ONVIF credentials from RTSP URL
   * @param {string} rtspUrl - RTSP URL
   * @returns {Object} Parsed credentials
   */
  parseCredentialsFromRtspUrl(rtspUrl) {
    try {
      // Match credentials pattern in RTSP URL: rtsp://username:password@ip:port/path
      const credMatch = rtspUrl.match(/rtsp:\/\/([^:]+):([^@]+)@/);
      if (credMatch) {
        return {
          username: credMatch[1],
          password: credMatch[2],
        };
      }
      return { username: 'admin', password: 'admin' }; // Default credentials
    } catch (error) {
      console.error('Error parsing credentials from RTSP URL:', error);
      return { username: 'admin', password: 'admin' };
    }
  }

  /**
   * Validate IP address format
   * @param {string} ip - IP address to validate
   * @returns {boolean} True if valid IP
   */
  isValidIp(ip) {
    const ipRegex = /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
    return ipRegex.test(ip);
  }

  /**
   * Format resolution for display
   * @param {number} width - Resolution width
   * @param {number} height - Resolution height
   * @returns {string} Formatted resolution string
   */
  formatResolution(width, height) {
    const commonLabels = {
      '1920x1080': '1080p',
      '1280x720': '720p',
      '800x600': 'SVGA',
      '640x480': 'VGA',
      '320x240': 'QVGA',
    };
    
    const key = `${width}x${height}`;
    return commonLabels[key] || key;
  }
}

// Export singleton instance
const cameraSettingsApi = new CameraSettingsApi();
export default cameraSettingsApi;
