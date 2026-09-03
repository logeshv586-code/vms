import React, { useEffect, useState } from 'react';
import { useCameraStore } from '../../store/cameraStore';
import {
  getPtzConfig,
  probePtzCapabilities,
  savePtzTrack,
  sendPtzTrackTarget,
  startPtzTrack,
  stopPtzTrack
} from '../../services/ptzService';
import './PTZControl.css';

const DEFAULT_TRACK = {
  enabled: false,
  onvif_port: 80,
  target_class: 'person',
  confidence: 0.5,
  dead_zone_percent: 12,
  pan_speed: 0.35,
  tilt_speed: 0.30,
  lost_target_seconds: 3,
  return_preset: null
};

const PTZAutoTrack = () => {
  const cameras = useCameraStore(state => state.cameras || []);
  const [cameraId, setCameraId] = useState(cameras[0]?.id || '');
  const [config, setConfig] = useState(DEFAULT_TRACK);
  const [capabilities, setCapabilities] = useState(null);
  const [runtime, setRuntime] = useState({ track_active: false });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!cameraId && cameras.length) setCameraId(cameras[0].id);
  }, [cameraId, cameras]);

  useEffect(() => {
    if (!cameraId) return;
    setCapabilities(null);
    setMessage('');
    setError('');
    getPtzConfig(cameraId)
      .then(response => {
        if (response?.success) {
          setConfig({ ...DEFAULT_TRACK, ...(response.data?.track || {}) });
          setRuntime(response.data?.runtime || { track_active: false });
        }
      })
      .catch(err => setError(err.message || 'Unable to load PTZ Auto Track configuration'));
  }, [cameraId]);

  const probe = async () => {
    setBusy(true); setMessage(''); setError('');
    try {
      const response = await probePtzCapabilities(cameraId, config.onvif_port);
      const data = response?.data || {};
      setCapabilities(data);
      if (data.verified) setMessage('ONVIF PTZ verified. You can save and arm the tracking controller.');
      else setError(data.reason || 'PTZ could not be verified for this camera.');
    } catch (err) {
      setError(err.message || 'PTZ capability test failed');
    } finally { setBusy(false); }
  };

  const save = async (enabled = config.enabled) => {
    const payload = {
      ...config,
      enabled,
      onvif_port: Number(config.onvif_port) || 80,
      confidence: Number(config.confidence),
      dead_zone_percent: Number(config.dead_zone_percent),
      pan_speed: Number(config.pan_speed),
      tilt_speed: Number(config.tilt_speed),
      lost_target_seconds: Number(config.lost_target_seconds),
      return_preset: config.return_preset || null
    };
    const response = await savePtzTrack(cameraId, payload);
    if (!response?.success) throw new Error(response?.error || 'Unable to save Auto Track');
    setConfig(payload);
    return payload;
  };

  const saveOnly = async () => {
    setBusy(true); setMessage(''); setError('');
    try {
      await save();
      setMessage('Auto Track settings saved.');
    } catch (err) {
      setError(err.message || 'Unable to save Auto Track');
    } finally { setBusy(false); }
  };

  const arm = async () => {
    setBusy(true); setMessage(''); setError('');
    try {
      await save(true);
      const response = await startPtzTrack(cameraId);
      if (!response?.success) throw new Error(response?.error || 'Unable to arm Auto Track');
      setRuntime(previous => ({ ...previous, track_active: true }));
      setMessage(response.message || 'Auto Track controller armed.');
    } catch (err) {
      setError(err.message || 'Unable to arm Auto Track');
    } finally { setBusy(false); }
  };

  const disarm = async () => {
    setBusy(true); setMessage(''); setError('');
    try {
      const response = await stopPtzTrack(cameraId);
      if (!response?.success) throw new Error(response?.error || 'Unable to stop Auto Track');
      setRuntime(previous => ({ ...previous, track_active: false }));
      setMessage(response.message || 'Auto Track disarmed.');
    } catch (err) {
      setError(err.message || 'Unable to stop Auto Track');
    } finally { setBusy(false); }
  };

  const testDirection = async (center_x, center_y) => {
    if (!runtime.track_active) {
      setError('Arm Auto Track before testing camera movement.');
      return;
    }
    setBusy(true); setMessage(''); setError('');
    try {
      const response = await sendPtzTrackTarget(cameraId, {
        center_x, center_y, confidence: 1, target_class: config.target_class
      });
      if (!response?.success) throw new Error(response?.error || 'Movement test failed');
      // Return target to center shortly afterwards so ContinuousMove is stopped.
      setTimeout(() => {
        sendPtzTrackTarget(cameraId, {
          center_x: 0.5, center_y: 0.5, confidence: 1, target_class: config.target_class
        }).catch(() => {});
      }, 450);
      setMessage('Movement test sent. The camera should move briefly, then stop.');
    } catch (err) {
      setError(err.message || 'Movement test failed');
    } finally { setBusy(false); }
  };

  const setNumber = (key, value) => setConfig(previous => ({ ...previous, [key]: Number(value) }));
  const statusClass = runtime.track_active ? 'running' : capabilities?.verified ? 'ready' : capabilities && !capabilities.verified ? 'error' : '';
  const statusText = runtime.track_active ? '● CONTROLLER ARMED' : capabilities?.verified ? '✓ PTZ VERIFIED' : capabilities ? 'PTZ NOT VERIFIED' : 'PTZ NOT TESTED';

  return (
    <div className="ptz-page">
      <div className="ptz-header">
        <div>
          <h2>PTZ Auto Track</h2>
          <p>Auto Track uses an AI target’s bounding-box center to decide whether the camera should pan or tilt. A center dead-zone prevents constant camera shaking.</p>
        </div>
        <span className={`ptz-status ${statusClass}`}>{statusText}</span>
      </div>

      <div className="ptz-workflow">
        <div className="ptz-step"><strong>1 · Detect & Track</strong><span>YOLO identifies the target class and maintains a track ID.</span></div>
        <div className="ptz-step"><strong>2 · Find Offset</strong><span>The target center is compared with the center of the video frame.</span></div>
        <div className="ptz-step"><strong>3 · Move PTZ</strong><span>Outside the dead-zone, ONVIF ContinuousMove pans/tilts toward the target.</span></div>
        <div className="ptz-step"><strong>4 · Stop / Recover</strong><span>Inside the dead-zone or after losing the target, camera movement stops.</span></div>
      </div>

      {message && <div className="ptz-message">{message}</div>}
      {error && <div className="ptz-message error">{error}</div>}

      <div className="ptz-grid">
        <div className="ptz-card">
          <h3>Camera & Target Policy</h3>
          <div className="ptz-field">
            <label>PTZ Camera</label>
            <select value={cameraId} onChange={event => setCameraId(event.target.value)}>
              {!cameras.length && <option value="">No cameras configured</option>}
              {cameras.map(camera => <option key={camera.id} value={camera.id}>{camera.name}</option>)}
            </select>
          </div>
          <div className="ptz-inline">
            <div className="ptz-field"><label>ONVIF Port</label><input type="number" min="1" max="65535" value={config.onvif_port} onChange={event => setNumber('onvif_port', event.target.value)} /></div>
            <div className="ptz-field"><label>Target Class</label><select value={config.target_class} onChange={event => setConfig(previous => ({ ...previous, target_class: event.target.value }))}><option value="person">Person</option><option value="car">Car</option><option value="motorcycle">Motorcycle</option><option value="truck">Truck</option><option value="bus">Bus</option></select></div>
          </div>
          <div className="ptz-inline">
            <div className="ptz-field"><label>Min Confidence</label><input type="number" step="0.05" min="0.05" max="0.99" value={config.confidence} onChange={event => setNumber('confidence', event.target.value)} /></div>
            <div className="ptz-field"><label>Dead Zone %</label><input type="number" min="2" max="45" value={config.dead_zone_percent} onChange={event => setNumber('dead_zone_percent', event.target.value)} /></div>
          </div>
          <div className="ptz-actions">
            <button className="ptz-btn primary" disabled={!cameraId || busy} onClick={probe}>Test PTZ</button>
            <button className="ptz-btn" disabled={!cameraId || busy} onClick={saveOnly}>Save</button>
          </div>
        </div>

        <div className="ptz-card">
          <h3>Movement Tuning</h3>
          <p className="ptz-card-note">Start conservatively. Faster pan/tilt values can cause overshoot, especially with network latency.</p>
          <div className="ptz-inline">
            <div className="ptz-field"><label>Pan Speed (0–1)</label><input type="number" step="0.05" min="0.05" max="1" value={config.pan_speed} onChange={event => setNumber('pan_speed', event.target.value)} /></div>
            <div className="ptz-field"><label>Tilt Speed (0–1)</label><input type="number" step="0.05" min="0.05" max="1" value={config.tilt_speed} onChange={event => setNumber('tilt_speed', event.target.value)} /></div>
          </div>
          <div className="ptz-field"><label>Lost Target Timeout (seconds)</label><input type="number" step="0.5" min="0.5" max="60" value={config.lost_target_seconds} onChange={event => setNumber('lost_target_seconds', event.target.value)} /></div>

          <div className="ptz-message warning">
            <strong>Important:</strong> “Controller Armed” verifies the PTZ movement controller. Automatic motion begins only when the realtime AI pipeline sends target centers. Use the pad below to verify direction safely before enabling a live handoff.
          </div>

          <div className="ptz-test-pad" aria-label="PTZ movement test pad">
            <span></span><button disabled={!runtime.track_active || busy} onClick={() => testDirection(0.5, 0.15)}>↑</button><span></span>
            <button disabled={!runtime.track_active || busy} onClick={() => testDirection(0.15, 0.5)}>←</button><button className="center" disabled={!runtime.track_active || busy} onClick={() => testDirection(0.5, 0.5)}>■</button><button disabled={!runtime.track_active || busy} onClick={() => testDirection(0.85, 0.5)}>→</button>
            <span></span><button disabled={!runtime.track_active || busy} onClick={() => testDirection(0.5, 0.85)}>↓</button><span></span>
          </div>

          <div className="ptz-actions">
            <button className="ptz-btn success" disabled={!cameraId || busy || !capabilities?.verified || runtime.track_active} onClick={arm}>Save & Arm Controller</button>
            <button className="ptz-btn danger" disabled={!cameraId || busy || !runtime.track_active} onClick={disarm}>Disarm / Stop</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PTZAutoTrack;
