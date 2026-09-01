import React, { useState, useEffect, useRef } from 'react';
import {
  Scissors,
  Download,
  Trash2,
  Play,
  RefreshCw,
  Search,
  Calendar,
  Clock,
  Camera,
  MapPin,
  HardDrive,
  Crop,
  X,
  FileVideo,
  Film,
  WifiOff,
  AlertCircle
} from 'lucide-react';
import archiveApi from '../../services/archiveApi';
import { API_BASE_URL } from '../../utils/apiConfig';
import './ExtractedVideosContent.css';

const LOCAL_STORAGE_KEY = 'vms_extracted_videos_cache';

const ExtractedVideosContent = () => {
  const [extractedVideos, setExtractedVideos] = useState(() => {
    try {
      const cached = localStorage.getItem(LOCAL_STORAGE_KEY);
      return cached ? JSON.parse(cached) : [];
    } catch (e) {
      return [];
    }
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isOfflineMode, setIsOfflineMode] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedVideo, setSelectedVideo] = useState(null);
  const [videoPlayerError, setVideoPlayerError] = useState(null);
  const [isDeleting, setIsDeleting] = useState(null);

  const retryTimerRef = useRef(null);

  const loadExtractedVideos = async (silent = false) => {
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const data = await archiveApi.listExtractedVideos();
      const list = data.extracted_videos || [];
      setExtractedVideos(list);
      setIsOfflineMode(false);
      try {
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(list));
      } catch (e) {
        console.warn('Could not cache extracted videos:', e);
      }
    } catch (err) {
      console.error('Failed to load extracted videos:', err);
      const isNetErr = err.message && (err.message.includes('Network error') || err.message.includes('connect to server'));
      
      // If we have cached items in local storage, display them in offline mode
      const cached = localStorage.getItem(LOCAL_STORAGE_KEY);
      if (cached) {
        try {
          const cachedList = JSON.parse(cached);
          if (cachedList.length > 0) {
            setExtractedVideos(cachedList);
            setIsOfflineMode(true);
          }
        } catch (e) {}
      }

      setError(err.message || 'Unable to connect to backend server. Please verify backend is running on port 8000.');
    } finally {
      if (!silent) setIsLoading(false);
    }
  };

  useEffect(() => {
    loadExtractedVideos();

    // Auto-retry polling if backend is reconnecting
    retryTimerRef.current = setInterval(() => {
      loadExtractedVideos(true);
    }, 10000);

    return () => {
      if (retryTimerRef.current) clearInterval(retryTimerRef.current);
    };
  }, []);

  const handleDelete = async (filename, e) => {
    if (e) e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this extracted video clip?')) return;

    setIsDeleting(filename);
    try {
      await archiveApi.deleteExtractedVideo(filename);
      setExtractedVideos(prev => {
        const updated = prev.filter(v => v.filename !== filename);
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(updated));
        return updated;
      });
      if (selectedVideo?.filename === filename) {
        setSelectedVideo(null);
      }
    } catch (err) {
      console.error('Failed to delete video clip:', err);
      alert('Failed to delete extracted video clip. Backend server might be restarting.');
    } finally {
      setIsDeleting(null);
    }
  };

  const handleDownload = (filename, e) => {
    if (e) e.stopPropagation();
    const downloadUrl = `${API_BASE_URL}/api/archive/download-extract/${filename}`;
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = filename;
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const formatSize = (sizeBytes) => {
    if (!sizeBytes) return 'Unknown';
    const mb = sizeBytes / (1024 * 1024);
    if (mb >= 1) return `${mb.toFixed(2)} MB`;
    return `${Math.round(sizeBytes / 1024)} KB`;
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return 'Unknown Date';
    try {
      return new Date(isoStr).toLocaleString();
    } catch (e) {
      return isoStr;
    }
  };

  const filteredVideos = extractedVideos.filter(item => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      (item.title || '').toLowerCase().includes(term) ||
      (item.location || '').toLowerCase().includes(term) ||
      (item.camera_ip || '').toLowerCase().includes(term) ||
      (item.filename || '').toLowerCase().includes(term) ||
      (item.notes || '').toLowerCase().includes(term)
    );
  });

  return (
    <div className="extracted-videos-page">
      {/* Header Bar */}
      <div className="extracted-page-header">
        <div>
          <div className="header-badge">
            <Scissors className="w-4 h-4 text-blue-600" />
            <span>Extracted Clips Library</span>
          </div>
          <h1 className="extracted-page-title">Extracted Videos</h1>
          <p className="extracted-page-subtitle">
            Saved video snippets and spatial cropped frames extracted from archived playbacks
          </p>
        </div>

        <button onClick={() => loadExtractedVideos(false)} disabled={isLoading} className="extracted-refresh-btn">
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Network Error / Offline Banner */}
      {error && (
        <div className={`extracted-connection-banner ${isOfflineMode ? 'warning' : 'danger'}`}>
          <div className="flex items-center gap-2">
            <WifiOff className="w-5 h-5 flex-shrink-0" />
            <div>
              <strong className="block font-semibold">
                {isOfflineMode ? 'Backend Server Disconnected (Cached View)' : 'Backend Connection Error'}
              </strong>
              <span className="text-xs opacity-90">{error}</span>
            </div>
          </div>
          <button onClick={() => loadExtractedVideos(false)} className="reconnect-banner-btn">
            <RefreshCw className="w-3.5 h-3.5 mr-1" />
            Reconnect Server
          </button>
        </div>
      )}

      {/* Search Bar */}
      <div className="extracted-search-container">
        <Search className="search-icon" />
        <input
          type="text"
          placeholder="Search by clip title, camera location, IP or filename..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="extracted-search-input"
        />
        {searchTerm && (
          <button onClick={() => setSearchTerm('')} className="clear-search-btn">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Content Grid */}
      {isLoading && extractedVideos.length === 0 ? (
        <div className="extracted-loading-state">
          <RefreshCw className="w-8 h-8 animate-spin text-blue-600 mb-2" />
          <h3>Connecting to VMS Backend Server...</h3>
          <p className="text-xs text-slate-500">Fetching extracted video recordings on port 8000</p>
        </div>
      ) : error && extractedVideos.length === 0 ? (
        <div className="extracted-error-state">
          <AlertCircle className="w-12 h-12 text-red-500 mb-3" />
          <h3>Unable to Connect to Server</h3>
          <p>{error}</p>
          <button onClick={() => loadExtractedVideos(false)} className="extracted-retry-btn">
            Retry Connection
          </button>
        </div>
      ) : filteredVideos.length === 0 ? (
        <div className="extracted-empty-state">
          <Film className="w-12 h-12 text-slate-400 mb-3" />
          <h3>No Extracted Videos Found</h3>
          <p>
            {searchTerm
              ? 'No clips match your search query.'
              : 'Extract video segments and crop frames from Archived Playback to view them here.'}
          </p>
        </div>
      ) : (
        <div className="extracted-videos-grid">
          {filteredVideos.map(video => (
            <div
              key={video.filename}
              className="extracted-video-card"
              onClick={() => {
                setVideoPlayerError(null);
                setSelectedVideo(video);
              }}
            >
              {/* Thumbnail Container */}
              <div className="card-thumbnail-container">
                <div className="thumbnail-placeholder">
                  <Film className="w-10 h-10 text-slate-500" />
                </div>
                <div className="play-overlay">
                  <Play className="w-8 h-8 text-white fill-white" />
                </div>

                <div className="card-crop-badge">
                  {video.has_crop ? (
                    <span className="badge-crop">
                      <Crop className="w-3 h-3" /> Cropped Frame
                    </span>
                  ) : (
                    <span className="badge-full">Full Frame</span>
                  )}
                </div>

                <div className="card-duration-badge">
                  <Clock className="w-3 h-3" />
                  <span>{video.duration_seconds || 0}s</span>
                </div>
              </div>

              {/* Card Meta Body */}
              <div className="card-body">
                <h4 className="card-title">{video.title || video.filename}</h4>

                <div className="card-meta-row">
                  <span className="meta-pill">
                    <MapPin className="w-3 h-3 text-red-500" />
                    {video.location || 'Location'}
                  </span>
                  <span className="meta-pill">
                    <Camera className="w-3 h-3 text-blue-500" />
                    {video.camera_ip || 'IP'}
                  </span>
                </div>

                <div className="card-info-list">
                  <div className="info-item">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>Snippet: {video.start_time || '00:00:00'} to {video.end_time || '00:00:00'}</span>
                  </div>
                  <div className="info-item">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    <span>Saved: {formatDate(video.created_at)}</span>
                  </div>
                  <div className="info-item">
                    <HardDrive className="w-3.5 h-3.5 text-slate-400" />
                    <span>Size: {formatSize(video.file_size)}</span>
                  </div>
                </div>

                {video.notes && (
                  <p className="card-notes">"{video.notes}"</p>
                )}

                {/* Card Actions */}
                <div className="card-actions-row">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setVideoPlayerError(null);
                      setSelectedVideo(video);
                    }}
                    className="card-action-btn play-btn"
                  >
                    <Play className="w-3.5 h-3.5" />
                    <span>Play</span>
                  </button>

                  <button
                    onClick={(e) => handleDownload(video.filename, e)}
                    className="card-action-btn download-btn"
                    title="Download Clip"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>

                  <button
                    onClick={(e) => handleDelete(video.filename, e)}
                    disabled={isDeleting === video.filename}
                    className="card-action-btn delete-btn"
                    title="Delete Clip"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Video Player Modal */}
      {selectedVideo && (
        <div className="extracted-player-modal-overlay" onClick={() => setSelectedVideo(null)}>
          <div className="extracted-player-modal-container" onClick={(e) => e.stopPropagation()}>
            <div className="player-modal-header">
              <div>
                <h3>{selectedVideo.title || selectedVideo.filename}</h3>
                <p>{selectedVideo.location} ({selectedVideo.camera_ip}) • Clip Range: {selectedVideo.start_time} - {selectedVideo.end_time}</p>
              </div>
              <button onClick={() => setSelectedVideo(null)} className="close-player-btn">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="player-video-wrapper">
              {videoPlayerError ? (
                <div className="player-video-error">
                  <AlertCircle className="w-10 h-10 text-red-500 mb-2" />
                  <h4>Unable to Play Extracted Video</h4>
                  <p className="text-xs text-slate-300 mb-3">{videoPlayerError}</p>
                  <button
                    onClick={() => {
                      setVideoPlayerError(null);
                      loadExtractedVideos(false);
                    }}
                    className="retry-player-btn"
                  >
                    <RefreshCw className="w-3.5 h-3.5 mr-1" />
                    Retry Connection
                  </button>
                </div>
              ) : (
                <video
                  src={`${API_BASE_URL}/api/archive/extracted-stream/${selectedVideo.filename}`}
                  controls
                  autoPlay
                  onError={(e) => {
                    console.error('Extracted video player error:', e);
                    setVideoPlayerError('Network connection lost or backend server unavailable on port 8000.');
                  }}
                  className="player-video-element"
                />
              )}
            </div>

            <div className="player-modal-footer">
              <span className="text-sm text-slate-500">
                Extracted on {formatDate(selectedVideo.created_at)} ({formatSize(selectedVideo.file_size)})
              </span>
              <button
                onClick={(e) => handleDownload(selectedVideo.filename, e)}
                className="player-download-btn"
              >
                <Download className="w-4 h-4 mr-2" />
                Download Extracted Video
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExtractedVideosContent;
