import axios from 'axios';

// Base URL for the backend API
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`Archive API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('Archive API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    console.log(`Archive API Response: ${response.status} ${response.config.url}`);

    // Validate that response is JSON when expected
    const contentType = response.headers['content-type'];
    if (contentType && !contentType.includes('application/json') && typeof response.data === 'string' && response.data.includes('<!DOCTYPE')) {
      console.warn('Received HTML response when JSON was expected');
      const error = new Error('Backend server returned HTML instead of JSON. Please check if the backend is running correctly.');
      error.response = response;
      return Promise.reject(error);
    }

    return response;
  },
  (error) => {
    console.error('Archive API Response Error:', error.response?.data || error.message);

    // Enhanced error logging for debugging
    if (error.response) {
      console.error('Response Status:', error.response.status);
      console.error('Response Headers:', error.response.headers);
      if (typeof error.response.data === 'string' && error.response.data.includes('<!DOCTYPE')) {
        console.error('Backend returned HTML instead of JSON - likely a routing or configuration issue');
      }
    }

    return Promise.reject(error);
  }
);

/**
 * Archive API service for managing recorded video files
 */
const archiveApi = {
  /**
   * Get list of available recordings for a specific stream
   * @param {string} streamId - Stream ID in format "collection_ip"
   * @returns {Promise<Object>} Response with recordings list
   */
  async getRecordings(streamId) {
    try {
      if (!streamId) {
        throw new Error('Stream ID is required');
      }

      const response = await api.get(`/api/archive/list/${streamId}`);
      return response.data;
    } catch (error) {
      console.error(`Error fetching recordings for stream ${streamId}:`, error);
      throw this._handleError(error, 'Failed to fetch recordings');
    }
  },

  /**
   * Get streaming URL for a specific recording
   * @param {string} streamId - Stream ID in format "collection_ip"
   * @param {string} filename - Recording filename
   * @returns {string} Streaming URL for the recording
   */
  getRecordingStreamUrl(streamId, filename) {
    if (!streamId || !filename) {
      throw new Error('Stream ID and filename are required');
    }
    return `${API_BASE_URL}/api/archive/stream/${streamId}/${filename}`;
  },

  /**
   * Get list of all streams that have recordings available
   * @returns {Promise<Object>} Response with available streams
   */
  async getAvailableStreams() {
    try {
      const response = await api.get('/api/archive/streams');
      return response.data;
    } catch (error) {
      console.error('Error fetching available streams:', error);
      throw this._handleError(error, 'Failed to fetch available streams');
    }
  },

  /**
   * Get all recordings across all streams
   * @returns {Promise<Object>} Response with all recordings
   */
  async getAllRecordings() {
    try {
      const response = await api.get('/api/archive/recordings');
      return response.data;
    } catch (error) {
      console.error('Error fetching all recordings:', error);
      throw this._handleError(error, 'Failed to fetch all recordings');
    }
  },

  /**
   * Get status of the archive recording system
   * @returns {Promise<Object>} Archive system status
   */
  async getArchiveStatus() {
    try {
      const response = await api.get('/api/archive/status');
      return response.data;
    } catch (error) {
      console.error('Error fetching archive status:', error);
      throw this._handleError(error, 'Failed to fetch archive status');
    }
  },

  /**
   * Delete a specific recording (admin function)
   * @param {string} streamId - Stream ID in format "collection_ip"
   * @param {string} filename - Recording filename to delete
   * @returns {Promise<Object>} Deletion result
   */
  async deleteRecording(streamId, filename) {
    try {
      if (!streamId || !filename) {
        throw new Error('Stream ID and filename are required');
      }

      const response = await api.delete(`/api/archive/recordings/${streamId}/${filename}`);
      return response.data;
    } catch (error) {
      console.error(`Error deleting recording ${streamId}/${filename}:`, error);
      throw this._handleError(error, 'Failed to delete recording');
    }
  },

  /**
   * Restart failed recording processes
   * @returns {Promise<Object>} Restart result with updated status
   */
  async restartRecordings() {
    try {
      const response = await api.post('/api/archive/restart');
      return response.data;
    } catch (error) {
      console.error('Error restarting recordings:', error);
      throw this._handleError(error, 'Failed to restart recordings');
    }
  },

  /**
   * Get recordings for a specific camera by collection and IP
   * @param {string} collectionName - Collection name
   * @param {string} cameraIp - Camera IP address
   * @returns {Promise<Object>} Response with recordings list
   */
  async getRecordingsForCamera(collectionName, cameraIp) {
    try {
      if (!collectionName || !cameraIp) {
        throw new Error('Collection name and camera IP are required');
      }

      const streamId = `${collectionName}_${cameraIp}`;
      return await this.getRecordings(streamId);
    } catch (error) {
      console.error(`Error fetching recordings for camera ${collectionName}/${cameraIp}:`, error);
      throw error;
    }
  },

  /**
   * Extract a video segment from a recording
   * @param {string} streamId - Stream ID in format "collection_ip"
   * @param {string} filename - Recording filename
  /**
   * Extract and crop a video segment from a recording
   * @param {string} streamId - Stream ID in format "collection_ip"
   * @param {string} filename - Recording filename
   * @param {string} startTime - Start time in HH:MM:SS format
   * @param {string} endTime - End time in HH:MM:SS format
   * @param {number} cropX - Crop X ratio (0..1)
   * @param {number} cropY - Crop Y ratio (0..1)
   * @param {number} cropW - Crop Width ratio (0..1)
   * @param {number} cropH - Crop Height ratio (0..1)
   * @param {string} title - Clip title
   * @param {string} notes - Clip notes
   * @param {boolean} saveToExtracted - Save to persistent Extracted Videos
   * @param {string} outputFilename - Optional custom output filename
   * @returns {Promise<Object>} Extraction result with download URL
   */
  async extractVideoSegment(
    streamId,
    filename,
    startTime,
    endTime,
    cropX = null,
    cropY = null,
    cropW = null,
    cropH = null,
    title = null,
    notes = null,
    saveToExtracted = true,
    outputFilename = null
  ) {
    try {
      if (!streamId || !filename || !startTime || !endTime) {
        throw new Error('Stream ID, filename, start time, and end time are required');
      }

      const params = new URLSearchParams({
        start_time: startTime,
        end_time: endTime,
        save_to_extracted: saveToExtracted
      });

      if (cropX !== null && cropX !== undefined) params.append('crop_x', cropX);
      if (cropY !== null && cropY !== undefined) params.append('crop_y', cropY);
      if (cropW !== null && cropW !== undefined) params.append('crop_w', cropW);
      if (cropH !== null && cropH !== undefined) params.append('crop_h', cropH);
      if (title) params.append('title', title);
      if (notes) params.append('notes', notes);
      if (outputFilename) params.append('output_filename', outputFilename);

      const response = await api.post(
        `/api/archive/extract/${streamId}/${filename}?${params}`,
        null,
        { timeout: 300000 } // 5 minute timeout for video processing & encoding
      );
      return response.data;
    } catch (error) {
      console.error(`Error extracting video segment from ${streamId}/${filename}:`, error);
      throw this._handleError(error, 'Failed to extract video segment');
    }
  },

  /**
   * Download an extracted video segment
   * @param {string} filename - Extracted segment filename
   * @returns {Promise<Blob>} File blob for download
   */
  async downloadExtractedSegment(filename) {
    try {
      if (!filename) {
        throw new Error('Filename is required');
      }

      const response = await api.get(`/api/archive/download-extract/${filename}`, {
        responseType: 'blob'
      });

      return response.data;
    } catch (error) {
      console.error(`Error downloading extracted segment ${filename}:`, error);
      throw this._handleError(error, 'Failed to download extracted segment');
    }
  },

  /**
   * List all saved extracted video clips
   * @returns {Promise<Object>} List of extracted videos
   */
  async listExtractedVideos() {
    try {
      const response = await api.get('/api/archive/extracted-videos');
      return response.data;
    } catch (error) {
      console.error('Error listing extracted videos:', error);
      throw this._handleError(error, 'Failed to list extracted videos');
    }
  },

  /**
   * Delete a saved extracted video clip
   * @param {string} filename - Clip filename to delete
   * @returns {Promise<Object>} Deletion result
   */
  async deleteExtractedVideo(filename) {
    try {
      if (!filename) throw new Error('Filename is required');
      const response = await api.delete(`/api/archive/extracted-videos/${filename}`);
      return response.data;
    } catch (error) {
      console.error(`Error deleting extracted video ${filename}:`, error);
      throw this._handleError(error, 'Failed to delete extracted video');
    }
  },

  /**
   * Get all recordings from all streams
   * @param {boolean} forceRefresh - Force refresh of recordings cache
   * @returns {Promise<Object>} Response with all recordings
   */
  async getAllRecordings(forceRefresh = false) {
    try {
      const params = forceRefresh ? '?force_refresh=true' : '';
      const response = await api.get(`/api/archive/recordings${params}`);
      return response.data;
    } catch (error) {
      console.error('Error fetching all recordings:', error);
      throw this._handleError(error, 'Failed to fetch all recordings');
    }
  },

  /**
   * Get recordings filtered by date range
   * @param {string} streamId - Stream ID in format "collection_ip"
   * @param {Date} startDate - Start date for filtering
   * @param {Date} endDate - End date for filtering
   * @returns {Promise<Object>} Filtered recordings
   */
  async getRecordingsByDateRange(streamId, startDate, endDate) {
    try {
      const recordings = await this.getRecordings(streamId);

      if (!recordings.recordings || recordings.recordings.length === 0) {
        return recordings;
      }

      // Filter recordings by date range
      const filteredRecordings = recordings.recordings.filter(recording => {
        if (!recording.timestamp) return false;

        const recordingDate = new Date(recording.timestamp);
        return recordingDate >= startDate && recordingDate <= endDate;
      });

      return {
        ...recordings,
        recordings: filteredRecordings,
        count: filteredRecordings.length
      };
    } catch (error) {
      console.error(`Error fetching recordings by date range for ${streamId}:`, error);
      throw error;
    }
  },

  /**
   * Parse stream ID to get collection name and camera IP
   * @param {string} streamId - Stream ID in format "collection_ip"
   * @returns {Object} Object with collectionName and cameraIp
   */
  parseStreamId(streamId) {
    // Handle non-string inputs gracefully
    if (!streamId) {
      return {
        collectionName: 'Unknown',
        cameraIp: 'Unknown'
      };
    }

    // Convert to string if it's not already
    const streamIdStr = String(streamId);

    if (!streamIdStr.includes('_')) {
      // If no underscore, treat the whole thing as collection name
      return {
        collectionName: streamIdStr,
        cameraIp: 'Unknown'
      };
    }

    const parts = streamIdStr.split('_');
    if (parts.length < 2) {
      return {
        collectionName: streamIdStr,
        cameraIp: 'Unknown'
      };
    }

    return {
      collectionName: parts[0],
      cameraIp: parts.slice(1).join('_') // Handle IPs with underscores
    };
  },

  /**
   * Format recording timestamp for display
   * @param {string} timestamp - ISO timestamp string
   * @returns {string} Formatted date string
   */
  formatRecordingDate(timestamp) {
    try {
      if (!timestamp) return 'Unknown Date';

      const date = new Date(timestamp);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    } catch (error) {
      console.error('Error formatting date:', error);
      return 'Invalid Date';
    }
  },

  /**
   * Calculate and format recording duration
   * @param {Object} recording - Recording object with timestamp
   * @returns {string} Formatted duration string
   */
  formatRecordingDuration(recording) {
    try {
      if (!recording || !recording.timestamp) {
        return 'Unknown Duration';
      }

      // For 24-hour recordings, we can calculate the expected duration
      // Each recording is designed to be 24 hours (86400 seconds)
      const expectedDurationHours = 24;

      // If the recording is current (today), calculate actual duration
      const recordingDate = new Date(recording.timestamp);
      const now = new Date();
      const isToday = recordingDate.toDateString() === now.toDateString();

      if (isToday) {
        // Calculate actual duration for current recording
        const durationMs = now.getTime() - recordingDate.getTime();
        const durationHours = Math.floor(durationMs / (1000 * 60 * 60));
        const durationMinutes = Math.floor((durationMs % (1000 * 60 * 60)) / (1000 * 60));

        if (durationHours > 0) {
          return `${durationHours}h ${durationMinutes}m (Recording)`;
        } else {
          return `${durationMinutes}m (Recording)`;
        }
      } else {
        // For completed recordings, show 24 hours
        return '24h (Complete)';
      }
    } catch (error) {
      console.error('Error calculating duration:', error);
      return 'Unknown Duration';
    }
  },

  /**
   * Format file size for display
   * @param {number} sizeBytes - File size in bytes
   * @returns {string} Formatted size string
   */
  formatFileSize(sizeBytes) {
    if (!sizeBytes || sizeBytes === 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const k = 1024;
    const i = Math.floor(Math.log(sizeBytes) / Math.log(k));
    
    return `${parseFloat((sizeBytes / Math.pow(k, i)).toFixed(2))} ${units[i]}`;
  },

  /**
   * Handle API errors consistently
   * @private
   */
  _handleError(error, defaultMessage) {
    if (error.response) {
      // Server responded with error status
      let message = defaultMessage;

      // Check if response is HTML (common when backend returns error pages)
      const responseData = error.response.data;
      if (typeof responseData === 'string' && responseData.includes('<!DOCTYPE')) {
        message = 'Backend server returned HTML instead of JSON. Please check if the backend is running correctly and the API endpoints are properly configured.';
      } else if (responseData?.detail) {
        message = responseData.detail;
      } else if (responseData?.message) {
        message = responseData.message;
      } else if (typeof responseData === 'string') {
        message = responseData;
      }

      const enhancedError = new Error(message);
      enhancedError.status = error.response.status;
      enhancedError.data = error.response.data;
      return enhancedError;
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      const enhancedError = new Error('Video processing request timed out. Please try selecting a shorter clip duration.');
      enhancedError.status = 408;
      return enhancedError;
    } else if (error.request) {
      // Request was made but no response received
      const enhancedError = new Error('Network error: Unable to connect to server. Please ensure the backend is running on port 8000.');
      enhancedError.status = 0;
      return enhancedError;
    } else {
      // Something else happened (including JSON parsing errors)
      let message = error.message || defaultMessage;

      // Handle JSON parsing errors specifically
      if (error.message && error.message.includes('Unexpected token')) {
        if (error.message.includes('<!DOCTYPE')) {
          message = 'Backend server returned HTML instead of JSON. This usually means the API endpoint is not found or the backend is not properly configured.';
        } else {
          message = 'Invalid JSON response from server. Please check backend configuration.';
        }
      }

      return new Error(message);
    }
  }
};

export default archiveApi;
