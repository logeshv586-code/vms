import React, { useState, useEffect } from 'react';
import { useCameras } from './CameraManager';
import './CollectionManager.css';
import AddCameraForm from './AddCameraForm';
import LayoutSelector from '../layout/LayoutSelector';
import VideoGrid from '../dashboard/VideoGrid';
import { DragDropProvider } from '../DragDropContext';
import penIcon from '../../icon/pen.png';
import deleteIcon from '../../icon/delete.png';
import streamIcon from '../../icon/cctv-camera.png';
import DraggableVideoCell from './DraggableVideoCell';

const CollectionManager = ({ onClose, onViewChange }) => {
  const {
    collections,
    createCollection,
    renameCollection,
    deleteCollection,
    addCameraToCollection,
    removeCameraFromCollection,
    getCamerasByCollection,
    activeCollection,
    setCollectionActive
  } = useCameras();

  const [newCollectionName, setNewCollectionName] = useState('');
  const [selectedCollection, setSelectedCollection] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [currentLayout, setCurrentLayout] = useState('2x2');
  const [error, setError] = useState('');
  const [editingCollection, setEditingCollection] = useState(null);
  const [editCollectionName, setEditCollectionName] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);
  const [showAddCameraForm, setShowAddCameraForm] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [currentCameras, setCurrentCameras] = useState([]);
  const [highlightedCamera, setHighlightedCamera] = useState(null);

  // Clear selected collection when collections change
  useEffect(() => {
    if (selectedCollection && !collections.find(c => c.id === selectedCollection)) {
      setSelectedCollection(null);
      setCollectionActive(null);
    }
  }, [collections, selectedCollection, setCollectionActive]);

  // Sync selected collection with active collection
  useEffect(() => {
    setSelectedCollection(activeCollection);
  }, [activeCollection]);

  const handleCreateCollection = (e) => {
    e.preventDefault();
    setError('');

    if (!newCollectionName.trim()) {
      setError('Please enter an area name');
      return;
    }

    // Check if collection with same name already exists
    const existingCollection = collections.find(
      c => c.name.toLowerCase() === newCollectionName.trim().toLowerCase()
    );

    if (existingCollection) {
      setError('An area with this name already exists');
      return;
    }

    try {
      const newCollectionId = createCollection(newCollectionName.trim());
      setNewCollectionName('');
      setShowCreateForm(false);
      // Select the newly created collection
      setSelectedCollection(newCollectionId);
      setCollectionActive(newCollectionId);
    } catch (err) {
      setError('Failed to create area. Please try again.');
    }
  };

  const handleSelectCollection = (collectionId) => {
    setSelectedCollection(collectionId);
    setCollectionActive(collectionId);
    setShowAddCameraForm(false);
    setEditingCamera(null);
  };

  const handleCloseCollection = () => {
    setSelectedCollection(null);
    setCollectionActive(null);
    setShowCreateForm(false);
    setShowAddCameraForm(false);
    setEditingCamera(null);
  };

  const handleStartRename = (collectionId, e) => {
    e.stopPropagation(); // Prevent collection selection
    const collection = collections.find(c => c.id === collectionId);
    if (collection) {
      setEditingCollection(collectionId);
      setEditCollectionName(collection.name);
    }
  };

  const handleRenameSubmit = (e) => {
    e.preventDefault();
    e.stopPropagation(); // Prevent collection selection

    if (!editCollectionName.trim()) {
      setError('Please enter an area name');
      return;
    }

    try {
      renameCollection(editingCollection, editCollectionName);
      setEditingCollection(null);
      setEditCollectionName('');
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to rename area. Please try again.');
    }
  };

  const handleCancelRename = (e) => {
    e.stopPropagation(); // Prevent collection selection
    setEditingCollection(null);
    setEditCollectionName('');
    setError('');
  };

  const handleDeleteClick = (collectionId, e) => {
    e.stopPropagation(); // Prevent collection selection
    setShowDeleteConfirm(collectionId);
  };

  const handleConfirmDelete = (collectionId) => {
    deleteCollection(collectionId);
    setShowDeleteConfirm(null);
  };

  const handleCancelDelete = () => {
    setShowDeleteConfirm(null);
  };

  const handleAddCameraClick = () => {
    setShowAddCameraForm(true);
    setEditingCamera(null);
  };

  const handleEditCamera = (camera) => {
    setEditingCamera(camera);
    setShowAddCameraForm(true);
  };

  const handleCloseCameraForm = () => {
    setShowAddCameraForm(false);
    setEditingCamera(null);
  };

  const handleMoveCamera = (cameraId) => {
    setHighlightedCamera(cameraId);
  };

  useEffect(() => {
    if (selectedCollection) {
      setCurrentCameras(getCamerasByCollection(selectedCollection));
    }
  }, [selectedCollection, getCamerasByCollection]);

  return (
    <div className="collection-manager">
      {/* Left Sidebar */}
      <div className="collections-sidebar">
        <div className="collections-header">
          <div className="header-with-close">
            <h3>Manage Areas</h3>
            <button
              className="close-manager-button"
              onClick={onClose}
              title="Close Area Manager"
            >
              ✕
            </button>
          </div>
          <button
            className="create-collection-button"
            onClick={() => setShowCreateForm(true)}
          >
            Create New Area
          </button>
        </div>

        {showCreateForm && (
          <form onSubmit={handleCreateCollection} className="collection-form">
            {error && <div className="error-message">{error}</div>}
            <input
              type="text"
              value={newCollectionName}
              onChange={(e) => setNewCollectionName(e.target.value)}
              placeholder="Enter area name (e.g., Anna Nagar)"
              className="collection-input"
              autoFocus
            />
            <div className="form-actions">
              <button type="submit" className="save-button">Create</button>
              <button
                type="button"
                className="cancel-button"
                onClick={() => {
                  setShowCreateForm(false);
                  setError('');
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        <div className="collections-container">
          {collections.length === 0 ? (
            <div className="no-collections">
              <p>No areas created yet</p>
              <p>Click "Create New Area" to get started</p>
            </div>
          ) : (
            collections.map(collection => (
              <div
                key={collection.id}
                className={`collection-item ${selectedCollection === collection.id ? 'selected' : ''}`}
                onClick={() => handleSelectCollection(collection.id)}
              >
                {editingCollection === collection.id ? (
                  <form
                    className="collection-edit-form"
                    onSubmit={handleRenameSubmit}
                    onClick={(e) => e.stopPropagation()}
                  >
                    {error && <div className="error-message">{error}</div>}
                    <input
                      type="text"
                      value={editCollectionName}
                      onChange={(e) => setEditCollectionName(e.target.value)}
                      className="collection-input"
                      autoFocus
                    />
                    <div className="form-actions">
                      <button type="submit" className="save-button">Save</button>
                      <button
                        type="button"
                        className="cancel-button"
                        onClick={handleCancelRename}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <span className="collection-name">{collection.name}</span>
                    <div className="collection-actions">
                      <span className="collection-count">{collection.cameras.length} cameras</span>
                      <button
                        className="collection-action-button rename-button"
                        onClick={(e) => handleStartRename(collection.id, e)}
                        title="Rename Area"
                      >
                        <img src={penIcon} alt="Rename" style={{ width: '16px', height: '16px' }} />
                      </button>
                      <button
                        className="collection-action-button delete-button"
                        onClick={(e) => handleDeleteClick(collection.id, e)}
                        title="Delete Area"
                      >
                        <img src={deleteIcon} alt="Delete" style={{ width: '16px', height: '16px' }} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Delete Area</h3>
            <p>Are you sure you want to delete this area? All cameras in this area will also be deleted.</p>
            <div className="modal-actions">
              <button
                className="confirm-button"
                onClick={() => handleConfirmDelete(showDeleteConfirm)}
              >
                Delete
              </button>
              <button
                className="cancel-button"
                onClick={handleCancelDelete}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Panel */}
      <div className="collection-details">
        {selectedCollection ? (
          <>
            <div className="collection-header">
              <div className="collection-title">
                <h3>{collections.find(c => c.id === selectedCollection)?.name}</h3>
              </div>
              <div className="collection-header-actions">
                <button
                  className="rtsp-stream-button"
                  onClick={() => onViewChange && onViewChange('rtsp-stream')}
                  style={{ display: 'flex', alignItems: 'center', marginRight: '10px' }}
                >
                  <img src={streamIcon} alt="RTSP Streams" style={{ width: '16px', height: '16px', marginRight: '5px' }} />
                  <span>Live</span>
                </button>
                <button
                  onClick={handleCloseCollection}
                  className="close-collection-button"
                >
                  Close Area
                </button>
              </div>
            </div>
            <div className="collection-content">
              <div className="collection-camera-grid">
                {currentLayout === 'custom' ? (
                  <div className="custom-layout">
                    {currentCameras.map((camera, index) => (
                      <DraggableVideoCell
                        key={camera.id}
                        camera={camera}
                        index={index}
                        moveCamera={handleMoveCamera}
                        isHighlighted={highlightedCamera === camera.id}
                        showControls={true}
                      />
                    ))}
                  </div>
                ) : (
                  <div className={`grid-layout ${currentLayout}`}>
                    {currentCameras.map((camera, index) => (
                      <DraggableVideoCell
                        key={camera.id}
                        camera={camera}
                        index={index}
                        moveCamera={handleMoveCamera}
                        isHighlighted={highlightedCamera === camera.id}
                        showControls={true}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Camera Management Section */}
              <div className="camera-management-section">
                <div className="section-header">
                  <h4>Camera Management</h4>
                  {!showAddCameraForm && (
                    <button
                      className="add-camera-button"
                      onClick={handleAddCameraClick}
                    >
                      Add New Camera
                    </button>
                  )}
                </div>

                {showAddCameraForm && (
                  <AddCameraForm
                    collectionId={selectedCollection}
                    onClose={handleCloseCameraForm}
                    editingCamera={editingCamera}
                  />
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="no-collection-selected">
            <h3>Select an Area</h3>
            <p>Choose an area from the sidebar or create a new one</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default CollectionManager;