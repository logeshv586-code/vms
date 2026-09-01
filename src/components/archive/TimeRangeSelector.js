import React, { useState, useEffect } from 'react';
import { Clock, Download, AlertCircle, Scissors, Play, RotateCcw } from 'lucide-react';
import './TimeRangeSelector.css';

const TimeRangeSelector = ({ 
  videoDuration = 0, 
  currentTime = 0,
  onTimeRangeChange, 
  onDownload,
  isExtracting = false 
}) => {
  // Convert time string to seconds
  const timeToSeconds = (timeStr) => {
    if (typeof timeStr === 'number') return timeStr;
    if (!timeStr) return 0;
    const parts = timeStr.toString().split(':').map(Number);
    if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    } else if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    }
    return parseFloat(timeStr) || 0;
  };

  // Convert seconds to HH:MM:SS time string
  const secondsToTime = (totalSeconds) => {
    const secs = Math.max(0, Math.floor(totalSeconds || 0));
    const hours = Math.floor(secs / 3600);
    const minutes = Math.floor((secs % 3600) / 60);
    const seconds = Math.floor(secs % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  const maxDuration = Math.max(videoDuration || 0, 1);

  const [startSec, setStartSec] = useState(0);
  const [endSec, setEndSec] = useState(videoDuration || 0);
  const [startText, setStartText] = useState('00:00:00');
  const [endText, setEndText] = useState(secondsToTime(videoDuration || 0));
  const [error, setError] = useState('');

  // Update range when video duration changes
  useEffect(() => {
    if (videoDuration > 0) {
      setStartSec(0);
      setStartText('00:00:00');
      setEndSec(videoDuration);
      setEndText(secondsToTime(videoDuration));
    }
  }, [videoDuration]);

  // Sync parent notification
  useEffect(() => {
    if (onTimeRangeChange && endSec > startSec) {
      onTimeRangeChange({
        startTime: startText,
        endTime: endText,
        startSeconds: startSec,
        endSeconds: endSec,
        duration: endSec - startSec
      });
    }
  }, [startSec, endSec, startText, endText]);

  // Slider change handlers
  const handleStartSliderChange = (e) => {
    const val = Math.min(parseFloat(e.target.value), endSec - 1);
    setStartSec(val);
    setStartText(secondsToTime(val));
    setError('');
  };

  const handleEndSliderChange = (e) => {
    const val = Math.max(parseFloat(e.target.value), startSec + 1);
    setEndSec(val);
    setEndText(secondsToTime(val));
    setError('');
  };

  // Text input change handlers
  const handleStartTextChange = (e) => {
    const val = e.target.value;
    setStartText(val);
    const parsed = timeToSeconds(val);
    if (!isNaN(parsed) && parsed >= 0 && parsed < endSec) {
      setStartSec(parsed);
      setError('');
    } else if (parsed >= endSec) {
      setError('Start time must be less than end time');
    }
  };

  const handleEndTextChange = (e) => {
    const val = e.target.value;
    setEndText(val);
    const parsed = timeToSeconds(val);
    if (!isNaN(parsed) && parsed > startSec && (videoDuration === 0 || parsed <= videoDuration)) {
      setEndSec(parsed);
      setError('');
    } else if (parsed <= startSec) {
      setError('End time must be after start time');
    }
  };

  const handleDownloadClick = () => {
    if (endSec <= startSec) {
      setError('End time must be after start time');
      return;
    }
    setError('');
    if (onDownload) {
      onDownload({
        startTime: secondsToTime(startSec),
        endTime: secondsToTime(endSec),
        startSeconds: startSec,
        endSeconds: endSec,
        duration: endSec - startSec
      });
    }
  };

  // Quick preset functions
  const setPresetFull = () => {
    setStartSec(0);
    setStartText('00:00:00');
    setEndSec(videoDuration);
    setEndText(secondsToTime(videoDuration));
    setError('');
  };

  const setPresetFirst30 = () => {
    setStartSec(0);
    setStartText('00:00:00');
    const end = Math.min(30, maxDuration);
    setEndSec(end);
    setEndText(secondsToTime(end));
    setError('');
  };

  const setPresetFirst5Min = () => {
    setStartSec(0);
    setStartText('00:00:00');
    const end = Math.min(300, maxDuration);
    setEndSec(end);
    setEndText(secondsToTime(end));
    setError('');
  };

  const setPresetLast5Min = () => {
    const start = Math.max(0, maxDuration - 300);
    setStartSec(start);
    setStartText(secondsToTime(start));
    setEndSec(maxDuration);
    setEndText(secondsToTime(maxDuration));
    setError('');
  };

  const setPresetCurrentWindow = () => {
    const cur = currentTime || 0;
    const start = Math.max(0, cur - 15);
    const end = Math.min(maxDuration, cur + 15);
    setStartSec(start);
    setStartText(secondsToTime(start));
    setEndSec(end);
    setEndText(secondsToTime(end));
    setError('');
  };

  // Calculate percentages for timeline visual bar
  const startPercent = Math.min(100, Math.max(0, (startSec / maxDuration) * 100));
  const endPercent = Math.min(100, Math.max(0, (endSec / maxDuration) * 100));
  const selectionWidth = Math.max(0, endPercent - startPercent);
  const selectedDuration = Math.max(0, endSec - startSec);

  const formatDisplayDuration = (secs) => {
    const hours = Math.floor(secs / 3600);
    const minutes = Math.floor((secs % 3600) / 60);
    const seconds = Math.floor(secs % 60);
    if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
    if (minutes > 0) return `${minutes}m ${seconds}s`;
    return `${seconds}s`;
  };

  return (
    <div className="enhanced-time-range-selector">
      {/* Header Section */}
      <div className="time-selector-header">
        <div className="flex items-center gap-2">
          <div className="header-icon">
            <Scissors className="clock-icon text-cyan-400" />
          </div>
          <div>
            <h3 className="header-title">Extract Video Segment</h3>
            <p className="text-xs text-slate-400">Select start and end time markers based on video duration</p>
          </div>
        </div>
        <div className="duration-badge">
          <span>Length: {formatDisplayDuration(selectedDuration)}</span>
        </div>
      </div>

      {/* Visual Timeline Range Bar */}
      <div className="timeline-visual-container">
        <div className="timeline-labels">
          <span className="time-marker">00:00:00</span>
          <span className="selected-window-info text-cyan-400 font-mono">
            {secondsToTime(startSec)} ➔ {secondsToTime(endSec)}
          </span>
          <span className="time-marker">{secondsToTime(maxDuration)}</span>
        </div>

        <div className="timeline-track-wrapper">
          <div className="timeline-track-background"></div>
          <div 
            className="timeline-track-selected"
            style={{ left: `${startPercent}%`, width: `${selectionWidth}%` }}
          ></div>

          {/* Dual Range Sliders */}
          <input
            type="range"
            min="0"
            max={maxDuration}
            step="1"
            value={startSec}
            onChange={handleStartSliderChange}
            disabled={isExtracting}
            className="range-slider range-slider-start"
            title="Start Time Marker"
          />
          <input
            type="range"
            min="0"
            max={maxDuration}
            step="1"
            value={endSec}
            onChange={handleEndSliderChange}
            disabled={isExtracting}
            className="range-slider range-slider-end"
            title="End Time Marker"
          />
        </div>
      </div>

      {/* Direct Input Controls */}
      <div className="time-inputs-section">
        <div className="time-input-group">
          <label className="time-label">Start Time (HH:MM:SS)</label>
          <input
            type="text"
            value={startText}
            onChange={handleStartTextChange}
            placeholder="00:00:00"
            className="time-input font-mono"
            disabled={isExtracting}
          />
        </div>
        
        <div className="time-separator">
          <span className="separator-text">to</span>
        </div>

        <div className="time-input-group">
          <label className="time-label">End Time (HH:MM:SS)</label>
          <input
            type="text"
            value={endText}
            onChange={handleEndTextChange}
            placeholder="00:00:00"
            className="time-input font-mono"
            disabled={isExtracting}
          />
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="error-message">
          <AlertCircle className="error-icon" />
          <span className="error-text">{error}</span>
        </div>
      )}

      {/* Presets & Download Action */}
      <div className="actions-section">
        <div className="quick-select-group">
          <span className="quick-select-label">Quick Selection Presets:</span>
          <div className="quick-select-buttons">
            <button
              type="button"
              onClick={setPresetFull}
              disabled={isExtracting}
              className="quick-select-btn"
            >
              Full Video
            </button>
            <button
              type="button"
              onClick={setPresetFirst30}
              disabled={isExtracting}
              className="quick-select-btn"
            >
              First 30s
            </button>
            <button
              type="button"
              onClick={setPresetFirst5Min}
              disabled={isExtracting || maxDuration <= 300}
              className="quick-select-btn"
            >
              First 5m
            </button>
            <button
              type="button"
              onClick={setPresetLast5Min}
              disabled={isExtracting || maxDuration <= 300}
              className="quick-select-btn"
            >
              Last 5m
            </button>
            {currentTime > 0 && (
              <button
                type="button"
                onClick={setPresetCurrentWindow}
                disabled={isExtracting}
                className="quick-select-btn current-window-btn"
              >
                Current +/- 15s
              </button>
            )}
          </div>
        </div>

        <div className="download-section">
          <button
            type="button"
            onClick={handleDownloadClick}
            disabled={isExtracting || endSec <= startSec}
            className={`download-segment-btn ${
              !isExtracting && endSec > startSec ? 'download-segment-btn-active' : 'download-segment-btn-disabled'
            }`}
          >
            <Download className="download-icon" />
            <span className="download-text">
              {isExtracting ? 'Extracting Segment...' : 'Extract & Download Segment'}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default TimeRangeSelector;
