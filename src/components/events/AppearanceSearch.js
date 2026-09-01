import React, { useState, useEffect, useRef } from 'react';
import './AppearanceSearch.css';
import {
  CloudUpload as UploadIcon,
  Search as SearchIcon,
  Person as PersonIcon,
  Category as ObjectIcon,
  Clear as ClearIcon,
  PlayArrow as PlayIcon,
  GetApp as DownloadIcon,
  Visibility as Eye
} from '@mui/icons-material';

function AppearanceSearch() {
  const [searchType, setSearchType] = useState('webcam'); // 'webcam', 'person' or 'object'
  const [isWebcamActive, setIsWebcamActive] = useState(false);
  const [selectedObject, setSelectedObject] = useState('');
  const [selectedStream, setSelectedStream] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [availableObjects, setAvailableObjects] = useState(['person', 'car', 'bicycle', 'bus', 'truck']);
  const [availableStreams, setAvailableStreams] = useState([]);
  const [webcamDetections, setWebcamDetections] = useState([]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadedImagePath, setUploadedImagePath] = useState('');
  const fileInputRef = useRef(null);

  // Load available streams on component mount
  useEffect(() => {
    loadAvailableStreams();
    // Cleanup webcam on unmount
    return () => {
      stopWebcam();
    };
  }, []);

  // Poll for webcam detections if active
  useEffect(() => {
    let interval;
    if (isWebcamActive && searchType === 'webcam') {
      interval = setInterval(fetchWebcamDetections, 1000);
    }
    return () => clearInterval(interval);
  }, [isWebcamActive, searchType]);

  const fetchWebcamDetections = async () => {
    try {
      const response = await fetch('/api/webcam/detections');
      if (response.ok) {
        const data = await response.json();
        setWebcamDetections(data.detections || []);
      }
    } catch (err) {
      console.error('Error fetching detections:', err);
    }
  };

  const startWebcam = async () => {
    try {
      const response = await fetch('/api/webcam/start', { method: 'POST' });
      if (response.ok) {
        setIsWebcamActive(true);
        setSuccess('Webcam started with YOLO26 tracking');
      } else {
        setError('Failed to start webcam');
      }
    } catch (err) {
      setError('Error connecting to webcam server');
    }
  };

  const stopWebcam = async () => {
    try {
      await fetch('/api/webcam/stop', { method: 'POST' });
      setIsWebcamActive(false);
    } catch (err) {
      console.error('Error stopping webcam:', err);
    }
  };

  const loadAvailableObjects = async () => {
    try {
      const response = await fetch('/api/appearance-search/searchable-objects');
      if (response.ok) {
        const data = await response.json();
        setAvailableObjects(data.objects || []);
      }
    } catch (error) {
      console.error('Error loading searchable objects:', error);
    }
  };

  const loadAvailableStreams = async () => {
    try {
      const response = await fetch('/api/appearance-search/available-streams');
      if (response.ok) {
        const data = await response.json();
        setAvailableStreams(data.streams || []);
      }
    } catch (error) {
      console.error('Error loading available streams:', error);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Validate file type
      if (!file.type.startsWith('image/')) {
        setError('Please select a valid image file');
        return;
      }
      
      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        setError('File size must be less than 10MB');
        return;
      }
      
      setSelectedFile(file);
      setError('');
    }
  };

  const handleUploadImage = async () => {
    if (!selectedFile) {
      setError('Please select an image file');
      return;
    }

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      setIsSearching(true);
      const response = await fetch('/api/appearance-search/upload-image', {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setUploadedImagePath(data.image_path);
        setSuccess('Image uploaded successfully');
        setError('');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to upload image');
      }
    } catch (error) {
      setError('Error uploading image: ' + error.message);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearch = async () => {
    if (searchType === 'person' && !uploadedImagePath) {
      setError('Please upload an image first');
      return;
    }
    
    if (searchType === 'object' && !selectedObject) {
      setError('Please select an object to search for');
      return;
    }

    const formData = new FormData();
    
    if (searchType === 'person') {
      formData.append('image_path', uploadedImagePath);
      if (selectedStream) {
        formData.append('stream_id', selectedStream);
      }
    } else {
      formData.append('object_name', selectedObject);
      if (selectedStream) {
        formData.append('stream_id', selectedStream);
      }
    }

    try {
      setIsSearching(true);
      setError('');
      setSearchResults([]);
      
      const endpoint = searchType === 'person' 
        ? '/api/appearance-search/search-person'
        : '/api/appearance-search/search-object';
      
      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const data = await response.json();
        setSearchResults(data.results || []);
        setSuccess(`Search completed. Found ${data.total_detections} detections.`);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Search failed');
      }
    } catch (error) {
      setError('Error during search: ' + error.message);
    } finally {
      setIsSearching(false);
    }
  };

  const handleClearResults = () => {
    setSearchResults([]);
    setSelectedFile(null);
    setUploadedImagePath('');
    setSelectedObject('');
    setSelectedStream('');
    setError('');
    setSuccess('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatTimestamp = (timestamp) => {
    return timestamp || 'Unknown';
  };

  const getVideoPlaybackUrl = (result) => {
    // Construct URL for video playback at specific timestamp
    const streamId = result.stream_id;
    const videoName = result.video_name;
    return `/api/archive/stream/${streamId}/${videoName}#t=${result.timestamp_ms / 1000}`;
  };

  const getThumbnailUrl = (result) => {
    // Get thumbnail URL if available
    if (result.thumbnail_path) {
      const filename = result.thumbnail_path.split(/[/\\]/).pop(); // Get filename from path
      return `/api/appearance-search/thumbnail/${filename}`;
    }
    return null;
  };

  return (
    <div className="appearance-search">
      <div className="appearance-search-header">
        <h2>Appearance Search</h2>
        <p>Search for persons or objects in recorded videos</p>
      </div>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {success && (
        <div className="success-message">
          {success}
        </div>
      )}

      <div className="search-controls">
        {/* Search Type Selection */}
        <div className="search-type-selector">
          <h3>Search Type</h3>
          <div className="search-type-buttons">
            <button
              className={`search-type-btn ${searchType === 'webcam' ? 'active' : ''}`}
              onClick={() => setSearchType('webcam')}
            >
              <Eye />
              <span>Live Webcam</span>
            </button>
            <button
              className={`search-type-btn ${searchType === 'person' ? 'active' : ''}`}
              onClick={() => setSearchType('person')}
            >
              <PersonIcon />
              <span>Person Search</span>
            </button>
            <button
              className={`search-type-btn ${searchType === 'object' ? 'active' : ''}`}
              onClick={() => setSearchType('object')}
            >
              <ObjectIcon />
              <span>Object Search</span>
            </button>
          </div>
        </div>

        {/* Webcam Controls */}
        {searchType === 'webcam' && (
          <div className="webcam-controls">
            {!isWebcamActive ? (
              <button className="start-webcam-btn" onClick={startWebcam}>
                <PlayIcon /> Start Live Tracking
              </button>
            ) : (
              <button className="stop-webcam-btn" onClick={stopWebcam}>
                <ClearIcon /> Stop Webcam
              </button>
            )}
          </div>
        )}

        {/* Person Search Controls */}
        {searchType === 'person' && (
          <div className="person-search-controls">
            <h3>Upload Image for Search</h3>
            <p className="helper-text">Upload an image of a person to find their appearances.</p>
            <div className="upload-section" style={{ display: 'flex', gap: '10px', marginTop: '10px', alignItems: 'center' }}>
              <input 
                type="file" 
                accept="image/*"
                ref={fileInputRef}
                onChange={handleFileSelect}
                className="file-input"
                disabled={isSearching}
                style={{ flex: 1 }}
              />
              <button 
                className="upload-btn primary-btn"
                onClick={handleUploadImage}
                disabled={!selectedFile || isSearching}
                style={{ padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '5px' }}
              >
                <UploadIcon /> Upload
              </button>
            </div>
            {uploadedImagePath && (
              <div className="uploaded-image-preview" style={{ marginTop: '15px' }}>
                <p>Image ready for search</p>
              </div>
            )}
          </div>
        )}

        {/* Object Search Controls */}
        {searchType === 'object' && (
          <div className="object-search-controls">
            <h3>Select Object</h3>
            <select
              value={selectedObject}
              onChange={(e) => setSelectedObject(e.target.value)}
              className="object-select"
              disabled={isSearching}
            >
              <option value="">Choose an object...</option>
              {availableObjects.map(obj => (
                <option key={obj} value={obj}>{obj}</option>
              ))}
            </select>
          </div>
        )}

        {/* Stream Selection */}
        <div className="stream-selection">
          <h3>Search Scope</h3>
          <select
            value={selectedStream}
            onChange={(e) => setSelectedStream(e.target.value)}
            className="stream-select"
            disabled={isSearching}
          >
            <option value="">All Streams</option>
            {availableStreams.map(stream => (
              <option key={stream.stream_id} value={stream.stream_id}>
                {stream.stream_id} ({stream.video_count} videos)
              </option>
            ))}
          </select>
        </div>

        {/* Search Actions */}
        {searchType !== 'webcam' && (
          <div className="search-actions">
            <button
              className="search-btn"
              onClick={handleSearch}
              disabled={isSearching || (searchType === 'object' && !selectedObject)}
            >
              <SearchIcon />
              <span>{isSearching ? 'Searching...' : 'Start Search'}</span>
            </button>
            <button
              className="clear-btn"
              onClick={handleClearResults}
              disabled={isSearching}
            >
              <ClearIcon />
              <span>Clear</span>
            </button>
          </div>
        )}
      </div>

      {/* Live Webcam Display */}
      {searchType === 'webcam' && isWebcamActive && (
        <div className="webcam-display-container">
          <div className="webcam-feed">
            <h3>YOLO26 Live Tracking</h3>
            <img 
              src="/api/video_feed/webcam" 
              alt="Live Webcam Tracking" 
              className="live-webcam-feed"
            />
          </div>
          <div className="webcam-detections-panel">
            <h3>Active Detections</h3>
            <div className="detections-list">
              {webcamDetections.length > 0 ? (
                <table>
                  <thead>
                    <tr>
                      <th>Track ID</th>
                      <th>Class</th>
                      <th>Confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {webcamDetections.map((det, idx) => (
                      <tr key={idx}>
                        <td>#{det.id}</td>
                        <td className="capitalize">{det.class}</td>
                        <td>{(det.confidence * 100).toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p>No objects detected currently...</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Search Results */}
      {searchResults.length > 0 && (
        <div className="search-results">
          <h3>Search Results ({searchResults.length} videos with detections)</h3>
          <div className="results-grid">
            {searchResults.map((result, index) => {
              const thumbnailUrl = getThumbnailUrl(result);
              return (
                <div key={index} className="result-item">
                  <div className="result-header">
                    <h4>{result.stream_id}</h4>
                    <span className="confidence">
                      Confidence: {(result.confidence * 100).toFixed(1)}%
                    </span>
                  </div>

                  {/* Thumbnail Image */}
                  {thumbnailUrl && (
                    <div className="result-thumbnail">
                      <img
                        src={thumbnailUrl}
                        alt="Detection thumbnail"
                        className="thumbnail-image"
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                    </div>
                  )}

                  <div className="result-details">
                    <p><strong>Video:</strong> {result.video_name}</p>
                    <p><strong>First Detection:</strong> {formatTimestamp(result.timestamp)}</p>
                    <p><strong>Frame:</strong> {result.frame_number}</p>
                  </div>
                  <div className="result-actions">
                    <button
                      className="play-btn"
                      onClick={() => window.open(getVideoPlaybackUrl(result), '_blank')}
                    >
                      <PlayIcon />
                      <span>Play Video</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {isSearching && (
        <div className="search-loading">
          <div className="loading-spinner"></div>
          <p>Searching through recorded videos...</p>
        </div>
      )}
    </div>
  );
}

export default AppearanceSearch;
