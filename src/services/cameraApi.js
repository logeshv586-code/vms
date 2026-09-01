import axios from 'axios';
import { API_BASE_URL } from '../utils/apiConfig';

/**
 * Camera API service for fetching camera data and stream status
 */
class CameraApi {
  /**
   * Get all cameras from the configuration file
   * @returns {Promise<Object>} Camera configuration data
   */
  async getCameras() {
    try {
      const response = await axios.get(`${API_BASE_URL}/cameras`);
      return response.data;
    } catch (error) {
      console.error('Error fetching cameras:', error);
      throw error;
    }
  }

  /**
   * Get all active streams and their status
   * @returns {Promise<Object>} Active streams data
   */
  async getActiveStreams() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/streams`);
      return response.data;
    } catch (error) {
      console.error('Error fetching active streams:', error);
      throw error;
    }
  }

  /**
   * Get health status including active stream count
   * @returns {Promise<Object>} Health status data
   */
  async getHealthStatus() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/health`);
      return response.data;
    } catch (error) {
      console.error('Error fetching health status:', error);
      throw error;
    }
  }

  /**
   * Transform camera configuration data into a flat array with additional metadata
   * @param {Object} cameraData - Raw camera configuration data
   * @param {Object} streamData - Active streams data
   * @returns {Array} Transformed camera array
   */
  transformCameraData(cameraData, streamData = {}) {
    const cameras = [];
    const activeStreams = streamData.streams || {};

    // Handle case where cameraData might have different structure
    const camerasConfig = cameraData.cameras || cameraData || {};

    // Iterate through collections and cameras
    Object.entries(camerasConfig).forEach(([collectionName, cameras_in_collection]) => {
      if (cameras_in_collection && typeof cameras_in_collection === 'object') {
        Object.entries(cameras_in_collection).forEach(([cameraIp, streamUrl]) => {
          // Generate consistent stream ID (matching backend logic)
          const streamId = `${collectionName}_${cameraIp}`;

          // Check if this camera has an active stream
          const isActive = activeStreams.hasOwnProperty(streamId) &&
                          activeStreams[streamId].is_running;

          cameras.push({
            id: `${collectionName}_${cameraIp}`,
            name: `${collectionName} (${cameraIp})`,
            ip: cameraIp,
            collection: collectionName,
            streamUrl: streamUrl,
            streamId: streamId,
            status: isActive ? 'Active' : 'Inactive',
            isActive: isActive,
            feedUrl: isActive ? `${API_BASE_URL}/api/video_feed/${streamId}` : null
          });
        });
      }
    });

    return cameras;
  }

  /**
   * Get comprehensive camera data with status information
   * @returns {Promise<Array>} Array of camera objects with status
   */
  async getCamerasWithStatus() {
    try {
      const [cameraData, streamData] = await Promise.all([
        this.getCameras(),
        this.getActiveStreams()
      ]);

      return this.transformCameraData(cameraData, streamData);
    } catch (error) {
      console.error('Error fetching cameras with status:', error);
      throw error;
    }
  }
}

// Export a singleton instance
export default new CameraApi();
