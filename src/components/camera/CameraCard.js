import React, { useState, useEffect } from 'react';
import MJPEGStreamPlayer from './MJPEGStreamPlayer';
import { useCameraStore } from '../../store/cameraStore';
import { useArchiveStore } from '../../store/archiveStore';
import './CameraCard.css';

const CameraCard = ({ camera, onCameraClick }) => {
  const { toggleBookmark, isBookmarked } = useCameraStore();
  const { getRecordingStatus } = useArchiveStore();

  const [isBookmarkedCamera, setIsBookmarkedCamera] = useState(isBookmarked(camera.id));

  // Generate stream ID for recording status
  // Handle both collection and collectionId properties
  const collectionName = camera.collection || camera.collectionId;
  const streamId = collectionName && camera.ip ? `${collectionName}_${camera.ip}` : null;
  const recordingStatus = streamId ? getRecordingStatus(streamId) : null;

  // Update bookmark state when it changes in the store
  useEffect(() => {
    setIsBookmarkedCamera(isBookmarked(camera.id));
  }, [camera.id, isBookmarked]);

  const handleBookmarkToggle = (e) => {
    e.stopPropagation();
    console.log('Toggling bookmark for camera:', camera.id, camera.name);
    toggleBookmark(camera.id);
    // Update local state immediately for better UI responsiveness
    setIsBookmarkedCamera(!isBookmarkedCamera);
  };

  const handleCardClick = () => {
    if (onCameraClick) {
      onCameraClick(camera);
    }
  };

  return (
    <div
      className={`camera-card ${isBookmarkedCamera ? 'bookmarked' : ''}`}
      onClick={handleCardClick}
    >
      <div className="camera-card-header">
        <h3 className="camera-name">{camera.name}</h3>
        <div className="camera-controls">
          {/* Recording status indicator */}
          {recordingStatus && (
            <div
              className={`recording-status-dot ${recordingStatus.status}`}
              title={`Recording Status: ${
                recordingStatus.status === 'recording' ? 'Recording' :
                recordingStatus.status === 'stopped' ? 'Not Recording' :
                recordingStatus.status === 'backend_unavailable' ? 'Backend Unavailable' :
                recordingStatus.status === 'stale' ? 'Connection Lost' :
                'Unknown'
              }`}
            >
              <div className={`status-indicator ${
                recordingStatus.status === 'recording' ? 'recording' :
                recordingStatus.status === 'backend_unavailable' ? 'backend-unavailable' :
                'stopped'
              }`} />
            </div>
          )}

          {/* Bookmark button */}
          <button
            className={`bookmark-button ${isBookmarkedCamera ? 'bookmarked' : ''}`}
            onClick={handleBookmarkToggle}
            title={isBookmarkedCamera ? 'Remove Bookmark' : 'Add Bookmark'}
          >
            <svg
              width="20"
              height="20"
              viewBox="0 0 24 24"
              fill={isBookmarkedCamera ? "#FFD700" : "none"}
              stroke={isBookmarkedCamera ? "#FFD700" : "#FFFFFF"}
              strokeWidth="2"
            >
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
            </svg>
          </button>
        </div>
      </div>

      <div className="camera-card-content">
        {camera.streamUrl || camera.ip ? (
          // Use new MJPEG stream player for all cameras with stream URL or IP
          <MJPEGStreamPlayer
            camera={camera}
          />
        ) : (
          // Fallback when no stream information is available
          <div className="camera-offline">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#999999" strokeWidth="2">
              <path d="M10.5 15.5L3 8.5"></path>
              <path d="M21 8.5L16.5 13"></path>
              <rect x="3" y="3" width="18" height="12" rx="2"></rect>
              <path d="M7 15v2"></path>
              <path d="M17 15v2"></path>
              <path d="M7 19h10"></path>
            </svg>
            <span>Camera offline</span>
          </div>
        )}
      </div>

      <div className="camera-card-footer">
        <span className="camera-status">
          Live
        </span>
        <span className="camera-ip">{camera.ip || 'Unknown IP'}</span>
      </div>
    </div>
  );
};

export default CameraCard;
