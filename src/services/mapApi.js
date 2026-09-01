import axios from 'axios';
import { API_BASE_URL } from '../utils/apiConfig';

/**
 * Service for managing camera coordinates and map configuration.
 */
class MapApi {
  /**
   * Get all camera latitude/longitude coordinates and custom map settings.
   * @returns {Promise<Object>} The camera locations and settings object.
   */
  async getCameraLocations() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/camera-locations`);
      return response.data;
    } catch (error) {
      console.error('Error fetching camera locations:', error);
      throw error;
    }
  }

  /**
   * Save updated camera coordinates and map preferences.
   * @param {Object} data - The updated configuration containing settings and locations.
   * @returns {Promise<Object>} The API response.
   */
  async saveCameraLocations(data) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/camera-locations`, data);
      return response.data;
    } catch (error) {
      console.error('Error saving camera locations:', error);
      throw error;
    }
  }

  /**
   * Search location geocoding via the backend proxy.
   * @param {string} query - The search query.
   * @returns {Promise<Object>} The results object containing `{ results, is_relaxed, relaxed_query }`.
   */
  async geocode(query) {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/geocode`, {
        params: { q: query }
      });
      return response.data;
    } catch (error) {
      console.error('Error geocoding location:', error);
      throw error;
    }
  }
}

// Export singleton instance
export default new MapApi();
