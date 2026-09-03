import React, { useEffect, useMemo, useState } from 'react';
import { fetchCameraRules, fetchEventRules } from '../../services/eventService';
import { useCameraStore } from '../../store/cameraStore';
import { enrichRule, getRulesForCamera } from '../../utils/detectionRules';

const LiveMonitoringRules = () => {
  const cameras = useCameraStore(state => state.cameras || []);
  const [rules, setRules] = useState([]);
  const [cameraRules, setCameraRules] = useState({});
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true); setError('');
    try {
      const [rulesResponse, cameraResponse] = await Promise.all([fetchEventRules(), fetchCameraRules()]);
      if (!rulesResponse?.success) throw new Error(rulesResponse?.error || 'Unable to load global rules');
      if (!cameraResponse?.success) throw new Error(cameraResponse?.error || 'Unable to load camera rules');
      setRules((rulesResponse.data?.rules || []).map(enrichRule));
      setCameraRules(cameraResponse.data?.cameraRules || {});
    } catch (err) {
      setError(err.message || 'Unable to load live monitoring configuration');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const globallyEnabled = useMemo(
    () => new Set(rules.filter(rule => rule.enabled).map(rule => Number(rule.id))),
    [rules]
  );

  return (
    <div className="ptz-page">
      <div className="ptz-header">
        <div>
          <h2>Live Monitoring Rules</h2>
          <p>This is the effective-rule audit view. A rule can run on a camera only when both conditions are true: the rule is globally enabled and it is assigned to that camera.</p>
        </div>
        <span className="ptz-status ready">{globallyEnabled.size}/23 SYSTEM ENABLED</span>
      </div>

      <div className="ptz-workflow">
        <div className="ptz-step"><strong>System Enabled</strong><span>Controlled from Detection Rule Set. Disabled here means unavailable everywhere.</span></div>
        <div className="ptz-step"><strong>Camera ON</strong><span>Controlled from Rules On Camera or AI Detection for one camera.</span></div>
        <div className="ptz-step"><strong>Effective</strong><span>System Enabled + Camera ON. Only this intersection reaches PatternEngine.</span></div>
        <div className="ptz-step"><strong>Detecting</strong><span>Runtime state. Requires a working stream and AI engine in addition to effective rules.</span></div>
      </div>

      {error && <div className="ptz-message error">{error} <button onClick={load}>Retry</button></div>}
      {loading ? <div className="loading-state">Checking live monitoring rules…</div> : (
        <div className="ptz-card">
          <h3>Effective Rules by Camera</h3>
          <p className="ptz-card-note">Use this table when you want to confirm “what is ON for this camera?” without opening every camera individually.</p>
          <div className="events-table-wrapper">
            <table className="events-table">
              <thead><tr><th>Camera</th><th>Assigned</th><th>Effective</th><th>Effective Rule Names</th></tr></thead>
              <tbody>
                {cameras.map(camera => {
                  const assigned = getRulesForCamera(cameraRules, camera);
                  const effective = assigned.filter(id => globallyEnabled.has(Number(id)));
                  const names = effective.map(id => rules.find(rule => Number(rule.id) === Number(id))?.name || `Rule ${id}`);
                  return (
                    <tr key={camera.id}>
                      <td>{camera.name}</td>
                      <td>{assigned.length}</td>
                      <td><span className={`status-badge ${effective.length ? 'active' : 'resolved'}`}>{effective.length} ON</span></td>
                      <td>{names.length ? names.join(', ') : 'No effective rules'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default LiveMonitoringRules;
