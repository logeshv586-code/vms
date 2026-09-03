import React, { useEffect, useMemo, useState } from 'react';
import { useCameraStore } from '../../store/cameraStore';
import {
  getPtzConfig,
  probePtzCapabilities,
  savePtzTour,
  startPtzTour,
  stopPtzTour
} from '../../services/ptzService';
import './PTZControl.css';

const DEFAULT_TOUR = {
  enabled: false,
  onvif_port: 80,
  presets: [],
  loop: true,
  return_to_first: true
};

const PTZAutoTour = () => {
  const cameras = useCameraStore(state => state.cameras || []);
  const [cameraId, setCameraId] = useState(cameras[0]?.id || '');
  const [config, setConfig] = useState(DEFAULT_TOUR);
  const [capabilities, setCapabilities] = useState(null);
  const [runtime, setRuntime] = useState({ tour_running: false });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!cameraId && cameras.length) setCameraId(cameras[0].id);
  }, [cameras, cameraId]);

  useEffect(() => {
    if (!cameraId) return;
    setCapabilities(null);
    setMessage('');
    setError('');
    getPtzConfig(cameraId)
      .then(response => {
        if (response?.success) {
          setConfig({ ...DEFAULT_TOUR, ...(response.data?.tour || {}) });
          setRuntime(response.data?.runtime || { tour_running: false });
        }
      })
      .catch(err => setError(err.message || 'Unable to load PTZ configuration'));
  }, [cameraId]);

  const selectedTokens = useMemo(
    () => new Set((config.presets || []).map(item => String(item.token))),
    [config.presets]
  );

  const probe = async () => {
    if (!cameraId) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await probePtzCapabilities(cameraId, config.onvif_port);
      const data = response?.data || {};
      setCapabilities(data);
      if (data.verified) setMessage(`PTZ verified. ${data.presets?.length || 0} ONVIF presets found.`);
      else setError(data.reason || 'This camera did not verify ONVIF PTZ support.');
    } catch (err) {
      setError(err.message || 'PTZ capability test failed');
    } finally {
      setBusy(false);
    }
  };

  const togglePreset = (preset) => {
    const token = String(preset.token);
    setConfig(previous => {
      const exists = (previous.presets || []).some(item => String(item.token) === token);
      return {
        ...previous,
        presets: exists
          ? previous.presets.filter(item => String(item.token) !== token)
          : [...previous.presets, { token, name: preset.name || 'Preset', dwell_seconds: 5 }]
      };
    });
  };

  const setDwell = (token, value) => {
    const dwell = Math.max(1, Math.min(300, Number(value) || 5));
    setConfig(previous => ({
      ...previous,
      presets: previous.presets.map(item => String(item.token) === String(token)
        ? { ...item, dwell_seconds: dwell }
        : item)
    }));
  };

  const save = async () => {
    if (!cameraId) return;
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await savePtzTour(cameraId, {
        ...config,
        onvif_port: Number(config.onvif_port) || 80
      });
      if (!response?.success) throw new Error(response?.error || 'Unable to save Auto Tour');
      setMessage('Auto Tour configuration saved.');
    } catch (err) {
      setError(err.message || 'Unable to save Auto Tour');
    } finally { setBusy(false); }
  };

  const start = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      await savePtzTour(cameraId, { ...config, enabled: true, onvif_port: Number(config.onvif_port) || 80 });
      const response = await startPtzTour(cameraId);
      if (!response?.success) throw new Error(response?.error || 'Unable to start Auto Tour');
      setConfig(previous => ({ ...previous, enabled: true }));
      setRuntime(previous => ({ ...previous, tour_running: true }));
      setMessage(response.message || 'Auto Tour started.');
    } catch (err) {
      setError(err.message || 'Unable to start Auto Tour');
    } finally { setBusy(false); }
  };

  const stop = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await stopPtzTour(cameraId);
      if (!response?.success) throw new Error(response?.error || 'Unable to stop Auto Tour');
      setRuntime(previous => ({ ...previous, tour_running: false }));
      setMessage(response.message || 'Auto Tour stopped.');
    } catch (err) {
      setError(err.message || 'Unable to stop Auto Tour');
    } finally { setBusy(false); }
  };

  const statusClass = runtime.tour_running ? 'running' : capabilities?.verified ? 'ready' : capabilities && !capabilities.verified ? 'error' : '';
  const statusText = runtime.tour_running ? '● TOUR RUNNING' : capabilities?.verified ? '✓ PTZ VERIFIED' : capabilities ? 'PTZ NOT VERIFIED' : 'PTZ NOT TESTED';

  return (
    <div className="ptz-page">
      <div className="ptz-header">
        <div>
          <h2>PTZ Auto Tour</h2>
          <p>Auto Tour moves a PTZ camera through its saved ONVIF presets on a schedule. It does not use AI tracking; it is a repeatable patrol path.</p>
        </div>
        <span className={`ptz-status ${statusClass}`}>{statusText}</span>
      </div>

      <div className="ptz-workflow">
        <div className="ptz-step"><strong>1 · Select Camera</strong><span>Choose a camera that physically supports PTZ and ONVIF.</span></div>
        <div className="ptz-step"><strong>2 · Verify ONVIF</strong><span>The backend connects to the camera and loads its real saved presets.</span></div>
        <div className="ptz-step"><strong>3 · Build Patrol</strong><span>Select presets and decide how many seconds to remain at each position.</span></div>
        <div className="ptz-step"><strong>4 · Start Tour</strong><span>The server cycles through the selected positions until you stop it.</span></div>
      </div>

      {message && <div className="ptz-message">{message}</div>}
      {error && <div className="ptz-message error">{error}</div>}

      <div className="ptz-grid">
        <div className="ptz-card">
          <h3>Camera & ONVIF</h3>
          <div className="ptz-field">
            <label>PTZ Camera</label>
            <select value={cameraId} onChange={event => setCameraId(event.target.value)}>
              {!cameras.length && <option value="">No cameras configured</option>}
              {cameras.map(camera => <option key={camera.id} value={camera.id}>{camera.name}</option>)}
            </select>
          </div>
          <div className="ptz-field">
            <label>ONVIF Port</label>
            <input type="number" min="1" max="65535" value={config.onvif_port}
              onChange={event => setConfig(previous => ({ ...previous, onvif_port: Number(event.target.value) }))} />
          </div>
          <label className="ptz-check"><input type="checkbox" checked={config.loop}
            onChange={event => setConfig(previous => ({ ...previous, loop: event.target.checked }))} />Loop continuously</label>
          <label className="ptz-check"><input type="checkbox" checked={config.return_to_first}
            onChange={event => setConfig(previous => ({ ...previous, return_to_first: event.target.checked }))} />Return to first preset when tour finishes</label>

          <div className="ptz-actions">
            <button className="ptz-btn primary" disabled={!cameraId || busy} onClick={probe}>Test PTZ & Load Presets</button>
            <button className="ptz-btn" disabled={!cameraId || busy} onClick={save}>Save</button>
          </div>

          <div className="ptz-explainer">
            <strong>Where do presets come from?</strong>
            <p>Presets are positions already stored inside the camera, usually created in the camera/NVR web interface. VMS reads those positions through ONVIF; it does not invent coordinates.</p>
          </div>
        </div>

        <div className="ptz-card">
          <h3>Patrol Presets</h3>
          <p className="ptz-card-note">First click “Test PTZ & Load Presets”. Then select the positions to include and set the dwell time for each one.</p>

          {!capabilities?.verified ? (
            <div className="ptz-message warning">PTZ hardware has not been verified yet. No tour will start until the ONVIF test succeeds.</div>
          ) : !(capabilities.presets || []).length ? (
            <div className="ptz-message warning">The camera supports ONVIF PTZ but returned no saved presets. Create presets in the camera/NVR first.</div>
          ) : (
            <div className="ptz-preset-list">
              {capabilities.presets.map(preset => {
                const active = selectedTokens.has(String(preset.token));
                const selected = config.presets.find(item => String(item.token) === String(preset.token));
                return (
                  <div key={preset.token} className={`ptz-preset-row ${active ? 'active' : ''}`}>
                    <input type="checkbox" checked={active} onChange={() => togglePreset(preset)} />
                    <div><span className="ptz-preset-name">{preset.name}</span><span className="ptz-preset-token">Token: {preset.token}</span></div>
                    <input type="number" min="1" max="300" disabled={!active}
                      title="Dwell seconds" value={selected?.dwell_seconds || 5}
                      onChange={event => setDwell(preset.token, event.target.value)} />
                  </div>
                );
              })}
            </div>
          )}

          <div className="ptz-actions">
            <button className="ptz-btn success" disabled={!cameraId || busy || !config.presets.length || !capabilities?.verified || runtime.tour_running} onClick={start}>Start Auto Tour</button>
            <button className="ptz-btn danger" disabled={!cameraId || busy || !runtime.tour_running} onClick={stop}>Stop Tour</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PTZAutoTour;
