import React, { useState, useEffect } from 'react';
import LayoutSelector from '../layout/LayoutSelector';
import VideoGrid from './VideoGrid';
import { DragDropProvider } from '../DragDropContext';
import { CameraProvider, useCameras } from '../camera/CameraManager';
import LeafletMap from '../maps/LeafletMap';
import GlobalMap from '../maps/GlobalMap';
import CollectionManager from '../camera/CollectionManager';
import CameraStreamView from '../camera/CameraStreamView';
import DashboardAnalytics from './DashboardAnalytics';
import { useCameraStore } from '../../store/cameraStore';
import { useArchiveStore } from '../../store/archiveStore';
import { API_BASE_URL } from '../../utils/apiConfig';
import { apiRequest } from '../../utils/api';
import './Dashboard.css';
import { getLayoutConfig } from '../layout/LayoutModes';
import { parseStreamUrl, generateCameraId } from '../../utils/cameraUtils';

const Dashboard = ({ currentView, showCollectionManager, setShowCollectionManager, activeTab, onViewChange }) => {
  const [currentLayout, setCurrentLayout] = useState('2x2');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCamera, setSelectedCamera] = useState(null);
  const { getBookmarkedCameras } = useCameras();
  const { collections, activeCollection, setCameras, cameras: storedCameras, setCollectionActive, cameraLocations, loadCameraLocations } = useCameraStore();
  const { startStatusPolling, stopStatusPolling } = useArchiveStore();
  const [streams, setStreams] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [gridKey, setGridKey] = useState(0);

  const handleSearch = (event) => {
    setSearchQuery(event.target.value);
  };

  const handleCameraSelect = (cameraName) => {
    setSelectedCamera(cameraName);
  };

  const handleCameraFocus = (cameraId, collectionName) => {
    const collection = collections.find(c => c.name === collectionName);
    if (collection) {
      setCollectionActive(collection.id);
    }
    onViewChange('camera');
    setSelectedCamera(cameraId);
  };

  useEffect(() => {
    loadCameraLocations();
  }, [loadCameraLocations]);

  // Handle camera swapping in the streams array
  const handleCameraSwap = (sourceIndex, targetIndex) => {
    // Validate indices
    if (sourceIndex < 0 || sourceIndex >= streams.length ||
        targetIndex < 0 || targetIndex >= streams.length ||
        sourceIndex === targetIndex) {
      return;
    }

    // Create a new streams array with swapped elements
    const newStreams = [...streams];
    [newStreams[sourceIndex], newStreams[targetIndex]] = [newStreams[targetIndex], newStreams[sourceIndex]];

    setStreams(newStreams);
    setGridKey(prev => prev + 1); // Force re-render
  };

  // Handle camera assignment from sidebar to grid cell
  const handleCameraAssign = (sidebarCamera, targetIndex) => {
    console.log(`Assigning camera ${sidebarCamera.name} to position ${targetIndex}`);

    // Create a stream object from the sidebar camera
    const streamObject = {
      camera_ip: sidebarCamera.ip,
      rtsp_url: sidebarCamera.streamUrl,
      stream_id: sidebarCamera.id,
      room_id: `room_${sidebarCamera.collectionId}`,
      collection_id: sidebarCamera.collectionId
    };

    // Get the current streams array
    const currentStreams = [...streams];

    // Ensure we have enough slots in the array
    while (currentStreams.length <= targetIndex) {
      currentStreams.push(null);
    }

    // Assign the camera to the target position
    currentStreams[targetIndex] = streamObject;

    // Update the streams
    setStreams(currentStreams);
    setGridKey(prev => prev + 1); // Force re-render
  };

  const handleCloseCollectionManager = () => {
    setShowCollectionManager(false);
  };

  // Initialize recording status polling when Dashboard mounts
  useEffect(() => {
    startStatusPolling();

    // Cleanup on unmount
    return () => {
      stopStatusPolling();
    };
  }, [startStatusPolling, stopStatusPolling]);

  useEffect(() => {
    if (activeCollection && currentView === 'camera') {
      const collection = collections.find(c => c.id === activeCollection);
      if (collection) {
        loadStreams(collection.name);
      }
    } else {
      // Clear streams when switching to other views
      setStreams([]);
    }
  }, [activeCollection, collections, currentView]);

  // This effect updates the camera store with the current stream cameras
  // to ensure they're available for bookmarking
  useEffect(() => {
    if (streams.length > 0 && currentView === 'camera') {
      // Create camera objects with stable IDs
      const streamCameras = streams.map((streamInfo, index) => {
        // Handle both old format (string URLs) and new format (objects with stream_id and room_id)
        if (typeof streamInfo === 'string') {
          // Legacy format - string URL
          const safeStreamUrl = streamInfo || '';
          let name = `Camera ${index + 1}`;
          let ip = '';
          let collectionName = '';

          // Use the utility function to parse the stream URL
          const parsed = parseStreamUrl(safeStreamUrl);
          if (parsed.collectionName && parsed.ip) {
            collectionName = parsed.collectionName;
            ip = parsed.ip;
            name = `${collectionName} (${ip})`;
          }

          // Create a stable ID based on collection and IP using the utility function
          const stableId = ip ? generateCameraId(collectionName, ip) : `stream-${index}`;

          return {
            id: stableId,
            name: name,
            streamUrl: safeStreamUrl,
            ip: ip,
            collection: collectionName,
            collectionId: activeCollection
          };
        } else {
          // New format - object with WebRTC info or RTSP URL
          const ip = streamInfo.camera_ip || '';
          // Get collection name from the active collection
          const collection = collections.find(c => c.id === activeCollection);
          const collectionName = collection ? collection.name : '';
          const name = ip ? `${collectionName} (${ip})` : `Camera ${index + 1}`;

          // Create a stable ID based on collection and IP
          const stableId = ip ? generateCameraId(collectionName, ip) : `stream-${index}`;

          // Check if we have an RTSP URL directly
          if (streamInfo.rtsp_url) {
            return {
              id: stableId,
              name: name,
              ip: ip,
              streamUrl: streamInfo.rtsp_url,
              collection: collectionName,
              collectionId: activeCollection
            };
          } else {
            return {
              id: stableId,
              name: name,
              ip: ip,
              streamId: streamInfo.stream_id,
              roomId: streamInfo.room_id,
              collection: collectionName,
              collectionId: activeCollection
            };
          }
        }
      });

      // Merge with existing cameras, preserving bookmarks
      const existingCameraIds = storedCameras.map(cam => cam.id);
      const newCameras = streamCameras.filter(cam => !existingCameraIds.includes(cam.id));

      if (newCameras.length > 0) {
        console.log('Adding new cameras to store:', newCameras.length);
        setCameras([...storedCameras, ...newCameras]);
      }
    }
  }, [streams, currentView, activeCollection, setCameras, storedCameras]);

  const loadStreams = async (collectionName) => {
    try {
      setLoading(true);
      setError(null);

      // Load camera configuration directly for MJPEG streaming
      console.log(`Loading camera configuration for collection: ${collectionName}`);
      const cameraData = await apiRequest(`/cameras`);

      if (cameraData.cameras && cameraData.cameras[collectionName]) {
        // Convert the camera configuration to an array of objects with RTSP URLs
        const rtspStreams = Object.entries(cameraData.cameras[collectionName]).map(([ip, rtspUrl]) => ({
          camera_ip: ip,
          rtsp_url: rtspUrl
        }));

        console.log(`Loaded ${rtspStreams.length} cameras for MJPEG streaming:`, rtspStreams);
        setStreams(rtspStreams);
        setLoading(false);
        return;
      } else {
        console.warn(`No cameras found for collection: ${collectionName}`);
        setStreams([]);
        setError(`No cameras configured for collection: ${collectionName}`);
      }
    } catch (err) {
      console.error("Error loading camera configuration:", err);
      setError(`Failed to load camera configuration: ${err.message}`);
      setStreams([]);
    } finally {
      setLoading(false);
    }
  };

  const renderContent = () => {
    // First check for dashboard analytics view
    if (currentView === 'dashboard-analytics') {
      return <DashboardAnalytics />;
    }

    // Then check for map views
    if (currentView === 'basic-map') {
      return (
        <div className="map-container" style={{ width: '100%', height: '100%' }}>
          <LeafletMap mode="view" onCameraSelect={handleCameraFocus} />
        </div>
      );
    }

    if (currentView === 'global-map') {
      return (
        <div className="map-container">
          <GlobalMap onCameraSelect={handleCameraSelect} />
        </div>
      );
    }

    // Check for the new rtsp-stream view
    if (currentView === 'rtsp-stream') {
      return <CameraStreamView />;
    }

    // Then check for loading and streams
    if (loading) {
      return <div className="loading">Loading streams...</div>;
    }

    if (error) {
      return <div className="error">{error}</div>;
    }

    if (streams.length > 0) {
      // Remove this block: always use VideoGrid for the collection view
      // (No more <div className="streams-grid">...)
    }

    switch (currentView) {
      case 'camera':
        // Prepare camera objects for VideoGrid
        const streamCameras = streams.map((streamInfo, index) => {
          // Handle both old format (string URLs) and new format (objects with stream_id and room_id)
          if (typeof streamInfo === 'string') {
            // Legacy format - string URL
            const safeStreamUrl = streamInfo || '';
            let name = `Camera ${index + 1}`;
            let ip = '';
            let collectionName = '';

            // Use the utility function to parse the stream URL
            const parsed = parseStreamUrl(safeStreamUrl);
            if (parsed.collectionName && parsed.ip) {
              collectionName = parsed.collectionName;
              ip = parsed.ip;
              name = `${collectionName} (${ip})`;
            }

            // Create a stable ID based on collection and IP using the utility function
            const stableId = ip ? generateCameraId(collectionName, ip) : `stream-${index}`;

            return {
              id: stableId,
              name: name,
              streamUrl: safeStreamUrl,
              ip: ip,
              collection: collectionName,
              collectionId: activeCollection
            };
          } else {
            // New format - object with WebRTC info or RTSP URL
            const ip = streamInfo.camera_ip || '';
            // Get collection name from the active collection
            const collection = collections.find(c => c.id === activeCollection);
            const collectionName = collection ? collection.name : '';
            const name = ip ? `${collectionName} (${ip})` : `Camera ${index + 1}`;

            // Create a stable ID based on collection and IP
            const stableId = ip ? generateCameraId(collectionName, ip) : `stream-${index}`;

            // Always use RTSP URL for MJPEG streaming
            return {
              id: stableId,
              name: name,
              ip: ip,
              streamUrl: streamInfo.rtsp_url,
              collection: collectionName,
              collectionId: activeCollection
            };
          }
        });
        return (
          <div className="dashboard-content">
            <div className="dashboard-main">
              {activeCollection ? (
                <DragDropProvider>
                  <CameraProvider>
                    <VideoGrid
                      key={`video-grid-${gridKey}`}
                      layout={currentLayout}
                      cameras={streamCameras}
                      cellCount={getLayoutConfig(currentLayout)?.cameraCount || 4}
                      onCameraClick={handleCameraSelect}
                      onCameraSwap={handleCameraSwap}
                      onCameraAssign={handleCameraAssign}
                      activeTab={activeTab || currentView}
                    />
                  </CameraProvider>
                </DragDropProvider>
              ) : (
                <div className="no-collection-message">
                  Please select a collection from the sidebar to view cameras
                </div>
              )}
            </div>
          </div>
        );
      case 'bookmark':
        const bookmarkedCameras = getBookmarkedCameras();
        return (
          <div className="dashboard-content">
            <div className="dashboard-main">
              <DragDropProvider>
                <CameraProvider>
                  <VideoGrid
                    layout={currentLayout}
                    cameras={bookmarkedCameras}
                    cellCount={getLayoutConfig(currentLayout)?.cameraCount || 4}
                    onCameraClick={handleCameraSelect}
                    onCameraSwap={null} // Bookmarks don't support swapping for now
                    onCameraAssign={null} // Bookmarks don't support assignment for now
                    activeTab={activeTab || currentView}
                  />
                </CameraProvider>
              </DragDropProvider>
              {bookmarkedCameras.length === 0 && (
                <div className="no-bookmarks-message">
                  <p>You haven't bookmarked any cameras yet.</p>
                  <p>Click the bookmark icon on any camera to add it to your bookmarks.</p>
                </div>
              )}
            </div>
          </div>
        );
      default:
        return <div className="no-streams">No streams available</div>;
    }
  };

  return (
    <div className="dashboard">
      {showCollectionManager ? (
        <CollectionManager onClose={handleCloseCollectionManager} onViewChange={onViewChange} />
      ) : (
        <>
          {currentView !== 'dashboard-analytics' && (
            <div className="dashboard-header">
              {currentView === 'camera' && (
                <div className="camera-search-container" style={{ display: 'flex', alignItems: 'center' }}>
                  <input
                    type="text"
                    placeholder="Search camera"
                    className="camera-search-input"
                    value={searchQuery}
                    onChange={handleSearch}

                  />
                </div>
              )}
              {(currentView === 'camera' || currentView === 'bookmark') && (
                <div className="layout-controls">
                  <LayoutSelector
                    currentLayoutId={currentLayout}
                    onLayoutChange={setCurrentLayout}
                  />
                </div>
              )}
            </div>
          )}
          <div className="dashboard-content">
            {renderContent()}
          </div>
        </>
      )}
    </div>
  );
};

export default Dashboard;