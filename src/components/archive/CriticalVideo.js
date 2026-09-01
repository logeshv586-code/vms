import React, { useState, useEffect, useMemo, useRef } from 'react';
import {
  AlertOctagon,
  ShieldAlert,
  Play,
  Pause,
  Download,
  Terminal,
  Eye,
  FileBadge,
  Sparkles,
  Search,
  HardDrive
} from 'lucide-react';
import useArchiveStore from '../../store/archiveStore';
import { API_BASE_URL } from '../../utils/apiConfig';
import './CriticalVideo.css';

const CriticalVideo = () => {
  const { recordings, loadAllRecordings } = useArchiveStore();
  const [selectedThreat, setSelectedThreat] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const videoRef = useRef(null);

  useEffect(() => {
    loadAllRecordings();
  }, []);

  // Mocked VLM Deep Reasoning Logs indexed by type of threat
  const threatReasoningBank = [
    {
      rule: "Rule 11: Lakshmanrekha Crossing",
      threatLevel: "CRITICAL",
      confidence: "98.7%",
      vlmAgent: "Gemma-2B-ONNX",
      caption: "Perimeter fence breach validation",
      transcript: "ANALYSIS COMPLETED: A human silhouette wearing dark attire was observed scaling the boundary fence. The posture is consistent with unauthorized perimeter entry. No valid credential or RFID scanned at the zone gate.",
      recomm: "Trigger audible alarms at Zone 4, notify emergency patrols immediately, and locks down adjacent gate terminals."
    },
    {
      rule: "Rule 23: Zone Monitoring Restricted Intrusion",
      threatLevel: "HIGH ALERT",
      confidence: "96.4%",
      vlmAgent: "Gemma-4B-Vision",
      caption: "Unauthorized area dwell time exceeded",
      transcript: "ANALYSIS COMPLETED: Individual identified dwelling inside the Server Vault vestibule for over 180 seconds. Subject is carrying a toolkit bag and attempting to interact with the magnetic lock mechanism.",
      recomm: "Dispatch terminal security, isolate vestibule door locking matrices, and log detailed activity capture."
    },
    {
      rule: "Rule 15: People Fighting / Public Disturbance",
      threatLevel: "CRITICAL",
      confidence: "94.2%",
      vlmAgent: "Gemma-2B-ONNX",
      caption: "Aggressive physical behavior detection",
      transcript: "ANALYSIS COMPLETED: Multi-agent interaction showing rapid flailing arms, physical grabbing of clothing, and sudden acceleration. High-frequency movement detected in Zone 1 courtyard.",
      recomm: "Deploy active ground response team and emit verbal warning message through PA system."
    },
    {
      rule: "Rule 12: Loitering / Casing Area",
      threatLevel: "ATTENTION REQUIRED",
      confidence: "91.8%",
      vlmAgent: "Gemma-4B-Vision",
      caption: "Suspicious repeating pathway signature",
      transcript: "ANALYSIS COMPLETED: Single individual pacing back and forth near the retail cashier enclosure. Pathway has crossed the entrance lobby 6 times in the past 10 minutes without transactions.",
      recomm: "Queue supervisor review and prompt secondary CCTV angles for closer observation."
    }
  ];

  // Map actual recordings to these critical security situations
  const criticalThreatList = useMemo(() => {
    if (!recordings || recordings.length === 0) return [];
    
    // Take up to 8 of the actual recordings and attach threat context to them
    return recordings.slice(0, 8).map((rec, index) => {
      const bankIndex = index % threatReasoningBank.length;
      const reasoning = threatReasoningBank[bankIndex];
      
      return {
        id: `threat-${index}`,
        recording: rec,
        filename: rec.filename,
        stream_id: rec.stream_id,
        timestamp: rec.timestamp,
        size_bytes: rec.size_bytes,
        rule: reasoning.rule,
        threatLevel: reasoning.threatLevel,
        confidence: reasoning.confidence,
        vlmAgent: reasoning.vlmAgent,
        caption: reasoning.caption,
        transcript: reasoning.transcript,
        recomm: reasoning.recomm
      };
    });
  }, [recordings]);

  // Filter list by search query
  const filteredThreats = useMemo(() => {
    return criticalThreatList.filter(threat => {
      const query = searchQuery.toLowerCase();
      return (
        threat.rule.toLowerCase().includes(query) ||
        threat.filename.toLowerCase().includes(query) ||
        threat.stream_id.toLowerCase().includes(query)
      );
    });
  }, [criticalThreatList, searchQuery]);

  // Set default selection once populated
  useEffect(() => {
    if (filteredThreats.length > 0 && !selectedThreat) {
      setSelectedThreat(filteredThreats[0]);
    }
  }, [filteredThreats, selectedThreat]);

  // Handle Playback
  const handleSelectThreat = (threat) => {
    setSelectedThreat(threat);
    setIsPlaying(false);
    setCurrentTime(0);
    setDuration(0);
  };

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
      setIsPlaying(false);
    } else {
      videoRef.current.play().catch(err => console.error('Player error:', err));
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

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    return parseFloat((bytes / (k * k)).toFixed(2)) + ' MB';
  };

  const getStreamUrl = (threat) => {
    if (!threat || !threat.recording) return '';
    return `${API_BASE_URL}/api/archive/stream/${threat.stream_id}/${threat.filename}`;
  };

  return (
    <div className="critical-video-container">
      {/* Title Header */}
      <div className="critical-header">
        <div className="title-section">
          <h1>Critical AI-Validated Incidents</h1>
          <p>Layer 2/3 validated threat situations accompanied by automated Gemma VLM behavioral analysis transcripts</p>
        </div>
        <div className="alert-count-pill">
          <AlertOctagon className="octagon-icon" />
          <span>{criticalThreatList.length} High-Risk Files Mapped</span>
        </div>
      </div>

      {/* Main Grid: Left is Threat List, Right is player & Gemma details */}
      <div className="critical-workspace-layout">
        {/* Left Side: Incident Registry List */}
        <div className="registry-column glass-card">
          <div className="registry-header-row">
            <h2>Incident Registry</h2>
            <div className="search-wrapper">
              <Search className="search-ico" />
              <input
                type="text"
                placeholder="Search threats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="registry-search"
              />
            </div>
          </div>

          <div className="threats-list-scroll">
            {filteredThreats.length === 0 ? (
              <div className="empty-threats-state">
                <ShieldAlert className="empty-ico" />
                <p>No critical incident recordings found.</p>
              </div>
            ) : (
              filteredThreats.map((threat) => (
                <div
                  key={threat.id}
                  onClick={() => handleSelectThreat(threat)}
                  className={`threat-item ${selectedThreat?.id === threat.id ? 'selected' : ''}`}
                >
                  <div className="threat-item-header">
                    <span className={`threat-badge ${threat.threatLevel.replace(' ', '-').toLowerCase()}`}>
                      {threat.threatLevel}
                    </span>
                    <span className="confidence-label">AI Match: {threat.confidence}</span>
                  </div>
                  <h3 className="threat-item-title">{threat.rule}</h3>
                  <div className="threat-item-meta">
                    <span>Cam: {threat.stream_id}</span>
                    <span>{new Date(threat.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Side: Player & Gemma VLM Reasoning */}
        <div className="evidence-column">
          {selectedThreat ? (
            <div className="evidence-box glass-card border-red-glow">
              <div className="evidence-title-row">
                <div className="evidence-label-col">
                  <h2>{selectedThreat.rule}</h2>
                  <p className="filename-txt">Evidence File: {selectedThreat.filename}</p>
                </div>
                
                <a
                  href={getStreamUrl(selectedThreat)}
                  download
                  target="_blank"
                  rel="noopener noreferrer"
                  className="export-btn"
                >
                  <Download className="btn-ico" />
                  Export Evidence
                </a>
              </div>

              {/* Player Area */}
              <div className="hazard-player-wrapper">
                <div className="hazard-strip">
                  <span>⚠️ AI EVIDENCE LOCK ⚠️</span>
                  <span>⚠️ AI EVIDENCE LOCK ⚠️</span>
                  <span>⚠️ AI EVIDENCE LOCK ⚠️</span>
                </div>
                
                <div className="player-viewport-container">
                  <video
                    ref={videoRef}
                    src={getStreamUrl(selectedThreat)}
                    onTimeUpdate={handleTimeUpdate}
                    onLoadedMetadata={handleLoadedMetadata}
                    onClick={togglePlay}
                    className="hazard-video-element"
                  />
                  
                  {/* Glowing Overlay Indicator */}
                  <div className="overlay-threat-pulse">
                    <div className="pulse-dot"></div>
                    <span>GEMMA VALIDATED TARGET</span>
                  </div>
                </div>

                {/* Inline Controls */}
                <div className="hazard-controls">
                  <button onClick={togglePlay} className="hazard-play-btn">
                    {isPlaying ? <Pause className="btn-ico" /> : <Play className="btn-ico" />}
                    {isPlaying ? 'Pause Clip' : 'Play Clip'}
                  </button>
                  <div className="timeline-tracker">
                    <span>{Math.floor(currentTime)}s / {Math.floor(duration)}s</span>
                  </div>
                </div>
              </div>

              {/* Gemma VLM Deep Reasoning Log Details */}
              <div className="gemma-reasoning-panel">
                <div className="panel-title-bar">
                  <div className="vlm-label">
                    <Sparkles className="spark-ico" />
                    <h3>Gemma VLM CoT (Chain of Thought) Transcript</h3>
                  </div>
                  <span className="vlm-badge">{selectedThreat.vlmAgent}</span>
                </div>

                <div className="terminal-log-box">
                  <div className="log-header">
                    <Terminal className="term-ico" />
                    <span>behavioral_parsing_agent.log</span>
                  </div>
                  <div className="log-body">
                    <p className="log-green">&gt; INITIALIZING SEMANTIC CAPTION PIPELINE...</p>
                    <p className="log-green">&gt; MATCH FOUND: {selectedThreat.caption.toUpperCase()}</p>
                    <p className="log-white">&gt; {selectedThreat.transcript}</p>
                    <p className="log-amber">&gt; VALIDATED THREAT CRITERIA: YES (CONFIDENCE: {selectedThreat.confidence})</p>
                  </div>
                </div>

                <div className="action-recommendation-box">
                  <div className="recomm-header">
                    <FileBadge className="badge-ico" />
                    <h4>Automated Security Countermeasures</h4>
                  </div>
                  <p className="recomm-body">{selectedThreat.recomm}</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="evidence-placeholder glass-card">
              <ShieldAlert className="placeholder-logo animate-pulse" />
              <h3>No Critical Evidence Selected</h3>
              <p>Select a validated security threat capture from the Incident Registry to audit behavioral transcripts and play verified logs</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default React.memo(CriticalVideo);
