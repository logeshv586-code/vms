import React, { useState, useEffect, useCallback } from 'react';
import './FaceAnalyticsPanel.css';
import { API_BASE_URL } from '../../utils/apiConfig';

const FaceAnalyticsPanel = ({ streamId = null }) => {
  const [activeTab, setActiveTab] = useState('captures');
  const [captures, setCaptures] = useState([]);
  const [recognitions, setRecognitions] = useState([]);
  const [watchlist, setWatchlist] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Watchlist form
  const [wlName, setWlName] = useState('');
  const [wlAlias, setWlAlias] = useState('');
  const [wlCategory, setWlCategory] = useState('suspect');
  const [wlNotes, setWlNotes] = useState('');
  const [wlShowForm, setWlShowForm] = useState(false);

  // Face registration
  const [regName, setRegName] = useState('');
  const [regCategory, setRegCategory] = useState('person');
  const [regFile, setRegFile] = useState(null);
  const [regLoading, setRegLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const streamParam = streamId ? `?stream_id=${streamId}` : '';

      const [capsRes, recRes, wlRes, sumRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/face/captures${streamParam}&limit=50`),
        fetch(`${API_BASE_URL}/api/face/recognitions${streamParam}&limit=50`),
        fetch(`${API_BASE_URL}/api/face/watchlist`),
        fetch(`${API_BASE_URL}/api/face/analytics/summary`),
      ]);

      if (capsRes.ok) {
        const d = await capsRes.json();
        setCaptures(d.captures || []);
      }
      if (recRes.ok) {
        const d = await recRes.json();
        setRecognitions(d.recognitions || []);
      }
      if (wlRes.ok) {
        const d = await wlRes.json();
        setWatchlist(d.watchlist || []);
      }
      if (sumRes.ok) {
        const d = await sumRes.json();
        setSummary(d.summary);
      }
    } catch (e) {
      setError('Failed to fetch face analytics data.');
    } finally {
      setLoading(false);
    }
  }, [streamId]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000); // Refresh every 15s
    return () => clearInterval(interval);
  }, [fetchData]);

  const formatTime = (ts) => {
    if (!ts) return '-';
    return new Date(ts * 1000).toLocaleString();
  };

  const getCategoryBadge = (category) => {
    const map = {
      criminal: { label: 'Criminal', color: '#ff4444' },
      suspect: { label: 'Suspect', color: '#ff8800' },
      person: { label: 'Person', color: '#4488ff' },
      staff: { label: 'Staff', color: '#44cc88' },
      unknown: { label: 'Unknown', color: '#888' },
    };
    const c = map[category] || map.unknown;
    return (
      <span
        className="face-badge"
        style={{ background: c.color }}
      >
        {c.label}
      </span>
    );
  };

  // ── Watchlist actions ────────────────────────────────────────────────
  const handleAddWatchlist = async () => {
    if (!wlName.trim()) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/face/watchlist`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: wlName, alias: wlAlias, category: wlCategory, notes: wlNotes }),
      });
      if (res.ok) {
        setWlName(''); setWlAlias(''); setWlNotes('');
        setWlShowForm(false);
        fetchData();
      }
    } catch (e) {
      setError('Failed to add watchlist entry.');
    }
  };

  const handleRemoveWatchlist = async (id) => {
    try {
      await fetch(`${API_BASE_URL}/api/face/watchlist/${id}`, { method: 'DELETE' });
      fetchData();
    } catch (e) {
      setError('Failed to remove watchlist entry.');
    }
  };

  // ── Face registration ────────────────────────────────────────────────
  const handleRegisterFace = async () => {
    if (!regName.trim() || !regFile) return;
    setRegLoading(true);
    try {
      const fd = new FormData();
      fd.append('name', regName);
      fd.append('category', regCategory);
      fd.append('file', regFile);
      const res = await fetch(`${API_BASE_URL}/api/face/register`, {
        method: 'POST',
        body: fd,
      });
      if (res.ok) {
        setRegName(''); setRegFile(null);
        alert('Face registered successfully!');
        fetchData();
      } else {
        const d = await res.json();
        setError(d.detail || 'Registration failed.');
      }
    } catch (e) {
      setError('Failed to register face.');
    } finally {
      setRegLoading(false);
    }
  };

  return (
    <div className="face-analytics-panel">
      {/* Header */}
      <div className="fap-header">
        <div className="fap-header-left">
          <span className="fap-icon">🧑‍💻</span>
          <h2 className="fap-title">Face Analytics</h2>
          {streamId && <span className="fap-stream-badge">{streamId}</span>}
        </div>
        <button className="fap-refresh-btn" onClick={fetchData} disabled={loading}>
          {loading ? '⏳' : '🔄'} Refresh
        </button>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="fap-summary-grid">
          <div className="fap-stat-card">
            <div className="fap-stat-value">{summary.total_captures ?? 0}</div>
            <div className="fap-stat-label">Total Captures</div>
          </div>
          <div className="fap-stat-card">
            <div className="fap-stat-value">{summary.total_recognitions ?? 0}</div>
            <div className="fap-stat-label">Recognitions</div>
          </div>
          <div className="fap-stat-card fap-stat-danger">
            <div className="fap-stat-value">{summary.watchlisted_detections ?? 0}</div>
            <div className="fap-stat-label">Watchlist Hits</div>
          </div>
          <div className="fap-stat-card">
            <div className="fap-stat-value">{summary.unknown_faces ?? 0}</div>
            <div className="fap-stat-label">Unknown Faces</div>
          </div>
        </div>
      )}

      {error && (
        <div className="fap-error">
          {error}
          <button onClick={() => setError('')}>✕</button>
        </div>
      )}

      {/* Tabs */}
      <div className="fap-tabs">
        {['captures', 'recognitions', 'watchlist', 'register'].map((tab) => (
          <button
            key={tab}
            className={`fap-tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'captures' && '📸 '}
            {tab === 'recognitions' && '🔍 '}
            {tab === 'watchlist' && '⚠️ '}
            {tab === 'register' && '➕ '}
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="fap-content">

        {/* Captures */}
        {activeTab === 'captures' && (
          <div className="fap-captures-grid">
            {captures.length === 0 ? (
              <div className="fap-empty">
                No face captures yet. Enable AI detection on a camera to start capturing.
              </div>
            ) : captures.map((cap) => (
              <div key={cap.id} className="fap-capture-card">
                {cap.image_path ? (
                  <img
                    src={`${API_BASE_URL}/api/face/captures/image/${cap.id}`}
                    alt="face capture"
                    className="fap-capture-img"
                    onError={(e) => { e.target.style.display = 'none'; }}
                  />
                ) : (
                  <div className="fap-capture-placeholder">👤</div>
                )}
                <div className="fap-capture-meta">
                  <div className="fap-capture-id">
                    {cap.tagged_as
                      ? <strong>{cap.tagged_as}</strong>
                      : <span className="fap-unknown">Unknown</span>
                    }
                  </div>
                  <div className="fap-capture-time">{formatTime(cap.timestamp)}</div>
                  <div className="fap-capture-camera">📷 {cap.stream_id}</div>
                  <div className="fap-capture-conf">
                    Conf: {cap.confidence ? `${(cap.confidence * 100).toFixed(0)}%` : '—'}
                  </div>
                  {cap.blur_score && (
                    <div className="fap-capture-blur">Blur: {cap.blur_score.toFixed(0)}</div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Recognitions */}
        {activeTab === 'recognitions' && (
          <div className="fap-table-container">
            <table className="fap-table">
              <thead>
                <tr>
                  <th>Identity</th>
                  <th>Category</th>
                  <th>Confidence</th>
                  <th>Camera</th>
                  <th>Time</th>
                  <th>Watchlisted</th>
                </tr>
              </thead>
              <tbody>
                {recognitions.length === 0 ? (
                  <tr><td colSpan={6} className="fap-empty">No recognition events yet.</td></tr>
                ) : recognitions.map((rec) => (
                  <tr key={rec.id} className={rec.is_watchlisted ? 'fap-row-danger' : ''}>
                    <td><strong>{rec.identity}</strong></td>
                    <td>{getCategoryBadge(rec.category)}</td>
                    <td>{rec.confidence ? `${(rec.confidence * 100).toFixed(1)}%` : '—'}</td>
                    <td>📷 {rec.stream_id}</td>
                    <td>{formatTime(rec.timestamp)}</td>
                    <td>{rec.is_watchlisted ? '🚨 YES' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Watchlist */}
        {activeTab === 'watchlist' && (
          <div>
            <div className="fap-watchlist-header">
              <span>Criminal / Suspect Watchlist ({watchlist.length})</span>
              <button
                className="fap-add-btn"
                onClick={() => setWlShowForm(!wlShowForm)}
              >
                {wlShowForm ? '✕ Cancel' : '+ Add Entry'}
              </button>
            </div>

            {wlShowForm && (
              <div className="fap-wl-form">
                <input
                  className="fap-input"
                  placeholder="Full Name *"
                  value={wlName}
                  onChange={(e) => setWlName(e.target.value)}
                />
                <input
                  className="fap-input"
                  placeholder="Alias (optional)"
                  value={wlAlias}
                  onChange={(e) => setWlAlias(e.target.value)}
                />
                <select
                  className="fap-input"
                  value={wlCategory}
                  onChange={(e) => setWlCategory(e.target.value)}
                >
                  <option value="suspect">Suspect</option>
                  <option value="criminal">Criminal</option>
                  <option value="person">Person of Interest</option>
                  <option value="staff">Staff</option>
                </select>
                <textarea
                  className="fap-input fap-textarea"
                  placeholder="Notes (optional)"
                  value={wlNotes}
                  onChange={(e) => setWlNotes(e.target.value)}
                />
                <button
                  className="fap-submit-btn"
                  onClick={handleAddWatchlist}
                  disabled={!wlName.trim()}
                >
                  Add to Watchlist
                </button>
              </div>
            )}

            <div className="fap-wl-list">
              {watchlist.length === 0 ? (
                <div className="fap-empty">No watchlist entries. Add suspects or criminals above.</div>
              ) : watchlist.map((entry) => (
                <div key={entry.id} className="fap-wl-card">
                  <div className="fap-wl-avatar">
                    {entry.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="fap-wl-info">
                    <div className="fap-wl-name">{entry.name}</div>
                    {entry.alias && <div className="fap-wl-alias">aka {entry.alias}</div>}
                    {getCategoryBadge(entry.category)}
                    {entry.notes && <div className="fap-wl-notes">{entry.notes}</div>}
                  </div>
                  <button
                    className="fap-wl-remove"
                    onClick={() => handleRemoveWatchlist(entry.id)}
                    title="Remove from watchlist"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Register face */}
        {activeTab === 'register' && (
          <div className="fap-register-form">
            <h3 className="fap-register-title">
              Register Face for Recognition
            </h3>
            <p className="fap-register-hint">
              Upload a clear, front-facing photo. The system will extract a face encoding
              and add it to the recognition database (Kaggle gallery seeding — Option A).
            </p>
            <div className="fap-register-fields">
              <label className="fap-label">Full Name *</label>
              <input
                className="fap-input"
                placeholder="e.g. John Doe"
                value={regName}
                onChange={(e) => setRegName(e.target.value)}
              />
              <label className="fap-label">Category</label>
              <select
                className="fap-input"
                value={regCategory}
                onChange={(e) => setRegCategory(e.target.value)}
              >
                <option value="person">Person</option>
                <option value="staff">Staff</option>
                <option value="suspect">Suspect</option>
                <option value="criminal">Criminal</option>
              </select>
              <label className="fap-label">Photo *</label>
              <input
                className="fap-input"
                type="file"
                accept="image/*"
                onChange={(e) => setRegFile(e.target.files[0])}
              />
              <button
                className="fap-submit-btn fap-register-btn"
                onClick={handleRegisterFace}
                disabled={!regName.trim() || !regFile || regLoading}
              >
                {regLoading ? '⏳ Registering...' : '📸 Register Face'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FaceAnalyticsPanel;
