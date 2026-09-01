import React, { useState, useEffect, useRef } from 'react';
import {
  Scissors,
  Crop,
  Clock,
  Save,
  Download,
  X,
  Play,
  Pause,
  Maximize2,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  FileText,
  Video,
  Layers,
  Sparkles
} from 'lucide-react';
import archiveApi from '../../services/archiveApi';
import './VideoEditorModal.css';

const secondsToTimeStr = (totalSeconds) => {
  if (!totalSeconds || isNaN(totalSeconds) || totalSeconds < 0) return '00:00:00';
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
};

const timeStrToSeconds = (timeStr) => {
  if (!timeStr) return 0;
  const parts = timeStr.split(':').map(Number);
  if (parts.length === 3) {
    return (parts[0] || 0) * 3600 + (parts[1] || 0) * 60 + (parts[2] || 0);
  }
  return 0;
};

const VideoEditorModal = ({
  recording,
  videoDuration = 0,
  videoSrc = '',
  cameraInfo = {},
  onClose,
  onSaveSuccess
}) => {
  const [startTime, setStartTime] = useState('00:00:00');
  const [endTime, setEndTime] = useState('00:00:00');
  const [isPlayingSnippet, setIsPlayingSnippet] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  // Crop settings (percentages 0..100)
  const [cropEnabled, setCropEnabled] = useState(true);
  const [cropBox, setCropBox] = useState({ x: 10, y: 10, w: 80, h: 80 });
  const [aspectRatio, setAspectRatio] = useState('free'); // 'free', '16:9', '4:3', '1:1', '9:16'

  // Metadata
  const [clipTitle, setClipTitle] = useState('');
  const [clipNotes, setClipNotes] = useState('');

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [successResult, setSuccessResult] = useState(null);

  // Refs
  const videoRef = useRef(null);
  const overlayRef = useRef(null);
  const isDraggingRef = useRef(false);
  const dragTypeRef = useRef(null); // 'move', 'nw', 'ne', 'sw', 'se', 'n', 's', 'w', 'e'
  const startDragPosRef = useRef({ x: 0, y: 0, box: { x: 10, y: 10, w: 80, h: 80 } });

  // Initialize title and end time on load
  useEffect(() => {
    if (videoDuration > 0) {
      setEndTime(secondsToTimeStr(videoDuration));
    }
    if (recording?.filename) {
      const baseName = recording.filename.replace(/\.[^/.]+$/, "");
      setClipTitle(`Crop_${baseName}`);
    }
  }, [videoDuration, recording]);

  // Handle Video Time Updates
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const curr = videoRef.current.currentTime;
    setCurrentTime(curr);

    const endSec = timeStrToSeconds(endTime);
    if (isPlayingSnippet && curr >= endSec) {
      videoRef.current.pause();
      setIsPlayingSnippet(false);
    }
  };

  // Toggle Snippet Playback
  const togglePlaySnippet = () => {
    if (!videoRef.current) return;
    const startSec = timeStrToSeconds(startTime);
    const endSec = timeStrToSeconds(endTime);

    if (isPlayingSnippet) {
      videoRef.current.pause();
      setIsPlayingSnippet(false);
    } else {
      if (videoRef.current.currentTime < startSec || videoRef.current.currentTime >= endSec) {
        videoRef.current.currentTime = startSec;
      }
      videoRef.current.play().catch(err => console.error("Play error:", err));
      setIsPlayingSnippet(true);
    }
  };

  // Seek to Start Time
  const seekToStart = () => {
    if (videoRef.current) {
      const startSec = timeStrToSeconds(startTime);
      videoRef.current.currentTime = startSec;
    }
  };

  // Seek to End Time
  const seekToEnd = () => {
    if (videoRef.current) {
      const endSec = timeStrToSeconds(endTime);
      videoRef.current.currentTime = Math.max(0, endSec - 0.5);
    }
  };

  // Handle Drag / Resize Mouse Events for Crop Overlay Box
  const handleMouseDown = (e, type) => {
    e.preventDefault();
    e.stopPropagation();
    isDraggingRef.current = true;
    dragTypeRef.current = type;
    startDragPosRef.current = {
      x: e.clientX,
      y: e.clientY,
      box: { ...cropBox }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = (e) => {
    if (!isDraggingRef.current || !overlayRef.current) return;

    const rect = overlayRef.current.getBoundingClientRect();
    const deltaXPercent = ((e.clientX - startDragPosRef.current.x) / rect.width) * 100;
    const deltaYPercent = ((e.clientY - startDragPosRef.current.y) / rect.height) * 100;

    const initialBox = startDragPosRef.current.box;
    let newBox = { ...initialBox };

    const type = dragTypeRef.current;

    if (type === 'move') {
      newBox.x = Math.max(0, Math.min(100 - initialBox.w, initialBox.x + deltaXPercent));
      newBox.y = Math.max(0, Math.min(100 - initialBox.h, initialBox.y + deltaYPercent));
    } else {
      if (type.includes('w')) {
        const maxW = initialBox.x + initialBox.w;
        newBox.x = Math.max(0, Math.min(maxW - 5, initialBox.x + deltaXPercent));
        newBox.w = maxW - newBox.x;
      }
      if (type.includes('e')) {
        newBox.w = Math.max(5, Math.min(100 - initialBox.x, initialBox.w + deltaXPercent));
      }
      if (type.includes('n')) {
        const maxH = initialBox.y + initialBox.h;
        newBox.y = Math.max(0, Math.min(maxH - 5, initialBox.y + deltaYPercent));
        newBox.h = maxH - newBox.y;
      }
      if (type.includes('s')) {
        newBox.h = Math.max(5, Math.min(100 - initialBox.y, initialBox.h + deltaYPercent));
      }
    }

    setCropBox(newBox);
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
    dragTypeRef.current = null;
    window.removeEventListener('mousemove', handleMouseMove);
    window.removeEventListener('mouseup', handleMouseUp);
  };

  // Aspect Ratio Preset Handler
  const applyAspectRatio = (ratio) => {
    setAspectRatio(ratio);
    if (ratio === 'free') return;
    if (ratio === 'full') {
      setCropBox({ x: 0, y: 0, w: 100, h: 100 });
      return;
    }

    let targetRatio = 16 / 9;
    if (ratio === '4:3') targetRatio = 4 / 3;
    if (ratio === '1:1') targetRatio = 1 / 1;
    if (ratio === '9:16') targetRatio = 9 / 16;

    // Calculate crop box fitting target ratio over video overlay bounds
    let w = 80;
    let h = 80;
    if (targetRatio > 1) {
      h = w / targetRatio;
      if (h > 90) {
        h = 90;
        w = h * targetRatio;
      }
    } else {
      w = h * targetRatio;
      if (w > 90) {
        w = 90;
        h = w / targetRatio;
      }
    }

    setCropBox({
      x: Math.round((100 - w) / 2),
      y: Math.round((100 - h) / 2),
      w: Math.round(w),
      h: Math.round(h)
    });
  };

  // Perform Extract and Save Operation
  const handleExtractAndSave = async (saveToGallery = true) => {
    if (!recording) return;

    setIsProcessing(true);
    setProcessingStatus(cropEnabled ? 'Cropping frame & extracting video segment...' : 'Extracting video segment...');
    setErrorMessage('');
    setSuccessResult(null);

    try {
      const cropX = cropEnabled ? (cropBox.x / 100) : 0;
      const cropY = cropEnabled ? (cropBox.y / 100) : 0;
      const cropW = cropEnabled ? (cropBox.w / 100) : 1;
      const cropH = cropEnabled ? (cropBox.h / 100) : 1;

      const result = await archiveApi.extractVideoSegment(
        recording.stream_id,
        recording.filename,
        startTime,
        endTime,
        cropX,
        cropY,
        cropW,
        cropH,
        clipTitle,
        clipNotes,
        saveToGallery
      );

      setIsProcessing(false);
      setSuccessResult(result);

      if (onSaveSuccess) {
        onSaveSuccess(result);
      }
    } catch (err) {
      console.error('Extraction error:', err);
      setIsProcessing(false);
      setErrorMessage(err.message || 'Failed to process video extraction');
    }
  };

  // Download directly
  const handleDownloadDirect = async () => {
    if (successResult?.filename) {
      try {
        const blob = await archiveApi.downloadExtractedSegment(successResult.filename);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = successResult.filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        console.error('Download error:', err);
        setErrorMessage('Failed to download extracted file');
      }
    } else {
      handleExtractAndSave(false);
    }
  };

  const selectedDuration = timeStrToSeconds(endTime) - timeStrToSeconds(startTime);

  return (
    <div className="video-editor-modal-overlay">
      <div className="video-editor-modal-container">
        {/* Modal Header */}
        <div className="editor-modal-header">
          <div className="flex items-center gap-2">
            <div className="editor-icon-badge">
              <Scissors className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="editor-modal-title">Video Editing Studio</h2>
              <p className="editor-modal-subtitle">
                Crop frame boundaries and trim duration segment
              </p>
            </div>
          </div>
          <button onClick={onClose} className="close-editor-btn" title="Close Editor">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Main Body Grid */}
        <div className="editor-modal-body">
          {/* Left Column: Video Preview & Spatial Crop Canvas */}
          <div className="editor-preview-column">
            <div className="video-viewport-wrapper" ref={overlayRef}>
              <video
                ref={videoRef}
                src={videoSrc}
                className="editor-video-element"
                onTimeUpdate={handleTimeUpdate}
                controls={false}
                crossOrigin="anonymous"
              />

              {/* Spatial Crop Box Overlay */}
              {cropEnabled && (
                <div
                  className="crop-overlay-box"
                  style={{
                    left: `${cropBox.x}%`,
                    top: `${cropBox.y}%`,
                    width: `${cropBox.w}%`,
                    height: `${cropBox.h}%`
                  }}
                  onMouseDown={(e) => handleMouseDown(e, 'move')}
                >
                  <div className="crop-box-label">
                    <Crop className="w-3 h-3" />
                    <span>{Math.round(cropBox.w)}% × {Math.round(cropBox.h)}%</span>
                  </div>

                  {/* Corner Handles */}
                  <div className="crop-handle handle-nw" onMouseDown={(e) => handleMouseDown(e, 'nw')} />
                  <div className="crop-handle handle-ne" onMouseDown={(e) => handleMouseDown(e, 'ne')} />
                  <div className="crop-handle handle-sw" onMouseDown={(e) => handleMouseDown(e, 'sw')} />
                  <div className="crop-handle handle-se" onMouseDown={(e) => handleMouseDown(e, 'se')} />

                  {/* Edge Handles */}
                  <div className="crop-handle handle-n" onMouseDown={(e) => handleMouseDown(e, 'n')} />
                  <div className="crop-handle handle-s" onMouseDown={(e) => handleMouseDown(e, 's')} />
                  <div className="crop-handle handle-w" onMouseDown={(e) => handleMouseDown(e, 'w')} />
                  <div className="crop-handle handle-e" onMouseDown={(e) => handleMouseDown(e, 'e')} />
                </div>
              )}
            </div>

            {/* Video Transport Controls */}
            <div className="video-transport-bar">
              <button
                onClick={togglePlaySnippet}
                className="transport-play-btn"
                title={isPlayingSnippet ? "Pause Preview" : "Play Selection Snippet"}
              >
                {isPlayingSnippet ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                <span>{isPlayingSnippet ? 'Pause' : 'Play Snippet'}</span>
              </button>

              <div className="time-display-badge">
                <Clock className="w-3.5 h-3.5 text-blue-500" />
                <span>Current: {secondsToTimeStr(currentTime)}</span>
              </div>

              <div className="flex gap-2">
                <button onClick={seekToStart} className="transport-seek-btn" title="Seek to Start Time">
                  Seek Start
                </button>
                <button onClick={seekToEnd} className="transport-seek-btn" title="Seek to End Time">
                  Seek End
                </button>
              </div>
            </div>
          </div>

          {/* Right Column: Editing Tools Control Panel */}
          <div className="editor-controls-column">
            {/* Tool Section 1: Frame Cropping Options */}
            <div className="editor-tool-card">
              <div className="tool-card-header">
                <Crop className="w-4 h-4 text-blue-600" />
                <h3>Frame Spatial Crop</h3>
                <label className="crop-toggle-label">
                  <input
                    type="checkbox"
                    checked={cropEnabled}
                    onChange={(e) => setCropEnabled(e.target.checked)}
                  />
                  <span>Enable Crop</span>
                </label>
              </div>

              {cropEnabled && (
                <div className="tool-card-content">
                  <span className="control-sublabel">Aspect Ratio Presets:</span>
                  <div className="aspect-ratio-grid">
                    {[
                      { id: 'free', label: 'Free' },
                      { id: '16:9', label: '16:9' },
                      { id: '4:3', label: '4:3' },
                      { id: '1:1', label: '1:1 Square' },
                      { id: '9:16', label: '9:16 Vertical' },
                      { id: 'full', label: 'Full Frame' }
                    ].map(item => (
                      <button
                        key={item.id}
                        onClick={() => applyAspectRatio(item.id)}
                        className={`aspect-preset-btn ${aspectRatio === item.id ? 'active' : ''}`}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>

                  <div className="crop-coordinates-info">
                    <span>X: {Math.round(cropBox.x)}%</span>
                    <span>Y: {Math.round(cropBox.y)}%</span>
                    <span>Width: {Math.round(cropBox.w)}%</span>
                    <span>Height: {Math.round(cropBox.h)}%</span>
                  </div>
                </div>
              )}
            </div>

            {/* Tool Section 2: Time Trimming Options */}
            <div className="editor-tool-card">
              <div className="tool-card-header">
                <Clock className="w-4 h-4 text-purple-600" />
                <h3>Time Duration Trim</h3>
              </div>

              <div className="tool-card-content">
                <div className="time-picker-row">
                  <div className="time-picker-group">
                    <label>Start Time</label>
                    <input
                      type="time"
                      step="1"
                      value={startTime}
                      max={secondsToTimeStr(videoDuration)}
                      onChange={(e) => {
                        let val = e.target.value;
                        if (videoDuration > 0 && timeStrToSeconds(val) >= videoDuration) {
                          val = secondsToTimeStr(Math.max(0, videoDuration - 1));
                        }
                        setStartTime(val);
                      }}
                      className="editor-time-input"
                    />
                  </div>

                  <div className="time-picker-group">
                    <label>End Time</label>
                    <input
                      type="time"
                      step="1"
                      value={endTime}
                      max={secondsToTimeStr(videoDuration)}
                      onChange={(e) => {
                        let val = e.target.value;
                        if (videoDuration > 0 && timeStrToSeconds(val) > videoDuration) {
                          val = secondsToTimeStr(videoDuration);
                        }
                        setEndTime(val);
                      }}
                      className="editor-time-input"
                    />
                  </div>
                </div>

                <div className="quick-trim-buttons">
                  <button
                    onClick={() => {
                      setStartTime('00:00:00');
                      setEndTime(secondsToTimeStr(Math.min(30, videoDuration)));
                    }}
                    className="quick-trim-btn"
                  >
                    30s Clip
                  </button>
                  <button
                    onClick={() => {
                      setStartTime('00:00:00');
                      setEndTime(secondsToTimeStr(Math.min(60, videoDuration)));
                    }}
                    className="quick-trim-btn"
                  >
                    1 min Clip
                  </button>
                  <button
                    onClick={() => {
                      setStartTime('00:00:00');
                      setEndTime(secondsToTimeStr(videoDuration));
                    }}
                    className="quick-trim-btn"
                  >
                    Full Duration
                  </button>
                </div>

                <div className="selected-duration-banner">
                  <span>Selected Clip Length: <strong>{selectedDuration > 0 ? `${selectedDuration} seconds` : 'Invalid Range'}</strong></span>
                </div>
              </div>
            </div>

            {/* Tool Section 3: Clip Details & Metadata */}
            <div className="editor-tool-card">
              <div className="tool-card-header">
                <FileText className="w-4 h-4 text-emerald-600" />
                <h3>Clip Information</h3>
              </div>

              <div className="tool-card-content">
                <div className="field-group">
                  <label>Clip Title / Label</label>
                  <input
                    type="text"
                    value={clipTitle}
                    onChange={(e) => setClipTitle(e.target.value)}
                    placeholder="Enter clip title..."
                    className="editor-text-input"
                  />
                </div>

                <div className="field-group">
                  <label>Notes / Description (Optional)</label>
                  <input
                    type="text"
                    value={clipNotes}
                    onChange={(e) => setClipNotes(e.target.value)}
                    placeholder="Add incident notes..."
                    className="editor-text-input"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Processing Indicator / Error Message / Success Banner */}
        {isProcessing && (
          <div className="editor-status-banner processing">
            <RefreshCw className="w-5 h-5 animate-spin text-blue-600 mr-2" />
            <span>{processingStatus}</span>
          </div>
        )}

        {errorMessage && (
          <div className="editor-status-banner error">
            <AlertCircle className="w-5 h-5 text-red-600 mr-2" />
            <span>{errorMessage}</span>
          </div>
        )}

        {successResult && (
          <div className="editor-status-banner success">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 mr-2" />
            <span>Extracted video saved to Extracted Videos gallery! ({successResult.filename})</span>
          </div>
        )}

        {/* Modal Footer Actions */}
        <div className="editor-modal-footer">
          <button onClick={onClose} className="footer-cancel-btn">
            Cancel
          </button>

          <div className="flex gap-3">
            <button
              onClick={() => handleExtractAndSave(false)}
              disabled={isProcessing || selectedDuration <= 0}
              className="footer-secondary-btn"
            >
              <Download className="w-4 h-4 mr-1.5" />
              Download Segment Only
            </button>

            <button
              onClick={() => handleExtractAndSave(true)}
              disabled={isProcessing || selectedDuration <= 0}
              className="footer-primary-btn"
            >
              <Save className="w-4 h-4 mr-1.5" />
              {isProcessing ? 'Processing Extract...' : 'Extract & Save to Extracted Videos'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoEditorModal;
