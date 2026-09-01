/**
 * IP Address Validation Utilities
 * Provides validation functions for IP addresses with focus on private network ranges
 */

/**
 * Validates IPv4 address format
 * @param {string} ip - The IP address to validate
 * @returns {boolean} True if valid IPv4 format, false otherwise
 */
export const isValidIPFormat = (ip) => {
  const regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;
  return regex.test(ip);
};

/**
 * Checks if an IP address is within private network ranges
 * Private ranges:
 * - 192.168.0.0 – 192.168.255.255 (Class C private networks)
 * - 10.0.0.0 – 10.255.255.255 (Class A private networks)
 * - 172.16.0.0 – 172.31.255.255 (Class B private networks)
 * @param {string} ip - The IP address to check
 * @returns {boolean} True if IP is in private range, false otherwise
 */
export const isPrivateIP = (ip) => {
  if (!isValidIPFormat(ip)) {
    return false;
  }

  const parts = ip.split('.').map(Number);
  const [first, second] = parts;

  // Class A private: 10.0.0.0 – 10.255.255.255
  if (first === 10) {
    return true;
  }

  // Class B private: 172.16.0.0 – 172.31.255.255
  if (first === 172 && second >= 16 && second <= 31) {
    return true;
  }

  // Class C private: 192.168.0.0 – 192.168.255.255
  if (first === 192 && second === 168) {
    return true;
  }

  return false;
};

/**
 * Validates that an IP address is both valid format and within private ranges
 * @param {string} ip - The IP address to validate
 * @returns {Object} Validation result with isValid boolean and error message
 */
export const validatePrivateIP = (ip) => {
  if (!ip || !ip.trim()) {
    return {
      isValid: false,
      error: 'IP address is required'
    };
  }

  const trimmedIP = ip.trim();

  if (!isValidIPFormat(trimmedIP)) {
    return {
      isValid: false,
      error: 'Please enter a valid IP address format (e.g., 192.168.1.100)'
    };
  }

  if (!isPrivateIP(trimmedIP)) {
    return {
      isValid: false,
      error: 'IP address must be within private network ranges:\n• 192.168.0.0 – 192.168.255.255 (most common)\n• 10.0.0.0 – 10.255.255.255\n• 172.16.0.0 – 172.31.255.255'
    };
  }

  return {
    isValid: true,
    error: null
  };
};

/**
 * Extracts IP address from a stream URL
 * @param {string} streamUrl - The stream URL to parse
 * @returns {string|null} The extracted IP address or null if not found
 */
export const extractIPFromStreamURL = (streamUrl) => {
  if (!streamUrl) {
    return null;
  }

  try {
    const url = new URL(streamUrl);
    const hostname = url.hostname;
    
    // Check if hostname is an IP address (not a domain name)
    if (isValidIPFormat(hostname)) {
      return hostname;
    }
    
    return null;
  } catch (error) {
    // If URL parsing fails, try to extract IP with regex
    const ipMatch = streamUrl.match(/(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})/);
    return ipMatch ? ipMatch[1] : null;
  }
};
