import React, { useState, useEffect, useMemo } from 'react';
import {
  HardDrive,
  Clock,
  Activity,
  Video,
  AlertTriangle,
  TrendingUp,
  FileText,
  Search,
  ChevronRight,
  RefreshCw,
  Server
} from 'lucide-react';
import useArchiveStore from '../../store/archiveStore';
import { API_BASE_URL } from '../../utils/apiConfig';
import './RecordingReport.css';

const RecordingReport = () => {
  const {
    recordings,
    loadAllRecordings,
    getRecordingStats,
    isLoading: storeLoading
  } = useArchiveStore();

  const [activeRecorders, setActiveRecorders] = useState([]);
  const [eventStats, setEventStats] = useState([]);
  const [eventLoading, setEventLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCameraFilter, setSelectedCameraFilter] = useState('all');

  // Load all statistics
  const loadReportData = async () => {
    try {
      // 1. Load recordings
      await loadAllRecordings(true);

      // 2. Load active recorders from current endpoint
      const currentRes = await fetch(`${API_BASE_URL}/api/archive/current`);
      if (currentRes.ok) {
        const data = await currentRes.json();
        setActiveRecorders(data.current_recordings || []);
      }

      // 3. Load event statistics
      setEventLoading(true);
      const eventRes = await fetch(`${API_BASE_URL}/api/augment/events/statistics`);
      if (eventRes.ok) {
        const eventData = await eventRes.json();
        setEventStats(eventData.data?.statistics || []);
      }
    } catch (error) {
      console.error('Error loading report data:', error);
    } finally {
      setEventLoading(false);
    }
  };

  useEffect(() => {
    loadReportData();
  }, []);

  // Compute stats
  const stats = useMemo(() => {
    return getRecordingStats();
  }, [recordings, getRecordingStats]);

  const storageUsagePercent = useMemo(() => {
    const totalAllocatedBytes = 2 * 1024 * 1024 * 1024 * 1024; // Mock 2 TB Allocated
    if (!stats.totalSize) return 0;
    return Math.min(parseFloat(((stats.totalSize / totalAllocatedBytes) * 100).toFixed(2)), 100);
  }, [stats]);

  // Unique camera list for filter dropdown
  const uniqueCameras = useMemo(() => {
    const cameras = new Set();
    recordings.forEach(rec => {
      if (rec.stream_id) cameras.add(rec.stream_id);
    });
    return Array.from(cameras);
  }, [recordings]);

  // Filtered recording history table
  const filteredRecordings = useMemo(() => {
    return recordings.filter(rec => {
      // IP/Camera Filter
      if (selectedCameraFilter !== 'all' && rec.stream_id !== selectedCameraFilter) {
        return false;
      }
      // Search Query Filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        const filenameMatch = rec.filename?.toLowerCase().includes(query);
        const streamMatch = rec.stream_id?.toLowerCase().includes(query);
        return filenameMatch || streamMatch;
      }
      return true;
    });
  }, [recordings, selectedCameraFilter, searchQuery]);

  // Total security events count
  const totalEventsCount = useMemo(() => {
    return eventStats.reduce((sum, item) => sum + (item.count || 0), 0);
  }, [eventStats]);

  // Format file size helper
  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleOpenPlayback = (recording) => {
    // Navigate directly to standard video streaming endpoint in a clean separate window
    const url = `${API_BASE_URL}/api/archive/stream/${recording.stream_id}/${recording.filename}`;
    window.open(url, '_blank');
  };

  const isPageLoading = storeLoading || eventLoading;

  return (
    <div className="recording-report-container">
      {/* Title Header */}
      <div className="report-header">
        <div className="title-section">
          <h1>Recording Telemetry & History</h1>
          <p>Complete historical activity, physical storage allocations, and security event frequencies</p>
        </div>
        <button 
          onClick={loadReportData} 
          className="refresh-btn" 
          disabled={isPageLoading}
        >
          <RefreshCw className={`refresh-icon ${isPageLoading ? 'spinning' : ''}`} />
          Refresh Stats
        </button>
      </div>

      {/* Storage & Telemetry Metrics Cards */}
      <div className="report-metrics-grid">
        {/* Card 1: Storage Allocation (Circular Progress) */}
        <div className="metric-card glass-card storage-card">
          <div className="card-header">
            <h3>SAN Storage Utilization</h3>
            <HardDrive className="header-icon cyan-glow" />
          </div>
          <div className="storage-body">
            <div className="circle-progress-wrapper">
              <svg className="circle-svg" viewBox="0 0 100 100">
                <circle className="circle-bg" cx="50" cy="50" r="40" />
                <circle 
                  className="circle-fill" 
                  cx="50" 
                  cy="50" 
                  r="40" 
                  style={{
                    strokeDasharray: '251.2',
                    strokeDashoffset: `${251.2 - (251.2 * storageUsagePercent) / 100}`
                  }}
                />
              </svg>
              <div className="circle-inner-label">
                <span className="percent-val">{storageUsagePercent}%</span>
                <span className="percent-sub">Used</span>
              </div>
            </div>
            <div className="storage-info-labels">
              <div className="label-item">
                <span className="dot dot-cyan"></span>
                <div className="text-col">
                  <span className="label-title">Occupied Archive Space</span>
                  <span className="label-value">{formatBytes(stats.totalSize)}</span>
                </div>
              </div>
              <div className="label-item">
                <span className="dot dot-gray"></span>
                <div className="text-col">
                  <span className="label-title">Total Allocated Capacity</span>
                  <span className="label-value">2.00 TB</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Card 2: Active Recorders */}
        <div className="metric-card glass-card recorder-count-card">
          <div className="card-header">
            <h3>Active Recording Feeds</h3>
            <Video className="header-icon green-glow" />
          </div>
          <div className="card-body large-number-body">
            <div className="big-stat-section">
              <span className="big-stat-num">{activeRecorders.length}</span>
              <span className="big-stat-label">Streams Writing Now</span>
            </div>
            <div className="sub-stat-row">
              <div className="sub-stat-item">
                <span className="sub-stat-num">{uniqueCameras.length}</span>
                <span className="sub-stat-label">Total Channels</span>
              </div>
              <div className="sub-stat-item">
                <span className="sub-stat-num">{stats.totalRecordings}</span>
                <span className="sub-stat-label">Past Segments</span>
              </div>
            </div>
          </div>
        </div>

        {/* Card 3: Security Detections */}
        <div className="metric-card glass-card event-frequency-card">
          <div className="card-header">
            <h3>Recorded Rule Violations</h3>
            <AlertTriangle className="header-icon amber-glow" />
          </div>
          <div className="card-body large-number-body">
            <div className="big-stat-section">
              <span className="big-stat-num">{totalEventsCount}</span>
              <span className="big-stat-label">AI Detections Saved</span>
            </div>
            <div className="threat-breakdown">
              <div className="threat-bar-container">
                <div className="threat-bar-fill" style={{ width: '85%' }}></div>
              </div>
              <span className="threat-caption">Peak Activity: 12:00 - 15:00 UTC</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Multi-grid (Active Recorders Status & Rule Frequencies) */}
      <div className="dashboard-subgrid">
        {/* Left Column: Live Active Recorders Status */}
        <div className="grid-card glass-card active-status-grid">
          <div className="card-title-row">
            <h2>Active Recorder Health</h2>
            <span className="status-live-pill">
              <span className="live-dot"></span>
              Live Feed Monitoring
            </span>
          </div>
          <div className="status-table-container">
            {activeRecorders.length === 0 ? (
              <div className="empty-inner-state">
                <Server className="empty-icon animate-pulse" />
                <p>No active recording processes running.</p>
              </div>
            ) : (
              <table className="report-table">
                <thead>
                  <tr>
                    <th>Camera/IP</th>
                    <th>Resolution</th>
                    <th>FPS</th>
                    <th>Bitrate</th>
                    <th>Active Session</th>
                  </tr>
                </thead>
                <tbody>
                  {activeRecorders.map((rec) => (
                    <tr key={rec.stream_id}>
                      <td className="camera-td">
                        <span className="cam-name">{rec.collection_name}</span>
                        <span className="cam-ip">{rec.camera_ip}</span>
                      </td>
                      <td>1920x1080</td>
                      <td>25 fps</td>
                      <td>2.4 Mbps</td>
                      <td>
                        <span className="duration-pill">
                          {Math.floor(rec.duration_seconds / 60)}m {rec.duration_seconds % 60}s
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right Column: AI Rule Violation Distribution */}
        <div className="grid-card glass-card event-distribution-grid">
          <div className="card-title-row">
            <h2>AI Detection Event Ratios</h2>
            <TrendingUp className="card-accent-icon" />
          </div>
          <div className="bar-chart-container">
            {eventStats.length === 0 ? (
              <div className="empty-inner-state">
                <Activity className="empty-icon" />
                <p>No security event logs captured.</p>
              </div>
            ) : (
              <div className="bar-list">
                {eventStats.map((item, index) => {
                  // Compute percentage relative to total events
                  const pct = totalEventsCount > 0 ? (item.count / totalEventsCount) * 100 : 0;
                  return (
                    <div key={index} className="chart-row">
                      <div className="chart-labels">
                        <span className="item-label">{item.event_name}</span>
                        <span className="item-count">{item.count} alerts</span>
                      </div>
                      <div className="bar-wrapper">
                        <div 
                          className="bar-filled" 
                          style={{ 
                            width: `${pct}%`,
                            background: index % 2 === 0 ? 'linear-gradient(90deg, #00f2fe, #4facfe)' : 'linear-gradient(90deg, #ff0844, #ffb199)'
                          }}
                        ></div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Filterable Recording History List */}
      <div className="history-section-card glass-card">
        <div className="history-section-header">
          <div className="history-title">
            <h2>Historical Archives List</h2>
            <p>Select and open any historical video segment recorded in the pipeline</p>
          </div>
          
          <div className="history-filters">
            {/* Camera selector filter */}
            <div className="filter-input-group">
              <Search className="search-icon" />
              <input
                type="text"
                placeholder="Search segments..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="search-input"
              />
            </div>
            
            <select
              value={selectedCameraFilter}
              onChange={(e) => setSelectedCameraFilter(e.target.value)}
              className="camera-dropdown"
            >
              <option value="all">All Channels</option>
              {uniqueCameras.map(cam => (
                <option key={cam} value={cam}>{cam}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="history-table-container">
          {filteredRecordings.length === 0 ? (
            <div className="no-history-state">
              <FileText className="empty-icon" />
              <h3>No Archive Segments Found</h3>
              <p>Try resetting filters or checking camera continuous recording state.</p>
            </div>
          ) : (
            <table className="history-table">
              <thead>
                <tr>
                  <th>Recording Filename</th>
                  <th>Camera Channel ID</th>
                  <th>Creation Date</th>
                  <th>Segment Size</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredRecordings.map((rec, index) => (
                  <tr key={index} className="history-row-item">
                    <td className="filename-td">
                      <span className="file-icon-badge">MP4</span>
                      <span className="file-name-txt">{rec.filename}</span>
                    </td>
                    <td className="stream-id-td">{rec.stream_id}</td>
                    <td>{new Date(rec.timestamp).toLocaleString()}</td>
                    <td>{formatBytes(rec.size_bytes)}</td>
                    <td>
                      <button 
                        onClick={() => handleOpenPlayback(rec)} 
                        className="play-row-btn"
                      >
                        Launch Player
                        <ChevronRight className="chevron-btn-icon" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

export default React.memo(RecordingReport);
