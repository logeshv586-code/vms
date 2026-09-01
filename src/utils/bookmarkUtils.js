import { normalizeCameraId } from './cameraUtils';

/**
 * Checks if a camera is bookmarked by comparing normalized IDs
 * 
 * @param {string} cameraId - The camera ID to check
 * @param {Array<string>} bookmarks - Array of bookmarked camera IDs
 * @returns {boolean} - True if the camera is bookmarked
 */
export const isBookmarked = (cameraId, bookmarks) => {
  // Normalize the camera ID
  const normalizedId = normalizeCameraId(cameraId);
  
  // Check if either the original or normalized ID is in bookmarks
  const result = bookmarks.some(bookmark => {
    const normalizedBookmark = normalizeCameraId(bookmark);
    return bookmark === cameraId || normalizedBookmark === normalizedId;
  });
  
  console.log('Checking if bookmarked:', cameraId, result);
  return result;
};

/**
 * Gets all bookmarked cameras using normalized ID comparison
 * 
 * @param {Array<Object>} cameras - Array of camera objects
 * @param {Array<string>} bookmarks - Array of bookmarked camera IDs
 * @returns {Array<Object>} - Array of bookmarked camera objects
 */
export const getBookmarkedCameras = (cameras, bookmarks) => {
  console.log('Getting bookmarked cameras. Total bookmarks:', bookmarks.length);
  console.log('Total cameras in store:', cameras.length);

  // Filter cameras using normalized ID comparison
  const bookmarkedCameras = cameras.filter(camera => isBookmarked(camera.id, bookmarks));
  
  console.log('Found bookmarked cameras:', bookmarkedCameras.length);
  return bookmarkedCameras;
};