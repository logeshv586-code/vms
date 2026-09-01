
/**
 * Utility functions for camera operations
 */

/**
 * Generates a unique camera ID based on collection name and IP
 * @param {string} collectionName - Name of the collection
 * @param {string} ip - IP address of the camera
 * @returns {string} A unique camera ID
 */
export const generateCameraId = (collectionName, ip) => {
  const normalizedCollection = normalizeCollectionName(collectionName);
  const normalizedIp = ip.replace(/\./g, '-');
  return `camera-${normalizedCollection}-${normalizedIp}`;
};

/**
 * Derives a consistent stream ID for a camera (format: Collection_IP or webcam)
 * @param {Object} camera - Camera object
 * @returns {string} Consistent stream ID used across API and engines
 */
export const getCameraStreamId = (camera) => {
  if (!camera) return '';
  if (camera.id === 'webcam' || camera.ip === 'webcam') return 'webcam';
  if (camera.streamId && camera.streamId.includes('_')) return camera.streamId;

  const collection = camera.collectionName || camera.collection || '';
  const ip = camera.ip || '';
  if (collection && ip) {
    return `${collection}_${ip}`;
  }

  if (camera.id) {
    const parsed = parseCameraId(camera.id);
    if (parsed.collectionName && parsed.ip) {
      return `${parsed.collectionName}_${parsed.ip}`;
    }
    return camera.id.replace(/^camera-/, '');
  }

  return '';
};

/**
 * Parses a camera ID to extract collection name and IP
 * @param {string} cameraId - The camera ID to parse
 * @param {Array} collections - Optional array of collections to match against for exact name
 * @returns {Object} Object containing collectionName, normalizedCollectionName, and ip
 */
export const parseCameraId = (cameraId, collections = null) => {
  // Remove 'camera-' prefix
  const withoutPrefix = cameraId.replace(/^camera-/, '');
  
  // Split by dashes
  const parts = withoutPrefix.split('-');
  
  // IP addresses always have 4 parts when dash-separated (e.g., 172-16-1-102)
  // So take the last 4 parts as IP and everything before as collection
  if (parts.length < 4) {
    return { collectionName: '', normalizedCollectionName: '', ip: '' };
  }

  // Last 4 parts form the IP address
  const ipParts = parts.slice(-4);
  const ip = ipParts.join('.');

  // Everything before the IP parts forms the collection name
  const collectionParts = parts.slice(0, -4);
  const normalizedCollectionName = collectionParts.join('-');

  // If collections array is provided, find the exact match
  let collectionName = denormalizeCollectionName(normalizedCollectionName);
  if (collections && Array.isArray(collections)) {
    const matchingCollection = collections.find(c => 
      normalizeCollectionName(c.name) === normalizedCollectionName
    );
    if (matchingCollection) {
      collectionName = matchingCollection.name;
    }
  }

  return {
    collectionName,
    normalizedCollectionName,
    ip
  };
};

/**
 * Normalizes a collection name by replacing spaces and special characters
 * @param {string} name - Collection name to normalize
 * @returns {string} Normalized collection name
 */
export const normalizeCollectionName = (name) => {
  return name.trim().toLowerCase().replace(/[^a-z0-9]/g, '-');
};

/**
 * Denormalizes a collection name by replacing dashes with spaces and capitalizing words
 * @param {string} name - Normalized collection name
 * @returns {string} Original collection name format
 */
export const denormalizeCollectionName = (name) => {
  return name
    .split('-')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
    .trim();
};

/**
 * Normalizes a camera ID by removing special characters
 * @param {string} cameraId - Camera ID to normalize
 * @returns {string} Normalized camera ID
 */
export const normalizeCameraId = (cameraId) => {
  return cameraId.trim().toLowerCase().replace(/[^a-z0-9-]/g, '');
};

/**
 * Parses a stream URL to extract collection name and IP
 * @param {string} streamUrl - The stream URL to parse
 * @returns {Object} Object containing collectionName and ip
 */
export const parseStreamUrl = (streamUrl) => {
  try {
    // Handle empty or invalid URLs
    if (!streamUrl) {
      return { collectionName: '', ip: '' };
    }

    // Try to extract collection name and IP from URL
    // Example format: rtsp://username:password@192.168.1.100:554/stream
    const url = new URL(streamUrl);
    const ip = url.hostname;

    // Try to get collection name from path or use empty string
    const pathParts = url.pathname.split('/').filter(Boolean);
    const collectionName = pathParts[0] || '';

    return { collectionName, ip };
  } catch (error) {
    console.warn('Failed to parse stream URL:', error);
    return { collectionName: '', ip: '' };
  }
};
