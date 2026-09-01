import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { getBestCredentials, generateRTSPUrl, storeSuccessfulCredentials, maskCredentials } from '../../utils/cameraCredentials';
import './MJPEGStreamPlayer.css';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const MJPEGStreamPlayer = ({ camera }) => {
  const [streamUrl, setStreamUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [streamId, setStreamId] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const imgRef = useRef(null);
  const retryTimeoutRef = useRef(null);
  const [retryCount, setRetryCount] = useState(0);
  const maxRetries = 3;
  const isStartingRef = useRef(false);

  // Generate consistent stream ID based on camera
  const generateStreamId = () => {
    if (camera.ip) {
      // Try to extract collection name from camera name or use a default
      let collectionName = 'default';

      // First try to use collectionId if available
      if (camera.collectionId) {
        collectionName = camera.collectionId;
      } else if (camera.name && camera.name.includes('(')) {
        // Extract collection name from camera name format "CollectionName (IP)"
        collectionName = camera.name.split('(')[0].trim();
      } else if (camera.collection) {
        // Try collection property
        collectionName = camera.collection;
      }

      // Normalize collection name to match backend format
      collectionName = collectionName.toLowerCase().replace(/\s+/g, '_');

      return `${collectionName}_${camera.ip}`;
    }
    return `camera_${camera.id}_${Date.now()}`;
  };

  const startStream = async () => {
    if (isStartingRef.current) {
      console.log('Stream start already in progress, skipping...');
      return;
    }

    const newStreamId = generateStreamId();

    try {
      isStartingRef.current = true;
      setIsLoading(true);
      setHasError(false);
      setErrorMessage('');
      setStreamId(newStreamId);

      // First, check if a stream already exists for this camera
      let collectionName = 'default';

      // Use the same logic as generateStreamId for consistency
      if (camera.collectionId) {
        collectionName = camera.collectionId;
      } else if (camera.name && camera.name.includes('(')) {
        collectionName = camera.name.split('(')[0].trim();
      } else if (camera.collection) {
        collectionName = camera.collection;
      }

      // Normalize collection name to match backend format
      collectionName = collectionName.toLowerCase().replace(/\s+/g, '_');

      try {
        const existingStreamResponse = await axios.get(`${API_BASE_URL}/api/get_stream_for_camera`, {
          params: {
            camera_ip: camera.ip,
            collection_name: collectionName
          },
          timeout: 5000
        });

        if (existingStreamResponse.data.success && existingStreamResponse.data.exists && existingStreamResponse.data.is_running) {
          // Use existing stream
          const feedUrl = existingStreamResponse.data.feed_url;
          const fullStreamUrl = feedUrl.startsWith('http') ? feedUrl : `${API_BASE_URL}${feedUrl}`;
          setStreamUrl(fullStreamUrl);
          setStreamId(existingStreamResponse.data.stream_id);
          console.log(`Using existing MJPEG stream: ${fullStreamUrl}`);
          setRetryCount(0);
          return;
        }
      } catch (error) {
        console.log('Could not check for existing stream, proceeding with new stream creation');
      }

      // Check if we have an RTSP URL
      let rtspUrl = camera.streamUrl;

      // If no RTSP URL, try to construct one from IP
      if (!rtspUrl && camera.ip) {
        // Get the best credentials for this camera IP
        const credentials = getBestCredentials(camera.ip);
        rtspUrl = generateRTSPUrl(camera.ip, credentials);
        console.log(`Using RTSP URL with credentials: ${maskCredentials(rtspUrl)}`);
      }

      if (!rtspUrl) {
        throw new Error('No RTSP URL available for camera');
      }

      console.log(`Starting MJPEG stream for camera ${camera.name} (${newStreamId}) with RTSP URL: ${rtspUrl}`);

      // Start the stream on the backend
      const response = await axios.post(`${API_BASE_URL}/api/start_stream`, {
        rtsp_url: rtspUrl,
        stream_id: newStreamId
      }, {
        timeout: 10000 // 10 second timeout
      });

      if (response.data.success) {
        const feedUrl = response.data.feed_url;
        const fullStreamUrl = feedUrl.startsWith('http') ? feedUrl : `${API_BASE_URL}${feedUrl}`;

        if (response.data.reused) {
          console.log(`MJPEG stream reused: ${fullStreamUrl}`);
        } else {
          console.log(`MJPEG stream started: ${fullStreamUrl}`);

          // Store successful credentials for future use
          if (camera.ip && rtspUrl) {
            const credentials = getBestCredentials(camera.ip);
            storeSuccessfulCredentials(camera.ip, credentials);
          }
        }
        setStreamUrl(fullStreamUrl);
        setRetryCount(0);
      } else {
        throw new Error(response.data.error || 'Failed to start stream');
      }

    } catch (error) {
      console.error('Error starting MJPEG stream:', error);
      setHasError(true);
      setErrorMessage(error.response?.data?.error || error.message || 'Failed to start stream');

      // Retry logic
      if (retryCount < maxRetries) {
        const retryDelay = Math.min(1000 * Math.pow(2, retryCount), 10000); // Exponential backoff, max 10s
        console.log(`Retrying stream start in ${retryDelay}ms (attempt ${retryCount + 1}/${maxRetries})`);

        retryTimeoutRef.current = setTimeout(() => {
          setRetryCount(prev => prev + 1);
          startStream();
        }, retryDelay);
      }
    } finally {
      isStartingRef.current = false;
    }
  };

  const stopStream = async () => {
    if (streamId) {
      try {
        console.log(`Stopping stream: ${streamId}`);
        await axios.delete(`${API_BASE_URL}/api/stop_stream/${streamId}`, {
          timeout: 5000
        });
      } catch (error) {
        console.error('Error stopping stream:', error);
      }
    }

    setStreamUrl(null);
    setStreamId(null);
    setIsLoading(false);
    setHasError(false);
    setErrorMessage('');

    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  };

  const handleImageLoad = () => {
    console.log(`MJPEG stream loaded successfully for camera ${camera.name}`);
    setIsLoading(false);
    setHasError(false);
    setErrorMessage('');
  };

  const handleImageError = (error) => {
    console.error(`MJPEG stream error for camera ${camera.name}:`, error);
    setHasError(true);
    setErrorMessage('Stream connection failed');
    setIsLoading(false);
  };

  const handleRetry = () => {
    setRetryCount(0);
    startStream();
  };

  // Start stream when component mounts or camera changes
  useEffect(() => {
    if (camera && (camera.ip || camera.streamUrl)) {
      startStream();
    }

    // Cleanup function
    return () => {
      stopStream();
    };
  }, [camera.id, camera.ip, camera.streamUrl]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, []);

  if (hasError) {
    return (
      <div className="mjpeg-stream-error">
        <div className="error-content">
          <div className="error-icon">⚠️</div>
          <div className="error-text">
            <div>Stream Error</div>
            <small>{errorMessage}</small>
          </div>
          {retryCount < maxRetries && (
            <button className="retry-button" onClick={handleRetry}>
              Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mjpeg-stream-player">
      {isLoading && (
        <div className="mjpeg-stream-loading">
          <div className="loading-spinner"></div>
          <span>Connecting to stream...</span>
          <small>{camera.ip || 'Camera'}</small>
        </div>
      )}
      {streamUrl && (
        <img
          ref={imgRef}
          src={streamUrl}
          alt={`Camera ${camera.name}`}
          className="mjpeg-stream-img"
          style={{ display: isLoading ? 'none' : 'block' }}
          onLoad={handleImageLoad}
          onError={handleImageError}
        />
      )}
    </div>
  );
};

export default MJPEGStreamPlayer;
