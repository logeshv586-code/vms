/**
 * API Configuration
 *
 * This file centralizes API configuration settings for the application.
 * It exports the base URL for API requests, which is read from environment variables.
 */

// Read the API base URL from environment variables
// Default to http://localhost:8000 if not specified
export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

/**
 * Get standardized augment API URL
 * @param {string} functionName - The function name for the augment API
 * @returns {string} - The complete URL for the augment API endpoint
 */
export const getAugmentUrl = (functionName) =>
  `${API_BASE_URL}/api/augment/${functionName}`;

// Export other API-related configuration as needed
export default {
  API_BASE_URL,
  getAugmentUrl
};
