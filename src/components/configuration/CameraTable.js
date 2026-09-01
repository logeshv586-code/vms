import React, { useState, useEffect } from 'react';
import cameraApi from '../../services/cameraApi';
import './CameraTable.css';

const maskStreamUrl = (url) => {
  if (!url) return '';
  try {
    const schemeIndex = url.indexOf('://');
    if (schemeIndex === -1) return url;
    
    const scheme = url.substring(0, schemeIndex + 3);
    const rest = url.substring(schemeIndex + 3);
    
    const atIndex = rest.lastIndexOf('@');
    if (atIndex === -1) return url;
    
    const credentials = rest.substring(0, atIndex);
    const hostAndPath = rest.substring(atIndex + 1);
    
    const colonIndex = credentials.indexOf(':');
    if (colonIndex === -1) {
      return `${scheme}***@${hostAndPath}`;
    }
    
    const username = credentials.substring(0, colonIndex);
    const password = credentials.substring(colonIndex + 1);
    
    const maskedUser = '*'.repeat(username.length || 5);
    const maskedPass = '*'.repeat(password.length || 5);
    
    return `${scheme}${maskedUser}:${maskedPass}@${hostAndPath}`;
  } catch (e) {
    return url;
  }
};

const CameraTable = ({ refreshKey }) => {
  const [cameras, setCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Fetch camera data
  const fetchCameras = async () => {
    try {
      setError(null);
      const cameraData = await cameraApi.getCamerasWithStatus();
      setCameras(cameraData);
    } catch (err) {
      setError('Failed to load camera data. Please check if the backend server is running.');
      console.error('Error fetching cameras:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  // Refresh camera data
  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchCameras();
  };

  // Initial load & respond to global header refresh
  useEffect(() => {
    fetchCameras();
  }, [refreshKey]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (!refreshing) {
        handleRefresh();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [refreshing]);

  // Render status indicator
  const renderStatusIndicator = (camera) => {
    return (
      <div className={`status-indicator ${camera.isActive ? 'active' : 'inactive'}`}>
        <span className="status-dot"></span>
        <span className="status-text">{camera.status}</span>
      </div>
    );
  };

  // Render loading state
  if (loading) {
    return (
      <div className="camera-table-container">
        <div className="loading-state">
          <div className="loading-spinner"></div>
          <p>Loading cameras...</p>
        </div>
      </div>
    );
  }

  // Render error state
  if (error) {
    return (
      <div className="camera-table-container">
        <div className="error-state">
          <p className="error-message">{error}</p>
          <button className="retry-button" onClick={handleRefresh}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Render empty state
  if (cameras.length === 0) {
    return (
      <div className="camera-table-container">
        <div className="empty-state">
          <p>No cameras configured. Use the "Add New Camera" button to add cameras.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="camera-table-container">
      <div className="table-header">
        <div className="table-title">
          <h3>Camera Overview</h3>
          <span className="camera-count">({cameras.length} cameras)</span>
        </div>
      </div>


      <div className="table-wrapper">
        <table className="camera-table">
          <thead>
            <tr>
              <th>Camera Name</th>
              <th>IP Address</th>
              <th>Collection</th>
              <th>Status</th>
              <th>Stream URL</th>
            </tr>
          </thead>
          <tbody>
            {cameras.map((camera) => (
              <tr key={camera.id} className={`camera-row ${camera.isActive ? 'active' : 'inactive'}`}>
                <td className="camera-name">
                  <div className="name-cell">
                    <span className="name-text">{camera.name}</span>
                  </div>
                </td>
                <td className="camera-ip">
                  <code>{camera.ip}</code>
                </td>
                <td className="camera-collection">
                  <span className="collection-badge">{camera.collection}</span>
                </td>
                <td className="camera-status">
                  {renderStatusIndicator(camera)}
                </td>
                <td className="camera-stream-url">
                  <div className="stream-url-cell">
                    <span className="stream-url" title={maskStreamUrl(camera.streamUrl)}>
                      {maskStreamUrl(camera.streamUrl)}
                    </span>
                    {camera.isActive && camera.feedUrl && (
                      <a 
                        href={camera.feedUrl} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="feed-link"
                        title="Open live feed"
                      >
                        📹
                      </a>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default CameraTable;
