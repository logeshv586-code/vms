import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../utils/apiConfig';
import './EventDetailsPanel.css';

function EventDetailsPanel({ event, onClose, onAcknowledge }) {
  if (!event) return null;

  const [archiveVideos, setArchiveVideos] = useState([]);
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [videoError, setVideoError] = useState(false);

  // Build the archive video URL for a camera's recording
  const getArchiveStreamUrl = (cameraId, filename) => {
    return `${API_BASE_URL}/api/archive/stream/${cameraId}/${filename}`;
  };

  // Fetch available archive recordings for the event's camera
  useEffect(() => {
    if (!event.camera_id) return;

    const fetchArchiveRecordings = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/archive/list/${event.camera_id}`);
        if (response.ok) {
          const data = await response.json();
          if (data.recordings && data.recordings.length > 0) {
            setArchiveVideos(data.recordings);
            // Find the recording closest to the event time
            const eventTime = new Date(event.created_at);
            let closest = data.recordings[0];
            let closestDiff = Infinity;
            for (const rec of data.recordings) {
              if (rec.start_time) {
                const recTime = new Date(rec.start_time);
                const diff = Math.abs(eventTime - recTime);
                if (diff < closestDiff) {
                  closestDiff = diff;
                  closest = rec;
                }
              }
            }
            setSelectedVideo(closest);
          }
        }
      } catch (err) {
        console.error('Failed to fetch archive recordings:', err);
      }
    };

    fetchArchiveRecordings();
  }, [event.camera_id, event.created_at]);

  // Determine the best video source: proof video if exists, else archive stream
  const getVideoSource = () => {
    // First try the video_proof_url if it exists
    if (event.video_proof_url) {
      return `${API_BASE_URL}${event.video_proof_url}`;
    }
    // Fall back to the closest archive recording
    if (selectedVideo && selectedVideo.filename) {
      const baseUrl = getArchiveStreamUrl(event.camera_id, selectedVideo.filename);
      if (selectedVideo.start_time && event.created_at) {
        const eventTime = new Date(event.created_at).getTime();
        const videoStartTime = new Date(selectedVideo.start_time).getTime();
        const offsetSeconds = Math.max(0, Math.floor((eventTime - videoStartTime) / 1000));
        // Show from 10 seconds before the event to 50 seconds after (1 minute total window)
        return baseUrl;
      }
      return baseUrl;
    }
    return null;
  };

  const videoSrc = getVideoSource();

  // Get the live stream URL for the camera (MJPEG feed)
  const getLiveStreamUrl = () => {
    return `${API_BASE_URL}/api/video_feed/${event.camera_id}`;
  };

  const formatDateTime = (isoString) => {
    if (!isoString) return 'N/A';
    const d = new Date(isoString);
    return d.toLocaleString([], { year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m > 0 ? m + 'm ' : ''}${s}s`;
  };

  const handleVideoError = () => {
    setVideoError(true);
    // If proof video failed, try to fall back to archive
    if (event.video_proof_url && selectedVideo) {
      setVideoError(false);
    }
  };

  return (
    <div className="event-details-overlay" onClick={onClose}>
      <div className="event-details-panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <h3>Event Details</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        
        <div className="panel-content">
          <div className="metadata-section">
            <div className="meta-grid">
              <div className="meta-item">
                <label>Event ID</label>
                <span>{event.event_id}</span>
              </div>
              <div className="meta-item">
                <label>Rule</label>
                <span>{event.rule_name}</span>
              </div>
              <div className="meta-item">
                <label>Category</label>
                <span>{event.category}</span>
              </div>
              <div className="meta-item">
                <label>Camera</label>
                <span>{event.camera_name}</span>
              </div>
              <div className="meta-item">
                <label>Location</label>
                <span>{event.location}</span>
              </div>
              <div className="meta-item">
                <label>Priority</label>
                <span className={`priority-badge ${event.priority?.toLowerCase()}`}>{event.priority}</span>
              </div>
              <div className="meta-item">
                <label>Detected At</label>
                <span>{formatDateTime(event.created_at)}</span>
              </div>
              <div className="meta-item">
                <label>Duration</label>
                <span>{formatDuration(event.duration)}</span>
              </div>
              <div className="meta-item">
                <label>Status</label>
                <span className={`status-badge ${event.status?.toLowerCase().replace(' ', '-')}`}>{event.status}</span>
              </div>
              <div className="meta-item">
                <label>Acknowledged</label>
                <span>{event.acknowledged ? 'Yes' : 'No'}</span>
              </div>
            </div>
          </div>

          <div className="media-section">
            <h4>Live Camera Feed</h4>
            <div className="live-feed-container" style={{ marginBottom: '15px' }}>
              <img 
                src={getLiveStreamUrl()} 
                alt={`Live feed from ${event.camera_name}`}
                style={{ width: '100%', maxHeight: '200px', objectFit: 'contain', borderRadius: '8px', backgroundColor: '#000' }}
                onError={(e) => { e.target.style.display = 'none'; }}
              />
            </div>

            <h4>Video Evidence (Archive Recording)</h4>
            <div className="video-player-container">
              {videoSrc && !videoError ? (
                <video 
                  key={videoSrc}
                  src={videoSrc} 
                  controls 
                  autoPlay 
                  loop
                  onError={handleVideoError}
                  style={{ width: '100%', borderRadius: '8px', backgroundColor: '#000' }}
                >
                  Your browser does not support the video tag.
                </video>
              ) : archiveVideos.length > 0 && selectedVideo ? (
                <video 
                  key={getArchiveStreamUrl(event.camera_id, selectedVideo.filename)}
                  src={getArchiveStreamUrl(event.camera_id, selectedVideo.filename)} 
                  controls 
                  autoPlay 
                  loop
                  style={{ width: '100%', borderRadius: '8px', backgroundColor: '#000' }}
                >
                  Your browser does not support the video tag.
                </video>
              ) : (
                <div className="video-placeholder">
                  <span className="play-icon">▶</span>
                  <p>No Video Evidence Available Yet</p>
                  <p style={{ fontSize: '12px', color: '#888' }}>Recording may still be in progress</p>
                </div>
              )}

              {/* Archive recording selector */}
              {archiveVideos.length > 1 && (
                <div className="archive-selector" style={{ marginTop: '10px' }}>
                  <label style={{ color: '#aaa', fontSize: '12px', marginRight: '8px' }}>Select Recording:</label>
                  <select 
                    value={selectedVideo?.filename || ''} 
                    onChange={(e) => {
                      const selected = archiveVideos.find(v => v.filename === e.target.value);
                      setSelectedVideo(selected);
                      setVideoError(false);
                    }}
                    style={{ 
                      padding: '4px 8px', 
                      borderRadius: '4px', 
                      backgroundColor: '#1a1a2e', 
                      color: '#fff', 
                      border: '1px solid #333',
                      fontSize: '12px'
                    }}
                  >
                    {archiveVideos.map((vid) => (
                      <option key={vid.filename} value={vid.filename}>
                        {vid.filename} {vid.size_mb ? `(${vid.size_mb} MB)` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="video-actions" style={{ marginTop: '10px' }}>
                {videoSrc && (
                  <>
                    <a href={videoSrc} download className="secondary-btn" style={{ textDecoration: 'none', display: 'inline-block', textAlign: 'center' }}>
                      Download Clip
                    </a>
                    <a href={videoSrc} download={`evidence_${event.event_id}.mp4`} className="secondary-btn" style={{ textDecoration: 'none', display: 'inline-block', textAlign: 'center' }}>
                      Export Evidence
                    </a>
                  </>
                )}
                {!videoSrc && (
                  <button className="secondary-btn" disabled>Export Evidence</button>
                )}
              </div>
            </div>
          </div>
          
          <div className="panel-actions">
            {!event.acknowledged && event.status === 'Active' && (
              <button className="primary-btn" onClick={() => onAcknowledge(event.event_id)}>Acknowledge Event</button>
            )}
            <button className="secondary-btn" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default EventDetailsPanel;
