// API service for storage management
import { API_BASE_URL } from '../utils/apiConfig';
import { apiRequest, getApiUrl } from '../utils/api';

// Fetch storage entries based on type (master or network)
export const fetchStorageEntries = async (storageType) => {
  try {
    return await apiRequest(`/storage/${storageType}`);
  } catch (error) {
    console.error('Failed to fetch storage entries:', error);
    throw error;
  }
};

// Toggle storage entry status (enable/disable)
export const toggleStorageStatus = async (storageId, enabled) => {
  try {
    return await apiRequest(`/storage/${storageId}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ enabled }),
    });
  } catch (error) {
    console.error('Failed to update storage status:', error);
    throw error;
  }
};

// Add new storage entry
export const addStorageEntry = async (storageData) => {
  try {
    return await apiRequest(`/storage`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(storageData),
    });
  } catch (error) {
    console.error('Failed to add storage entry:', error);
    throw error;
  }
};

// Delete storage entry
export const deleteStorageEntry = async (storageId) => {
  try {
    return await apiRequest(`/storage/${storageId}`, {
      method: 'DELETE',
    });
  } catch (error) {
    console.error('Failed to delete storage entry:', error);
    throw error;
  }
};

// Replace the mock API implementation with persistent storage
export const mockStorageApi = {
  // Use localStorage to persist storage data
  getMasterStorage: () => {
    const stored = localStorage.getItem('vms_master_storage');
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch (error) {
        console.error('Error parsing master storage data:', error);
        // If parsing fails, return initial data
      }
    }

    // Initial data only shown first time
    const initial = [
      {
        id: 'm1',
        storageClass: 'Primary',
        path: 'C:\\VMS\\Storage',
        capacity: '500 GB',
        free: '250 GB',
        storageType: 'Local Disk',
        enabled: true
      },
      {
        id: 'm2',
        storageClass: 'Secondary',
        path: 'D:\\VMS\\Backup',
        capacity: '1 TB',
        free: '750 GB',
        storageType: 'Local Disk',
        enabled: false
      }
    ];
    localStorage.setItem('vms_master_storage', JSON.stringify(initial));
    return initial;
  },

  getNetworkStorage: () => {
    const stored = localStorage.getItem('vms_network_storage');
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch (error) {
        console.error('Error parsing network storage data:', error);
        // If parsing fails, return initial data
      }
    }

    // Initial data only shown first time
    const initial = [
      {
        id: 'n1',
        storageClass: 'Remote',
        path: '\\\\server\\share',
        capacity: '2 TB',
        free: '1.5 TB',
        username: 'admin',
        storageType: 'Network Share',
        enabled: true
      },
      {
        id: 'n2',
        storageClass: 'Cloud',
        path: 's3://vms-bucket',
        capacity: '5 TB',
        free: '4.8 TB',
        username: 'cloud-user',
        storageType: 'S3 Bucket',
        enabled: false
      }
    ];
    localStorage.setItem('vms_network_storage', JSON.stringify(initial));
    return initial;
  },

  // Add methods to save changes
  saveMasterStorage: (data) => {
    localStorage.setItem('vms_master_storage', JSON.stringify(data));
  },

  saveNetworkStorage: (data) => {
    localStorage.setItem('vms_network_storage', JSON.stringify(data));
  }
};