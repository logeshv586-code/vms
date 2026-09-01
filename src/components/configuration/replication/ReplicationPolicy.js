import React, { useState, useEffect } from 'react';
import { fetchReplicationPolicies, saveReplicationSettings, mockReplicationApi } from '../../../services/replicationPolicyService';
import './ReplicationPolicy.css';

const ReplicationPolicy = () => {
  const [replicationData, setReplicationData] = useState({
    modes: [],
    groups: [],
    policies: [],
    settings: {}
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Fetch replication policy data
  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      setError(null);

      try {
        // In a real application, you would use the fetchReplicationPolicies API call
        // const data = await fetchReplicationPolicies();

        // For development without a backend, use the mock API
        const data = mockReplicationApi.getReplicationData();
        setReplicationData(data);
      } catch (err) {
        setError('Failed to load replication policy data. Please try again.');
        console.error('Error fetching replication policy data:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, []);

  // Handle checkbox toggle
  const handleToggle = (key) => {
    setReplicationData(prevData => ({
      ...prevData,
      settings: {
        ...prevData.settings,
        [key]: !prevData.settings[key]
      }
    }));
  };

  // Handle dropdown change
  const handleDropdownChange = (key, value) => {
    setReplicationData(prevData => ({
      ...prevData,
      settings: {
        ...prevData.settings,
        [key]: value
      }
    }));
  };

  // Handle save
  const handleSave = async () => {
    setIsLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      // In a real application, you would use the saveReplicationSettings API call
      // await saveReplicationSettings(replicationData.settings);

      // For development without a backend, use the mock API
      mockReplicationApi.saveReplicationData(replicationData);
      
      setSuccessMessage('Replication policy settings saved successfully.');
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        setSuccessMessage(null);
      }, 3000);
    } catch (err) {
      setError('Failed to save replication policy settings. Please try again.');
      console.error('Error saving replication policy settings:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="replication-policy-card">
      <h2 className="replication-policy-title">Replication Policy</h2>

      {/* Error Message */}
      {error && (
        <div className="replication-error-message">
          {error}
          <button
            className="replication-error-dismiss"
            onClick={() => setError(null)}
          >
            ✕
          </button>
        </div>
      )}

      {/* Success Message */}
      {successMessage && (
        <div className="replication-success-message">
          {successMessage}
          <button
            className="replication-success-dismiss"
            onClick={() => setSuccessMessage(null)}
          >
            ✕
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="replication-loading">
          <div className="replication-loading-spinner"></div>
          Loading replication policy data...
        </div>
      ) : (
        <div className="replication-policy-content">
          {/* Mode Selector */}
          <div className="replication-mode-selector">
            <select 
              value={replicationData.settings.mode || ''}
              onChange={(e) => handleDropdownChange('mode', e.target.value)}
              className="replication-mode-dropdown"
            >
              {replicationData.modes.map((mode) => (
                <option key={mode} value={mode}>{mode}</option>
              ))}
            </select>
            <button className="replication-info-button" title="Replication Mode Information">
              ⓘ
            </button>
          </div>

          {/* Policy Table */}
          <div className="replication-policy-table">
            <div className="replication-policy-header">
            <span style={{ color: 'white' }}>Replication Policy</span>
            </div>
            
            {replicationData.policies.map((policy) => (
              <div key={policy.key} className="replication-policy-row">
                <div className="replication-policy-checkbox">
                  <input
                    type="checkbox"
                    id={policy.key}
                    checked={!!replicationData.settings[policy.key]}
                    onChange={() => handleToggle(policy.key)}
                  />
                  <label htmlFor={policy.key}>{policy.label}</label>
                </div>
                
                {policy.hasDropdown && (
                  <div className="replication-policy-dropdowns">
                    <select
                      value={replicationData.settings[`${policy.key}_target`] || ''}
                      onChange={(e) => handleDropdownChange(`${policy.key}_target`, e.target.value)}
                      className="replication-target-dropdown"
                    >
                      {replicationData.groups.map((group) => (
                        <option key={group} value={group}>{group}</option>
                      ))}
                    </select>
                    
                    {policy.key === 'eventFetch' && (
                      <select
                        value={replicationData.settings[`${policy.key}_secondary`] || ''}
                        onChange={(e) => handleDropdownChange(`${policy.key}_secondary`, e.target.value)}
                        className="replication-target-dropdown"
                      >
                        {replicationData.groups.map((group) => (
                          <option key={group} value={group}>{group}</option>
                        ))}
                      </select>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Save Button */}
          <div className="replication-save-container">
            <button
              className="replication-save-button"
              onClick={handleSave}
              disabled={isLoading}
            >
              {isLoading ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReplicationPolicy;
