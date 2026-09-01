import React, { useState, useEffect } from 'react';
import { fetchStorageEntries, toggleStorageStatus, addStorageEntry, deleteStorageEntry, mockStorageApi } from '../../../services/storageService';
import './StorageManager.css';

const StorageManager = () => {
  const [selectedType, setSelectedType] = useState('network'); // 'master' or 'network'
  const [storageData, setStorageData] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [currentStorage, setCurrentStorage] = useState(null);

  // Fetch storage data when type changes
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // In a real application, you would use the fetchStorageEntries API call
        // const data = await fetchStorageEntries(selectedType);

        // For development without a backend, use the mock API
        const data = selectedType === 'master'
          ? mockStorageApi.getMasterStorage()
          : mockStorageApi.getNetworkStorage();

        setStorageData(data);
      } catch (err) {
        setError('Failed to load storage data. Please try again.');
        console.error('Error fetching storage data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [selectedType]);

  // Toggle storage enabled/disabled status
  const toggleStorage = async (storageId, enabled) => {
    try {
      setIsLoading(true);

      // Update the local state
      const updatedData = storageData.map(item =>
        item.id === storageId ? { ...item, enabled } : item
      );
      
      setStorageData(updatedData);
      
      // Persist the changes
      if (selectedType === 'master') {
        mockStorageApi.saveMasterStorage(updatedData);
      } else {
        mockStorageApi.saveNetworkStorage(updatedData);
      }

      console.log(`Storage ${storageId} ${enabled ? 'enabled' : 'disabled'} successfully`);
    } catch (err) {
      setError(`Failed to ${enabled ? 'enable' : 'disable'} storage. Please try again.`);
      console.error('Error toggling storage status:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Add new storage entry
  const handleAddStorage = async (newStorageData) => {
    try {
      setIsLoading(true);

      const newId = `${selectedType[0]}${Date.now()}`;
      const addedStorage = {
        id: newId,
        ...newStorageData,
        enabled: true
      };

      const updatedData = [...storageData, addedStorage];
      setStorageData(updatedData);
      
      // Persist the changes
      if (selectedType === 'master') {
        mockStorageApi.saveMasterStorage(updatedData);
      } else {
        mockStorageApi.saveNetworkStorage(updatedData);
      }
      
      setIsAddModalOpen(false);
      console.log('New storage added successfully:', addedStorage);
    } catch (err) {
      setError('Failed to add new storage. Please try again.');
      console.error('Error adding storage:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Edit existing storage entry
  const handleEditStorage = async (updatedStorageData) => {
    try {
      setIsLoading(true);

      const updatedData = storageData.map(item =>
        item.id === currentStorage.id ? { ...item, ...updatedStorageData } : item
      );
      
      setStorageData(updatedData);
      
      // Persist the changes
      if (selectedType === 'master') {
        mockStorageApi.saveMasterStorage(updatedData);
      } else {
        mockStorageApi.saveNetworkStorage(updatedData);
      }

      setIsEditModalOpen(false);
      setCurrentStorage(null);
      console.log('Storage updated successfully:', updatedStorageData);
    } catch (err) {
      setError('Failed to update storage. Please try again.');
      console.error('Error updating storage:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Delete storage entry
  const handleDeleteStorage = async () => {
    try {
      setIsLoading(true);

      const updatedData = storageData.filter(item => item.id !== currentStorage.id);
      setStorageData(updatedData);
      
      // Persist the changes
      if (selectedType === 'master') {
        mockStorageApi.saveMasterStorage(updatedData);
      } else {
        mockStorageApi.saveNetworkStorage(updatedData);
      }

      setIsDeleteConfirmOpen(false);
      setCurrentStorage(null);
      console.log('Storage deleted successfully:', currentStorage.id);
    } catch (err) {
      setError('Failed to delete storage. Please try again.');
      console.error('Error deleting storage:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Open edit modal with current storage data
  const openEditModal = (storage) => {
    setCurrentStorage(storage);
    setIsEditModalOpen(true);
  };

  // Open delete confirmation with current storage
  const openDeleteConfirm = (storage) => {
    setCurrentStorage(storage);
    setIsDeleteConfirmOpen(true);
  };

  return (
    <div className="storage-manager-card">
      <h2 className="storage-manager-title">Storage Manager</h2>
      {/* Toggle Select Type */}
      <div className="storage-type-toggle">
        <label className="storage-type-label">
          <input
            type="radio"
            value="master"
            checked={selectedType === 'master'}
            onChange={() => setSelectedType('master')}
            className="storage-type-radio"
          />
          <span className="storage-type-text">Master Server Storage (Events)</span>
        </label>
        <label className="storage-type-label">
          <input
            type="radio"
            value="network"
            checked={selectedType === 'network'}
            onChange={() => setSelectedType('network')}
            className="storage-type-radio"
          />
          <span className="storage-type-text">Network Storage Configuration</span>
        </label>
      </div>

      {/* Error Message */}
      {error && (
        <div className="storage-error-message">
          {error}
          <button
            className="storage-error-dismiss"
            onClick={() => setError(null)}
          >
            ✕
          </button>
        </div>
      )}

      {/* Table */}
      <div className="storage-table-container">
        <table className="storage-table">
          <thead className="storage-table-header">
            <tr>
              <th className="storage-table-cell">Storage Class</th>
              <th className="storage-table-cell">Drive/Bucket</th>
              <th className="storage-table-cell">Capacity</th>
              <th className="storage-table-cell">Free</th>
              {selectedType === 'network' && <th className="storage-table-cell">Username</th>}
              <th className="storage-table-cell">Storage Type</th>
              <th className="storage-table-cell">Status</th>
              <th className="storage-table-cell">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={selectedType === 'network' ? 8 : 7} className="storage-table-loading">
                  <div className="storage-loading-spinner"></div>
                  Loading storage data...
                </td>
              </tr>
            ) : storageData.length === 0 ? (
              <tr>
                <td colSpan={selectedType === 'network' ? 8 : 7} className="storage-table-empty">
                  No storage entries found.
                </td>
              </tr>
            ) : (
              storageData.map((item) => (
                <tr key={item.id} className="storage-table-row">
                  <td className="storage-table-cell">{item.storageClass}</td>
                  <td className="storage-table-cell">{item.path}</td>
                  <td className="storage-table-cell">{item.capacity}</td>
                  <td className="storage-table-cell">{item.free}</td>
                  {selectedType === 'network' && <td className="storage-table-cell">{item.username || '-'}</td>}
                  <td className="storage-table-cell">{item.storageType}</td>
                  <td className="storage-table-cell">
                    <button
                      className={`storage-action-button ${item.enabled ? 'storage-disable-button' : 'storage-enable-button'}`}
                      onClick={() => toggleStorage(item.id, !item.enabled)}
                      disabled={isLoading}
                    >
                      {item.enabled ? 'Disable' : 'Enable'}
                    </button>
                  </td>
                  <td className="storage-table-cell storage-action-cell">
                    <div className="storage-action-buttons">
                      <button
                        className="storage-edit-button"
                        onClick={() => openEditModal(item)}
                        disabled={isLoading}
                        title="Edit storage"
                      >
                        <span className="storage-icon">✎</span>
                      </button>
                      <button
                        className="storage-delete-button"
                        onClick={() => openDeleteConfirm(item)}
                        disabled={isLoading}
                        title="Delete storage"
                      >
                        <span className="storage-icon">✕</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add New Button - Allow adding for both master and network storage */}
      <div className="storage-add-button-container">
        <button
          className="storage-add-button"
          onClick={() => setIsAddModalOpen(true)}
          disabled={isLoading}
        >
          Add New {selectedType === 'master' ? 'Master' : 'Network'} Storage
        </button>
      </div>

      {/* Add Storage Modal */}
      {isAddModalOpen && (
        <div className="storage-modal-overlay" onClick={() => setIsAddModalOpen(false)}>
          <div className="storage-modal" onClick={e => e.stopPropagation()}>
            <h3 className="storage-modal-title">Add New Network Storage</h3>
            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
              const newStorage = {
                storageClass: formData.get('storageClass'),
                path: formData.get('path'),
                capacity: formData.get('capacity'),
                free: formData.get('free'),
                username: formData.get('username'),
                storageType: formData.get('storageType')
              };
              handleAddStorage(newStorage);
            }}>
              <div className="storage-form-group">
                <label htmlFor="storageClass">Storage Class</label>
                <input type="text" id="storageClass" name="storageClass" required />
              </div>
              <div className="storage-form-group">
                <label htmlFor="path">Drive/Bucket Path</label>
                <input type="text" id="path" name="path" required />
              </div>
              <div className="storage-form-group">
                <label htmlFor="capacity">Capacity</label>
                <input type="text" id="capacity" name="capacity" required />
              </div>
              <div className="storage-form-group">
                <label htmlFor="free">Free Space</label>
                <input type="text" id="free" name="free" required />
              </div>
              <div className="storage-form-group">
                <label htmlFor="username">Username</label>
                <input type="text" id="username" name="username" />
              </div>
              <div className="storage-form-group">
                <label htmlFor="storageType">Storage Type</label>
                <select id="storageType" name="storageType" required>
                  <option value="Network Share">Network Share</option>
                  <option value="S3 Bucket">S3 Bucket</option>
                  <option value="FTP Server">FTP Server</option>
                  <option value="Cloud Storage">Cloud Storage</option>
                </select>
              </div>
              <div className="storage-modal-actions">
                <button type="button" className="storage-modal-cancel" onClick={() => setIsAddModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="storage-modal-submit" disabled={isLoading}>
                  {isLoading ? 'Adding...' : 'Add Storage'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Storage Modal */}
      {isEditModalOpen && currentStorage && (
        <div className="storage-modal-overlay" onClick={() => setIsEditModalOpen(false)}>
          <div className="storage-modal" onClick={e => e.stopPropagation()}>
            <h3 className="storage-modal-title">Edit Storage</h3>
            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
              const updatedStorage = {
                storageClass: formData.get('storageClass'),
                path: formData.get('path'),
                capacity: formData.get('capacity'),
                free: formData.get('free'),
                username: formData.get('username'),
                storageType: formData.get('storageType')
              };
              handleEditStorage(updatedStorage);
            }}>
              <div className="storage-form-group">
                <label htmlFor="edit-storageClass">Storage Class</label>
                <input
                  type="text"
                  id="edit-storageClass"
                  name="storageClass"
                  defaultValue={currentStorage.storageClass}
                  required
                />
              </div>
              <div className="storage-form-group">
                <label htmlFor="edit-path">Drive/Bucket Path</label>
                <input
                  type="text"
                  id="edit-path"
                  name="path"
                  defaultValue={currentStorage.path}
                  required
                />
              </div>
              <div className="storage-form-group">
                <label htmlFor="edit-capacity">Capacity</label>
                <input
                  type="text"
                  id="edit-capacity"
                  name="capacity"
                  defaultValue={currentStorage.capacity}
                  required
                />
              </div>
              <div className="storage-form-group">
                <label htmlFor="edit-free">Free Space</label>
                <input
                  type="text"
                  id="edit-free"
                  name="free"
                  defaultValue={currentStorage.free}
                  required
                />
              </div>
              {selectedType === 'network' && (
                <div className="storage-form-group">
                  <label htmlFor="edit-username">Username</label>
                  <input
                    type="text"
                    id="edit-username"
                    name="username"
                    defaultValue={currentStorage.username || ''}
                  />
                </div>
              )}
              <div className="storage-form-group">
                <label htmlFor="edit-storageType">Storage Type</label>
                <select
                  id="edit-storageType"
                  name="storageType"
                  defaultValue={currentStorage.storageType}
                  required
                >
                  <option value="Local Disk">Local Disk</option>
                  <option value="Network Share">Network Share</option>
                  <option value="S3 Bucket">S3 Bucket</option>
                  <option value="FTP Server">FTP Server</option>
                  <option value="Cloud Storage">Cloud Storage</option>
                </select>
              </div>
              <div className="storage-modal-actions">
                <button type="button" className="storage-modal-cancel" onClick={() => setIsEditModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="storage-modal-submit" disabled={isLoading}>
                  {isLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {isDeleteConfirmOpen && currentStorage && (
        <div className="storage-modal-overlay" onClick={() => setIsDeleteConfirmOpen(false)}>
          <div className="storage-confirm-dialog" onClick={e => e.stopPropagation()}>
            <h3 className="storage-confirm-title">Confirm Deletion</h3>
            <p className="storage-confirm-message">
              Are you sure you want to delete the storage <strong>{currentStorage.storageClass}</strong> ({currentStorage.path})?
            </p>
            <p className="storage-confirm-warning">
              This action cannot be undone.
            </p>
            <div className="storage-modal-actions">
              <button
                className="storage-modal-cancel"
                onClick={() => setIsDeleteConfirmOpen(false)}
                disabled={isLoading}
              >
                Cancel
              </button>
              <button
                className="storage-delete-confirm-button"
                onClick={handleDeleteStorage}
                disabled={isLoading}
              >
                {isLoading ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StorageManager;


