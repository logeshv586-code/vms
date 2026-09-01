import React, { useState, useEffect, useCallback } from 'react';
import './GestureAnalyticsPanel.css';
import { API_BASE_URL } from '../../utils/apiConfig';

const CATEGORY_META = {
  help: { label: 'SOS / Help', color: '#ff4444', icon: '🆘' },
  threat: { label: 'Threat', color: '#ff8800', icon: '⚠️' },
  asl: { label: 'ASL', color: '#4488ff', icon: '🤟' },
  accessibility: { label: 'Accessibility', color: '#44cc88', icon: '♿' },
  neutral: { label: 'Neutral', color: '#888', icon: '👋' },
};

const GestureAnalyticsPanel = ({ streamId = null }) => {
  const [activeTab, setActiveTab] = useState('live');
  const [gestures, setGestures] = useState([]);
  const [summary, setSummary] = useState(null);
  const [vocabulary, setVocabulary] = useState({});
  const [aslSequence, setAslSequence] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const streamParam = streamId ? `?stream_id=${streamId}` : '';

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const catParam = selectedCategory ? `&category=${selectedCategory}` : '';
      const [gestRes, sumRes, aslRes, vocabRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/gestures/log${streamParam ? streamParam + catParam : (catParam ? '?' + catParam.slice(1) : '')}&limit=100`),
        fetch(`${API_BASE_URL}/api/gestures/analytics${streamParam}`),
        fetch(`${API_BASE_URL}/api/gestures/log/asl${streamParam}&limit=100`),
        fetch(`${API_BASE_URL}/api/gestures/vocabulary`),
      ]);

      if (gestRes.ok) {
        const d = await gestRes.json();
        setGestures(d.gestures || []);
      }
      if (sumRes.ok) {
        const d = await sumRes.json();
        setSummary(d.summary);
      }
      if (aslRes.ok) {
        const d = await aslRes.json();
        setAslSequence(d.asl_sequence || '');
      }
      if (vocabRes.ok) {
        const d = await vocabRes.json();
        setVocabulary(d.vocabulary || {});
      }
    } catch (e) {
      setError('Failed to fetch gesture data.');
    } finally {
      setLoading(false);
    }
  }, [streamId, selectedCategory]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const formatTime = (ts) => ts ? new Date(ts * 1000).toLocaleTimeString() : '-';

  const getCategoryMeta = (cat) => CATEGORY_META[cat] || CATEGORY_META.neutral;

  return (
    <div className="gesture-analytics-panel">
      {/* Header */}
      <div className="gap-header">
        <div className="gap-header-left">
          <span className="gap-icon">🤲</span>
          <h2 className="gap-title">Gesture Analytics</h2>
          {streamId && <span className="gap-stream-badge">{streamId}</span>}
        </div>
        <button className="gap-refresh-btn" onClick={fetchData} disabled={loading}>
          {loading ? '⏳' : '🔄'} Refresh
        </button>
      </div>

      {/* Alert strip for recent SOS */}
      {summary && summary.sos_help_signals > 0 && (
        <div className="gap-sos-strip">
          🆘 <strong>{summary.sos_help_signals}</strong> SOS / help signal{summary.sos_help_signals > 1 ? 's' : ''} detected
        </div>
      )}

      {/* Summary cards */}
      {summary && (
        <div className="gap-summary-grid">
          <div className="gap-stat-card">
            <div className="gap-stat-value">{summary.total_gestures ?? 0}</div>
            <div className="gap-stat-label">Total Gestures</div>
          </div>
          <div className="gap-stat-card gap-stat-sos">
            <div className="gap-stat-value">🆘 {summary.sos_help_signals ?? 0}</div>
            <div className="gap-stat-label">SOS / Help</div>
          </div>
          <div className="gap-stat-card gap-stat-threat">
            <div className="gap-stat-value">⚠️ {summary.threat_signals ?? 0}</div>
            <div className="gap-stat-label">Threats</div>
          </div>
          <div className="gap-stat-card gap-stat-asl">
            <div className="gap-stat-value">🤟 {summary.asl_events ?? 0}</div>
            <div className="gap-stat-label">ASL Events</div>
          </div>
        </div>
      )}

      {error && (
        <div className="gap-error">
          {error} <button onClick={() => setError('')}>✕</button>
        </div>
      )}

      {/* Tabs */}
      <div className="gap-tabs">
        {['live', 'asl', 'vocabulary'].map((tab) => (
          <button
            key={tab}
            className={`gap-tab ${activeTab === tab ? 'active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'live' && '📡 '}
            {tab === 'asl' && '🤟 '}
            {tab === 'vocabulary' && '📖 '}
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
            {tab === 'live' && gestures.length > 0 && (
              <span className="gap-tab-count">{gestures.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="gap-content">

        {/* Live feed */}
        {activeTab === 'live' && (
          <div>
            {/* Category filter */}
            <div className="gap-filter-row">
              <span className="gap-filter-label">Filter:</span>
              {['', 'help', 'threat', 'asl', 'accessibility', 'neutral'].map((cat) => (
                <button
                  key={cat}
                  className={`gap-filter-btn ${selectedCategory === cat ? 'active' : ''}`}
                  style={cat && selectedCategory === cat ? { borderColor: getCategoryMeta(cat).color, color: getCategoryMeta(cat).color } : {}}
                  onClick={() => setSelectedCategory(cat)}
                >
                  {cat ? `${getCategoryMeta(cat).icon} ${getCategoryMeta(cat).label}` : '🔍 All'}
                </button>
              ))}
            </div>

            {/* Gesture log */}
            <div className="gap-gesture-list">
              {gestures.length === 0 ? (
                <div className="gap-empty">
                  No gesture events. Enable AI detection and wave at the camera.
                </div>
              ) : gestures.map((g) => {
                const meta = getCategoryMeta(g.category);
                return (
                  <div
                    key={g.id}
                    className={`gap-gesture-item gap-cat-${g.category}`}
                    style={{ borderLeftColor: meta.color }}
                  >
                    <div className="gap-gesture-icon">{meta.icon}</div>
                    <div className="gap-gesture-info">
                      <div className="gap-gesture-label">
                        {g.gesture.replace('asl_', 'ASL: ').replace(/_/g, ' ')}
                        {g.asl_letter && (
                          <span className="gap-asl-letter">{g.asl_letter}</span>
                        )}
                      </div>
                      <div className="gap-gesture-meta">
                        <span className="gap-badge" style={{ background: meta.color }}>
                          {meta.label}
                        </span>
                        <span className="gap-camera">📷 {g.stream_id}</span>
                        <span className="gap-time">🕐 {formatTime(g.timestamp)}</span>
                        {g.confidence && (
                          <span className="gap-conf">{(g.confidence * 100).toFixed(0)}%</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ASL sequence */}
        {activeTab === 'asl' && (
          <div>
            <div className="gap-asl-panel">
              <div className="gap-asl-header">
                <span>🤟 ASL Letter Sequence (last 50 detections)</span>
              </div>
              <div className="gap-asl-sequence">
                {aslSequence ? (
                  aslSequence.split('').map((letter, i) => (
                    <span key={i} className="gap-asl-char">{letter}</span>
                  ))
                ) : (
                  <span className="gap-empty">No ASL letters detected yet.</span>
                )}
              </div>
              {aslSequence && (
                <div className="gap-asl-word">
                  Detected text: <strong className="gap-asl-text">{aslSequence}</strong>
                </div>
              )}
            </div>

            {/* ASL reference guide */}
            <div className="gap-asl-guide">
              <h4 className="gap-asl-guide-title">Supported Gestures</h4>
              <div className="gap-asl-categories">
                {Object.entries(CATEGORY_META).filter(([k]) => k !== 'neutral').map(([cat, meta]) => (
                  <div key={cat} className="gap-asl-cat-card" style={{ borderColor: meta.color + '55' }}>
                    <div className="gap-asl-cat-title" style={{ color: meta.color }}>
                      {meta.icon} {meta.label}
                    </div>
                    <div className="gap-asl-cat-list">
                      {Object.entries(vocabulary)
                        .filter(([, v]) => v.category === cat)
                        .slice(0, cat === 'asl' ? 26 : 10)
                        .map(([key, val]) => (
                          <span key={key} className="gap-asl-chip" title={val.description}>
                            {val.emoji} {key.replace('asl_', '').replace(/_/g, ' ')}
                          </span>
                        ))
                      }
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Vocabulary */}
        {activeTab === 'vocabulary' && (
          <div className="gap-vocab">
            <div className="gap-vocab-grid">
              {Object.entries(vocabulary).map(([key, val]) => {
                const meta = getCategoryMeta(val.category);
                return (
                  <div key={key} className="gap-vocab-card" style={{ borderTopColor: meta.color }}>
                    <div className="gap-vocab-emoji">{val.emoji || '👋'}</div>
                    <div className="gap-vocab-name">
                      {key.replace('asl_', 'ASL ').replace(/_/g, ' ')}
                    </div>
                    <div className="gap-vocab-desc">{val.description}</div>
                    <span className="gap-badge" style={{ background: meta.color }}>
                      {meta.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GestureAnalyticsPanel;
