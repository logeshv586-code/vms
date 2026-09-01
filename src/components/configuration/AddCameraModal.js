import React, { useState, useEffect } from 'react';
import { useCameraStore } from '../../store/cameraStore';
import AddCollectionModal from './AddCollectionModal';
import './AddCameraModal.css';
import './WizardModalStyles.css';
import addIcon from '../../icon/add-icon.png';
import axios from 'axios';
import { API_BASE_URL } from '../../utils/apiConfig';
import { validatePrivateIP, extractIPFromStreamURL } from '../../utils/ipValidation';
import { parseRTSPUrl, generateRTSPUrl } from '../../utils/cameraCredentials';
import { ipcRenderer } from '../../services/electronService';

const AddCameraModal = ({ onClose }) => {
  const { collections, createCollection, addCamera, updateCameraConfig, saveCameraConfig } = useCameraStore();

  // Form state
  const [cameraModel, setCameraModel] = useState('');
  const [ipStart, setIpStart] = useState('');
  const [ipEnd, setIpEnd] = useState('');
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [port, setPort] = useState('554');
  const [protocol, setProtocol] = useState('rtsp');
  const [path, setPath] = useState('');
  const [analyticStream, setAnalyticStream] = useState('');
  const [selectedCollection, setSelectedCollection] = useState('');
  const [error, setError] = useState('');
  const [showAddCollectionModal, setShowAddCollectionModal] = useState(false);

  // Wizard state
  const [currentStep, setCurrentStep] = useState(1);
  const totalSteps = 3;

  // Validation state
  const [validationErrors, setValidationErrors] = useState({});
  const [isValidating, setIsValidating] = useState(false);
  const [stepValidation, setStepValidation] = useState({
    1: false, // Camera Details
    2: false, // Connection
    3: false  // Collection
  });

  // Range processing state
  const [isProcessingRange, setIsProcessingRange] = useState(false);
  const [rangeProgress, setRangeProgress] = useState({ current: 0, total: 0 });
  const [rangeResults, setRangeResults] = useState(null);

  // Credential preservation state
  const [originalCredentials, setOriginalCredentials] = useState({
    username: '',
    password: '',
    hasOriginal: false
  });
  const [formCredentialsChanged, setFormCredentialsChanged] = useState({
    username: false,
    password: false
  });

  // Validation functions
  const validateCameraData = async (ip, streamUrl, collectionName = null, excludeIp = null) => {
    try {
      const response = await fetch('/api/collections/validate-camera', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ip,
          streamUrl,
          collection_name: collectionName,
          exclude_ip: excludeIp
        }),
      });

      const result = await response.json();
      return result;
    } catch (error) {
      console.error('Validation error:', error);
      return {
        valid: false,
        error: 'Failed to validate camera data. Please try again.',
        type: 'network_error'
      };
    }
  };

  // Enhanced RTSP URL synchronization with intelligent credential preservation
  const buildRTSPUrlWithCredentialPreservation = (targetIP, existingRTSPUrl = null) => {
    try {
      // Determine which credentials to use based on preservation rules
      let finalUsername = username;
      let finalPassword = password;

      // Rule 1: If we have an existing RTSP URL and form credentials haven't changed, preserve original credentials
      if (existingRTSPUrl && originalCredentials.hasOriginal) {
        // Check if form credentials have been explicitly changed by user
        if (!formCredentialsChanged.username && originalCredentials.username) {
          finalUsername = originalCredentials.username;
        }
        if (!formCredentialsChanged.password && originalCredentials.password) {
          finalPassword = originalCredentials.password;
        }
      }

      // Rule 2: If form credentials are explicitly provided and changed, use them
      if (formCredentialsChanged.username && username.trim()) {
        finalUsername = username;
      }
      if (formCredentialsChanged.password && password.trim()) {
        finalPassword = password;
      }

      // Rule 3: Fallback to form values if no preserved credentials available
      if (!finalUsername && username.trim()) {
        finalUsername = username;
      }
      if (!finalPassword && password.trim()) {
        finalPassword = password;
      }

      // Build the URL with determined credentials
      const finalPort = port || '554';
      const finalPath = path ? `/${path}` : '';

      return `${protocol}://${finalUsername}:${finalPassword}@${targetIP}:${finalPort}${finalPath}`;
    } catch (error) {
      console.error('Error building RTSP URL with credential preservation:', error);
      // Fallback to simple URL construction
      const portString = port ? `:${port}` : ':554';
      return `${protocol}://${username}:${password}@${targetIP}${portString}${path ? '/' + path : ''}`;
    }
  };

  // Function to extract and store original credentials from existing RTSP URL
  const extractAndStoreOriginalCredentials = (rtspUrl) => {
    if (!rtspUrl) return;

    try {
      const parsed = parseRTSPUrl(rtspUrl);
      if (parsed.username && parsed.password) {
        setOriginalCredentials({
          username: parsed.username,
          password: parsed.password,
          hasOriginal: true
        });

        // If form fields are empty, populate them with extracted credentials
        if (!username && parsed.username) {
          setUsername(parsed.username);
        }
        if (!password && parsed.password) {
          setPassword(parsed.password);
        }
        if (!port && parsed.port && parsed.port !== '554') {
          setPort(parsed.port);
        }
        if (!path && parsed.path && parsed.path !== '/') {
          setPath(parsed.path.replace('/', ''));
        }

        console.log('Extracted original credentials from existing RTSP URL');
      }
    } catch (error) {
      console.error('Failed to extract credentials from RTSP URL:', error);
    }
  };

  // Function to check if current form credentials differ from original
  const updateCredentialChangeTracking = (field, newValue) => {
    if (originalCredentials.hasOriginal) {
      const originalValue = originalCredentials[field] || '';
      const hasChanged = newValue !== originalValue;

      setFormCredentialsChanged(prev => ({
        ...prev,
        [field]: hasChanged
      }));
    } else {
      // If no original credentials, any non-empty value is considered a change
      setFormCredentialsChanged(prev => ({
        ...prev,
        [field]: newValue.trim() !== ''
      }));
    }
  };

  // Step validation functions
  const validateStep1 = async () => {
    const errors = {};

    // Camera Model validation
    if (!cameraModel.trim()) {
      errors.cameraModel = 'Camera Model is required';
    }

    // IP Range validation
    if (!ipStart.trim()) {
      errors.ipStart = 'IP address is required';
    } else {
      // Validate IP format and private range
      const ipValidation = validatePrivateIP(ipStart);
      if (!ipValidation.isValid) {
        errors.ipStart = ipValidation.error;
      }
      // Note: Duplicate checking is now handled by the smart range processing endpoint
    }

    // IP End validation (if provided)
    if (ipEnd && ipEnd.trim()) {
      const ipEndNum = parseInt(ipEnd, 10);
      const ipStartNum = parseInt(ipStart.split('.').pop(), 10);

      if (isNaN(ipEndNum) || ipEndNum < ipStartNum || ipEndNum > 255) {
        errors.ipEnd = 'End IP must be a number between start IP and 255';
      }
    }

    setValidationErrors(prev => ({ ...prev, ...errors }));
    const isValid = Object.keys(errors).length === 0;
    setStepValidation(prev => ({ ...prev, 1: isValid }));
    return isValid;
  };

  const validateStep2 = () => {
    const errors = {};

    // Username validation
    if (!username.trim()) {
      errors.username = 'Username is required';
    }

    // Password validation
    if (!password.trim()) {
      errors.password = 'Password is required';
    }

    setValidationErrors(prev => ({ ...prev, ...errors }));
    const isValid = Object.keys(errors).length === 0;
    setStepValidation(prev => ({ ...prev, 2: isValid }));
    return isValid;
  };

  const validateStep3 = () => {
    const errors = {};

    // Collection selection validation
    if (!selectedCollection) {
      errors.selectedCollection = 'Please select a collection';
    }

    setValidationErrors(prev => ({ ...prev, ...errors }));
    const isValid = Object.keys(errors).length === 0;
    setStepValidation(prev => ({ ...prev, 3: isValid }));
    return isValid;
  };

  // Navigation functions with validation
  const goToNextStep = async () => {
    let canProceed = false;

    // Validate current step before proceeding
    switch (currentStep) {
      case 1:
        canProceed = await validateStep1();
        break;
      case 2:
        canProceed = validateStep2();
        break;
      case 3:
        canProceed = validateStep3();
        break;
      default:
        canProceed = true;
    }

    if (canProceed && currentStep < totalSteps) {
      setCurrentStep(currentStep + 1);
      setError(''); // Clear any previous errors
    }
  };

  const goToPreviousStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
      setError(''); // Clear any previous errors
    }
  };

  const goToStep = async (step) => {
    if (step >= 1 && step <= totalSteps) {
      // If going forward, validate all steps up to the target step
      if (step > currentStep) {
        let canProceed = true;
        for (let i = currentStep; i < step && canProceed; i++) {
          switch (i) {
            case 1:
              canProceed = await validateStep1();
              break;
            case 2:
              canProceed = validateStep2();
              break;
            case 3:
              canProceed = validateStep3();
              break;
          }
        }
        if (canProceed) {
          setCurrentStep(step);
          setError('');
        }
      } else {
        // Going backward is always allowed
        setCurrentStep(step);
        setError('');
      }
    }
  };

  // Calculate progress percentage
  const progressPercentage = ((currentStep - 1) / (totalSteps - 1)) * 100;

  useEffect(() => {
    const handleSaveResponse = (event, response) => {
      if (!response.success) {
        setError(`Failed to save camera configuration: ${response.error}`);
      }
    };

    ipcRenderer.on('save-camera-config-reply', handleSaveResponse);
    return () => {
      ipcRenderer.removeListener('save-camera-config-reply', handleSaveResponse);
    };
  }, []);

  // Effect to handle credential extraction from existing cameras when editing
  useEffect(() => {
    // Check if we're editing an existing camera by looking for existing RTSP URLs in the selected collection
    if (selectedCollection && ipStart) {
      const collection = collections.find(c => c.id === selectedCollection);
      if (collection && collection.cameras) {
        // Look for existing camera with the same IP to extract credentials
        const existingCamera = collection.cameras.find(camera => {
          const cameraIP = extractIPFromStreamURL(camera.streamUrl);
          return cameraIP === ipStart;
        });

        if (existingCamera && existingCamera.streamUrl && !originalCredentials.hasOriginal) {
          console.log('Found existing camera with same IP, extracting credentials...');
          extractAndStoreOriginalCredentials(existingCamera.streamUrl);
        }
      }
    }
  }, [selectedCollection, ipStart, collections, originalCredentials.hasOriginal]);

  // Effect to handle RTSP URL synchronization and credential preservation
  useEffect(() => {
    // This effect demonstrates the enhanced RTSP URL synchronization with credential preservation
    if (ipStart && (username || originalCredentials.username) && (password || originalCredentials.password)) {
      const previewUrl = buildRTSPUrlWithCredentialPreservation(ipStart);
      console.log('RTSP URL synchronized with credential preservation:', {
        ip: ipStart,
        preservedCredentials: originalCredentials.hasOriginal,
        credentialsChanged: formCredentialsChanged,
        previewUrl: previewUrl.replace(/:[^:@]*@/, ':***@') // Mask password for logging
      });
    }
  }, [ipStart, username, password, protocol, port, path, originalCredentials, formCredentialsChanged]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setRangeResults(null);

    // Validate all steps before submission
    const step1Valid = await validateStep1();
    const step2Valid = validateStep2();
    const step3Valid = validateStep3();

    if (!step1Valid || !step2Valid || !step3Valid) {
      setError('Please fix all validation errors before submitting');
      return;
    }

    try {
      const collection = collections.find(c => c.id === selectedCollection);
      if (!collection) {
        setError('Selected collection not found');
        return;
      }

      setIsProcessingRange(true);

      // Prepare data for the smart range processing endpoint
      const rangeData = {
        collection_name: collection.name,
        ip_start: ipStart,
        ip_end: ipEnd || null,
        camera_model: cameraModel,
        username: username || '',
        password: password || '',
        port: port || '554',
        main_stream: path || '',
        analytic_stream: analyticStream || '',
        protocol: protocol || 'rtsp'
      };

      // Calculate total IPs for progress tracking
      const ipStartNum = parseInt(ipStart.split('.').pop(), 10);
      const ipEndNum = ipEnd ? parseInt(ipEnd, 10) : ipStartNum;
      const totalIPs = ipEndNum - ipStartNum + 1;

      setRangeProgress({ current: 0, total: totalIPs });

      // Call the smart range processing endpoint
      const response = await axios.post(`${API_BASE_URL}/api/collections/add-camera-range`, rangeData);

      if (response.data) {
        setRangeResults(response.data.results);

        // Update the camera store with successful cameras
        if (response.data.results.successful_cameras) {
          response.data.results.successful_cameras.forEach(camera => {
            updateCameraConfig(collection.name, camera.ip, camera.stream_url);
          });

          // Save the configuration to file
          saveCameraConfig();
        }

        // Show success message or results summary
        if (response.data.results.successful_cameras.length > 0) {
          console.log('Camera range processing completed:', response.data.message);

          // If all cameras were successful, close modal after a brief delay
          if (response.data.results.skipped_duplicates.length === 0 &&
              response.data.results.validation_errors.length === 0 &&
              response.data.results.processing_errors.length === 0) {
            setTimeout(() => {
              resetFormAndClose();
            }, 2000);
          }
        }
      }

    } catch (err) {
      console.error('Error in camera range processing:', err);
      if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail.message || err.response.data.detail);
      } else {
        setError(err.message || 'Failed to add camera range. Please try again.');
      }
    } finally {
      setIsProcessingRange(false);
    }
  };

  const resetFormAndClose = () => {
    setCameraModel('');
    setIpStart('');
    setIpEnd('');
    setUsername('admin');
    setPassword('');
    setPort('554');
    setProtocol('rtsp');
    setPath('');
    setAnalyticStream('');
    setSelectedCollection('');
    setRangeResults(null);
    setRangeProgress({ current: 0, total: 0 });
    onClose();
  };

  return (
    <div className="wizard-modal-overlay">
      <div className="wizard-modal-content">
        {/* Header */}
        <div className="wizard-modal-header">
          <h3>Camera Onboarding</h3>
          <button className="wizard-modal-close-button" onClick={onClose}>✕</button>
        </div>

        {/* Progress Indicator */}
        <div className="wizard-progress-container">
          <div className="wizard-progress-text">Step {currentStep} of {totalSteps}</div>
          <div className="wizard-progress-bar">
            <div
              className="wizard-progress-fill"
              style={{ width: `${progressPercentage}%` }}
            ></div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="wizard-tabs">
          <button
            className={`wizard-tab ${currentStep === 1 ? 'active' : ''} ${stepValidation[1] ? 'validated' : ''} ${Object.keys(validationErrors).some(key => ['cameraModel', 'ipStart', 'ipEnd'].includes(key)) ? 'error' : ''}`}
            onClick={() => goToStep(1)}
          >
            Camera Details
          </button>
          <button
            className={`wizard-tab ${currentStep === 2 ? 'active' : ''} ${stepValidation[2] ? 'validated' : ''} ${Object.keys(validationErrors).some(key => ['username', 'password'].includes(key)) ? 'error' : ''}`}
            onClick={() => goToStep(2)}
          >
            Connection
          </button>
          <button
            className={`wizard-tab ${currentStep === 3 ? 'active' : ''} ${stepValidation[3] ? 'validated' : ''} ${validationErrors.selectedCollection ? 'error' : ''}`}
            onClick={() => goToStep(3)}
          >
            Collection
          </button>
        </div>

        {/* Form Content */}
        <div className="wizard-modal-body">
          <form onSubmit={(e) => { e.preventDefault(); }}>
            {/* Step 1: Camera Details */}
            <div className={`wizard-tab-content ${currentStep === 1 ? 'active' : ''}`}>
              <div className="wizard-form-group">
                <label htmlFor="cameraModel">
                  Camera Model <span className="required-asterisk">*</span>
                </label>
                <input
                  type="text"
                  id="cameraModel"
                  value={cameraModel}
                  onChange={(e) => {
                    setCameraModel(e.target.value);
                    // Clear validation error when user starts typing
                    if (validationErrors.cameraModel) {
                      setValidationErrors(prev => {
                        const newErrors = { ...prev };
                        delete newErrors.cameraModel;
                        return newErrors;
                      });
                    }
                  }}
                  placeholder="e.g. AXIS M3205-V"
                  className={validationErrors.cameraModel ? 'error' : ''}
                  required
                />
                {validationErrors.cameraModel && (
                  <div className="field-error">{validationErrors.cameraModel}</div>
                )}
              </div>

              <div className="wizard-form-group">
                <label>
                  IP Range <span className="required-asterisk">*</span>
                </label>
                <div className="ip-range-inputs">
                  <input
                    type="text"
                    value={ipStart}
                    onChange={(e) => {
                      setIpStart(e.target.value);
                      // Clear validation error when user starts typing
                      if (validationErrors.ipStart) {
                        setValidationErrors(prev => {
                          const newErrors = { ...prev };
                          delete newErrors.ipStart;
                          return newErrors;
                        });
                      }
                    }}
                    placeholder="e.g. 192.168.1.100"
                    className={validationErrors.ipStart ? 'error' : ''}
                    required
                  />
                  <span>to</span>
                  <input
                    type="text"
                    value={ipEnd}
                    onChange={(e) => {
                      setIpEnd(e.target.value);
                      // Clear validation error when user starts typing
                      if (validationErrors.ipEnd) {
                        setValidationErrors(prev => {
                          const newErrors = { ...prev };
                          delete newErrors.ipEnd;
                          return newErrors;
                        });
                      }
                    }}
                    placeholder="e.g. 110 (optional)"
                    className={validationErrors.ipEnd ? 'error' : ''}
                  />
                </div>
                {validationErrors.ipStart && (
                  <div className="field-error">{validationErrors.ipStart}</div>
                )}
                {validationErrors.ipEnd && (
                  <div className="field-error">{validationErrors.ipEnd}</div>
                )}
                {isValidating && (
                  <div className="validation-status">
                    <span>Validating IP address...</span>
                  </div>
                )}
              </div>
            </div>

            {/* Step 2: Connection */}
            <div className={`wizard-tab-content ${currentStep === 2 ? 'active' : ''}`}>
              <div className="wizard-form-group">
                <label>Protocol</label>
                <select
                  value={protocol}
                  onChange={(e) => setProtocol(e.target.value)}
                >
                  <option value="rtsp">RTSP</option>
                  <option value="http">HTTP</option>
                </select>
              </div>

              <div className="wizard-form-group">
                <label>
                  Authentication <span className="required-asterisk">*</span>
                </label>
                <div className="auth-inputs">
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => {
                      const newValue = e.target.value;
                      setUsername(newValue);
                      updateCredentialChangeTracking('username', newValue);
                      // Clear validation error when user starts typing
                      if (validationErrors.username) {
                        setValidationErrors(prev => {
                          const newErrors = { ...prev };
                          delete newErrors.username;
                          return newErrors;
                        });
                      }
                    }}
                    placeholder="Username"
                    className={validationErrors.username ? 'error' : ''}
                    required
                  />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => {
                      const newValue = e.target.value;
                      setPassword(newValue);
                      updateCredentialChangeTracking('password', newValue);
                      // Clear validation error when user starts typing
                      if (validationErrors.password) {
                        setValidationErrors(prev => {
                          const newErrors = { ...prev };
                          delete newErrors.password;
                          return newErrors;
                        });
                      }
                    }}
                    placeholder="Password"
                    className={validationErrors.password ? 'error' : ''}
                    required
                  />
                </div>
                {validationErrors.username && (
                  <div className="field-error">{validationErrors.username}</div>
                )}
                {validationErrors.password && (
                  <div className="field-error">{validationErrors.password}</div>
                )}
              </div>

              <div className="wizard-form-group">
                <label htmlFor="port">Port (default: 554)</label>
                <input
                  type="text"
                  id="port"
                  value={port}
                  onChange={(e) => setPort(e.target.value)}
                  placeholder="554"
                />
              </div>

              <div className="wizard-form-group">
                <label htmlFor="path">Path (optional)</label>
                <input
                  type="text"
                  id="path"
                  value={path}
                  onChange={(e) => setPath(e.target.value)}
                  placeholder="e.g. stream1"
                />
              </div>

              <div className="wizard-form-group">
                <label htmlFor="analyticStream">Analytic Stream (optional)</label>
                <input
                  type="text"
                  id="analyticStream"
                  value={analyticStream}
                  onChange={(e) => setAnalyticStream(e.target.value)}
                  placeholder="e.g. analytics"
                />
              </div>

              {/* RTSP URL Preview - Hidden for security */}
              {/* Preview removed to prevent credential exposure in UI */}
            </div>

            {/* Step 3: Collection */}
            <div className={`wizard-tab-content ${currentStep === 3 ? 'active' : ''}`}>
              <div className="wizard-form-group">
                <label htmlFor="collection">
                  Select Collection <span className="required-asterisk">*</span>
                </label>
                <div className="collection-select-container">
                  <select
                    id="collection"
                    value={selectedCollection}
                    onChange={(e) => {
                      setSelectedCollection(e.target.value);
                      // Clear validation error when user makes selection
                      if (validationErrors.selectedCollection) {
                        setValidationErrors(prev => {
                          const newErrors = { ...prev };
                          delete newErrors.selectedCollection;
                          return newErrors;
                        });
                      }
                    }}
                    className={validationErrors.selectedCollection ? 'error' : ''}
                    required
                  >
                    <option value="">Select a collection</option>
                    {collections.map(collection => (
                      <option key={collection.id} value={collection.id}>
                        {collection.name}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="add-collection-link"
                    onClick={() => setShowAddCollectionModal(true)}
                  >
                    <img src={addIcon} alt="Add" className="button-icon" />
                    Add New Collection
                  </button>
                </div>
                {validationErrors.selectedCollection && (
                  <div className="field-error">{validationErrors.selectedCollection}</div>
                )}
              </div>
            </div>

            {error && <div className="wizard-error-message">{error}</div>}
          </form>
        </div>

        {/* Range Processing Progress */}
        {isProcessingRange && (
          <div className="range-processing-overlay">
            <div className="range-processing-content">
              <h4>Processing Camera Range...</h4>
              <div className="range-progress-bar">
                <div
                  className="range-progress-fill"
                  style={{ width: `${(rangeProgress.current / rangeProgress.total) * 100}%` }}
                ></div>
              </div>
              <p>Processing {rangeProgress.current} of {rangeProgress.total} cameras</p>
            </div>
          </div>
        )}

        {/* Range Results Display */}
        {rangeResults && (
          <div className="range-results-section">
            <h4>Processing Results</h4>

            {rangeResults.successful_cameras.length > 0 && (
              <div className="result-group success">
                <h5>✅ Successfully Created ({rangeResults.successful_cameras.length})</h5>
                <ul>
                  {rangeResults.successful_cameras.map((camera, index) => (
                    <li key={index}>{camera.ip} - {camera.name}</li>
                  ))}
                </ul>
              </div>
            )}

            {rangeResults.skipped_duplicates.length > 0 && (
              <div className="result-group warning">
                <h5>⚠️ Skipped Duplicates ({rangeResults.skipped_duplicates.length})</h5>
                <ul>
                  {rangeResults.skipped_duplicates.map((item, index) => (
                    <li key={index}>
                      {item.ip} - Already exists in {item.existing_collection}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {rangeResults.validation_errors.length > 0 && (
              <div className="result-group error">
                <h5>❌ Validation Errors ({rangeResults.validation_errors.length})</h5>
                <ul>
                  {rangeResults.validation_errors.map((item, index) => (
                    <li key={index}>{item.ip} - {item.error}</li>
                  ))}
                </ul>
              </div>
            )}

            {rangeResults.processing_errors.length > 0 && (
              <div className="result-group error">
                <h5>❌ Processing Errors ({rangeResults.processing_errors.length})</h5>
                <ul>
                  {rangeResults.processing_errors.map((item, index) => (
                    <li key={index}>{item.ip} - {item.error}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="result-actions">
              <button
                className="wizard-nav-button"
                onClick={resetFormAndClose}
              >
                Close
              </button>
            </div>
          </div>
        )}

        {/* Footer with Navigation */}
        <div className="wizard-modal-footer">
          <div className="wizard-left-footer">
            {currentStep > 1 && (
              <button
                className="wizard-nav-button"
                onClick={goToPreviousStep}
              >
                Back
              </button>
            )}
          </div>

          <div className="wizard-right-footer">
            {currentStep < totalSteps ? (
              <button
                className={`wizard-nav-button ${isValidating ? 'disabled' : ''}`}
                onClick={goToNextStep}
                disabled={isValidating}
              >
                {isValidating ? 'Validating...' : 'Next'}
              </button>
            ) : (
              <button
                className={`wizard-nav-button ${(isValidating || isProcessingRange) ? 'disabled' : ''}`}
                onClick={handleSubmit}
                disabled={isValidating || isProcessingRange}
              >
                {isProcessingRange ? 'Processing Range...' : isValidating ? 'Validating...' : 'Submit'}
              </button>
            )}
          </div>
        </div>
      </div>

      {showAddCollectionModal && (
        <AddCollectionModal
          onClose={() => setShowAddCollectionModal(false)}
          onCollectionAdded={() => setShowAddCollectionModal(false)}
        />
      )}
    </div>
  );
};

export default AddCameraModal;