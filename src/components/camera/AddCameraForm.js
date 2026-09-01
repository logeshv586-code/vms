import React, { useState, useEffect } from 'react';
import { useCameras } from './CameraManager';
import { extractIPFromStreamURL, validatePrivateIP } from '../../utils/ipValidation';
import './AddCameraForm.css';

const AddCameraForm = ({ collectionId, onClose, editingCamera = null }) => {
  const { addCamera, updateCamera, removeCamera, collections, activeCollection } = useCameras();
  const [cameraName, setCameraName] = useState('');
  const [streamUrl, setStreamUrl] = useState('');
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [showForm, setShowForm] = useState(true);
  const [error, setError] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);

  // Initialize form with editing camera data if provided
  useEffect(() => {
    if (editingCamera) {
      setCameraName(editingCamera.name);
      setStreamUrl(editingCamera.streamUrl);
    } else {
      setCameraName('');
      setStreamUrl('');
    }
  }, [editingCamera]);

  // Show form when there's an active collection
  useEffect(() => {
    if (activeCollection) {
      setShowForm(true);
      setSelectedCollection(activeCollection);
    }
  }, [activeCollection]);

  // Set selected collection based on collectionId prop
  useEffect(() => {
    if (collectionId) {
      setSelectedCollection(collectionId);
    }
  }, [collectionId]);

  // Validate camera data with backend
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

  const validateForm = async () => {
    if (!cameraName.trim()) {
      setError('Please enter a camera name');
      return false;
    }

    if (!streamUrl.trim()) {
      setError('Please enter a stream URL');
      return false;
    }

    if (!streamUrl.trim().startsWith('rtsp://') && !streamUrl.trim().startsWith('http://')) {
      setError('Stream URL must start with rtsp:// or http://');
      return false;
    }

    // Extract IP address from stream URL for validation
    const extractedIP = extractIPFromStreamURL(streamUrl.trim());
    if (!extractedIP) {
      setError('Could not extract IP address from stream URL. Please ensure the URL contains a valid IP address.');
      return false;
    }

    // Basic client-side IP validation
    const ipValidation = validatePrivateIP(extractedIP);
    if (!ipValidation.isValid) {
      setError(`Camera IP address (${extractedIP}) must be within private network ranges:\n• 192.168.0.0 – 192.168.255.255 (most common)\n• 10.0.0.0 – 10.255.255.255\n• 172.16.0.0 – 172.31.255.255`);
      return false;
    }

    // Backend validation including duplicate checking
    setIsValidating(true);
    const targetCollectionId = collectionId || selectedCollection || activeCollection;
    const targetCollection = collections.find(c => c.id === targetCollectionId);
    const collectionName = targetCollection?.name;

    const excludeIp = editingCamera ? extractIPFromStreamURL(editingCamera.streamUrl) : null;

    const validation = await validateCameraData(
      extractedIP,
      streamUrl.trim(),
      collectionName,
      excludeIp
    );

    setIsValidating(false);
    setValidationResult(validation);

    if (!validation.valid) {
      if (validation.type === 'duplicate') {
        setError(`${validation.error}\n\nExisting camera found in collection: ${validation.existingCollection}`);
      } else {
        setError(validation.error);
      }
      return false;
    }

    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const isValid = await validateForm();
    if (!isValid) return;

    try {
      const targetCollectionId = collectionId || selectedCollection || activeCollection;

      if (editingCamera) {
        // Update existing camera
        await updateCamera(editingCamera.id, {
          name: cameraName.trim(),
          streamUrl: streamUrl.trim(),
          collectionId: targetCollectionId
        });
      } else {
        // Add new camera
        addCamera(cameraName.trim(), streamUrl.trim(), targetCollectionId);
      }

      // Reset form
      setCameraName('');
      setStreamUrl('');
      setError('');
      setValidationResult(null);

      // Close form if onClose is provided
      if (onClose) {
        onClose();
      }
    } catch (err) {
      console.error('Error submitting camera:', err);

      // Handle enhanced error messages from the camera store
      let errorMessage = `Failed to ${editingCamera ? 'update' : 'add'} camera.`;

      if (err.message) {
        errorMessage = err.message;
      }

      // Add additional context for specific error types
      if (err.type === 'duplicate') {
        errorMessage += '\n\nPlease choose a different IP address or stream URL.';
      } else if (err.type === 'validation') {
        errorMessage += '\n\nPlease check your input and try again.';
      } else if (err.statusCode === 409) {
        errorMessage += '\n\nThis camera configuration conflicts with an existing camera.';
      }

      setError(errorMessage);
    }
  };

  const handleDelete = () => {
    if (!editingCamera) return;

    try {
      removeCamera(editingCamera.id);
      setShowDeleteConfirm(false);
      if (onClose) {
        onClose();
      }
    } catch (err) {
      setError('Failed to delete camera. Please try again.');
    }
  };

  const handleCancel = () => {
    setCameraName('');
    setStreamUrl('');
    setError('');
    setShowDeleteConfirm(false);
    if (onClose) {
      onClose();
    }
  };

  if (!showForm) return null;

  return (
    <div className="add-camera-form">
      <div className="form-header">
        <h3>{editingCamera ? 'Edit Camera' : 'Add New Camera'}</h3>
        {onClose && (
          <button className="close-button" onClick={handleCancel}>
            ✕
          </button>
        )}
      </div>
      <form onSubmit={handleSubmit}>
        {error && <div className="error-message">{error}</div>}
        <div className="form-group">
          <label htmlFor="camera-name">Camera Name</label>
          <input
            id="camera-name"
            type="text"
            value={cameraName}
            onChange={(e) => setCameraName(e.target.value)}
            placeholder="Enter camera name"
            required
          />
        </div>
        <div className="form-group">
          <label htmlFor="stream-url">Stream URL (RTSP/HTTP)</label>
          <input
            id="stream-url"
            type="text"
            value={streamUrl}
            onChange={(e) => setStreamUrl(e.target.value)}
            placeholder="e.g. rtsp://admin:password@192.168.1.100:554/stream"
            required
          />
        </div>
        {/* Validation Status */}
        {isValidating && (
          <div className="validation-status">
            <span>Validating camera data...</span>
          </div>
        )}

        {validationResult && validationResult.valid && (
          <div className="validation-success">
            ✓ Camera data is valid and ready to be added
          </div>
        )}

        <div className="form-actions">
          <button
            type="submit"
            className="primary-button"
            disabled={isValidating}
          >
            {isValidating ? 'Validating...' : (editingCamera ? 'Update Camera' : 'Add Camera')}
          </button>
          {editingCamera && (
            <button
              type="button"
              className="delete-button"
              onClick={() => setShowDeleteConfirm(true)}
              disabled={isValidating}
            >
              Delete Camera
            </button>
          )}
          <button
            type="button"
            className="cancel-button"
            onClick={handleCancel}
            disabled={isValidating}
          >
            Cancel
          </button>
        </div>
      </form>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Delete Camera</h3>
            <p>Are you sure you want to delete this camera?</p>
            <div className="modal-actions">
              <button
                className="confirm-button"
                onClick={handleDelete}
              >
                Delete
              </button>
              <button
                className="cancel-button"
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AddCameraForm;