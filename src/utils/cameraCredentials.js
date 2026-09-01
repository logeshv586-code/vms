/**
 * Camera credentials management utility
 * Handles different credential combinations for RTSP cameras
 */

// Common credential combinations found in the logs
export const COMMON_CREDENTIALS = [
  { username: 'admin', password: 'gbfdsrjdjygd', description: 'Primary credentials' },
  { username: 'admin', password: 'Admin@123', description: 'Default credentials' },
  { username: 'admin', password: 'fesfgeargerg', description: 'Alternative credentials 1' },
  { username: 'admin', password: 'asgnert', description: 'Alternative credentials 2' },
  { username: 'admin', password: 'admin', description: 'Simple admin' },
  { username: 'admin', password: '123456', description: 'Common password' },
  { username: 'root', password: 'admin', description: 'Root access' },
  { username: 'user', password: 'user', description: 'User access' }
];

/**
 * Generate RTSP URL with credentials
 * @param {string} ip - Camera IP address
 * @param {Object} credentials - Credentials object with username and password
 * @param {number} port - RTSP port (default: 554)
 * @param {string} path - RTSP path (default: empty)
 * @returns {string} Complete RTSP URL
 */
export const generateRTSPUrl = (ip, credentials, port = 554, path = '') => {
  const { username, password } = credentials;
  const pathPart = path ? `/${path}` : '';
  return `rtsp://${username}:${password}@${ip}:${port}${pathPart}`;
};

/**
 * Extract credentials from RTSP URL
 * @param {string} rtspUrl - RTSP URL
 * @returns {Object} Object containing username, password, ip, port, and path
 */
export const parseRTSPUrl = (rtspUrl) => {
  try {
    const url = new URL(rtspUrl);
    return {
      username: url.username || '',
      password: url.password || '',
      ip: url.hostname || '',
      port: url.port || '554',
      path: url.pathname || ''
    };
  } catch (error) {
    console.error('Failed to parse RTSP URL:', error);
    return {
      username: '',
      password: '',
      ip: '',
      port: '554',
      path: ''
    };
  }
};

/**
 * Get the best credentials for a camera IP based on success history
 * @param {string} ip - Camera IP address
 * @returns {Object} Best credentials to try
 */
export const getBestCredentials = (ip) => {
  // Try to get stored successful credentials for this IP
  const storedCredentials = localStorage.getItem(`camera_credentials_${ip}`);
  if (storedCredentials) {
    try {
      const parsed = JSON.parse(storedCredentials);
      if (parsed.username && parsed.password) {
        return parsed;
      }
    } catch (error) {
      console.warn('Failed to parse stored credentials:', error);
    }
  }

  // Return the first (most likely to work) credentials
  return COMMON_CREDENTIALS[0];
};

/**
 * Store successful credentials for a camera IP
 * @param {string} ip - Camera IP address
 * @param {Object} credentials - Successful credentials
 */
export const storeSuccessfulCredentials = (ip, credentials) => {
  try {
    localStorage.setItem(`camera_credentials_${ip}`, JSON.stringify(credentials));
    console.log(`Stored successful credentials for camera ${ip}`);
  } catch (error) {
    console.error('Failed to store credentials:', error);
  }
};

/**
 * Get all credential combinations to try for a camera
 * @param {string} ip - Camera IP address
 * @returns {Array} Array of credential objects to try in order
 */
export const getCredentialCombinations = (ip) => {
  const bestCredentials = getBestCredentials(ip);
  
  // Put the best credentials first, then try others
  const combinations = [bestCredentials];
  
  // Add other combinations that aren't the best one
  COMMON_CREDENTIALS.forEach(cred => {
    if (cred.username !== bestCredentials.username || cred.password !== bestCredentials.password) {
      combinations.push(cred);
    }
  });
  
  return combinations;
};

/**
 * Mask credentials in URL for logging
 * @param {string} rtspUrl - RTSP URL with credentials
 * @returns {string} URL with masked credentials
 */
export const maskCredentials = (rtspUrl) => {
  try {
    const url = new URL(rtspUrl);
    if (url.username && url.password) {
      return rtspUrl.replace(`${url.username}:${url.password}@`, '***:***@');
    }
    return rtspUrl;
  } catch (error) {
    return rtspUrl;
  }
};

/**
 * Validate IP address format
 * @param {string} ip - IP address to validate
 * @returns {boolean} True if valid IP address
 */
export const isValidIP = (ip) => {
  const ipRegex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
  return ipRegex.test(ip);
};

/**
 * Check if IP is in private range
 * @param {string} ip - IP address to check
 * @returns {boolean} True if IP is in private range
 */
export const isPrivateIP = (ip) => {
  if (!isValidIP(ip)) return false;
  
  const parts = ip.split('.').map(Number);
  
  // 192.168.x.x
  if (parts[0] === 192 && parts[1] === 168) return true;
  
  // 10.x.x.x
  if (parts[0] === 10) return true;
  
  // 172.16.x.x - 172.31.x.x
  if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
  
  return false;
};
