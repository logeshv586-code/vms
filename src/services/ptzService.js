import { apiRequest } from '../utils/api';

const BASE = '/api/augment/ptz';

const cameraPath = (cameraId) => encodeURIComponent(cameraId);

export const getPtzConfig = (cameraId) =>
  apiRequest(`${BASE}/config/${cameraPath(cameraId)}`);

export const probePtzCapabilities = (cameraId, port = 80) =>
  apiRequest(`${BASE}/capabilities/${cameraPath(cameraId)}?port=${encodeURIComponent(port)}`);

export const savePtzTour = (cameraId, config) =>
  apiRequest(`${BASE}/tour/${cameraPath(cameraId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });

export const startPtzTour = (cameraId) =>
  apiRequest(`${BASE}/tour/${cameraPath(cameraId)}/start`, { method: 'POST' });

export const stopPtzTour = (cameraId) =>
  apiRequest(`${BASE}/tour/${cameraPath(cameraId)}/stop`, { method: 'POST' });

export const savePtzTrack = (cameraId, config) =>
  apiRequest(`${BASE}/track/${cameraPath(cameraId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config)
  });

export const startPtzTrack = (cameraId) =>
  apiRequest(`${BASE}/track/${cameraPath(cameraId)}/start`, { method: 'POST' });

export const stopPtzTrack = (cameraId) =>
  apiRequest(`${BASE}/track/${cameraPath(cameraId)}/stop`, { method: 'POST' });

export const sendPtzTrackTarget = (cameraId, target) =>
  apiRequest(`${BASE}/track/${cameraPath(cameraId)}/target`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(target)
  });
