import React, { useState, useEffect } from 'react';
import { useCameraStore } from '../../../store/cameraStore';
import useCameraSettingsStore from '../../../store/cameraSettingsStore';
import cameraSettingsApi from '../../../services/cameraSettingsApi';
import { ImCamera } from "react-icons/im";
import '../CameraSettings.css';

const CameraSettings = () => {
  const [selectedCameraIP, setSelectedCameraIP] = useState('');
  const [availableCameras, setAvailableCameras] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [credentials, setCredentials] = useState({
    username: 'admin',
    password: 'Admin@123',
    port: 80
  });
  const [credentialsSource, setCredentialsSource] = useState('default');
  const [selectedResolution, setSelectedResolution] = useState('');
  const [selectedFrameRate, setSelectedFrameRate] = useState(25);
  const [selectedMaxBitrate, setSelectedMaxBitrate] = useState(2048);
  const [selectedVideoEncoding, setSelectedVideoEncoding] = useState('');

  const { cameras } = useCameraStore();
  const {
    cameraSettings,
    setCameraSettings,
    setSupportedResolutions,
    setCurrentResolution,
    setConnectionStatus,
    setCurrentStreamSettings,
    setSupportedStreamSettings,
    getSupportedResolutions,
    getCurrentResolution,
    getConnectionStatus,
    getCurrentStreamSettings,
    getSupportedStreamSettings
  } = useCameraSettingsStore();

  // Load available cameras from the store
  useEffect(() => {
    const cameraIPs = cameras.map(camera => camera.ip).filter(ip => ip);
    setAvailableCameras(cameraIPs);
  }, [cameras]);

  // Auto-load credentials when camera is selected
  useEffect(() => {
    if (selectedCameraIP) {
      const extractedCredentials = extractCredentialsFromCollections(selectedCameraIP);
      setCredentials(extractedCredentials);

      if (extractedCredentials.username !== 'admin' || extractedCredentials.password !== 'admin') {
        setCredentialsSource('collection');
      } else {
        const storedSettings = getCameraSettings(selectedCameraIP);
        if (storedSettings.onvifCredentials) {
          setCredentials(storedSettings.onvifCredentials);
          setCredentialsSource('stored');
        } else {
          setCredentialsSource('default');
        }
      }
    }
  }, [selectedCameraIP]);

  // Auto-load current settings when camera is selected
  useEffect(() => {
    if (selectedCameraIP) {
      const settings = getCurrentStreamSettings(selectedCameraIP);
      if (settings) {
        if (settings.frameRate !== undefined) setSelectedFrameRate(settings.frameRate);
        if (settings.maxBitrate !== undefined) setSelectedMaxBitrate(settings.maxBitrate);
        if (settings.videoEncoding !== undefined) setSelectedVideoEncoding(settings.videoEncoding);
      }

      const currentRes = getCurrentResolution(selectedCameraIP);
      if (currentRes && currentRes.width && currentRes.height) {
        setSelectedResolution(`${currentRes.width}x${currentRes.height}`);
      }
    }
  }, [selectedCameraIP, getCurrentStreamSettings, getCurrentResolution]);

  const getCameraSettings = (cameraIp) => {
    return cameraSettings[cameraIp] || {};
  };

  const extractCredentialsFromCollections = (cameraIP) => {
    try {
      const camera = cameras.find(cam => cam.ip === cameraIP);
      if (camera) {
        if (camera.username && camera.password) {
          return {
            username: camera.username,
            password: camera.password,
            port: camera.port || 80
          };
        }
        if (camera.streamUrl) {
          const parsed = cameraSettingsApi.parseCredentialsFromRtspUrl(camera.streamUrl);
          if (parsed && parsed.username && parsed.password) {
            return {
              username: parsed.username,
              password: parsed.password,
              port: camera.port || 80
            };
          }
        }
      }
    } catch (error) {
      console.error('Error extracting credentials from collections:', error);
    }

    return {
      username: 'admin',
      password: 'Admin@123',
      port: 80
    };
  };

  const handleCameraSelect = (event) => {
    const ip = event.target.value;
    setSelectedCameraIP(ip);
    setError('');
    setSuccess('');

    // Reset video settings to default values when camera changes
    setSelectedResolution('');
    setSelectedFrameRate(25);
    setSelectedMaxBitrate(2048);
    setSelectedVideoEncoding('');
  };

  const handleCredentialChange = (field, value) => {
    setCredentials(prev => ({
      ...prev,
      [field]: value
    }));
    setCredentialsSource('manual');
  };

  const testConnection = async () => {
    if (!selectedCameraIP) {
      setError('Please select a camera IP address first.');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      const result = await cameraSettingsApi.testOnvifConnection({
        ip: selectedCameraIP,
        username: credentials.username,
        password: credentials.password,
        port: credentials.port
      });

      if (result.success) {
        setSuccess(result.message);
        setConnectionStatus(selectedCameraIP, 'connected');

        // Update credentials with working port
        const updatedCredentials = {
          ...credentials,
          port: result.port_used
        };
        setCredentials(updatedCredentials);

        // Save credentials to store
        setCameraSettings(selectedCameraIP, {
          onvifCredentials: updatedCredentials
        });

        // Load current resolution and supported resolutions
        await loadCameraInfo();
      } else {
        setError(result.message);
        setConnectionStatus(selectedCameraIP, 'error');
      }
    } catch (error) {
      console.error('Connection test failed:', error);
      setError(`Connection failed: ${error.message}`);
      setConnectionStatus(selectedCameraIP, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const loadCameraInfo = async () => {
    try {
      // Load supported resolutions
      const resolutionsResult = await cameraSettingsApi.getSupportedResolutions(
        selectedCameraIP,
        credentials.username,
        credentials.password,
        credentials.port
      );

      if (resolutionsResult.success) {
        setSupportedResolutions(selectedCameraIP, resolutionsResult.resolutions);
      }

      // Load current resolution
      const currentResResult = await cameraSettingsApi.getCurrentResolution(
        selectedCameraIP,
        credentials.username,
        credentials.password,
        credentials.port
      );

      if (currentResResult.success && currentResResult.resolution && currentResResult.resolution.width && currentResResult.resolution.height) {
        setCurrentResolution(selectedCameraIP, currentResResult.resolution);
        setSelectedResolution(`${currentResResult.resolution.width}x${currentResResult.resolution.height}`);
      }

      // Load supported stream settings
      const supportedStreamResult = await cameraSettingsApi.getSupportedStreamSettings(
        selectedCameraIP,
        credentials.username,
        credentials.password,
        credentials.port
      );

      if (supportedStreamResult.success) {
        setSupportedStreamSettings(selectedCameraIP, supportedStreamResult.settings);
      }

      // Load current stream settings
      const currentStreamResult = await cameraSettingsApi.getCurrentStreamSettings(
        selectedCameraIP,
        credentials.username,
        credentials.password,
        credentials.port
      );

      if (currentStreamResult.success && currentStreamResult.settings) {
        setCurrentStreamSettings(selectedCameraIP, currentStreamResult.settings);

        // Update form fields with current settings
        const settings = currentStreamResult.settings;
        if (settings && settings.frameRate !== undefined) setSelectedFrameRate(settings.frameRate);
        if (settings && settings.maxBitrate !== undefined) setSelectedMaxBitrate(settings.maxBitrate);
        if (settings && settings.videoEncoding !== undefined) {
          // Normalize video encoding value to ensure consistency
          let normalizedEncoding = settings.videoEncoding;
          if (normalizedEncoding === 'H264' || normalizedEncoding === 'h264' || normalizedEncoding === '0') {
            normalizedEncoding = 'H.264';
          } else if (normalizedEncoding === 'H265' || normalizedEncoding === 'h265' || normalizedEncoding === '1') {
            normalizedEncoding = 'H.265';
          }
          setSelectedVideoEncoding(normalizedEncoding);
        }
      }

    } catch (error) {
      console.error('Error loading camera info:', error);
      setError(`Failed to load camera information: ${error.message}`);
    }
  };

  const applyVideoSettings = async () => {
    if (!selectedCameraIP) {
      setError('Please select a camera IP address first.');
      return;
    }

    setIsLoading(true);
    setError('');
    setSuccess('');

    try {
      let hasErrors = false;
      let successMessages = [];

      // Apply resolution if selected
      if (selectedResolution) {
        try {
          const [width, height] = selectedResolution.split('x').map(Number);
          const resolutionRequest = {
            ip: selectedCameraIP,
            username: credentials.username,
            password: credentials.password,
            port: credentials.port,
            width: width,
            height: height,
            frame_rate: selectedFrameRate || 15,
            bitrate: selectedMaxBitrate || 1024
          };

          const resolutionResult = await cameraSettingsApi.setCameraResolution(resolutionRequest);
          if (resolutionResult.success) {
            successMessages.push('Resolution updated successfully');
          } else {
            setError(resolutionResult.message || 'Failed to apply resolution');
            hasErrors = true;
          }
        } catch (error) {
          console.error('Error applying resolution:', error);
          setError(`Failed to apply resolution: ${error.message}`);
          hasErrors = true;
        }
      }

      // Apply stream settings if any are selected
      const streamSettings = {};
      if (selectedFrameRate) streamSettings.frameRate = selectedFrameRate;
      if (selectedMaxBitrate) streamSettings.maxBitrate = selectedMaxBitrate;
      if (selectedVideoEncoding) {
        streamSettings.videoEncoding = selectedVideoEncoding;
        console.log('Applying video encoding setting:', selectedVideoEncoding);
      }

      if (Object.keys(streamSettings).length > 0) {
        try {
          const streamSettingsRequest = {
            ip: selectedCameraIP,
            username: credentials.username,
            password: credentials.password,
            port: credentials.port,
            ...streamSettings
          };

          const streamResult = await cameraSettingsApi.setCameraStreamSettings(streamSettingsRequest);
          if (streamResult.success) {
            successMessages.push('Stream settings updated successfully');
          } else {
            setError(streamResult.message || 'Failed to apply stream settings');
            hasErrors = true;
          }
        } catch (error) {
          console.error('Error applying stream settings:', error);
          setError(`Failed to apply stream settings: ${error.message}`);
          hasErrors = true;
        }
      }

      if (!hasErrors && successMessages.length > 0) {
        setSuccess(successMessages.join(', '));

        // Reload current settings to reflect changes
        await loadCameraInfo();
      } else if (successMessages.length === 0) {
        setError('No settings selected to apply');
      }
    } catch (error) {
      console.error('Error applying video settings:', error);
      setError(`Failed to apply settings: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Get current data from store
  const currentRes = getCurrentResolution(selectedCameraIP);
  const supportedRes = getSupportedResolutions(selectedCameraIP);
  const connectionStat = getConnectionStatus(selectedCameraIP);
  const currentStreamSettings = getCurrentStreamSettings(selectedCameraIP);
  const supportedStreamSettings = getSupportedStreamSettings(selectedCameraIP);

  return (
    <div className="settings-container">
      <div className="header">
        <h1><ImCamera style={{ marginRight: '10px' }} />Camera Configuration</h1>
        <p>Configure camera resolution and ONVIF settings for your IP cameras</p>
      </div>

      <div className="tabs">
        <button className="tab active">Camera Settings</button>
      </div>

      <div className="settings-content">
        {/* Compact layout with all sections in a grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px', height: '20%' }}>
          {/* Camera Selection & Credentials */}
          <div className="settings-section">
            <h3 className="section-title">Camera & Credentials</h3>
            <div className="setting-row">
              <label className="setting-label">Camera IP</label>
              <div className="setting-control">
                <select
                  value={selectedCameraIP}
                  onChange={handleCameraSelect}
                  disabled={isLoading}
                >
                  <option value="">Select Camera IP</option>
                  {availableCameras.map(ip => (
                    <option key={ip} value={ip}>{ip}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="setting-row">
              <label className="setting-label">Username</label>
              <div className="setting-control">
                <input
                  type="text"
                  value={credentials.username}
                  onChange={(e) => handleCredentialChange('username', e.target.value)}
                  disabled={isLoading || !selectedCameraIP}
                />
              </div>
            </div>

            <div className="setting-row">
              <label className="setting-label">Password</label>
              <div className="setting-control">
                <input
                  type="password"
                  value={credentials.password}
                  onChange={(e) => handleCredentialChange('password', e.target.value)}
                  disabled={isLoading || !selectedCameraIP}
                />
              </div>
            </div>

            <div className="setting-row">
              <label className="setting-label">Port</label>
              <div className="setting-control">
                <input
                  type="number"
                  value={credentials.port}
                  onChange={(e) => handleCredentialChange('port', parseInt(e.target.value))}
                  disabled={isLoading || !selectedCameraIP}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '8px', borderTop: '1px solid #e0e0e0', marginTop: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: connectionStat === 'connected' ? '#4CAF50' : connectionStat === 'error' ? '#f44336' : '#666' }}></span>
                <span>{connectionStat || 'Not tested'}</span>
              </div>
              <button
                style={{
                  padding: '4px 12px',
                  backgroundColor: '#000',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '11px',
                  cursor: 'pointer'
                }}
                onClick={testConnection}
                disabled={isLoading || !selectedCameraIP}
              >
                {isLoading ? 'Testing...' : 'Test'}
              </button>
            </div>
          </div>

          {/* Video Properties */}
          <div className="settings-section">
            <h3 className="section-title">Video Properties</h3>

            <div className="setting-row">
              <label className="setting-label">Resolution</label>
              <div className="setting-control">
                <select
                  value={selectedResolution}
                  onChange={(e) => setSelectedResolution(e.target.value)}
                  disabled={isLoading || !selectedCameraIP || connectionStat !== 'connected'}
                >
                  <option value="">Select Resolution</option>
                  {supportedRes?.map((res, index) => (
                    <option key={index} value={`${res.width}x${res.height}`}>
                      {res.label || `${res.width}x${res.height}`}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Encoding Settings */}
          <div className="settings-section">
            <h3 className="section-title">Encoding Settings</h3>

            <div className="setting-row">
              <label className="setting-label">Frame Rate</label>
              <div className="setting-control">
                <div className="input-with-unit">
                  <select
                    value={selectedFrameRate}
                    onChange={(e) => {
                      const value = e.target.value;
                      if (value.includes('/') || isNaN(value)) {
                        setSelectedFrameRate(value);
                      } else {
                        setSelectedFrameRate(parseInt(value));
                      }
                    }}
                    disabled={isLoading || !selectedCameraIP || connectionStat !== 'connected'}
                  >
                    <option value="">Frame Rate</option>
                    {supportedStreamSettings?.frameRates?.map((rate, index) => (
                      <option key={index} value={rate.value}>
                        {rate.label}
                      </option>
                    ))}
                  </select>
                  <span className="unit-label">fps</span>
                </div>
              </div>
            </div>

            <div className="setting-row">
              <label className="setting-label">Max. Bitrate</label>
              <div className="setting-control">
                <div className="input-with-unit">
                  <select
                    value={selectedMaxBitrate}
                    onChange={(e) => setSelectedMaxBitrate(parseInt(e.target.value))}
                    disabled={isLoading || !selectedCameraIP || connectionStat !== 'connected'}
                  >
                    <option value="">Max Bitrate</option>
                    {supportedStreamSettings?.maxBitrates?.map((bitrate, index) => (
                      <option key={index} value={bitrate.value}>
                        {bitrate.label}
                      </option>
                    ))}
                  </select>
                  <span className="unit-label">Kbps</span>
                </div>
              </div>
            </div>

            <div className="setting-row">
              <label className="setting-label">Video Encoding</label>
              <div className="setting-control">
                <select
                  value={selectedVideoEncoding}
                  onChange={(e) => setSelectedVideoEncoding(e.target.value)}
                  disabled={isLoading || !selectedCameraIP || connectionStat !== 'connected'}
                >
                  <option value="">Video Encoding </option>
                  {supportedStreamSettings?.videoEncodings?.map((encoding, index) => (
                    <option key={index} value={encoding.value}>
                      {encoding.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Save Configuration Section */}
        <div className="actions-section" style={{ marginTop: '16px' }}>
          <div className="status-indicator">
            <span className="status-dot"></span>
            <span>Configuration Valid</span>
          </div>
          <div className="button-group">
            <button
              className="save-button"
              onClick={applyVideoSettings}
              disabled={isLoading || !selectedCameraIP || connectionStat !== 'connected'}
            >
              <svg className="save-icon" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V7l-4-4zm-5 16c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3zm3-10H5V5h10v4z"/>
              </svg>
              {isLoading ? 'Applying...' : 'Save Configuration'}
            </button>
          </div>
        </div>

        {/* Error and Success Messages */}
        {error && (
          <div style={{
            padding: '8px 12px',
            backgroundColor: '#ffebee',
            border: '1px solid #f44336',
            borderRadius: '6px',
            color: '#d32f2f',
            marginTop: '12px',
            fontSize: '12px'
          }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {success && (
          <div style={{
            padding: '8px 12px',
            backgroundColor: '#e8f5e8',
            border: '1px solid #4CAF50',
            borderRadius: '6px',
            color: '#2e7d32',
            marginTop: '12px',
            fontSize: '12px'
          }}>
            <strong>Success:</strong> {success}
          </div>
        )}
      </div>
    </div>
  );
};

export default CameraSettings;
