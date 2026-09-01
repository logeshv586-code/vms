// API service for events management
import { API_BASE_URL } from '../utils/apiConfig';
import { apiRequest } from '../utils/api';

// Fetch event rules
export const fetchEventRules = async () => {
  try {
    return await apiRequest(`/api/augment/events/rules`);
  } catch (error) {
    console.error('Failed to fetch event rules:', error);
    throw error;
  }
};

// Update event rules
export const updateEventRules = async (rules) => {
  try {
    return await apiRequest(`/api/augment/events/rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules })
    });
  } catch (error) {
    console.error('Failed to update event rules:', error);
    throw error;
  }
};

// Toggle a single detection rule
export const toggleDetectionRule = async (eventName, enabled) => {
  try {
    return await apiRequest(`/api/augment/detection-rule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event: eventName,
        enabled: enabled
      })
    });
  } catch (error) {
    console.error(`Failed to toggle detection rule '${eventName}':`, error);
    throw error;
  }
};

// Fetch event statistics
export const fetchEventStatistics = async (params = {}) => {
  try {
    // Build query string from params
    const queryParams = new URLSearchParams();
    if (params.camera_id) queryParams.append('camera_id', params.camera_id);
    if (params.event_id) queryParams.append('event_id', params.event_id);

    const queryString = queryParams.toString();
    const url = `/api/augment/events/statistics${queryString ? `?${queryString}` : ''}`;

    return await apiRequest(url);
  } catch (error) {
    console.error('Failed to fetch event statistics:', error);
    throw error;
  }
};

// Fetch camera rules (which rules are applied to which cameras)
export const fetchCameraRules = async () => {
  try {
    return await apiRequest(`/api/augment/camera-rules`);
  } catch (error) {
    console.error('Failed to fetch camera rules:', error);
    throw error;
  }
};

// Apply rules to cameras
export const applyCameraRules = async (cameraIds, ruleIds) => {
  try {
    return await apiRequest(`/api/augment/apply-camera-rules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cameraIds,
        ruleIds
      })
    });
  } catch (error) {
    console.error('Failed to apply rules to cameras:', error);
    throw error;
  }
};

// Toggle a specific rule for a specific camera
export const toggleCameraRule = async (cameraId, ruleId, enabled) => {
  try {
    // We'll use the existing apply-camera-rules endpoint
    // Get the current rules for this camera first
    const rulesResponse = await fetchCameraRules();
    if (!rulesResponse.success) {
      throw new Error('Failed to fetch current camera rules');
    }

    const cameraRules = rulesResponse.data.cameraRules || {};
    const currentRules = cameraRules[cameraId] || [];

    // Create new rules array based on the enabled state
    let newRules;
    if (enabled) {
      // Add the rule if it's not already there
      newRules = [...currentRules, ruleId].filter((v, i, a) => a.indexOf(v) === i);
    } else {
      // Remove the rule
      newRules = currentRules.filter(id => id !== ruleId);
    }

    // Apply the updated rules
    return await applyCameraRules([cameraId], newRules);
  } catch (error) {
    console.error(`Failed to toggle rule ${ruleId} for camera ${cameraId}:`, error);
    throw error;
  }
};
