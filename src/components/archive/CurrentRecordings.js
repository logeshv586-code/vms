import React, { useState, useEffect } from 'react';
import {
  Video,
  Play,
  Clock,
  HardDrive,
  CheckCircle,
  AlertCircle,
  RefreshCw,
  Eye
} from 'lucide-react';
import { API_BASE_URL } from '../../utils/apiConfig';
import './CurrentRecordings.css';

const CurrentRecordings = ({ onViewRecording, refreshKey }) => {
  const [currentRecordings, setCurrentRecordings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  // Fetch current recordings
  const fetchCurrentRecordings = async () => {
    try {
      setError(null);
      const response = await fetch(`${API_BASE_URL}/api/archive/current`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      const validRecordings = (data.current_recordings || []).filter(recording => (recording.file_size || 0) >= 10240 || recording.is_recording);
      setCurrentRecordings(validRecordings);
      setLastUpdate(new Date());
    } catch (err) {
      console.error('Error fetching current recordings:', err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Initial load & respond to global header refresh
  useEffect(() => {
    fetchCurrentRecordings();
    
    const interval = setInterval(fetchCurrentRecordings, 10000);
    return () => clearInterval(interval);
  }, [refreshKey]);

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Format duration
  const formatDuration = (seconds) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle view recording
  const handleViewRecording = (recording) => {
    if (onViewRecording) {
      onViewRecording(recording);
    } else {
      // Open recording in new tab for viewing while recording
      const videoUrl = `${API_BASE_URL}/api/archive/stream/${recording.stream_id}/${recording.filename}`;
      window.open(videoUrl, '_blank');
    }
  };

  // Manual refresh
  const handleRefresh = () => {
    setIsLoading(true);
    fetchCurrentRecordings();
  };

  return (
    <div className="current-recordings-content">
      <div className="current-recordings-container">
        {/* Header */}
        <div className="current-recordings-header">
          <div className="header-title">
            <h1>Current Recordings</h1>
            <p>Live recordings that can be viewed while recording</p>
          </div>
        </div>


        {/* Status Card */}
        <div className="recording-status-card">
          <div className="status-header">
            <h3>Recording Status</h3>
            <div className="system-status">
              {error ? (
                <>
                  <AlertCircle className="status-icon error" />
                  System Error
                </>
              ) : (
                <>
                  <CheckCircle className="status-icon active" />
                  System Active
                </>
              )}
            </div>
          </div>
          
          <div className="status-info">
            <div className="status-item">
              <Video className="status-item-icon" />
              <div className="status-item-content">
                <span className="status-label">Active Recordings</span>
                <span className="status-value">{currentRecordings.length}</span>
              </div>
            </div>
            
            <div className="status-item">
              <Clock className="status-item-icon" />
              <div className="status-item-content">
                <span className="status-label">Last Updated</span>
                <span className="status-value">
                  {lastUpdate ? lastUpdate.toLocaleTimeString() : 'Never'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p>Loading current recordings...</p>
          </div>
        )}

        {/* Error State */}
        {error && !isLoading && (
          <div className="error-container">
            <AlertCircle className="error-icon" />
            <h3>Error Loading Recordings</h3>
            <p>{error}</p>
            <button onClick={handleRefresh} className="retry-button">
              Try Again
            </button>
          </div>
        )}

        {/* Current Recordings Grid */}
        {!isLoading && !error && (
          <div className="recordings-section">
            <div className="section-header">
              <h2>Live Recordings</h2>
              <span className="recordings-count">
                {currentRecordings.length} recording{currentRecordings.length !== 1 ? 's' : ''}
              </span>
            </div>

            {currentRecordings.length === 0 ? (
              <div className="no-recordings">
                <div className="no-recordings-icon">📹</div>
                <h3>No Active Recordings</h3>
                <p>No cameras are currently recording.</p>
                <p className="hint">
                  Recordings will appear here when cameras start recording.
                </p>
              </div>
            ) : (
              <div className="recordings-grid">
                {currentRecordings.map(recording => (
                  <div key={recording.stream_id} className="recording-card">
                    {/* Thumbnail */}
                    <div className="recording-thumbnail">
                      <div className="thumbnail-placeholder">
                        <Video className="camera-icon" />
                      </div>
                      <div className={`recording-badge ${recording.process_status || 'recording'}`}>
                        <div className="recording-dot"></div>
                        {recording.process_status === 'restarting' ? 'RESTARTING' : 'LIVE'}
                      </div>
                    </div>

                    {/* Content */}
                    <div className="recording-content">
                      <div className="recording-header">
                        <h4 className="recording-title">{recording.collection_name}</h4>
                        <span className="camera-ip">{recording.camera_ip}</span>
                      </div>

                      <div className="recording-details">
                        <div className="detail-item">
                          <Clock className="detail-icon" />
                          <span>Duration: {formatDuration(recording.duration_seconds)}</span>
                        </div>

                        <div className="detail-item">
                          <HardDrive className="detail-icon" />
                          <span>Size: {formatFileSize(recording.file_size)}</span>
                        </div>

                        {recording.process_status && recording.process_status !== 'recording' && (
                          <div className="detail-item status-item">
                            <div className={`status-dot ${recording.process_status}`}></div>
                            <span>Status: {recording.process_status === 'restarting' ? 'Restarting...' : recording.process_status}</span>
                          </div>
                        )}
                      </div>

                      <div className="recording-actions">
                        <button 
                          onClick={() => handleViewRecording(recording)}
                          className="view-button"
                        >
                          <Eye className="button-icon" />
                          View Live
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CurrentRecordings;
