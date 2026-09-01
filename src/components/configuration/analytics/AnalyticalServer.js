import React, { useState, useEffect } from 'react';
import './AnalyticalServer.css';
import { API_BASE_URL } from '../../../utils/apiConfig';
import { apiRequest } from '../../../utils/api';
import editIcon from '../../../icon/pen.png';
import deleteIcon from '../../../icon/delete.png';
import addIcon from '../../../icon/add-icon.png';

// Helper function to validate IPv4 addresses
const isValidIP = (ip) => {
  const regex = /^(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;
  return regex.test(ip);
};

const AnalyticalServer = () => {
  const [servers, setServers] = useState([]);
  const [editingServer, setEditingServer] = useState(null);
  const [newIp, setNewIp] = useState('');
  const [newName, setNewName] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);
  const [error, setError] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);

  // Fetch servers from API when component mounts
  useEffect(() => {
    // Clear any existing errors
    setError('');
    fetchServers();
  }, []);

  // Function to fetch servers from the API
  const fetchServers = async () => {
    try {
      const response = await apiRequest('/api/augment/servers');
      if (response && response.success) {
        setServers(response.data || []);
      } else {
        // If API call fails, keep the empty array
        console.warn('API error:', response?.error || 'Unknown error');
      }
    } catch (err) {
      console.error('Error fetching servers:', err);
      // Keep the empty array
    }
  };

  // Function to add a new server
  const handleAddServer = async () => {
    setError('');

    // Validate inputs
    if (!newIp || !newName) {
      setError('Please enter both IP address and server name');
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

      // Create a new server object with a unique ID
      const newServer = {
        id: servers.length > 0 ? Math.max(...servers.map(s => s.id)) + 1 : 1,
        ip: ipToSave,
        name: nameToSave
      };

      // Add the server to the local state immediately for better UX
      setServers(prevServers => [...prevServers, newServer]);

      // Clear the form
      setNewIp('');
      setNewName('');
      setShowAddForm(false);

      // Try to save to the API in the background
      try {
        const response = await apiRequest('/api/augment/servers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ip: ipToSave, name: nameToSave }),
        });

        if (!response || !response.success) {
          console.warn('API call to add server failed, but UI was updated:', response?.error || 'Unknown error');
        }
      } catch (apiError) {
        console.warn('API call to add server failed, but UI was updated:', apiError);
      }
    } catch (err) {
      setError('Failed to add server. Please try again.');
      console.error('Error adding server:', err);
    }
  };

  // Function to start editing a server
  const handleEditClick = (server) => {
    setEditingServer(server.id);
    setNewIp(server.ip);
    setNewName(server.name);
  };

  // Function to save edited server
  const handleSaveEdit = async (id) => {
    setError('');

    // Validate inputs
    if (!newIp || !newName) {
      setError('Please enter both IP address and server name');
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
      const updatedServers = servers.map(server =>
        server.id === id ? { ...server, ip: ipToSave, name: nameToSave } : server
      );
      setServers(updatedServers);
      setEditingServer(null);
      setNewIp('');
      setNewName('');

      // Try to update in the API in the background
      try {
        const response = await apiRequest(`/api/augment/servers/${id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ip: ipToSave, name: nameToSave }),
        });

        if (!response || !response.success) {
          console.warn('API call to update server failed, but UI was updated:', response?.error || 'Unknown error');
        }
      } catch (apiError) {
        console.warn('API call to update server failed, but UI was updated:', apiError);
      }
    } catch (err) {
      setError('Failed to update server. Please try again.');
      console.error('Error updating server:', err);
    }
  };

  // Function to cancel editing
  const handleCancelEdit = () => {
    setEditingServer(null);
    setNewIp('');
    setNewName('');
    setError('');
  };

  // Function to show delete confirmation
  const handleDeleteClick = (id) => {
    setShowDeleteConfirm(id);
  };

  // Function to confirm server deletion
  const handleConfirmDelete = async (id) => {
    try {
      // Update the UI immediately for better UX
      const updatedServers = servers.filter(server => server.id !== id);
      setServers(updatedServers);
      setShowDeleteConfirm(null);

      // Try to delete from the API in the background
      try {
        const response = await apiRequest(`/api/augment/servers/${id}`, {
          method: 'DELETE'
        });

        if (!response || !response.success) {
          console.warn('API call to delete server failed, but UI was updated:', response?.error || 'Unknown error');
        }
      } catch (apiError) {
        console.warn('API call to delete server failed, but UI was updated:', apiError);
      }
    } catch (err) {
      setError('Failed to delete server. Please try again.');
      console.error('Error deleting server:', err);
    }
  };

  // Function to cancel deletion
  const handleCancelDelete = () => {
    setShowDeleteConfirm(null);
  };

  return (
    <div className="analytical-server-container">
      <div className="analytical-server-header">
        <h2>Analytical Server</h2>
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
          className="add-server-button"
          title={showAddForm ? "Cancel" : "Add a new analytical server"}
        >
          <img src={addIcon} alt="Add" className="button-icon" />
          {showAddForm ? "Cancel" : "Add New Server"}
        </button>
      </div>

      {showAddForm && (
        <div className="add-server-form-container">
          <h3 className="form-title">Add New Analytical Server</h3>
          <form
            className="add-server-form"
            onSubmit={(e) => {
              e.preventDefault();
              if (newIp && newName) {
                handleAddServer();
                setShowAddForm(false);
              }
            }}
          >
            <div className="form-fields-container">
              <div className="form-group">
                <label htmlFor="server-ip" className="input-label">Server IP</label>
                <input
                  id="server-ip"
                  type="text"
                  placeholder="192.168.1.100"
                  value={newIp}
                  onChange={(e) => setNewIp(e.target.value)}
                  className="server-input"
                  autoComplete="off"
                />
                <small className="input-helper-text">Enter a valid IPv4 address (e.g., 192.168.1.1)</small>
              </div>
              <div className="form-group">
                <label htmlFor="server-name" className="input-label">Server Name</label>
                <input
                  id="server-name"
                  type="text"
                  placeholder="Analytics Server 1"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="server-input"
                  autoComplete="off"
                />
              </div>
            </div>
            <div className="form-actions">
              <button
                type="submit"
                className="add-button"
                title="Add server"
                disabled={!newIp || !newName}
              >
                <img src={addIcon} alt="Add" className="button-icon" />
                Add Server
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

      <div className="server-table">
        <div className="server-table-header">
          <div className="server-column">Server IP</div>
          <div className="server-column">Server Name</div>
          <div className="server-column actions-column">Actions</div>
        </div>

        <div className="server-table-body">
          {servers.length === 0 ? (
            <div className="no-servers">No servers added yet. Click "Add New Server" to get started.</div>
          ) : (
            servers.map((server) => (
              <div key={server.id} className="server-row">
                {editingServer === server.id ? (
                  // Edit mode
                  <div className="edit-form-row">
                    <h4 className="edit-form-title">Edit Server</h4>
                    <div className="edit-form-fields">
                      <div className="edit-form-group">
                        <label htmlFor="edit-server-ip" className="edit-input-label">Server IP</label>
                        <input
                          id="edit-server-ip"
                          type="text"
                          value={newIp}
                          onChange={(e) => setNewIp(e.target.value)}
                          className="edit-input"
                          autoComplete="off"
                        />
                        <small className="input-helper-text">Enter a valid IPv4 address (e.g., 192.168.1.1)</small>
                      </div>
                      <div className="edit-form-group">
                        <label htmlFor="edit-server-name" className="edit-input-label">Server Name</label>
                        <input
                          id="edit-server-name"
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
                        onClick={() => handleSaveEdit(server.id)}
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
                    <div className="server-column">{server.ip}</div>
                    <div className="server-column">{server.name}</div>
                    <div className="server-column actions-column">
                      <button
                        className="edit-button"
                        onClick={() => handleEditClick(server)}
                        title="Edit Server"
                      >
                        <img src={editIcon} alt="Edit" />
                      </button>
                      <button
                        className="delete-button"
                        onClick={() => handleDeleteClick(server.id)}
                        title="Delete Server"
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
            <h3>Delete Analytical Server</h3>
            <p>
              Are you sure you want to delete this server? This action cannot be undone and may affect any analytics services that depend on this server.
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
                Yes, Delete Server
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalyticalServer;
