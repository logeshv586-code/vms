import React, { useState, useEffect } from 'react';
import { fetchEventRules, toggleDetectionRule } from '../../services/eventsService';
import './DetectionRuleSet.css';

const DetectionRuleSet = () => {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState('');
  const [toggleLoading, setToggleLoading] = useState({});

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetchEventRules();

      if (response.success) {
        setRules(response.data.rules);
      } else {
        setError(response.error || 'Failed to load event rules');
      }
    } catch (err) {
      setError('Error loading event rules: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleRule = async (rule) => {
    try {
      // Set loading state for this specific rule
      setToggleLoading(prev => ({ ...prev, [rule.id]: true }));
      setError(null);

      // Toggle the rule's enabled status
      const newEnabledState = !rule.enabled;

      // Call the API to update the rule
      const response = await toggleDetectionRule(rule.name, newEnabledState);

      if (response.success) {
        // Update the local state
        setRules(prevRules =>
          prevRules.map(r =>
            r.id === rule.id ? { ...r, enabled: newEnabledState } : r
          )
        );

        setSuccessMessage(`${rule.name} ${newEnabledState ? 'enabled' : 'disabled'} successfully`);
        // Clear success message after 3 seconds
        setTimeout(() => setSuccessMessage(''), 3000);
      } else {
        setError(response.error || `Failed to toggle ${rule.name}`);
      }
    } catch (err) {
      setError(`Error toggling ${rule.name}: ${err.message}`);
    } finally {
      // Clear loading state for this rule
      setToggleLoading(prev => ({ ...prev, [rule.id]: false }));
    }
  };

  if (loading && rules.length === 0) {
    return <div className="detection-rule-set-loading">Loading event rules...</div>;
  }

  if (error && rules.length === 0) {
    return <div className="detection-rule-set-error">{error}</div>;
  }

  return (
    <div className="detection-rule-set">
      <div className="detection-rule-set-header">
        <h2>Detection Rule Set</h2>
      </div>

      {successMessage && (
        <div className="success-message">{successMessage}</div>
      )}

      {error && (
        <div className="error-message">{error}</div>
      )}

      <div className="detection-rules-grid">
        {rules.map(rule => (
          <div
            key={rule.id}
            className={`detection-rule-item ${rule.enabled ? 'rule-enabled' : ''}`}
          >
            <label className="detection-rule-label">
              <input
                type="checkbox"
                checked={rule.enabled}
                onChange={() => handleToggleRule(rule)}
                disabled={toggleLoading[rule.id]}
                className="detection-rule-checkbox"
              />
              <span className="detection-rule-name">
                {toggleLoading[rule.id] ? (
                  <span className="loading-indicator">⟳</span>
                ) : null}
                {rule.name}
              </span>
            </label>
          </div>
        ))}
      </div>

      <div className="selected-rules-summary">
        <div className="selected-rules-summary-header">
          <h3>Currently Enabled Rules Summary ({rules.filter(r => r.enabled).length} Active)</h3>
        </div>
        {rules.filter(r => r.enabled).length === 0 ? (
          <div className="no-rules-enabled">
            <p>No detection rules are currently enabled globally.</p>
          </div>
        ) : (
          <div className="selected-rules-tags-container">
            {rules.filter(r => r.enabled).map(rule => (
              <div key={rule.id} className="selected-rule-tag">
                <span className="rule-tag-id">#{rule.id}</span>
                <span className="rule-tag-name">{rule.name}</span>
                <span className="rule-tag-indicator">●</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DetectionRuleSet;
