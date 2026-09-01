import axios from 'axios';
import { API_BASE_URL } from '../utils/apiConfig';

/**
 * Collections API Service
 * 
 * This service provides methods to interact with the backend collections API.
 * It handles all operations related to collections and cameras within collections.
 */
class CollectionsApiService {
  constructor() {
    this.baseUrl = `${API_BASE_URL}/api/collections`;
  }

  /**
   * Get all collections
   * @returns {Promise<Array>} - List of collection names
   */
  async getCollections() {
    try {
      const response = await axios.get(this.baseUrl);
      return response.data.collections;
    } catch (error) {
      console.error('Error fetching collections:', error);
      throw error;
    }
  }

  /**
   * Get a specific collection with its cameras
   * @param {string} collectionName - Name of the collection
   * @returns {Promise<Object>} - Collection object with cameras
   */
  async getCollection(collectionName) {
    try {
      const response = await axios.get(`${this.baseUrl}/${encodeURIComponent(collectionName)}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching collection ${collectionName}:`, error);
      throw error;
    }
  }

  /**
   * Create a new collection
   * @param {string} collectionName - Name of the new collection
   * @param {Object} cameras - Optional initial cameras for the collection
   * @returns {Promise<Object>} - Created collection
   */
  async createCollection(collectionName, cameras = {}) {
    try {
      const response = await axios.post(this.baseUrl, {
        name: collectionName,
        cameras
      });
      return response.data;
    } catch (error) {
      console.error(`Error creating collection ${collectionName}:`, error);
      throw error;
    }
  }

  /**
   * Update (rename) a collection
   * @param {string} collectionName - Current name of the collection
   * @param {string} newName - New name for the collection
   * @returns {Promise<Object>} - Updated collection
   */
  async updateCollection(collectionName, newName) {
    try {
      const response = await axios.put(
        `${this.baseUrl}/${encodeURIComponent(collectionName)}`,
        { name: newName }
      );
      return response.data;
    } catch (error) {
      console.error(`Error updating collection ${collectionName}:`, error);
      throw error;
    }
  }

  /**
   * Delete a collection
   * @param {string} collectionName - Name of the collection to delete
   * @returns {Promise<Object>} - Response message
   */
  async deleteCollection(collectionName) {
    try {
      const response = await axios.delete(`${this.baseUrl}/${encodeURIComponent(collectionName)}`);
      return response.data;
    } catch (error) {
      console.error(`Error deleting collection ${collectionName}:`, error);
      throw error;
    }
  }

  /**
   * Add a camera to a collection
   * @param {string} collectionName - Name of the collection
   * @param {string} ip - IP address of the camera
   * @param {string} streamUrl - Stream URL of the camera
   * @returns {Promise<Object>} - Added camera
   */
  async addCameraToCollection(collectionName, ip, streamUrl) {
    try {
      const response = await axios.post(
        `${this.baseUrl}/${encodeURIComponent(collectionName)}/cameras`,
        { ip, streamUrl }
      );
      return response.data;
    } catch (error) {
      console.error(`Error adding camera to collection ${collectionName}:`, error);
      throw error;
    }
  }

  /**
   * Update a camera in a collection
   * @param {string} collectionName - Name of the collection
   * @param {string} ip - IP address of the camera
   * @param {string} streamUrl - New stream URL for the camera
   * @returns {Promise<Object>} - Updated camera
   */
  async updateCameraInCollection(collectionName, ip, streamUrl) {
    try {
      const response = await axios.put(
        `${this.baseUrl}/${encodeURIComponent(collectionName)}/cameras/${encodeURIComponent(ip)}`,
        { ip, streamUrl }
      );
      return response.data;
    } catch (error) {
      console.error(`Error updating camera in collection ${collectionName}:`, error);
      throw error;
    }
  }

  /**
   * Remove a camera from a collection
   * @param {string} collectionName - Name of the collection
   * @param {string} ip - IP address of the camera to remove
   * @returns {Promise<Object>} - Response message
   */
  async removeCameraFromCollection(collectionName, ip) {
    try {
      const response = await axios.delete(
        `${this.baseUrl}/${encodeURIComponent(collectionName)}/cameras/${encodeURIComponent(ip)}`
      );
      return response.data;
    } catch (error) {
      console.error(`Error removing camera from collection ${collectionName}:`, error);
      throw error;
    }
  }
}

// Create and export a singleton instance
const collectionsApi = new CollectionsApiService();
export default collectionsApi;
