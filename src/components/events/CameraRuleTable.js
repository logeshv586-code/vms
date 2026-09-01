import React, { useState, useRef, useEffect } from 'react';
import './CameraRuleTable.css';

const CameraRuleTable = ({
  cameras,
  selectedCameras,
  onCameraSelect,
  cameraRules,
  rules,
  collections,
  enabledRules = [],
  onToggleCameraRule
}) => {
  const [selectedZone, setSelectedZone] = useState('');
  const [tooltipInfo, setTooltipInfo] = useState({ visible: false, text: '', x: 0, y: 0 });
  const tooltipTimeoutRef = useRef(null);

  // Set the first collection as default selected zone when component mounts
  useEffect(() => {
    if (collections.length > 0 && !selectedZone) {
      setSelectedZone(collections[0].id);
    }
  }, [collections, selectedZone]);

  const isSelected = (cameraId) => selectedCameras.includes(cameraId);

  const getCameraArea = (camera) => {
    const collection = collections.find(c => c.id === camera.collectionId);
    return collection ? collection.name : 'Unknown';
  };

  const getAppliedRules = (cameraId) => {
    if (!cameraRules[cameraId]) return [];
    return cameraRules[cameraId];
  };

  const isRuleApplied = (cameraId, ruleId) => {
    return getAppliedRules(cameraId).includes(ruleId);
  };

  const handleZoneChange = (e) => {
    setSelectedZone(e.target.value);
  };

  const handleRuleCheckboxChange = (cameraId, ruleId, isChecked) => {
    if (onToggleCameraRule) {
      onToggleCameraRule(cameraId, ruleId, isChecked);
    }
  };

  const showTooltip = (e, ruleName) => {
    // Clear any existing timeout
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current);
    }

    // Calculate position relative to the viewport
    const rect = e.target.getBoundingClientRect();

    setTooltipInfo({
      visible: true,
      text: ruleName,
      x: rect.left + window.scrollX,
      y: rect.bottom + window.scrollY
    });
  };

  const hideTooltip = () => {
    // Use a small delay to prevent flickering when moving between elements
    tooltipTimeoutRef.current = setTimeout(() => {
      setTooltipInfo({ ...tooltipInfo, visible: false });
    }, 100);
  };

  // Get cameras for the selected zone
  const getZoneCameras = () => {
    if (!selectedZone) return [];
    return cameras.filter(camera => camera.collectionId === selectedZone);
  };

  // Get the name of the selected zone
  const getSelectedZoneName = () => {
    if (!selectedZone) return '';
    const zone = collections.find(c => c.id === selectedZone);
    return zone ? zone.name : '';
  };

  return (
    <div className="camera-rule-table">
      <div className="zone-selector-container">
        <h3>Zone Selector</h3>
        <div className="zone-dropdown">
          <select
            className="zone-select"
            value={selectedZone}
            onChange={handleZoneChange}
          >
            {collections.map(collection => (
              <option key={collection.id} value={collection.id}>
                {collection.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {selectedZone && (
        <div className="zone-cameras-container">
          <h3>Cameras in {getSelectedZoneName()}</h3>

          {getZoneCameras().length === 0 ? (
            <div className="no-cameras">No cameras found in this zone</div>
          ) : (
            <div className="camera-rules-list">
              {getZoneCameras().map(camera => (
                <div key={camera.id} className="camera-rule-item">
                  <div className="camera-name">
                    <span>{camera.name}</span>
                  </div>
                  <div className="applied-rules">
                    <h4>Applied Rules</h4>
                    <div className="detection-checkboxes">
                      {rules.filter(rule => enabledRules.includes(rule.id)).map(rule => (
                        <div
                          key={rule.id}
                          className="detection-checkbox-container"
                        >
                          <label className="detection-checkbox-label">
                            <input
                              type="checkbox"
                              checked={isRuleApplied(camera.id, rule.id)}
                              onChange={(e) => handleRuleCheckboxChange(camera.id, rule.id, e.target.checked)}
                              className="detection-checkbox"
                            />
                            <span className="detection-name">{rule.id}. {rule.name}</span>
                          </label>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tooltip */}
      {tooltipInfo.visible && (
        <div
          className="detection-tooltip"
          style={{
            left: `${tooltipInfo.x}px`,
            top: `${tooltipInfo.y}px`
          }}
        >
          {tooltipInfo.text}
        </div>
      )}
    </div>
  );
};

export default CameraRuleTable;
