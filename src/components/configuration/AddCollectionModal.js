import React, { useState, useEffect } from 'react';
import { useCameraStore } from '../../store/cameraStore';
import { useUserStore } from '../../store/userStore';
import './AddCollectionModal.css';
import './WizardModalStyles.css';
import deleteIcon from '../../icon/delete.png';
import penIcon from '../../icon/pen.png';

const AddCollectionModal = ({ onClose }) => {
  const {
    collections,
    createCollection,
    renameCollection,
    deleteCollection,
    cameras,
    removeCameraFromCollection,
    getCamerasByCollection,
    updateCamera
  } = useCameraStore();
  const { currentUser } = useUserStore();

  // Check if user is supervisor
  const isSupervisor = currentUser?.role === 'Supervisor';

  // Form state
  const [collectionName, setCollectionName] = useState('');
  const [error, setError] = useState('');
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [editCameraName, setEditCameraName] = useState('');
  const [editStreamUrl, setEditStreamUrl] = useState('');
  const [showDeleteCameraConfirm, setShowDeleteCameraConfirm] = useState(null);

  // Wizard state
  const [currentStep, setCurrentStep] = useState(isSupervisor ? 2 : 1);
  const totalSteps = 2;

  // Navigation functions
  const goToNextStep = () => {
    if (currentStep < totalSteps) {
      setCurrentStep(currentStep + 1);
    }
  };

  const goToPreviousStep = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const goToStep = (step) => {
    if (step >= 1 && step <= totalSteps) {
      setCurrentStep(step);
    }
  };

  // Calculate progress percentage
  const progressPercentage = ((currentStep - 1) / (totalSteps - 1)) * 100;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!collectionName.trim()) {
      setError('Please enter a collection name');
      return;
    }

    try {
      // Show loading state or disable button here if needed
      if (selectedCollection) {
        await renameCollection(selectedCollection, collectionName.trim());
      } else {
        await createCollection(collectionName.trim());
      }
      setCollectionName('');
      setSelectedCollection(null);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to save collection');
    }
  };

  const handleDelete = async () => {
    if (!selectedCollection) return;

    try {
      // Show loading state or disable button here if needed
      await deleteCollection(selectedCollection);
      setSelectedCollection(null);
      setCollectionName('');
      setShowDeleteConfirm(false);
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to delete collection');
    }
  };

  const handleRemoveCamera = async (collectionId, cameraId) => {
    try {
      // Show loading state or disable button here if needed
      await removeCameraFromCollection(cameraId, collectionId);
      setShowDeleteCameraConfirm(null);
    } catch (err) {
      setError(err.message || 'Failed to remove camera from collection');
    }
  };

  const handleEditCamera = (camera) => {
    setEditingCamera(camera);
    setEditCameraName(camera.name);
    setEditStreamUrl(camera.streamUrl);
  };

  const handleSaveCamera = () => {
    if (!editCameraName.trim()) {
      setError('Please enter a camera name');
      return;
    }

    if (!editStreamUrl.trim()) {
      setError('Please enter a stream URL');
      return;
    }

    try {
      updateCamera(editingCamera.id, {
        name: editCameraName.trim(),
        streamUrl: editStreamUrl.trim()
      });
      setEditingCamera(null);
      setEditCameraName('');
      setEditStreamUrl('');
      setError('');
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    if (selectedCollection) {
      const collection = collections.find(c => c.id === selectedCollection);
      if (collection) {
        setCollectionName(collection.name);
      }
    } else {
      setCollectionName('');
    }
  }, [selectedCollection, collections]);

  return (
    <div className="wizard-modal-overlay">
      <div className="wizard-modal-content">
        {/* Header */}
        <div className="wizard-modal-header">
          <h3>Manage Collection</h3>
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
        {!isSupervisor && (
          <div className="wizard-tabs">
            <button
              className={`wizard-tab ${currentStep === 1 ? 'active' : ''}`}
              onClick={() => goToStep(1)}
            >
              Create Collection
            </button>
            <button
              className={`wizard-tab ${currentStep === 2 ? 'active' : ''}`}
              onClick={() => goToStep(2)}
            >
              Manage Existing
            </button>
          </div>
        )}

        {/* Form Content */}
        <div className="wizard-modal-body">
          <form onSubmit={(e) => { e.preventDefault(); }}>
            {/* Step 1: Create Collection */}
            {!isSupervisor && (
              <div className={`wizard-tab-content ${currentStep === 1 ? 'active' : ''}`}>
                <div className="wizard-form-group">
                  <label htmlFor="collectionName">Collection Name</label>
                  <input
                    type="text"
                    id="collectionName"
                    value={collectionName}
                    onChange={(e) => setCollectionName(e.target.value)}
                    placeholder="Enter new collection name"
                  />
                </div>
                {error && <div className="wizard-error-message">{error}</div>}
              </div>
            )}

            {/* Step 2: Manage Existing Collections */}
            <div className={`wizard-tab-content ${currentStep === 2 ? 'active' : ''}`}>
              <div className="collections-list">
                <h4>Existing Collections</h4>
                {collections.map(collection => (
                  <div key={collection.id} className="collection-item">
                    <div className="collection-header">
                      <span className="collection-name">{collection.name}</span>
                      {!isSupervisor && (
                        <div className="collection-actions">
                          <button
                            className="action-button edit-button"
                            onClick={() => {
                              setSelectedCollection(collection.id);
                              setCollectionName(collection.name);
                              goToStep(1);
                            }}
                          >
                            Edit
                          </button>
                          <button
                            className="action-button delete-button"
                            onClick={() => {
                              setSelectedCollection(collection.id);
                              setShowDeleteConfirm(true);
                            }}
                          >
                            <img src={deleteIcon} alt="Delete" className="button-icon" />
                          </button>
                        </div>
                      )}
                    </div>
                    <div className="collection-cameras">
                      {getCamerasByCollection(collection.id).map(camera => (
                        <div key={camera.id} className="camera-item">
                          {editingCamera?.id === camera.id ? (
                            <div className="camera-edit-form">
                              <input
                                type="text"
                                value={editCameraName}
                                onChange={(e) => setEditCameraName(e.target.value)}
                                placeholder="Camera name"
                              />
                              <input
                                type="text"
                                value={editStreamUrl}
                                onChange={(e) => setEditStreamUrl(e.target.value)}
                                placeholder="Stream URL"
                              />
                              <div className="camera-edit-actions">
                                <button
                                  type="button"
                                  className="action-button save-button"
                                  onClick={handleSaveCamera}
                                >
                                  Save
                                </button>
                                <button
                                  type="button"
                                  className="action-button cancel-button"
                                  onClick={() => {
                                    setEditingCamera(null);
                                    setEditCameraName('');
                                    setEditStreamUrl('');
                                    setError('');
                                  }}
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <>
                              <span className="camera-name">{camera.name}</span>
                              {!isSupervisor && (
                                <div className="camera-actions">
                                  <button
                                    className="action-button edit-button"
                                    onClick={() => handleEditCamera(camera)}
                                    title="Edit camera"
                                  >
                                    <img src={penIcon} alt="Edit" className="button-icon" />
                                  </button>
                                  <button
                                    className="action-button remove-camera-button"
                                    onClick={() => setShowDeleteCameraConfirm(camera.id)}
                                    title="Remove camera from collection"
                                  >
                                    <img src={deleteIcon} alt="Remove" className="button-icon" />
                                  </button>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </form>
        </div>

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
            {!isSupervisor && currentStep === 1 ? (
              <button
                className="wizard-nav-button"
                onClick={(e) => {
                  if (collectionName.trim()) {
                    handleSubmit(e);
                    goToNextStep();
                  } else {
                    setError('Please enter a collection name');
                  }
                }}
              >
                {selectedCollection ? 'Update' : 'Add'}
              </button>
            ) : (
              <button
                className="wizard-nav-button"
                onClick={onClose}
              >
                Done
              </button>
            )}
          </div>
        </div>
      </div>

      {showDeleteConfirm && (
        <div className="wizard-modal-overlay">
          <div className="wizard-modal-content">
            <div className="wizard-modal-header">
              <h3>Delete Collection</h3>
              <button className="wizard-modal-close-button" onClick={() => setShowDeleteConfirm(false)}>✕</button>
            </div>
            <div className="wizard-modal-body">
              <p>Are you sure you want to delete this collection? This action cannot be undone.</p>
            </div>
            <div className="wizard-modal-footer">
              <div className="wizard-left-footer">
                <button className="wizard-nav-button" onClick={() => setShowDeleteConfirm(false)}>
                  Cancel
                </button>
              </div>
              <div className="wizard-right-footer">
                <button className="wizard-nav-button" onClick={handleDelete}>
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showDeleteCameraConfirm && (
        <div className="wizard-modal-overlay">
          <div className="wizard-modal-content">
            <div className="wizard-modal-header">
              <h3>Remove Camera</h3>
              <button className="wizard-modal-close-button" onClick={() => setShowDeleteCameraConfirm(null)}>✕</button>
            </div>
            <div className="wizard-modal-body">
              <p>Are you sure you want to remove this camera from the collection?</p>
            </div>
            <div className="wizard-modal-footer">
              <div className="wizard-left-footer">
                <button
                  className="wizard-nav-button"
                  onClick={() => setShowDeleteCameraConfirm(null)}
                >
                  Cancel
                </button>
              </div>
              <div className="wizard-right-footer">
                <button
                  className="wizard-nav-button"
                  onClick={() => {
                    const camera = cameras.find(c => c.id === showDeleteCameraConfirm);
                    if (camera && camera.collectionId) {
                      handleRemoveCamera(camera.collectionId, camera.id);
                    }
                  }}
                >
                  Remove
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AddCollectionModal;