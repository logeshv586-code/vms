// API service for replication policy management
import { API_BASE_URL } from '../utils/apiConfig';
import { apiRequest, getApiUrl } from '../utils/api';

// Fetch replication policy data
export const fetchReplicationPolicies = async () => {
  try {
    return await apiRequest(`/api/augment/replication-policy`);
  } catch (error) {
    console.error('Failed to fetch replication policies:', error);
    throw error;
  }
};

// Save replication policy settings
export const saveReplicationSettings = async (settings) => {
  try {
    return await apiRequest(`/api/augment/replication-policy`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(settings),
    });
  } catch (error) {
    console.error('Failed to save replication settings:', error);
    throw error;
  }
};

// Mock API implementation for development without backend
export const mockReplicationApi = {
  // Get replication policy data
  getReplicationData: () => {
    const stored = localStorage.getItem('vms_replication_policy');
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch (error) {
        console.error('Error parsing replication policy data:', error);
        // If parsing fails, return initial data
      }
    }

    // Initial data only shown first time
    const initial = {
      modes: ["Full data safekeeping", "Custom"],
      groups: ["DR Backup", "Mobile Snatching", "Other"],
      policies: [
        { key: "archiveFetch", label: "Archive Fetch", hasDropdown: true },
        { key: "markedClipFetch", label: "Marked Clip Fetch", hasDropdown: true },
        { key: "eventFetch", label: "Event Fetch", hasDropdown: true },
        { key: "eventSnapFetch", label: "Event Snap Fetch", hasDropdown: false },
        { key: "eventClipFetch", label: "Event Clip Fetch", hasDropdown: false },
        { key: "systemConfigFetch", label: "System Configuration Fetch", hasDropdown: false },
        { key: "auditTrailFetch", label: "Audit Trail Fetch", hasDropdown: false }
      ],
      settings: {
        mode: "Full data safekeeping",
        archiveFetch: true,
        archiveFetch_target: "DR Backup",
        markedClipFetch: true,
        markedClipFetch_target: "DR Backup",
        eventFetch: true,
        eventFetch_target: "DR Backup",
        eventSnapFetch: true,
        eventClipFetch: true,
        systemConfigFetch: true,
        auditTrailFetch: true
      }
    };
    
    localStorage.setItem('vms_replication_policy', JSON.stringify(initial));
    return initial;
  },

  // Save replication policy data
  saveReplicationData: (data) => {
    localStorage.setItem('vms_replication_policy', JSON.stringify(data));
  }
};