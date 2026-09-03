import { apiRequest } from '../utils/api';

const EVENTS_API = '/api/augment/events';

const unwrapList = (response) => (response?.success ? (response.data || []) : []);

export const getCurrentEvents = async () => {
  const response = await apiRequest(`${EVENTS_API}/current`);
  return unwrapList(response);
};

export const searchEvents = async (filters = {}) => {
  const queryParams = new URLSearchParams();
  const ignored = new Set([
    'all',
    'All Categories',
    'All Rules',
    'All Priorities',
    'All Statuses',
    'All Locations'
  ]);

  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '' && !ignored.has(value)) {
      queryParams.append(key, value);
    }
  });

  const query = queryParams.toString();
  const response = await apiRequest(`${EVENTS_API}/search${query ? `?${query}` : ''}`);
  return unwrapList(response);
};

export const acknowledgeEvent = async (eventId) => {
  if (!eventId) throw new Error('eventId is required');
  const response = await apiRequest(`${EVENTS_API}/acknowledge/${encodeURIComponent(eventId)}`, {
    method: 'POST'
  });
  return Boolean(response?.success);
};

export const resolveEvent = async (eventId) => {
  if (!eventId) throw new Error('eventId is required');
  const response = await apiRequest(`${EVENTS_API}/resolve/${encodeURIComponent(eventId)}`, {
    method: 'POST'
  });
  return Boolean(response?.success);
};

export const fetchEventRules = () => apiRequest(`${EVENTS_API}/rules`);

export const updateEventRules = (rules) => apiRequest(`${EVENTS_API}/rules`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ rules })
});

export const toggleDetectionRule = (eventName, enabled) => apiRequest('/api/augment/detection-rule', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ event: eventName, enabled: Boolean(enabled) })
});

export const fetchEventStatistics = (params = {}) => {
  const queryParams = new URLSearchParams();
  if (params.camera_id) queryParams.append('camera_id', params.camera_id);
  if (params.event_id) queryParams.append('event_id', params.event_id);
  const query = queryParams.toString();
  return apiRequest(`${EVENTS_API}/statistics${query ? `?${query}` : ''}`);
};

export const fetchCameraRules = () => apiRequest('/api/augment/camera-rules');

export const applyCameraRules = (cameraIds, ruleIds) => apiRequest('/api/augment/apply-camera-rules', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ cameraIds, ruleIds })
});

export const toggleCameraRule = async (cameraId, ruleId, enabled) => {
  const rulesResponse = await fetchCameraRules();
  if (!rulesResponse?.success) throw new Error('Failed to fetch current camera rules');

  const cameraRules = rulesResponse.data?.cameraRules || {};
  const currentRules = cameraRules[cameraId] || [];
  const newRules = enabled
    ? [...new Set([...currentRules, ruleId])]
    : currentRules.filter(id => id !== ruleId);

  return applyCameraRules([cameraId], newRules);
};

// Backward-compatible object API used by older screens.
export const eventService = {
  getCurrentEvents,
  searchEvents,
  acknowledgeEvent,
  resolveEvent,
  fetchEventRules,
  updateEventRules,
  toggleDetectionRule,
  fetchEventStatistics,
  fetchCameraRules,
  applyCameraRules,
  toggleCameraRule
};

export default eventService;
