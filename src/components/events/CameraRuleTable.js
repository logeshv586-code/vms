import React, { useEffect, useState } from 'react';
import { getRuleMeta } from '../../utils/detectionRules';
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

  useEffect(() => {
    if (collections.length > 0 && !selectedZone) setSelectedZone(collections[0].id);
    if (selectedZone && !collections.some(collection => collection.id === selectedZone)) {
      setSelectedZone(collections[0]?.id || '');
    }
  }, [collections, selectedZone]);

  const getAppliedRules = cameraId => Array.isArray(cameraRules[cameraId]) ? cameraRules[cameraId].map(Number) : [];
  const isRuleApplied = (cameraId, ruleId) => getAppliedRules(cameraId).includes(Number(ruleId));
  const zoneCameras = selectedZone ? cameras.filter(camera => camera.collectionId === selectedZone) : [];
  const selectedZoneName = collections.find(collection => collection.id === selectedZone)?.name || '';
  const enabledRuleObjects = rules.filter(rule => enabledRules.includes(Number(rule.id)));

  return (
    <div className="camera-rule-table">
      <div className="zone-selector-container">
        <div>
          <h3>Camera Group / Zone</h3>
          <p>Select a camera, then switch each globally enabled rule ON or OFF for that camera.</p>
        </div>
        <select className="zone-select" value={selectedZone} onChange={event => setSelectedZone(event.target.value)}>
          {collections.map(collection => <option key={collection.id} value={collection.id}>{collection.name}</option>)}
        </select>
      </div>

      {selectedZone && (
        <div className="zone-cameras-container">
          <div className="zone-camera-heading">
            <h3>Cameras in {selectedZoneName}</h3>
            <span>{zoneCameras.length} camera{zoneCameras.length === 1 ? '' : 's'}</span>
          </div>

          {zoneCameras.length === 0 ? (
            <div className="no-cameras">No cameras found in this group.</div>
          ) : (
            <div className="camera-rules-list">
              {zoneCameras.map(camera => {
                const activeCount = getAppliedRules(camera.id).filter(id => enabledRules.includes(Number(id))).length;
                return (
                  <div key={camera.id} className={`camera-rule-item ${selectedCameras.includes(camera.id) ? 'camera-selected' : ''}`}>
                    <div className="camera-rule-heading">
                      <label className="camera-select-label">
                        <input type="checkbox" checked={selectedCameras.includes(camera.id)}
                          onChange={() => onCameraSelect(camera.id)} />
                        <span>{camera.name}</span>
                      </label>
                      <span className={`camera-active-count ${activeCount ? 'has-rules' : ''}`}>
                        {activeCount}/{enabledRuleObjects.length} ON
                      </span>
                    </div>

                    <div className="detection-checkboxes">
                      {enabledRuleObjects.map(rule => {
                        const active = isRuleApplied(camera.id, rule.id);
                        const color = getRuleMeta(Number(rule.id))?.color || '#64748b';
                        return (
                          <label key={rule.id} className={`detection-checkbox-label ${active ? 'rule-on' : 'rule-off'}`}
                            style={active ? { '--camera-rule-color': color } : undefined}>
                            <input type="checkbox" checked={active}
                              onChange={event => onToggleCameraRule?.(camera.id, Number(rule.id), event.target.checked)}
                              className="detection-checkbox" />
                            <span className="detection-name">{rule.id}. {rule.name}</span>
                            <span className="camera-rule-state">{active ? 'ON' : 'OFF'}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default CameraRuleTable;
