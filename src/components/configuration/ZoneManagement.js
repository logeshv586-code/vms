import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Square, 
  Circle, 
  Slash, 
  Save, 
  Trash2, 
  Plus, 
  MousePointer2, 
  Maximize2,
  Video,
  RectangleHorizontal
} from 'lucide-react';
import { useCameraStore } from '../../store/cameraStore';
import { apiRequest } from '../../utils/api';
import { API_BASE_URL } from '../../utils/apiConfig';
import { getCameraStreamId } from '../../utils/cameraUtils';
import WebRTCDetectionPlayer from '../camera/WebRTCDetectionPlayer';
import './ZoneManagement.css';

const ZoneManagement = ({ preselectedCamera = null, onClose = null }) => {
  const { cameras, loadCameraConfig, collections, getCamerasByCollection } = useCameraStore();
  const [selectedCamera, setSelectedCamera] = useState(preselectedCamera);
  const [zones, setZones] = useState([]);

  const [autoApplyRules, setAutoApplyRules] = useState(false);
  const [activeTool, setActiveTool] = useState('polygon'); // polygon, circle, line, rectangle
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentPoints, setCurrentPoints] = useState([]);
  const [tempCircle, setTempCircle] = useState(null);
  const [tempRect, setTempRect] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(Date.now());
  const [message, setMessage] = useState({ type: '', text: '' });
  
  const canvasRef = useRef(null);
  const videoRef = useRef(null);
  const containerRef = useRef(null);

  // Auto-select first camera if none is selected
  useEffect(() => {
    const validCameras = cameras.filter(cam => cam.id !== 'webcam' && cam.ip !== 'webcam');
    if (validCameras.length > 0 && !selectedCamera) {
      setSelectedCamera(validCameras[0]);
    }
  }, [cameras, selectedCamera]);

  // Load zones for selected camera
  useEffect(() => {
    if (selectedCamera) {
      const streamId = getCameraStreamId(selectedCamera);
      if (streamId) {
        fetchZones(streamId);
      }
    }
  }, [selectedCamera?.id, selectedCamera?.ip, selectedCamera?.collection]);

  const fetchZones = async (streamId) => {
    setIsLoading(true);
    try {
      const response = await apiRequest(`/api/augment/camera-zones/${streamId}`);
      if (response && response.success) {
        setZones(response.data.zones || []);
      }
    } catch (err) {
      console.error('Error fetching zones:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!selectedCamera) return;
    setIsLoading(true);
    try {
      // Ensure we have the consistent streamId even if state hasn't updated yet
      const streamId = getCameraStreamId(selectedCamera);
      
      if (!streamId) {
        throw new Error('Camera ID is missing');
      }

      console.log(`Saving zones for stream: ${streamId}`);
      const response = await apiRequest(`/api/augment/camera-zones/${streamId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(zones)
      });
      
      if (response && response.success) {
        // Automatically apply rules 11 and 23 if requested
        if (autoApplyRules) {
          await applyMonitoringRules(streamId);
        }
        setMessage({ type: 'success', text: 'Zones and rules saved successfully' });
      } else {
        throw new Error(response?.error || 'Backend returned success: false');
      }
    } catch (err) {
      console.error('Save failed:', err);
      setMessage({ type: 'error', text: `Failed to save configuration: ${err.message}` });
    } finally {
      setIsLoading(false);
      setTimeout(() => setMessage({ type: '', text: '' }), 5000);
    }
  };

  const applyMonitoringRules = async (derivedStreamId) => {
    if (!selectedCamera) return;
    try {
      // Get current rules first
      const getRulesRes = await apiRequest('/api/augment/camera-rules');
      let currentRules = [];
      if (getRulesRes && getRulesRes.success) {
        currentRules = getRulesRes.data.cameraRules[selectedCamera.id] || [];
      }

      // Add rules 11 (Lakshmanrekha) and 23 (Zone Monitoring) if not already there
      const newRules = [...new Set([...currentRules, 11, 23])];
      
      await apiRequest('/api/augment/apply-camera-rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cameraIds: [selectedCamera.id],
          ruleIds: newRules
        })
      });
    } catch (err) {
      console.error('Error applying monitoring rules:', err);
    }
  };

  const getMousePos = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    return [
      (e.clientX - rect.left) / rect.width,
      (e.clientY - rect.top) / rect.height
    ];
  };

  const refreshStream = () => {
    setStreamKey(Date.now());
    setStreamError(false);
  };

  const handleMouseDown = (e) => {
    if (!selectedCamera) return;
    const [x, y] = getMousePos(e);

    if (activeTool === 'polygon' || activeTool === 'line') {
      setIsDrawing(true);
      setCurrentPoints([...currentPoints, [x, y]]);
      
      // If line tool, finish after 2 points
      if (activeTool === 'line' && currentPoints.length === 1) {
        const newZone = {
          id: `zone_${Date.now()}`,
          name: `Line ${zones.length + 1}`,
          type: 'polygon',
          polygon: [...currentPoints, [x, y]]
        };
        setZones([...zones, newZone]);
        setCurrentPoints([]);
        setIsDrawing(false);
      }
    } else if (activeTool === 'circle') {
      setIsDrawing(true);
      setTempCircle({ center: [x, y], radius: 0 });
    } else if (activeTool === 'rectangle') {
      setIsDrawing(true);
      setTempRect({ start: [x, y], end: [x, y] });
    }
  };

  const handleMouseMove = (e) => {
    if (!isDrawing) return;
    const [x, y] = getMousePos(e);

    if (activeTool === 'circle' && tempCircle) {
      const dx = x - tempCircle.center[0];
      const dy = y - tempCircle.center[1];
      const radius = Math.sqrt(dx * dx + dy * dy);
      setTempCircle({ ...tempCircle, radius });
    } else if (activeTool === 'rectangle' && tempRect) {
      setTempRect({ ...tempRect, end: [x, y] });
    }
  };

  const handleMouseUp = () => {
    if (activeTool === 'circle' && tempCircle) {
      if (tempCircle.radius > 0.01) {
        const newZone = {
          id: `zone_${Date.now()}`,
          name: `Circle ${zones.length + 1}`,
          type: 'circle',
          center: tempCircle.center,
          radius: tempCircle.radius
        };
        setZones([...zones, newZone]);
      }
      setTempCircle(null);
      setIsDrawing(false);
    } else if (activeTool === 'rectangle' && tempRect) {
      const [x1, y1] = tempRect.start;
      const [x2, y2] = tempRect.end;
      if (Math.abs(x1 - x2) > 0.01 || Math.abs(y1 - y2) > 0.01) {
        const newZone = {
          id: `zone_${Date.now()}`,
          name: `Rect ${zones.length + 1}`,
          type: 'polygon',
          polygon: [
            [x1, y1], [x2, y1], [x2, y2], [x1, y2]
          ]
        };
        setZones([...zones, newZone]);
      }
      setTempRect(null);
      setIsDrawing(false);
    }
  };

  const finishPolygon = () => {
    if (currentPoints.length >= 3) {
      const newZone = {
        id: `zone_${Date.now()}`,
        name: `Zone ${zones.length + 1}`,
        type: 'polygon',
        polygon: currentPoints
      };
      setZones([...zones, newZone]);
    }
    setCurrentPoints([]);
    setIsDrawing(false);
  };

  const deleteZone = async (id) => {
    const newZones = zones.filter(z => z.id !== id);
    setZones(newZones);
    await saveZonesToBackend(newZones);
  };

  const clearAllZones = async () => {
    setZones([]);
    setCurrentPoints([]);
    await saveZonesToBackend([]);
  };

  const saveZonesToBackend = async (zonesToSave) => {
    if (!selectedCamera) return;
    setIsLoading(true);
    try {
      const streamId = selectedCamera.streamId || selectedCamera.id?.replace('camera-', '').toLowerCase();
      if (!streamId) throw new Error('Camera ID is missing');

      const response = await apiRequest(`/api/augment/camera-zones/${streamId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(zonesToSave)
      });
      
      if (response && response.success) {
        setMessage({ type: 'success', text: 'Zones updated successfully' });
      } else {
        throw new Error(response?.error || 'Backend returned success: false');
      }
    } catch (err) {
      setMessage({ type: 'error', text: `Failed to update zones: ${err.message}` });
    } finally {
      setIsLoading(false);
      setTimeout(() => setMessage({ type: '', text: '' }), 3000);
    }
  };

  // Use refs for frequently-changing state so the draw loop never needs to restart
  const zonesRef = useRef(zones);
  const currentPointsRef = useRef(currentPoints);
  const isDrawingRef = useRef(isDrawing);
  const tempCircleRef = useRef(tempCircle);
  const tempRectRef = useRef(tempRect);
  const activeToolRef = useRef(activeTool);

  useEffect(() => { zonesRef.current = zones; }, [zones]);
  useEffect(() => { currentPointsRef.current = currentPoints; }, [currentPoints]);
  useEffect(() => { isDrawingRef.current = isDrawing; }, [isDrawing]);
  useEffect(() => { tempCircleRef.current = tempCircle; }, [tempCircle]);
  useEffect(() => { tempRectRef.current = tempRect; }, [tempRect]);
  useEffect(() => { activeToolRef.current = activeTool; }, [activeTool]);

  // Single long-lived draw loop — never restarts on tool/state changes
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let animId;

    const draw = () => {
      // Auto-sync canvas pixel dimensions to its CSS layout size
      const parent = canvas.parentElement;
      if (parent) {
        const pw = parent.clientWidth;
        const ph = parent.clientHeight;
        if (canvas.width !== pw || canvas.height !== ph) {
          canvas.width = pw;
          canvas.height = ph;
        }
      }

      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      // Draw existing zones
      zonesRef.current.forEach(zone => {
        ctx.strokeStyle = '#00ffff';
        ctx.fillStyle = 'rgba(0, 255, 255, 0.15)';
        ctx.lineWidth = 2;

        if (zone.type === 'circle') {
          ctx.beginPath();
          ctx.ellipse(
            zone.center[0] * w, zone.center[1] * h,
            zone.radius * w, zone.radius * h,
            0, 0, Math.PI * 2
          );
          ctx.stroke();
          ctx.fill();
        } else {
          ctx.beginPath();
          zone.polygon.forEach((p, i) => {
            if (i === 0) ctx.moveTo(p[0] * w, p[1] * h);
            else ctx.lineTo(p[0] * w, p[1] * h);
          });
          if (zone.polygon.length > 2) ctx.closePath();
          ctx.stroke();
          ctx.fill();
        }

        // Draw label
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 13px Inter, sans-serif';
        ctx.shadowColor = 'rgba(0,0,0,0.7)';
        ctx.shadowBlur = 3;
        const labelX = zone.type === 'circle' ? zone.center[0] * w : zone.polygon[0][0] * w;
        const labelY = zone.type === 'circle' ? (zone.center[1] * h - zone.radius * h - 8) : zone.polygon[0][1] * h - 8;
        ctx.fillText(zone.name, labelX, labelY);
        ctx.shadowBlur = 0;
      });

      // Draw current in-progress shape
      const _isDrawing = isDrawingRef.current;
      const _activeTool = activeToolRef.current;
      const _currentPoints = currentPointsRef.current;
      const _tempCircle = tempCircleRef.current;
      const _tempRect = tempRectRef.current;

      if (_isDrawing) {
        ctx.strokeStyle = '#ff00ff';
        ctx.fillStyle = 'rgba(255, 0, 255, 0.12)';
        ctx.lineWidth = 2;
        if (_activeTool === 'polygon' || _activeTool === 'line') {
          ctx.beginPath();
          _currentPoints.forEach((p, i) => {
            if (i === 0) ctx.moveTo(p[0] * w, p[1] * h);
            else ctx.lineTo(p[0] * w, p[1] * h);
          });
          ctx.stroke();
          _currentPoints.forEach(p => {
            ctx.fillStyle = '#ff00ff';
            ctx.beginPath();
            ctx.arc(p[0] * w, p[1] * h, 5, 0, Math.PI * 2);
            ctx.fill();
          });
        } else if (_activeTool === 'circle' && _tempCircle) {
          ctx.beginPath();
          ctx.ellipse(
            _tempCircle.center[0] * w, _tempCircle.center[1] * h,
            _tempCircle.radius * w, _tempCircle.radius * h,
            0, 0, Math.PI * 2
          );
          ctx.stroke();
          ctx.fillStyle = 'rgba(255, 0, 255, 0.12)';
          ctx.fill();
        } else if (_activeTool === 'rectangle' && _tempRect) {
          const [x1, y1] = _tempRect.start;
          const [x2, y2] = _tempRect.end;
          ctx.strokeRect(x1 * w, y1 * h, (x2 - x1) * w, (y2 - y1) * h);
          ctx.fillStyle = 'rgba(255, 0, 255, 0.12)';
          ctx.fillRect(x1 * w, y1 * h, (x2 - x1) * w, (y2 - y1) * h);
        }
      }

      animId = requestAnimationFrame(draw);
    };

    animId = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animId);
  }, [selectedCamera?.id]); // Only restart when camera changes

  return (
    <div className="zone-mgmt-container">
      <div className="zone-mgmt-header">
        <div className="header-info">
          <h2>Analytical Zone Management</h2>
          <p>Define restricted areas and virtual lines for monitoring</p>
        </div>
        <div className="header-actions">
          <div className="auto-apply-toggle">
            <input 
              type="checkbox" 
              id="autoApply" 
              checked={autoApplyRules} 
              onChange={(e) => setAutoApplyRules(e.target.checked)} 
            />
            <label htmlFor="autoApply">Auto-enable Monitoring Rules (11, 23)</label>
          </div>
          <button className="save-btn" onClick={handleSave} disabled={isLoading || !selectedCamera}>
            <Save size={18} />
            <span>Save Configuration</span>
          </button>
        </div>
      </div>

      <div className="zone-mgmt-layout">
        {/* Left Sidebar: Camera List & Zones */}
        <div className="zone-mgmt-sidebar">
          <div className="sidebar-section">
            <h3>Cameras</h3>
            <div className="camera-list">
              {collections.map((collection) => {
                const collectionCameras = getCamerasByCollection(collection.id).filter(
                  cam => cam.id !== 'webcam' && cam.ip !== 'webcam'
                );
                if (collectionCameras.length === 0) return null;

                return (
                  <div key={collection.id} className="camera-group">
                    <div className="group-label">
                      <span className="folder-icon">📂</span> {collection.name}
                    </div>
                    {collectionCameras.map(cam => (
                      <button 
                        key={cam.id} 
                        className={`camera-item ${selectedCamera?.id === cam.id ? 'active' : ''}`}
                        onClick={() => {
                          setSelectedCamera(cam);
                        }}
                      >
                        <div className="camera-item-icon">
                          <Video size={18} />
                        </div>
                        <div className="camera-item-details">
                          <span className="camera-name-text">{cam.name || cam.cameraName || 'Unnamed Camera'}</span>
                          <span className="camera-ip-text">{cam.ip || 'Unknown IP'}</span>
                          <span className="camera-status-tag">
                            <span className="status-dot-green"></span>
                            Live
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="sidebar-section">
            <h3>Configured Zones</h3>
            <div className="zone-list">
              {zones.length === 0 ? (
                <div className="empty-state">No zones defined</div>
              ) : (
                zones.map(zone => (
                  <div key={zone.id} className="zone-item">
                    <div className="zone-info">
                      <span className="zone-name">{zone.name}</span>
                      <span className="zone-type">{zone.type}</span>
                    </div>
                    <button className="delete-zone-btn" onClick={() => deleteZone(zone.id)}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Main Area: Stream & Drawing Tools */}
        <div className="zone-mgmt-main">
          {selectedCamera ? (
            <div className="drawing-container" ref={containerRef}>
              <div className="toolbar">
                <button 
                  className={`tool-btn ${activeTool === 'polygon' ? 'active' : ''}`}
                  onClick={() => { setActiveTool('polygon'); setCurrentPoints([]); }}
                  title="Polygon Tool"
                >
                  <Square size={20} />
                </button>
                <button 
                  className={`tool-btn ${activeTool === 'circle' ? 'active' : ''}`}
                  onClick={() => { setActiveTool('circle'); setCurrentPoints([]); }}
                  title="Circle Tool"
                >
                  <Circle size={20} />
                </button>
                <button 
                  className={`tool-btn ${activeTool === 'rectangle' ? 'active' : ''}`}
                  onClick={() => { setActiveTool('rectangle'); setCurrentPoints([]); }}
                  title="Rectangle Tool"
                >
                  <RectangleHorizontal size={20} />
                </button>
                <button 
                  className={`tool-btn ${activeTool === 'line' ? 'active' : ''}`}
                  onClick={() => { setActiveTool('line'); setCurrentPoints([]); }}
                  title="Lakshmanrekha Tool"
                >
                  <Slash size={20} />
                </button>
                {currentPoints.length >= 3 && (
                  <button className="finish-btn" onClick={finishPolygon}>
                    Finish Polygon
                  </button>
                )}
                <button 
                  className="clear-btn" 
                  onClick={clearAllZones}
                  title="Clear All"
                >
                  <Trash2 size={20} />
                </button>
                <button 
                  className="tool-btn" 
                  onClick={refreshStream}
                  title="Refresh Stream"
                >
                  <Maximize2 size={20} />
                </button>
              </div>

              <div className="video-viewport">
                {streamError ? (
                  <div className="stream-error-overlay">
                    <Video size={48} />
                    <h3>Stream Connection Failed</h3>
                    <p>The camera feed is currently unreachable. Check your network or RTSP settings.</p>
                    <button className="retry-btn" onClick={refreshStream}>Retry Connection</button>
                  </div>
                ) : null}
                <div className="video-wrapper">
                  <WebRTCDetectionPlayer 
                    key={streamKey}
                    streamId={selectedCamera.streamId}
                    collectionName={selectedCamera.collectionName || selectedCamera.collection}
                    cameraIp={selectedCamera.ip}
                    onError={(err) => {
                      console.error('WebRTC stream failed', err);
                      setStreamError(true);
                    }}
                    onPlay={() => setStreamError(false)}
                  >
                    <canvas 
                      ref={canvasRef}
                      onMouseDown={handleMouseDown}
                      onMouseMove={handleMouseMove}
                      onMouseUp={handleMouseUp}
                      className="drawing-canvas"
                    />
                  </WebRTCDetectionPlayer>
                </div>
              </div>

              <div className="viewport-footer">
                <div className="drawing-help">
                  {activeTool === 'polygon' && "Click to add points. Click 'Finish' to close the polygon."}
                  {activeTool === 'circle' && "Click and drag to draw a circular zone."}
                  {activeTool === 'rectangle' && "Click and drag to draw a rectangular zone."}
                  {activeTool === 'line' && "Click two points to define a Lakshmanrekha boundary line."}
                </div>
              </div>
            </div>
          ) : (
            <div className="select-camera-placeholder">
              <Maximize2 size={48} />
              <h3>Select a camera to manage zones</h3>
              <p>Choose a camera from the list to start defining monitoring rules</p>
            </div>
          )}
        </div>
      </div>

      <AnimatePresence>
        {message.text && (
          <motion.div 
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            className={`status-toast ${message.type}`}
          >
            {message.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ZoneManagement;
