import React, { useState, useEffect } from 'react';
import { fetchEventRules, fetchCameraRules, applyCameraRules, toggleCameraRule } from '../../services/eventsService';
import { useCameraStore } from '../../store/cameraStore';
import RuleToolbar from './RuleToolbar';
import CameraRuleTable from './CameraRuleTable';
import './RulesOnCamera.css';

const RulesOnCamera = () => {
  const [rules, setRules] = useState([]);
  const [enabledRules, setEnabledRules] = useState([]);
  const [selectedRules, setSelectedRules] = useState([]);
  const [cameras, setCameras] = useState([]);
  const [selectedCameras, setSelectedCameras] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArea, setSelectedArea] = useState('All Areas');
  const { collections } = useCameraStore();
  const [cameraRules, setCameraRules] = useState({});

  // Load rules and cameras on component mount
  useEffect(() => {
    loadRulesAndCameras();
  }, []);

  const loadRulesAndCameras = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch event rules
      const rulesResponse = await fetchEventRules();
      if (!rulesResponse.success) {
        setError(rulesResponse.error || 'Failed to load event rules');
        return;
      }

      // Set rules and filter enabled ones
      const allRules = rulesResponse.data.rules;
      setRules(allRules);
      setEnabledRules(allRules.filter(rule => rule.enabled).map(rule => rule.id));

      // Get cameras from store
      const allCameras = useCameraStore.getState().cameras;
      setCameras(allCameras);

      // Fetch camera rules
      const cameraRulesResponse = await fetchCameraRules();
      if (cameraRulesResponse.success) {
        setCameraRules(cameraRulesResponse.data.cameraRules || {});
      }
    } catch (err) {
      setError('Error loading data: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRuleToggle = (ruleId) => {
    setSelectedRules(prevSelected => {
      if (prevSelected.includes(ruleId)) {
        return prevSelected.filter(id => id !== ruleId);
      } else {
        return [...prevSelected, ruleId];
      }
    });
  };

  const handleCameraSelect = (cameraId) => {
    setSelectedCameras(prevSelected => {
      if (prevSelected.includes(cameraId)) {
        return prevSelected.filter(id => id !== cameraId);
      } else {
        return [...prevSelected, cameraId];
      }
    });
  };

  const handleSelectAllCameras = (isSelected) => {
    if (isSelected) {
      const filteredCameras = getFilteredCameras().map(camera => camera.id);
      setSelectedCameras(filteredCameras);
    } else {
      setSelectedCameras([]);
    }
  };

  const handleApplyRules = async () => {
    if (selectedRules.length === 0) {
      setError('Please select at least one rule to apply');
      return;
    }

    if (selectedCameras.length === 0) {
      setError('Please select at least one camera');
      return;
    }

    // Validate that all selected rules are enabled
    const disabledRules = selectedRules.filter(ruleId => !enabledRules.includes(ruleId));
    if (disabledRules.length > 0) {
      const disabledRuleNames = disabledRules.map(ruleId => {
        const rule = rules.find(r => r.id === ruleId);
        return rule ? rule.name : `Rule ${ruleId}`;
      }).join(', ');

      setError(`Cannot apply disabled rules: ${disabledRuleNames}. Enable them in Detection Rule Set first.`);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await applyCameraRules(selectedCameras, selectedRules);

      if (response.success) {
        setSuccessMessage('Rules applied successfully to selected cameras');
        setCameraRules(response.data.cameraRules);

        // Clear selection after successful application
        setSelectedRules([]);
        setSelectedCameras([]);

        // Clear success message after 3 seconds
        setTimeout(() => setSuccessMessage(''), 3000);
      } else {
        setError(response.error || 'Failed to apply rules to cameras');
      }
    } catch (err) {
      setError('Error applying rules: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  // Handle toggling a specific rule for a specific camera
  const handleToggleCameraRule = async (cameraId, ruleId, isChecked) => {
    try {
      setLoading(true);
      setError(null);

      // Validate that the rule is enabled
      if (!enabledRules.includes(ruleId)) {
        const ruleName = rules.find(r => r.id === ruleId)?.name || `Rule ${ruleId}`;
        setError(`Cannot apply disabled rule: ${ruleName}. Enable it in Detection Rule Set first.`);
        return;
      }

      // Get current rules for this camera
      const currentRules = cameraRules[cameraId] || [];

      // Create new rules array based on the checkbox state
      let newRules;
      if (isChecked) {
        // Add the rule if it's not already there
        newRules = [...currentRules, ruleId].filter((v, i, a) => a.indexOf(v) === i);
      } else {
        // Remove the rule
        newRules = currentRules.filter(id => id !== ruleId);
      }

      // Call API to update the camera rules
      const response = await applyCameraRules([cameraId], newRules);

      if (response.success) {
        // Update local state
        setCameraRules(response.data.cameraRules);
        setSuccessMessage(`Rule ${ruleId} ${isChecked ? 'enabled' : 'disabled'} for camera`);

        // Clear success message after 3 seconds
        setTimeout(() => setSuccessMessage(''), 3000);
      } else {
        setError(response.error || 'Failed to update camera rule');
      }
    } catch (err) {
      setError('Error updating camera rule: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchChange = (e) => {
    setSearchQuery(e.target.value);
  };

  const handleAreaChange = (e) => {
    setSelectedArea(e.target.value);
  };

  const getFilteredCameras = () => {
    return cameras.filter(camera => {
      // Filter by search query
      const matchesSearch = camera.name.toLowerCase().includes(searchQuery.toLowerCase());

      // Filter by area
      const cameraCollection = collections.find(c => c.id === camera.collectionId);
      const cameraArea = cameraCollection ? cameraCollection.name : '';
      const matchesArea = selectedArea === 'All Areas' || cameraArea === selectedArea;

      return matchesSearch && matchesArea;
    });
  };

  const getAreaOptions = () => {
    const areas = ['All Areas', ...collections.map(c => c.name)];
    return areas;
  };

  if (loading && cameras.length === 0) {
    return <div className="rules-on-camera-loading">Loading data...</div>;
  }

  return (
    <div className="rules-on-camera">
      <div className="rules-on-camera-header">
        <h2>Rules on Camera</h2>
        <p>Apply detection rules to cameras by zone</p>
      </div>

      {successMessage && (
        <div className="success-message">{successMessage}</div>
      )}

      {error && (
        <div className="error-message">{error}</div>
      )}

      <div className="rules-on-camera-filters">
        <div className="search-filter">
          <input
            type="text"
            placeholder="Search Cameras"
            value={searchQuery}
            onChange={handleSearchChange}
            className="search-input"
          />
        </div>
        <div className="area-filter">
          <select
            value={selectedArea}
            onChange={handleAreaChange}
            className="area-select"
          >
            {getAreaOptions().map(area => (
              <option key={area} value={area}>{area}</option>
            ))}
          </select>
        </div>
        <div className="select-all-container">
          <label className="select-all-label">
            <input
              type="checkbox"
              checked={selectedCameras.length > 0 && selectedCameras.length === getFilteredCameras().length}
              onChange={(e) => handleSelectAllCameras(e.target.checked)}
              className="select-all-checkbox"
            />
            Select All
          </label>
        </div>
        <button
          className="filter-apply-button"
          onClick={handleApplyRules}
          disabled={loading || selectedRules.length === 0 || selectedCameras.length === 0}
        >
          Apply Rules
        </button>
      </div>

      <div className="rules-on-camera-content">
        <RuleToolbar
          rules={rules}
          enabledRules={enabledRules}
          selectedRules={selectedRules}
          onRuleToggle={handleRuleToggle}
        />

        <CameraRuleTable
          cameras={getFilteredCameras()}
          selectedCameras={selectedCameras}
          onCameraSelect={handleCameraSelect}
          cameraRules={cameraRules}
          rules={rules}
          collections={collections}
          enabledRules={enabledRules}
          onToggleCameraRule={handleToggleCameraRule}
        />
      </div>
    </div>
  );
};

export default RulesOnCamera;
