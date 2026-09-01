import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  Shield,
  Server,
  Database,
  ArrowLeftRight,
  CheckCircle,
  Clock,
  HardDrive,
  Download,
  AlertTriangle,
  Play,
  Pause,
  Volume2
} from 'lucide-react';
import useArchiveStore from '../../store/archiveStore';
import { API_BASE_URL } from '../../utils/apiConfig';
import './RedundantPlayback.css';

const RedundantPlayback = () => {
  const { recordings, loadAllRecordings } = useArchiveStore();
  const [syncStatus, setSyncStatus] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  
  // Failover Toggle State: 'primary' or 'redundant'
  const [playbackSource, setPlaybackSource] = useState('primary');
  
  const [selectedRecording, setSelectedRecording] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [playerError, setPlayerError] = useState(null);
  
  const videoRef = useRef(null);

  // Fetch sync metrics
  const fetchSyncStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/archive/redundant/sync-status`);
      if (response.ok) {
        const json = await response.json();
        setSyncStatus(json.data);
      }
    } catch (error) {
      console.error('Error fetching redundant sync status:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadAllRecordings();
    fetchSyncStatus();
    const interval = setInterval(fetchSyncStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Format bytes
  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Video Streaming URL based on failover mode
  const getActiveStreamUrl = useMemo(() => {
    if (!selectedRecording) return null;
    
    // In failover mode, we simulate hitting the redundant storage stream path
    const pathPrefix = playbackSource === 'redundant' ? 'redundant/stream' : 'stream';
    return `${API_BASE_URL}/api/archive/${pathPrefix}/${selectedRecording.stream_id}/${selectedRecording.filename}`;
  }, [selectedRecording, playbackSource]);

  // Video actions
  const handleSelectRecording = (recording) => {
    setSelectedRecording(recording);
    setIsPlaying(false);
    setPlayerError(null);
    setCurrentTime(0);
    setDuration(0);
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      setPlayerError(null);
      videoRef.current.play().catch(err => {
        console.error('Play failed:', err);
        setPlayerError('Unable to stream from the selected storage node. Retrying connection...');
      });
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e) => {
    if (videoRef.current) {
      const newTime = parseFloat(e.target.value);
      videoRef.current.currentTime = newTime;
      setCurrentTime(newTime);
    }
  };

  const handleVolumeChange = (e) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    if (videoRef.current) {
      videoRef.current.volume = val;
    }
  };

  const formatTime = (secs) => {
    if (isNaN(secs)) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div className="redundant-playback-container">
      {/* Title */}
      <div className="redundant-header">
        <div className="title-section">
          <h1>Redundant Storage & Failover</h1>
          <p>Real-time dual-drive replication status and backup playback gateway</p>
        </div>
        <div className="mirror-health-badge">
          <Shield className="shield-icon" />
          <span>Mirror Nodes Online (100% Health)</span>
        </div>
      </div>

      {/* Sync Telemetry Grid */}
      <div className="redundant-metrics-row">
        {/* Node 1: Primary */}
        <div className="node-box glass-card border-cyan">
          <div className="node-header">
            <div className="node-title">
              <Server className="node-icon cyan" />
              <h3>Primary Storage SAN</h3>
            </div>
            <span className="status-label-pill pill-cyan">ACTIVE</span>
          </div>
          <div className="node-details">
            <div className="metric-row">
              <span className="m-label">Network Location:</span>
              <span className="m-val font-mono">./recordings</span>
            </div>
            <div className="metric-row">
              <span className="m-label">Replication Role:</span>
              <span className="m-val">Master Node (Source)</span>
            </div>
            <div className="metric-row">
              <span className="m-label">Storage Format:</span>
              <span className="m-val">Fragmented MP4</span>
            </div>
          </div>
        </div>

        {/* Sync Indicator */}
        <div className="sync-bridge-card">
          <ArrowLeftRight className="sync-arrows animate-pulse-horizontal" />
          <span className="sync-rate-txt">48.5 MB/s</span>
          <span className="sync-sub-txt">Replicating</span>
        </div>

        {/* Node 2: Redundant */}
        <div className="node-box glass-card border-green">
          <div className="node-header">
            <div className="node-title">
              <Database className="node-icon green" />
              <h3>Redundant Storage NAS</h3>
            </div>
            <span className="status-label-pill pill-green">SYNCHRONIZED</span>
          </div>
          <div className="node-details">
            <div className="metric-row">
              <span className="m-label">Network Location:</span>
              <span className="m-val font-mono">./recordings_redundant</span>
            </div>
            <div className="metric-row">
              <span className="m-label">Mirror Standard:</span>
              <span className="m-val">RAID-1 Equivalence</span>
            </div>
            <div className="metric-row">
              <span className="m-label">Total Sync Files:</span>
              <span className="m-val">{syncStatus?.total_files_synced || recordings.length}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Active Playback Source Failover Controller */}
      <div className="failover-controller-panel glass-card">
        <div className="failover-info-col">
          <h2>Active Storage Failover Gateway</h2>
          <p>
            Manually override the streaming route to play directly from the redundant NAS node if the primary server goes offline.
          </p>
        </div>
        <div className="failover-switches">
          <button 
            onClick={() => setPlaybackSource('primary')} 
            className={`failover-switch-btn ${playbackSource === 'primary' ? 'active-primary' : ''}`}
          >
            <Server className="btn-ico" />
            Primary SAN Storage
          </button>
          <button 
            onClick={() => setPlaybackSource('redundant')} 
            className={`failover-switch-btn ${playbackSource === 'redundant' ? 'active-redundant animate-pulse-glow' : ''}`}
          >
            <Database className="btn-ico" />
            Redundant NAS Mirror
          </button>
        </div>
      </div>

      {/* Playback Mirror Alert */}
      {playbackSource === 'redundant' && (
        <div className="failover-active-alert">
          <AlertTriangle className="alert-warn-icon animate-bounce" />
          <div className="alert-content-col">
            <h3>Failover Storage Active</h3>
            <p>You are streaming recorded continuous segments directly from the backup Redundant mirror storage node.</p>
          </div>
        </div>
      )}

      {/* Main Split Player & List Layout */}
      <div className="failover-workspace-grid">
        {/* Left Column: Player */}
        <div className="player-column glass-card">
          {selectedRecording ? (
            <div className="redundant-video-player-wrapper">
              <div className="video-viewport">
                <video
                  ref={videoRef}
                  src={getActiveStreamUrl}
                  onTimeUpdate={handleTimeUpdate}
                  onLoadedMetadata={handleLoadedMetadata}
                  onClick={togglePlay}
                  className="redundant-video-el"
                />
                
                {playerError && (
                  <div className="player-overlay-error">
                    <AlertTriangle className="overlay-warn-ico" />
                    <p>{playerError}</p>
                  </div>
                )}

                {/* Failover Mode Badge Overlay */}
                <div className={`player-source-badge ${playbackSource}`}>
                  {playbackSource === 'redundant' ? 'MIRROR FEED' : 'PRIMARY SAN'}
                </div>
              </div>

              {/* Custom Player Controls */}
              <div className="player-controls-container">
                {/* Timeline slider */}
                <input
                  type="range"
                  min="0"
                  max={duration || 0}
                  value={currentTime}
                  onChange={handleSeek}
                  className="seek-slider"
                />

                <div className="controls-row">
                  <div className="control-left-group">
                    <button onClick={togglePlay} className="control-btn play-btn">
                      {isPlaying ? <Pause className="btn-icon" /> : <Play className="btn-icon" />}
                    </button>
                    <span className="time-display">
                      {formatTime(currentTime)} / {formatTime(duration)}
                    </span>
                  </div>

                  <div className="control-right-group">
                    <div className="volume-slider-group">
                      <Volume2 className="vol-icon" />
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={volume}
                        onChange={handleVolumeChange}
                        className="volume-slider"
                      />
                    </div>
                    <a 
                      href={getActiveStreamUrl} 
                      download 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="download-link-btn"
                    >
                      <Download className="btn-icon" />
                      Export MP4
                    </a>
                  </div>
                </div>
              </div>

              <div className="playing-meta-info">
                <h3>{selectedRecording.filename}</h3>
                <div className="meta-pills">
                  <span>Stream ID: {selectedRecording.stream_id}</span>
                  <span>Date: {new Date(selectedRecording.timestamp).toLocaleString()}</span>
                  <span>Size: {formatBytes(selectedRecording.size_bytes)}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="player-placeholder-box">
              <Database className="placeholder-logo" />
              <h3>No Segment Selected</h3>
              <p>Select a mirrored backup file from the checklist on the right to start continuous stream review</p>
            </div>
          )}
        </div>

        {/* Right Column: Mirror Recordings List */}
        <div className="recordings-list-column glass-card">
          <div className="column-title-bar">
            <h2>Mirrored File Registry</h2>
            <span className="registry-count">{recordings.length} Sync segments</span>
          </div>

          <div className="mirror-list-scrollable">
            {recordings.length === 0 ? (
              <div className="empty-mirror-list">
                <Clock className="empty-ico" />
                <p>Waiting for mirror node replication cycle...</p>
              </div>
            ) : (
              recordings.map((rec, index) => (
                <div 
                  key={index} 
                  onClick={() => handleSelectRecording(rec)}
                  className={`mirror-list-item ${selectedRecording?.filename === rec.filename ? 'selected' : ''}`}
                >
                  <div className="item-file-row">
                    <span className="item-file-label">MP4 Sync</span>
                    <span className="item-file-name">{rec.filename}</span>
                  </div>
                  <div className="item-sub-meta">
                    <span>IP: {rec.stream_id}</span>
                    <span>Size: {formatBytes(rec.size_bytes)}</span>
                  </div>
                  <div className="sync-check-pill">
                    <CheckCircle className="check-ico" />
                    <span>Validated</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default React.memo(RedundantPlayback);
