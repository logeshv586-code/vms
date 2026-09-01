import axios from 'axios';
import { API_BASE_URL } from '../utils/apiConfig';

/**
 * Dashboard Analytics API service for fetching real-time VMS statistics
 */
class DashboardAnalyticsApi {
  constructor() {
    this.baseURL = `${API_BASE_URL}/api/dashboard`;
    console.log('DashboardAnalyticsApi - Base URL:', this.baseURL);

    // Create axios instance with timeout
    this.axiosInstance = axios.create({
      timeout: 10000, // 10 second timeout
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor for debugging
    this.axiosInstance.interceptors.request.use(
      (config) => {
        console.log(`Dashboard API Request: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => {
        console.error('Dashboard API Request Error:', error);
        return Promise.reject(error);
      }
    );

    // Add response interceptor for debugging
    this.axiosInstance.interceptors.response.use(
      (response) => {
        console.log(`Dashboard API Response: ${response.status} ${response.config.url}`);
        return response;
      },
      (error) => {
        console.error('Dashboard API Response Error:', error.response?.status, error.message);
        return Promise.reject(error);
      }
    );
  }

  /**
   * Get comprehensive dashboard analytics data
   * @returns {Promise<Object>} Complete dashboard analytics
   */
  async getDashboardAnalytics() {
    try {
      console.log('Fetching dashboard analytics from:', `${this.baseURL}/analytics`);
      const response = await this.axiosInstance.get(`${this.baseURL}/analytics`);
      console.log('Dashboard analytics response:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error fetching dashboard analytics:', error);
      if (error.code === 'ECONNREFUSED') {
        throw new Error('Cannot connect to backend server. Please ensure the backend is running on the correct port.');
      } else if (error.code === 'ECONNABORTED') {
        throw new Error('Request timeout. The server is taking too long to respond.');
      } else if (error.response) {
        throw new Error(`Server error: ${error.response.status} - ${error.response.statusText}`);
      } else if (error.request) {
        throw new Error('Network error. Please check your connection and ensure the backend server is running.');
      } else {
        throw new Error(`Request failed: ${error.message}`);
      }
    }
  }

  /**
   * Get current system performance metrics
   * @returns {Promise<Object>} System metrics (CPU, memory, disk, uptime)
   */
  async getSystemMetrics() {
    try {
      const response = await axios.get(`${this.baseURL}/system-metrics`);
      return response.data;
    } catch (error) {
      console.error('Error fetching system metrics:', error);
      throw error;
    }
  }

  /**
   * Get camera statistics
   * @returns {Promise<Object>} Camera stats (total, active, inactive, collections)
   */
  async getCameraStats() {
    try {
      const response = await axios.get(`${this.baseURL}/camera-stats`);
      return response.data;
    } catch (error) {
      console.error('Error fetching camera stats:', error);
      throw error;
    }
  }

  /**
   * Get recording statistics
   * @returns {Promise<Object>} Recording stats (total, size, by time period)
   */
  async getRecordingStats() {
    try {
      const response = await axios.get(`${this.baseURL}/recording-stats`);
      return response.data;
    } catch (error) {
      console.error('Error fetching recording stats:', error);
      throw error;
    }
  }

  /**
   * Get event statistics
   * @returns {Promise<Object>} Event stats (total, by type, recent events)
   */
  async getEventStats() {
    try {
      const response = await axios.get(`${this.baseURL}/event-stats`);
      return response.data;
    } catch (error) {
      console.error('Error fetching event stats:', error);
      throw error;
    }
  }

  /**
   * Get user statistics
   * @returns {Promise<Object>} User stats (total, active sessions, roles)
   */
  async getUserStats() {
    try {
      const response = await axios.get(`${this.baseURL}/user-stats`);
      return response.data;
    } catch (error) {
      console.error('Error fetching user stats:', error);
      throw error;
    }
  }

  /**
   * Get detailed storage usage information
   * @returns {Promise<Object>} Storage usage details
   */
  async getStorageUsage() {
    try {
      const response = await axios.get(`${this.baseURL}/storage-usage`);
      return response.data;
    } catch (error) {
      console.error('Error fetching storage usage:', error);
      throw error;
    }
  }

  /**
   * Get recent activity summary
   * @returns {Promise<Object>} Activity summary
   */
  async getActivitySummary() {
    try {
      const response = await axios.get(`${this.baseURL}/activity-summary`);
      return response.data;
    } catch (error) {
      console.error('Error fetching activity summary:', error);
      throw error;
    }
  }
}

// Create and export a singleton instance
const dashboardAnalyticsApi = new DashboardAnalyticsApi();
export default dashboardAnalyticsApi;
