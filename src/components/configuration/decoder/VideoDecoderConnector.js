import React, { useState, useEffect } from 'react';
import './VideoDecoderConnector.css';
import { apiRequest } from '../../../utils/api';
import editIcon from '../../../icon/pen.png';
import deleteIcon from '../../../icon/delete.png';
import addIcon from '../../../icon/add-icon.png';

// Helper function to validate IPv4 addresses
const isValidIP = (ip) => {
  const regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;
  return regex.test(ip);
};

const VideoDecoderConnector = () => {
  const [connectors, setConnectors] = useState([]);
  const [editingConnector, setEditingConnector] = useState(null);
  const [newIp, setNewIp] = useState('');
  const [newName, setNewName] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  // Fetch connectors from API when component mounts
  useEffect(() => {
    // Clear any existing errors
    setError('');
    fetchConnectors();
  }, []);

  // Function to fetch connectors from the API
  const fetchConnectors = async () => {
    try {
      const response = await apiRequest('/api/augment/decoders');
      if (response && response.success) {
        setConnectors(response.data || []);
      } else {
        // If API call fails, keep the empty array
        console.warn('API error:', response?.error || 'Unknown error');
      }
    } catch (err) {
      console.error('Error fetching video decoder connectors:', err);
      // Keep the empty array
    }
  };

  // Function to add a new connector
  const handleAddConnector = async () => {
    setError('');

    // Validate inputs
    if (!newIp || !newName) {
      setError('Please enter both IP address and connector name');
      return;
    }

    // Validate IP format using the helper function
    if (!isValidIP(newIp)) {
      setError('Please enter a valid IPv4 address (e.g., 192.168.1.1). Each part must be a number between 0-255.');
      return;
    }

    try {
      // Store the values before clearing the form
      const ipToSave = newIp;
      const nameToSave = newName;

      // Create a new connector object with a unique ID
      const newConnector = {
        id: connectors.length > 0 ? Math.max(...connectors.map(c => c.id)) + 1 : 1,
        ip: ipToSave,
        name: nameToSave
      };

      // Add the connector to the local state immediately for better UX
      setConnectors(prevConnectors => [...prevConnectors, newConnector]);

      // Clear the form
      setNewIp('');
      setNewName('');
      setShowAddForm(false);

      // Try to save to the API in the background
      try {
        const response = await apiRequest('/api/augment/decoders', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ip: ipToSave, name: nameToSave }),
        });

        if (!response || !response.success) {
          console.warn('API call to add decoder failed, but UI was updated:', response?.error || 'Unknown error');
        }
      } catch (apiError) {
        console.warn('API call to add decoder failed, but UI was updated:', apiError);
      }
    } catch (err) {
      setError('Failed to add decoder connector. Please try again.');
      console.error('Error adding decoder connector:', err);
    }
  };

  // Function to start editing a connector
  const handleEditClick = (connector) => {
    setEditingConnector(connector.id);
    setNewIp(connector.ip);
    setNewName(connector.name);
  };

  // Function to save edited connector
  const handleSaveEdit = async (id) => {
    setError('');

    // Validate inputs
    if (!newIp || !newName) {
      setError('Please enter both IP address and connector name');
      return;
    }

    // Validate IP format using the helper function
    if (!isValidIP(newIp)) {
      setError('Please enter a valid IPv4 address (e.g., 192.168.1.1). Each part must be a number between 0-255.');
      return;
    }

    try {
      // Store the values before clearing the form
      const ipToSave = newIp;
      const nameToSave = newName;

      // Update the UI immediately for better UX
      const updatedConnectors = connectors.map(connector =>
        connector.id === id ? { ...connector, ip: ipToSave, name: nameToSave } : connector
      );
      setConnectors(updatedConnectors);
      setEditingConnector(null);
      setNewIp('');
      setNewName('');

      // Try to update in the API in the background
      try {
        const response = await apiRequest(`/api/augment/decoders/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ip: ipToSave, name: nameToSave }),
        });

        if (!response || !response.success) {
          console.warn('API call to update decoder failed, but UI was updated:', response?.error || 'Unknown error');
        }
      } catch (apiError) {
        console.warn('API call to update decoder failed, but UI was updated:', apiError);
      }
    } catch (err) {
      setError('Failed to update decoder connector. Please try again.');
      console.error('Error updating decoder connector:', err);
    }
  };

  // Function to cancel editing
  const handleCancelEdit = () => {
    setEditingConnector(null);
    setNewIp('');
    setNewName('');
    setError('');
  };

  // Function to show delete confirmation
  const handleDeleteClick = (id) => {
    setShowDeleteConfirm(id);
  };

  // Function to confirm connector deletion
  const handleConfirmDelete = async (id) => {
    try {
      // Update the UI immediately for better UX
      const updatedConnectors = connectors.filter(connector => connector.id !== id);
      setConnectors(updatedConnectors);
      setShowDeleteConfirm(null);

      // Try to delete from the API in the background
      try {
        const response = await apiRequest(`/api/augment/decoders/${id}`, {
          method: 'DELETE'
        });

        if (!response || !response.success) {
          console.warn('API call to delete decoder failed, but UI was updated:', response?.error || 'Unknown error');
        }
      } catch (apiError) {
        console.warn('API call to delete decoder failed, but UI was updated:', apiError);
      }
    } catch (err) {
      setError('Failed to delete decoder connector. Please try again.');
      console.error('Error deleting decoder connector:', err);
    }
  };

  // Function to cancel deletion
  const handleCancelDelete = () => {
    setShowDeleteConfirm(null);
  };

  return (
    <div className="video-decoder-container">
      <div className="video-decoder-header">
        <h2>Video Decoder Connector</h2>
        <button
          onClick={() => {
            if (showAddForm) {
              // Reset form when canceling
              setNewIp('');
              setNewName('');
              setError('');
            }
            setShowAddForm(!showAddForm);
          }}
          className="add-connector-button"
          title={showAddForm ? "Cancel" : "Add a new video decoder connector"}
        >
          <img src={addIcon} alt="Add" className="button-icon" />
          {showAddForm ? "Cancel" : "Add New Connector"}
        </button>
      </div>

      {showAddForm && (
        <div className="add-connector-form-container">
          <h3 className="form-title">Add New Video Decoder Connector</h3>
          <form
            className="add-connector-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (newIp && newName) {
                handleAddConnector();
                setShowAddForm(false);
              }
            }}
          >
            <div className="form-fields-container">
              <div className="form-group">
                <label htmlFor="connector-ip" className="input-label">Connector IP</label>
                <input
                  id="connector-ip"
                  type="text"
                  placeholder="192.168.1.50"
                  value={newIp}
                  onChange={(e) => setNewIp(e.target.value)}
                  className="connector-input"
                  autoComplete="off"
                />
                <small className="input-helper-text">Enter a valid IPv4 address (e.g., 192.168.1.50)</small>
              </div>
              <div className="form-group">
                <label htmlFor="connector-name" className="input-label">Connector Name</label>
                <input
                  id="connector-name"
                  type="text"
                  placeholder="Lobby Decoder"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="connector-input"
                  autoComplete="off"
                />
              </div>
            </div>
            <div className="form-actions">
              <button
                type="submit"
                className="add-button"
                title="Add connector"
                disabled={!newIp || !newName}
              >
                <img src={addIcon} alt="Add" className="button-icon" />
                Add Connector
              </button>
            </div>
          </form>
        </div>
      )}

      {error && (
        <div className="error-message">
          {error}
          <button
            className="dismiss-error"
            onClick={() => setError('')}
            title="Dismiss error"
          >
            ✕
          </button>
        </div>
      )}

      <div className="connector-table">
        <div className="connector-table-header">
          <div className="connector-column">Connector IP</div>
          <div className="connector-column">Connector Name</div>
          <div className="connector-column actions-column">Actions</div>
        </div>

        <div className="connector-table-body">
          {connectors.length === 0 ? (
            <div className="no-connectors">No video decoder connectors added yet. Click "Add New Connector" to get started.</div>
          ) : (
            connectors.map((connector) => (
              <div key={connector.id} className="connector-row">
                {editingConnector === connector.id ? (
                  // Edit mode
                  <div className="edit-form-row">
                    <h4 className="edit-form-title">Edit Connector</h4>
                    <div className="edit-form-fields">
                      <div className="edit-form-group">
                        <label htmlFor="edit-connector-ip" className="edit-input-label">Connector IP</label>
                        <input
                          id="edit-connector-ip"
                          type="text"
                          value={newIp}
                          onChange={(e) => setNewIp(e.target.value)}
                          className="edit-input"
                          autoComplete="off"
                        />
                        <small className="input-helper-text">Enter a valid IPv4 address (e.g., 192.168.1.50)</small>
                      </div>
                      <div className="edit-form-group">
                        <label htmlFor="edit-connector-name" className="edit-input-label">Connector Name</label>
                        <input
                          id="edit-connector-name"
                          type="text"
                          value={newName}
                          onChange={(e) => setNewName(e.target.value)}
                          className="edit-input"
                          autoComplete="off"
                        />
                      </div>
                    </div>
                    <div className="edit-form-actions">
                      <button
                        className="save-button"
                        onClick={() => handleSaveEdit(connector.id)}
                        disabled={!newIp || !newName}
                      >
                        <i className="fas fa-check"></i> Save
                      </button>
                      <button
                        className="cancel-button"
                        onClick={handleCancelEdit}
                      >
                        <i className="fas fa-times"></i> Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  // View mode
                  <>
                    <div className="connector-column">{connector.ip}</div>
                    <div className="connector-column">{connector.name}</div>
                    <div className="connector-column actions-column">
                      <button
                        className="edit-button"
                        onClick={() => handleEditClick(connector)}
                        title="Edit Connector"
                      >
                        <img src={editIcon} alt="Edit" />
                      </button>
                      <button
                        className="delete-button"
                        onClick={() => handleDeleteClick(connector.id)}
                        title="Delete Connector"
                      >
                        <img src={deleteIcon} alt="Delete" />
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
            <h3>Delete Video Decoder Connector</h3>
            <p>
              Are you sure you want to delete this connector? This action cannot be undone and may affect any video display services that depend on this decoder.
            </p>
            <div className="modal-actions">
              <button
                className="cancel-button"
                onClick={handleCancelDelete}
              >
                Cancel
              </button>
              <button
                className="confirm-button"
                onClick={() => handleConfirmDelete(showDeleteConfirm)}
              >
                Yes, Delete Connector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoDecoderConnector;
