// API service for alerts configuration management
import { API_BASE_URL } from '../utils/apiConfig';
import { apiRequest, getApiUrl } from '../utils/api';

// Fetch alerts configuration data
export const fetchAlertsConfig = async () => {
  try {
    return await apiRequest(`/api/augment/alerts/config`);
  } catch (error) {
    console.error('Failed to fetch alerts configuration:', error);
    throw error;
  }
};

// Update alerts configuration
export const updateAlertsConfig = async (configData) => {
  try {
    return await apiRequest(`/api/augment/alerts/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configData)
    });
  } catch (error) {
    console.error('Failed to update alerts configuration:', error);
    throw error;
  }
};

export default {
  fetchAlertsConfig,
  updateAlertsConfig
};
