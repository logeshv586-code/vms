import React, { useEffect, useState, useCallback } from 'react';
import './AppearanceSearch.css';

function VehicleData() {
  const [detections, setDetections] = useState([]);
  const [streamFilter, setStreamFilter] = useState(''); // filter detections by stream
  const [streamSearch, setStreamSearch] = useState(''); // search within streams list
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [streams, setStreams] = useState([]); // running monitors
  const [allStreams, setAllStreams] = useState([]); // configured streams
  const [status, setStatus] = useState({ type: '', msg: '' });

  const fetchDetections = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (streamFilter) params.set('stream_id', streamFilter);
      params.set('limit', '100');
      const res = await fetch(`/api/vehicle-monitoring/detections?${params.toString()}`);
      if (!res.ok) throw new Error(`Failed to fetch detections (${res.status})`);
      const data = await res.json();
      setDetections(data.detections || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, [streamFilter]);

  const fetchStreams = useCallback(async () => {
    try {
      const res = await fetch('/api/vehicle-monitoring/streams');
      if (!res.ok) return;
      const data = await res.json();
      setStreams(data.streams || []);
    } catch (_) {}
  }, []);

  const fetchAllStreams = useCallback(async () => {
    try {
      // Get list of collections then each collection’s cameras
      const res = await fetch('/api/collections/');
      if (!res.ok) return;
      const data = await res.json();
      const collections = data.collections || [];
      const all = [];
      for (const c of collections) {
        const r = await fetch(`/api/collections/${encodeURIComponent(c)}`);
        if (!r.ok) continue;
        const cd = await r.json();
        const cams = cd.cameras || {};
        Object.entries(cams).forEach(([ip, url]) => {
          all.push({ stream_id: `${c}_${ip}`, url });
        });
      }
      setAllStreams(all);
    } catch (_) {}
  }, []);

  useEffect(() => {
    fetchDetections();
    fetchStreams();
    fetchAllStreams();
    const id1 = setInterval(fetchDetections, 5000);
    const id2 = setInterval(fetchStreams, 5000);
    const id3 = setInterval(fetchAllStreams, 15000);
    return () => { clearInterval(id1); clearInterval(id2); clearInterval(id3); };
  }, [fetchDetections, fetchStreams, fetchAllStreams]);

  const startAll = async () => {
    try {
      const res = await fetch('/api/vehicle-monitoring/start-all', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setStatus({ type: 'success', msg: `Detections started${data.started?.length ? ` for ${data.started.length} stream(s)` : ' (filtered by camera rules)'}.` });
      } else {
        setStatus({ type: 'error', msg: 'Failed to start monitors' });
      }
      fetchStreams();
      fetchDetections();
    } catch (e) {
      setStatus({ type: 'error', msg: e.message });
    }
  };

  const stopAll = async () => {
    try {
      // Fetch active streams and stop each
      const res = await fetch('/api/vehicle-monitoring/streams');
      const data = res.ok ? await res.json() : { streams: [] };
      const list = data.streams || [];
      await Promise.all(list.map(s => fetch(`/api/vehicle-monitoring/stop?stream_id=${encodeURIComponent(s.stream_id)}`, { method: 'POST' })));
      setStatus({ type: 'success', msg: 'Detections stopped.' });
      fetchStreams();
    } catch (e) {
      setStatus({ type: 'error', msg: e.message });
    }
  };

  const isMonitoring = streams.length > 0;

  const grouped = detections.reduce((acc, d) => {
    const key = d.stream_id;
    acc[key] = acc[key] || [];
    acc[key].push(d);
    return acc;
  }, {});

  const formatTime = (t) => new Date(t * 1000).toLocaleString();

  return (
    <div className="appearance-search" style={{ padding: '30px 40px', background: '#f8fafc' }}>
      <div className="appearance-search-header" style={{ marginBottom: '30px', borderBottom: '1px solid #e2e8f0', paddingBottom: '20px' }}>
        <h2 style={{ color: '#132447', fontSize: '32px', fontWeight: '700', marginBottom: '8px' }}>Vehicle Monitoring</h2>
        <p style={{ color: '#7A869A', fontSize: '16px', margin: 0 }}>
          Real-time vehicle detection, category classification, and license plate recognition using AI tracking.
        </p>
      </div>

      <div className="search-header" style={{ background: '#fff', borderRadius: '16px', padding: '24px', boxShadow: '0 4px 16px rgba(0,0,0,0.04)', marginBottom: '30px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '16px', flex: 1, minWidth: '300px' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                className="stream-select"
                style={{ width: '100%', paddingLeft: '16px', borderRadius: '10px' }}
                placeholder="Filter detections by stream ID (e.g. Eagle_192.168.4.242)"
                value={streamFilter}
                onChange={(e) => setStreamFilter(e.target.value)}
              />
            </div>
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                className="stream-select"
                style={{ width: '100%', paddingLeft: '16px', borderRadius: '10px' }}
                placeholder="Search camera streams..."
                value={streamSearch}
                onChange={(e) => setStreamSearch(e.target.value)}
              />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <button className="upload-btn" style={{ minWidth: '120px', borderRadius: '10px', height: '48px' }} onClick={fetchDetections}>Refresh</button>
            <button className="upload-btn" style={{ minWidth: '160px', borderRadius: '10px', height: '48px', background: '#38a169' }} onClick={startAll}>Start Monitors</button>
            <button className="upload-btn" style={{ minWidth: '160px', borderRadius: '10px', height: '48px', background: '#e53e3e' }} onClick={stopAll} disabled={!isMonitoring}>Stop Monitors</button>
          </div>
        </div>
        {status.msg && (
          <div style={{ 
            padding: '12px 20px', 
            borderRadius: '10px', 
            fontSize: '14px', 
            fontWeight: '500',
            background: status.type === 'error' ? '#fff5f5' : '#f0fff4',
            color: status.type === 'error' ? '#c53030' : '#22543d',
            border: `1px solid ${status.type === 'error' ? '#fed7d7' : '#c6f6d5'}`,
            display: 'inline-block',
            alignSelf: 'flex-start'
          }}>
            ● {status.msg}
          </div>
        )}
      </div>

      {error && <div className="error-message" style={{ margin: '0 0 24px' }}>{error}</div>}

      {isLoading ? (
        <div className="search-loading" style={{ borderRadius: '16px', padding: '60px' }}>
          <div className="loading-spinner"></div>
          <p style={{ marginTop: '16px', fontWeight: '500' }}>Loading vehicle detections...</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
          
          {/* Active Detections */}
          <div className="search-results" style={{ borderRadius: '16px', padding: '30px', boxShadow: '0 4px 16px rgba(0,0,0,0.04)' }}>
            <h3 style={{ fontSize: '22px', fontWeight: '600', color: '#132447', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px', marginBottom: '24px' }}>
              Detected Vehicles
            </h3>
            {Object.keys(grouped).length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 20px', color: '#718096' }}>
                <p style={{ fontSize: '16px', margin: 0 }}>No detections yet. Click "Start Monitors" to begin camera stream tracking.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '30px' }}>
                {Object.entries(grouped).map(([stream, items]) => (
                  <div key={stream} style={{ background: '#f8fafc', borderRadius: '16px', padding: '24px', border: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
                      <div>
                        <h4 style={{ margin: 0, fontSize: '18px', color: '#132447', fontWeight: '700' }}>
                          Stream: {stream}
                        </h4>
                        <span style={{ fontSize: '14px', color: '#718096', display: 'block', marginTop: '4px' }}>
                          Camera Feed Monitor ID: {stream}
                        </span>
                      </div>
                      <div style={{ background: '#ebf8ff', color: '#2b6cb0', padding: '6px 16px', borderRadius: '30px', fontWeight: '700', fontSize: '13px', border: '1px solid #bee3f8' }}>
                        {items.length} ACTIVE DETECTION{items.length !== 1 ? 'S' : ''}
                      </div>
                    </div>

                    <div style={{ overflowX: 'auto', background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.02)' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '850px' }}>
                        <thead>
                          <tr style={{ background: '#f1f5f9', borderBottom: '2px solid #e2e8f0' }}>
                            <th style={{ padding: '16px 20px', fontWeight: '600', color: '#4a5568', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Vehicle Snapshot</th>
                            <th style={{ padding: '16px 20px', fontWeight: '600', color: '#4a5568', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Plate Snapshot</th>
                            <th style={{ padding: '16px', fontWeight: '600', color: '#4a5568', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Vehicle ID</th>
                            <th style={{ padding: '16px', fontWeight: '600', color: '#4a5568', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>License Plate</th>
                            <th style={{ padding: '16px', fontWeight: '600', color: '#4a5568', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Confidence</th>
                            <th style={{ padding: '16px', fontWeight: '600', color: '#4a5568', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Vehicle Type</th>
                            <th style={{ padding: '16px', fontWeight: '600', color: '#4a5568', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Category</th>
                            <th style={{ padding: '16px 20px', fontWeight: '600', color: '#4a5568', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Timestamp</th>
                          </tr>
                        </thead>
                        <tbody>
                          {items.map((d) => {
                            // Badge styling based on vehicle category
                            let badgeBg = '#edf2f7';
                            let badgeColor = '#4a5568';
                            const categoryLower = (d.vehicle_category || '').toLowerCase();
                            if (categoryLower.includes('two-wheeler')) {
                              badgeBg = '#fffaf0';
                              badgeColor = '#dd6b20'; // Orange
                            } else if (categoryLower.includes('heavy vehicle') || categoryLower.includes('heavy commercial')) {
                              badgeBg = '#ebf8ff';
                              badgeColor = '#3182ce'; // Blue
                            } else if (categoryLower.includes('sedan') || categoryLower.includes('suv')) {
                              badgeBg = '#f0fff4';
                              badgeColor = '#38a169'; // Green
                            }

                            // Vehicle type badge styling
                            let typeBg = '#f7fafc';
                            let typeColor = '#4a5568';
                            const typeLower = (d.vehicle_type || '').toLowerCase();
                            if (typeLower === 'car') {
                              typeBg = '#e6fffa';
                              typeColor = '#319795'; // Teal
                            } else if (typeLower === 'motorcycle') {
                              typeBg = '#fff5f5';
                              typeColor = '#e53e3e'; // Red/Pink
                            } else if (typeLower === 'bus') {
                              typeBg = '#faf5ff';
                              typeColor = '#805ad5'; // Purple
                            } else if (typeLower === 'truck') {
                              typeBg = '#f0fff4';
                              typeColor = '#2b6cb0'; // Darker blue
                            }

                            return (
                              <tr key={d.id} style={{ borderBottom: '1px solid #edf2f7', transition: 'background-color 0.2s' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8fafc'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                                <td style={{ padding: '12px 20px' }}>
                                  {d.snapshots?.vehicle ? (
                                    <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden', width: '96px', height: '64px', cursor: 'zoom-in', boxShadow: '0 2px 4px rgba(0,0,0,0.04)' }}>
                                      <img src={d.snapshots.vehicle} alt="Vehicle" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onClick={() => window.open(d.snapshots.vehicle, '_blank')} />
                                    </div>
                                  ) : (
                                    <span style={{ fontSize: '12px', color: '#a0aec0' }}>No snapshot</span>
                                  )}
                                </td>
                                <td style={{ padding: '12px 20px' }}>
                                  {d.snapshots?.plate ? (
                                    <div style={{ border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden', width: '96px', height: '48px', cursor: 'zoom-in', boxShadow: '0 2px 4px rgba(0,0,0,0.04)' }}>
                                      <img src={d.snapshots.plate} alt="Plate" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onClick={() => window.open(d.snapshots.plate, '_blank')} />
                                    </div>
                                  ) : (
                                    <span style={{ fontSize: '12px', color: '#a0aec0' }}>No snapshot</span>
                                  )}
                                </td>
                                <td style={{ padding: '16px 20px', color: '#2d3748', fontWeight: '700', fontSize: '14px' }}>
                                  #{d.vehicle_id}
                                </td>
                                <td style={{ padding: '16px' }}>
                                  <span style={{ fontFamily: 'monospace', fontWeight: '800', fontSize: '14px', background: '#1a202c', color: '#f7fafc', padding: '6px 12px', borderRadius: '6px', letterSpacing: '0.8px', border: '1px solid #2d3748', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
                                    {d.license_plate || 'UNKNOWN'}
                                  </span>
                                </td>
                                <td style={{ padding: '16px' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <div style={{ width: '60px', height: '6px', background: '#e2e8f0', borderRadius: '3px', overflow: 'hidden' }}>
                                      <div style={{ width: `${(d.license_plate_score || 0) * 100}%`, height: '100%', background: (d.license_plate_score || 0) > 0.85 ? '#48bb78' : '#ed8936' }} />
                                    </div>
                                    <span style={{ fontSize: '13px', fontWeight: '700', color: (d.license_plate_score || 0) > 0.85 ? '#2f855a' : '#c05621' }}>
                                      {d.license_plate_score ? `${(d.license_plate_score * 100).toFixed(0)}%` : '—'}
                                    </span>
                                  </div>
                                </td>
                                <td style={{ padding: '16px' }}>
                                  <span style={{ display: 'inline-block', padding: '6px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.5px', backgroundColor: typeBg, color: typeColor, border: `1px solid ${typeColor}20` }}>
                                    {d.vehicle_type || 'Unknown'}
                                  </span>
                                </td>
                                <td style={{ padding: '16px' }}>
                                  <span style={{ display: 'inline-block', padding: '6px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.5px', backgroundColor: badgeBg, color: badgeColor, border: `1px solid ${badgeColor}20` }}>
                                    {d.vehicle_category || 'Vehicle'}
                                  </span>
                                </td>
                                <td style={{ padding: '16px 20px', color: '#4a5568', fontSize: '13px', fontWeight: '500' }}>
                                  {formatTime(d.timestamp)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Camera Streams Settings Panel */}
          <div className="search-results" style={{ borderRadius: '16px', padding: '30px', boxShadow: '0 4px 16px rgba(0,0,0,0.04)' }}>
            <h3 style={{ fontSize: '20px', fontWeight: '600', color: '#132447', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px', marginBottom: '20px' }}>
              Camera Streams Status & Rules Settings
            </h3>
            <p style={{ color: '#7A869A', fontSize: '14px', marginBottom: '20px' }}>
              Vehicle Monitoring (Rule 22) must be enabled in standard camera rules config for streams to start.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {allStreams
                .filter(s => !streamSearch || s.stream_id.toLowerCase().includes(streamSearch.toLowerCase()))
                .map((s) => {
                  const running = streams.some(r => r.stream_id === s.stream_id);
                  return (
                    <div key={s.stream_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc', padding: '16px 20px', borderRadius: '12px', border: '1px solid #e2e8f0', flexWrap: 'wrap', gap: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <div style={{ 
                          width: '10px', 
                          height: '10px', 
                          borderRadius: '50%', 
                          background: running ? '#48bb78' : '#a0aec0',
                          boxShadow: running ? '0 0 8px #48bb78' : 'none'
                        }} />
                        <div>
                          <strong style={{ color: '#2d3748', fontSize: '15px' }}>{s.stream_id}</strong>
                          <span style={{ fontSize: '13px', color: '#718096', display: 'block', marginTop: '2px' }}>
                            RTSP Feed URL: {s.url}
                          </span>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '12px' }}>
                        <button
                          className="upload-btn"
                          style={{ 
                            minWidth: '100px', 
                            padding: '8px 16px', 
                            borderRadius: '8px', 
                            fontSize: '14px', 
                            background: running ? '#e2e8f0' : '#3182ce',
                            color: running ? '#718096' : '#fff'
                          }}
                          onClick={async () => {
                            const res = await fetch(`/api/vehicle-monitoring/start?stream_id=${encodeURIComponent(s.stream_id)}`, { method: 'POST' });
                            const ok = res.ok;
                            try { 
                              const j = await res.json(); 
                              if (ok && j?.stream_id) setStatus({ type: 'success', msg: `Started stream: ${j.stream_id}` }); 
                              else if (ok) setStatus({ type: 'success', msg: `Started stream: ${s.stream_id}` }); 
                            } catch (_) { 
                              if (ok) setStatus({ type: 'success', msg: `Started stream: ${s.stream_id}` }); 
                            }
                            if (!ok) setStatus({ type: 'error', msg: `Failed to start stream: ${s.stream_id} (Ensure Rule 22 is active and assigned)` });
                            fetchStreams();
                          }}
                          disabled={running}
                        >
                          Start Feed
                        </button>
                        <button
                          className="upload-btn"
                          style={{ 
                            minWidth: '100px', 
                            padding: '8px 16px', 
                            borderRadius: '8px', 
                            fontSize: '14px', 
                            background: '#e53e3e',
                            color: '#fff'
                          }}
                          onClick={async () => {
                            const res = await fetch(`/api/vehicle-monitoring/stop?stream_id=${encodeURIComponent(s.stream_id)}`, { method: 'POST' });
                            if (res.ok) setStatus({ type: 'success', msg: `Stopped stream: ${s.stream_id}` });
                            else setStatus({ type: 'error', msg: `Failed to stop stream: ${s.stream_id}` });
                            fetchStreams();
                          }}
                          disabled={!running}
                        >
                          Stop Feed
                        </button>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
          
        </div>
      )}
    </div>
  );
}

export default VehicleData;


