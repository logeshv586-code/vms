import React, { useEffect, useMemo, useState } from 'react';
import { applyCameraRules, fetchCameraRules, fetchEventRules } from '../../services/eventService';
import { useCameraStore } from '../../store/cameraStore';
import { enrichRule, getRulesForCamera } from '../../utils/detectionRules';
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
  const [cameraRules, setCameraRules] = useState({});
  const collections = useCameraStore(state => state.collections || []);

  const normalizeCameraRules = (raw, cameraList) => {
    const output = {};
    cameraList.forEach(camera => { output[camera.id] = getRulesForCamera(raw || {}, camera); });
    return output;
  };

  const loadRulesAndCameras = async () => {
    try {
      setLoading(true);
      setError(null);
      const allCameras = useCameraStore.getState().cameras || [];
      const [rulesResponse, cameraRulesResponse] = await Promise.all([
        fetchEventRules(),
        fetchCameraRules()
      ]);
      if (!rulesResponse?.success) throw new Error(rulesResponse?.error || 'Failed to load event rules');
      if (!cameraRulesResponse?.success) throw new Error(cameraRulesResponse?.error || 'Failed to load camera rules');

      const allRules = (rulesResponse.data?.rules || []).map(enrichRule);
      setRules(allRules);
      setEnabledRules(allRules.filter(rule => rule.enabled).map(rule => Number(rule.id)));
      setCameras(allCameras);
      setCameraRules(normalizeCameraRules(cameraRulesResponse.data?.cameraRules || {}, allCameras));
    } catch (err) {
      setError(`Error loading data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadRulesAndCameras(); }, []);

  const handleRuleToggle = ruleId => setSelectedRules(previous =>
    previous.includes(ruleId) ? previous.filter(id => id !== ruleId) : [...previous, ruleId]
  );

  const handleCameraSelect = cameraId => setSelectedCameras(previous =>
    previous.includes(cameraId) ? previous.filter(id => id !== cameraId) : [...previous, cameraId]
  );

  const filteredCameras = useMemo(() => cameras.filter(camera => {
    const matchesSearch = String(camera.name || '').toLowerCase().includes(searchQuery.toLowerCase());
    const collection = collections.find(item => item.id === camera.collectionId);
    const area = collection?.name || '';
    return matchesSearch && (selectedArea === 'All Areas' || area === selectedArea);
  }), [cameras, collections, searchQuery, selectedArea]);

  const handleSelectAllCameras = selected => {
    setSelectedCameras(selected ? filteredCameras.map(camera => camera.id) : []);
  };

  const applyRules = async ruleIds => {
    if (!selectedCameras.length) {
      setError('Select at least one camera first.');
      return;
    }
    const invalid = ruleIds.filter(ruleId => !enabledRules.includes(Number(ruleId)));
    if (invalid.length) {
      setError(`These rules are globally disabled and cannot be assigned: ${invalid.join(', ')}`);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const response = await applyCameraRules(selectedCameras, ruleIds);
      if (!response?.success) throw new Error(response?.error || 'Failed to update camera rules');
      setCameraRules(previous => {
        const next = { ...previous };
        selectedCameras.forEach(cameraId => { next[cameraId] = [...ruleIds]; });
        return next;
      });
      setSuccessMessage(ruleIds.length
        ? `Applied ${ruleIds.length} rule(s) to ${selectedCameras.length} camera(s).`
        : `All detection rules are OFF for ${selectedCameras.length} selected camera(s).`);
      setSelectedRules([]);
      setSelectedCameras([]);
      setTimeout(() => setSuccessMessage(''), 3500);
    } catch (err) {
      setError(`Error applying rules: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleCameraRule = async (cameraId, ruleId, checked) => {
    if (!enabledRules.includes(Number(ruleId))) {
      setError(`Rule ${ruleId} is globally disabled. Enable it in Detection Rule Set first.`);
      return;
    }
    const current = (cameraRules[cameraId] || []).map(Number);
    const next = checked
      ? [...new Set([...current, Number(ruleId)])]
      : current.filter(id => id !== Number(ruleId));

    // Optimistic UI gives immediate ON/OFF feedback, then rolls back on failure.
    setCameraRules(previous => ({ ...previous, [cameraId]: next }));
    try {
      const response = await applyCameraRules([cameraId], next);
      if (!response?.success) throw new Error(response?.error || 'Failed to update camera rule');
      const ruleName = rules.find(rule => Number(rule.id) === Number(ruleId))?.name || `Rule ${ruleId}`;
      setSuccessMessage(`${ruleName} is ${checked ? 'ON' : 'OFF'} for this camera.`);
      setTimeout(() => setSuccessMessage(''), 2500);
    } catch (err) {
      setCameraRules(previous => ({ ...previous, [cameraId]: current }));
      setError(`Error updating camera rule: ${err.message}`);
    }
  };

  const configuredCameras = cameras.filter(camera => (cameraRules[camera.id] || []).length > 0).length;
  const areaOptions = ['All Areas', ...collections.map(collection => collection.name)];

  if (loading && cameras.length === 0) return <div className="rules-on-camera-loading">Loading data...</div>;

  return (
    <div className="rules-on-camera">
      <div className="rules-on-camera-header">
        <h2>Rules on Camera</h2>
        <p>
          A rule is effective only when it is <strong>globally enabled</strong> and <strong>ON for the camera</strong>.
          Runtime AI can still show STANDBY/OFFLINE until that camera feed and engine are running.
        </p>
        <div style={{ marginTop: 8, color: '#64748b', fontSize: 12 }}>
          {enabledRules.length}/23 globally enabled · {configuredCameras}/{cameras.length} cameras have at least one rule
        </div>
      </div>

      {successMessage && <div className="success-message">{successMessage}</div>}
      {error && <div className="error-message">{error}</div>}

      <div className="rules-on-camera-filters">
        <div className="search-filter">
          <input type="text" placeholder="Search Cameras" value={searchQuery}
            onChange={event => setSearchQuery(event.target.value)} className="search-input" />
        </div>
        <div className="area-filter">
          <select value={selectedArea} onChange={event => setSelectedArea(event.target.value)} className="area-select">
            {areaOptions.map(area => <option key={area} value={area}>{area}</option>)}
          </select>
        </div>
        <div className="select-all-container">
          <label className="select-all-label">
            <input type="checkbox"
              checked={filteredCameras.length > 0 && selectedCameras.length === filteredCameras.length}
              onChange={event => handleSelectAllCameras(event.target.checked)} className="select-all-checkbox" />
            Select visible cameras
          </label>
        </div>
        <button className="filter-apply-button" onClick={() => applyRules(selectedRules)}
          disabled={loading || selectedRules.length === 0 || selectedCameras.length === 0}>
          Apply Selected Rules
        </button>
        <button className="filter-apply-button" style={{ background: '#64748b' }} onClick={() => applyRules([])}
          disabled={loading || selectedCameras.length === 0}>
          Turn All OFF
        </button>
      </div>

      <div className="rules-on-camera-content">
        <RuleToolbar rules={rules} enabledRules={enabledRules} selectedRules={selectedRules} onRuleToggle={handleRuleToggle} />
        <CameraRuleTable cameras={filteredCameras} selectedCameras={selectedCameras} onCameraSelect={handleCameraSelect}
          cameraRules={cameraRules} rules={rules} collections={collections} enabledRules={enabledRules}
          onToggleCameraRule={handleToggleCameraRule} />
      </div>
    </div>
  );
};

export default RulesOnCamera;
