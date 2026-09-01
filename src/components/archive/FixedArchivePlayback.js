// Fixed Archive Playback with proper video codec support
import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Video,
  Play,
  Pause,
  Download,
  Clock,
  HardDrive,
  ChevronLeft,
  AlertCircle,
  AlertTriangle,
  RefreshCw,
  Scissors,
  Filter,
  X,
  Calendar,
  Camera,
  MapPin,
  Monitor,
  Film,
  Search
} from 'lucide-react';
import { useArchiveStore } from '../../store/archiveStore';
import { useCameraStore } from '../../store/cameraStore';
import TimeRangeSelector from './TimeRangeSelector';
import VideoAnalyticsPanel from './VideoAnalyticsPanel';
import VideoEditorModal from './VideoEditorModal';
import archiveApi from '../../services/archiveApi';
import { API_BASE_URL } from '../../utils/apiConfig';
import './ArchivePlaybackContent.css';
import './VideoAnalyticsPanel.css';

const FixedArchivePlayback = ({ onSelectRecording, selectedRecordingId, selectedRecordingProp, onViewChange, refreshKey }) => {
  const {
    recordings,
    isLoading,
    error,
    loadRecordings,
    clearError
  } = useArchiveStore();

  const [selectedRecording, setSelectedRecording] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [videoError, setVideoError] = useState(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [conversionProgress, setConversionProgress] = useState(0);
  const [useConvertedVideo, setUseConvertedVideo] = useState(false);
  const [isAutoConverting, setIsAutoConverting] = useState(false);
  const [showTimeRangeSelector, setShowTimeRangeSelector] = useState(false);
  const [showVideoEditor, setShowVideoEditor] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionProgress, setExtractionProgress] = useState('');
  const [timeRange, setTimeRange] = useState(null);
  const [selectedIpFilter, setSelectedIpFilter] = useState('all');
  const [selectedLocationFilter, setSelectedLocationFilter] = useState('all');
  const [selectedCameraFilter, setSelectedCameraFilter] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDateFilter, setSelectedDateFilter] = useState('all');
  const [customStartDate, setCustomStartDate] = useState('');
  const [customEndDate, setCustomEndDate] = useState('');

  const { cameras, loadCameraConfig } = useCameraStore();

  useEffect(() => {
    loadCameraConfig();
  }, [loadCameraConfig]);

  const videoRef = useRef(null);
  const autoConvertAttempted = useRef(false);
  const retryCount = useRef(0);

  // Map stream_id to camera details from store, falling back to parsed values
  const getRecordingCameraInfo = useMemo(() => {
    const cache = {};
    return (streamId) => {
      if (!streamId) return { name: 'Unknown Camera', location: 'Unknown Location', ip: 'Unknown IP' };
      if (cache[streamId]) return cache[streamId];
      
      const parts = streamId.split('_');
      const parsedLocation = parts[0] || 'Unknown Location';
      const parsedIp = parts.slice(1).join('_') || 'Unknown IP';
      
      // Look for a camera in the camera store matching the IP or collection
      const camera = cameras.find(c => c.ip === parsedIp && (c.collection === parsedLocation || c.collectionName === parsedLocation));
      
      const info = {
        name: camera ? camera.name : `${parsedLocation} (${parsedIp})`,
        location: camera ? (camera.collection || camera.collectionName) : parsedLocation,
        ip: parsedIp
      };
      
      cache[streamId] = info;
      return info;
    };
  }, [cameras]);

  // Extract unique IP addresses from recordings
  const availableIPs = useMemo(() => {
    const ips = new Set();
    recordings.forEach(recording => {
      if (recording.stream_id) {
        const info = getRecordingCameraInfo(recording.stream_id);
        if (info.ip) {
          ips.add(info.ip);
        }
      }
    });
    return Array.from(ips).sort();
  }, [recordings, getRecordingCameraInfo]);

  // Extract unique locations from recordings
  const availableLocations = useMemo(() => {
    const locations = new Set();
    recordings.forEach(recording => {
      if (recording.stream_id) {
        const info = getRecordingCameraInfo(recording.stream_id);
        if (info.location) {
          locations.add(info.location);
        }
      }
    });
    return Array.from(locations).sort();
  }, [recordings, getRecordingCameraInfo]);

  // Extract unique cameras from recordings
  const availableCameras = useMemo(() => {
    const seen = new Set();
    const list = [];
    recordings.forEach(recording => {
      if (recording.stream_id && !seen.has(recording.stream_id)) {
        seen.add(recording.stream_id);
        const info = getRecordingCameraInfo(recording.stream_id);
        list.push({
          streamId: recording.stream_id,
          name: info.name,
          location: info.location
        });
      }
    });
    return list.sort((a, b) => a.name.localeCompare(b.name));
  }, [recordings, getRecordingCameraInfo]);

  // Filter available cameras by the selected location
  const filteredAvailableCameras = useMemo(() => {
    if (selectedLocationFilter === 'all') {
      return availableCameras;
    }
    return availableCameras.filter(cam => cam.location === selectedLocationFilter);
  }, [availableCameras, selectedLocationFilter]);

  // Reset selected camera filter if it becomes unavailable in the selected location
  useEffect(() => {
    if (selectedLocationFilter !== 'all' && selectedCameraFilter !== 'all') {
      const isStillAvailable = filteredAvailableCameras.some(cam => cam.streamId === selectedCameraFilter);
      if (!isStillAvailable) {
        setSelectedCameraFilter('all');
      }
    }
  }, [selectedLocationFilter, filteredAvailableCameras, selectedCameraFilter]);

  // Helper function to filter recordings by date
  const filterRecordingsByDate = (recordings, dateFilter, customStart, customEnd) => {
    if (dateFilter === 'all') {
      return recordings;
    }

    const now = new Date();
    let startDate, endDate;

    switch (dateFilter) {
      case 'today':
        startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
        break;
      case 'yesterday':
        startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
        endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        break;
      case 'week':
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        endDate = now;
        break;
      case 'month':
        startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
        endDate = now;
        break;
      case 'custom':
        if (customStart && customEnd) {
          startDate = new Date(customStart);
          endDate = new Date(customEnd);
          endDate.setHours(23, 59, 59, 999); // Include the entire end date
        } else {
          return recordings; // Return all if custom dates are not set
        }
        break;
      default:
        return recordings;
    }

    return recordings.filter(recording => {
      if (!recording.timestamp) return false;
      const recordingDate = new Date(recording.timestamp);
      return recordingDate >= startDate && recordingDate < endDate;
    });
  };

  // Filter recordings based on selected filters
  const filteredRecordings = useMemo(() => {
    let filtered = recordings.filter(recording => (recording.size_bytes || 0) >= 10240);

    // Apply Location filter
    if (selectedLocationFilter !== 'all') {
      filtered = filtered.filter(recording => {
        if (recording.stream_id) {
          const info = getRecordingCameraInfo(recording.stream_id);
          return info.location === selectedLocationFilter;
        }
        return false;
      });
    }

    // Apply Camera filter
    if (selectedCameraFilter !== 'all') {
      filtered = filtered.filter(recording => recording.stream_id === selectedCameraFilter);
    }

    // Apply IP filter
    if (selectedIpFilter !== 'all') {
      filtered = filtered.filter(recording => {
        if (recording.stream_id) {
          const info = getRecordingCameraInfo(recording.stream_id);
          return info.ip === selectedIpFilter;
        }
        return false;
      });
    }

    // Apply Search term filter
    if (searchTerm.trim() !== '') {
      const term = searchTerm.toLowerCase().trim();
      filtered = filtered.filter(recording => {
        const info = getRecordingCameraInfo(recording.stream_id);
        const filename = (recording.filename || '').toLowerCase();
        return (
          info.name.toLowerCase().includes(term) ||
          info.location.toLowerCase().includes(term) ||
          info.ip.toLowerCase().includes(term) ||
          filename.includes(term)
        );
      });
    }

    // Apply date filter
    filtered = filterRecordingsByDate(filtered, selectedDateFilter, customStartDate, customEndDate);

    return filtered;
  }, [
    recordings,
    selectedLocationFilter,
    selectedCameraFilter,
    selectedIpFilter,
    searchTerm,
    selectedDateFilter,
    customStartDate,
    customEndDate,
    getRecordingCameraInfo
  ]);

  // Initial load & respond to global header refresh
  useEffect(() => {
    loadRecordings();
  }, [loadRecordings, refreshKey]);


  useEffect(() => {
    if (selectedRecordingProp) {
      // Map fields from get_current_recordings to standard completed recording format
      const mappedRecording = {
        ...selectedRecordingProp,
        timestamp: selectedRecordingProp.timestamp || selectedRecordingProp.start_time || new Date().toISOString(),
        size_bytes: selectedRecordingProp.size_bytes || selectedRecordingProp.file_size || 0,
      };
      setSelectedRecording(mappedRecording);
    } else if (selectedRecordingId) {
      const recording = recordings.find(r => r.filename === selectedRecordingId);
      if (recording) {
        setSelectedRecording(recording);
      }
    }
  }, [selectedRecordingId, selectedRecordingProp, recordings]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    clearError();
    try {
      await loadRecordings();
    } catch (err) {
      console.error('Failed to refresh:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handlePlayPause = () => {
    if (videoRef.current && !isConverting) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        // Clear any previous errors before attempting to play
        setVideoError(null);
        videoRef.current.play().catch(err => {
          console.error('Play failed:', err);
          setVideoError('Unable to play video. The file may be corrupted or use an unsupported codec.');
        });
      }
    }
  };

  const handleVideoTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleVideoLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
      setVideoError(null);
    }
  };

  const handleVideoError = async (e) => {
    const target = e.target;
    let error = target.error;
    let currentSrc = target.currentSrc || target.src;

    // If the error occurred on a <source> element, e.target is the <source> tag.
    // We try to retrieve the error and source URL from the parent <video> element (currentTarget).
    if (!error && target.tagName === 'SOURCE') {
      const videoElement = e.currentTarget;
      if (videoElement) {
        error = videoElement.error;
        currentSrc = videoElement.currentSrc || target.src || currentSrc;
      }
    }

    console.error(`Video error on ${currentSrc || 'unknown source'}:`, error);

    const errorCode = error?.code;
    const errorMessage_raw = error?.message || 'Unknown error';
    let errorMessage = 'Video playback failed. ';

    if (errorCode) {
      switch (errorCode) {
        case 1: // MEDIA_ERR_ABORTED
          errorMessage += 'Playback was aborted.';
          break;
        case 2: // MEDIA_ERR_NETWORK
          errorMessage += 'Network error occurred. The connection to the server was lost.';
          break;
        case 3: // MEDIA_ERR_DECODE
          errorMessage += 'Video codec not supported or file is corrupted. Try converting the format.';
          break;
        case 4: // MEDIA_ERR_SRC_NOT_SUPPORTED
          errorMessage += 'Video format or source not supported by browser.';
          break;
        default:
          errorMessage += `Error code ${errorCode}: ${errorMessage_raw}`;
      }
    } else {
      errorMessage += 'Failed to load video source. The file may not exist, or the format is not supported by your browser.';
    }

    // Step 1: Retry direct stream once with a short delay
    if (retryCount.current < 1 && selectedRecording && !isAutoConverting) {
      retryCount.current += 1;
      console.log(`Retrying video playback (attempt ${retryCount.current})...`);
      setVideoError(null);
      await new Promise(resolve => setTimeout(resolve, 2000));
      if (videoRef.current) {
        videoRef.current.load();
      }
      return;
    }

    // Step 2: Auto-convert on second failure (only once per recording)
    if (!autoConvertAttempted.current && selectedRecording && !isAutoConverting) {
      autoConvertAttempted.current = true;
      console.log('Auto-converting video for browser playback...');
      setIsAutoConverting(true);
      setVideoError(null);

      try {
        const encodedStreamId = encodeURIComponent(selectedRecording.stream_id);
        const encodedFilename = encodeURIComponent(selectedRecording.filename);
        const convertUrl = `${API_BASE_URL}/api/archive/convert/${encodedStreamId}/${encodedFilename}`;
        console.log('Auto-convert request:', convertUrl);

        const response = await fetch(convertUrl, { method: 'POST' });
        if (response.ok) {
          console.log('Auto-conversion succeeded, reloading video with converted source');
          setUseConvertedVideo(true);
          setIsAutoConverting(false);
          if (videoRef.current) {
            videoRef.current.load();
          }
          return;
        } else {
          console.error('Auto-conversion failed:', response.status);
          setIsAutoConverting(false);
        }
      } catch (convErr) {
        console.error('Auto-conversion error:', convErr);
        setIsAutoConverting(false);
      }
    }

    setVideoError(`${errorMessage} (Source: ${currentSrc || 'unknown source'})`);
  };

  const handleConvertVideo = async () => {
    if (!selectedRecording) return;

    setIsConverting(true);
    setVideoError(null);

    try {
      // Try to convert the video using the backend conversion endpoint
      const encodedStreamId = encodeURIComponent(selectedRecording.stream_id);
      const encodedFilename = encodeURIComponent(selectedRecording.filename);
      const convertUrl = `${API_BASE_URL}/api/archive/convert/${encodedStreamId}/${encodedFilename}`;
      console.log('Converting video:', convertUrl);

      // Call the conversion endpoint (which handles index repair / transcoding)
      const response = await fetch(convertUrl, { method: 'POST' });
      if (response.ok) {
        setUseConvertedVideo(true);
        setVideoError(null);
        // Force video element to reload with converted source
        if (videoRef.current) {
          videoRef.current.load();
        }
      } else {
        throw new Error('Conversion service failed or is unavailable');
      }
    } catch (error) {
      console.error('Video conversion failed:', error);
      setVideoError('Video conversion failed. Please try downloading the file and playing it with VLC or another media player.');
    } finally {
      setIsConverting(false);
    }
  };

  const downloadRecording = (recording) => {
    if (!recording) return;

    // Use the proper API endpoint for downloading
    const downloadUrl = `${API_BASE_URL}/api/archive/stream/${recording.stream_id}/${recording.filename}`;

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = recording.filename;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const captureVideoFrame = () => {
    if (!videoRef.current) return;
    try {
      const video = videoRef.current;
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || video.clientWidth;
      canvas.height = video.videoHeight || video.clientHeight;
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob((blob) => {
          if (blob) {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
            const cameraName = selectedRecording?.stream_id || 'camera';
            a.href = url;
            a.download = `frame_${cameraName}_${timestamp}.jpg`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
          }
        }, 'image/jpeg', 0.95);
      }
    } catch (err) {
      console.error('Failed to capture video frame:', err);
      alert('Unable to capture video frame. This might be due to security/cross-origin constraints if the video is loaded from a different domain.');
    }
  };

  // Handle time range selection for video segment extraction
  const handleTimeRangeChange = (range) => {
    setTimeRange(range);
  };

  // Handle video segment download
  const handleSegmentDownload = async (range) => {
    if (!selectedRecording || !range) return;

    setIsExtracting(true);
    setExtractionProgress('Preparing video segment...');

    try {
      // Extract the video segment
      const result = await archiveApi.extractVideoSegment(
        selectedRecording.stream_id,
        selectedRecording.filename,
        range.startTime,
        range.endTime
      );

      setExtractionProgress('Downloading segment...');

      // Download the extracted segment
      const blob = await archiveApi.downloadExtractedSegment(result.filename);

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      setExtractionProgress('Download completed!');
      setTimeout(() => {
        setExtractionProgress('');
        setShowTimeRangeSelector(false);
      }, 2000);

    } catch (error) {
      console.error('Error downloading video segment:', error);
      setExtractionProgress('Error: Failed to download video segment');
      setTimeout(() => setExtractionProgress(''), 3000);
    } finally {
      setIsExtracting(false);
    }
  };

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '00:00:00';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const getVideoSources = (recording) => {
    if (!recording) return [];

    const encodedStreamId = encodeURIComponent(recording.stream_id);
    const encodedFilename = encodeURIComponent(recording.filename);

    if (useConvertedVideo) {
      // Use converted video source
      return [
        `${API_BASE_URL}/api/archive/convert/${encodedStreamId}/${encodedFilename}`
      ];
    }

    return [
      `${API_BASE_URL}/api/archive/stream/${encodedStreamId}/${encodedFilename}`
    ];
  };

  const handlePlayRecording = (recording) => {
    setSelectedRecording(recording);
    setVideoError(null);
    setUseConvertedVideo(false);
    setIsConverting(false);
    setIsAutoConverting(false);
    autoConvertAttempted.current = false; // Reset auto-convert flag for new recording
    retryCount.current = 0; // Reset retry count for new recording
    if (onSelectRecording) {
      onSelectRecording(recording.filename);
    }
  };

  // Extract camera ID from stream_id
  const getCameraId = (streamId) => {
    if (!streamId) return 'CAM-XX';
    const parts = streamId.split('_');
    return `CAM-${parts.length > 1 ? parts[parts.length - 1].split('.').pop() || '01' : '01'}`;
  };

  const getCameraLocation = (streamId) => {
    if (!streamId) return 'Unknown Location';
    return streamId.replace(/_/g, ' ');
  };

  if (selectedRecording) {
    return (
      <div className="archive-playback-content">
        <div className="recordings-container">
          {/* Enhanced Back Navigation */}
          <div className="flex items-center mb-4">
            <button
              onClick={() => {
                setSelectedRecording(null);
                if (onSelectRecording) {
                  onSelectRecording(null);
                }
              }}
              className="flex items-center text-gray-600 hover:text-black mr-4"
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', background: '#f3f4f6', border: '1px solid #e5e7eb', borderRadius: '8px', cursor: 'pointer', fontSize: '14px', fontWeight: '500', color: '#374151', transition: 'all 0.2s ease' }}
            >
              <ChevronLeft className="w-5 h-5" />
              Back to Recordings
            </button>
          </div>

          <div style={{ borderRadius: '16px', overflow: 'hidden', border: '1px solid #e5e7eb', background: '#ffffff', boxShadow: '0 4px 24px rgba(0,0,0,0.08)' }}>
            {/* Video Player Area */}
            <div style={{ background: '#0c1425', position: 'relative' }}>
              {videoError ? (
                <div className="video-error-enhanced">
                  <div className="video-error-content">
                    <div className="error-icon-container">
                      <AlertCircle />
                    </div>
                    <h3>Video Playback Error</h3>
                    <p className="error-subtitle">
                      {videoError.includes('Network') ? 'Network error occurred.' : 'Playback unavailable'}
                    </p>
                    <div className="error-reason" style={{
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      maxWidth: '100%'
                    }} title={videoError}>
                      <AlertTriangle style={{ width: 14, height: 14, flexShrink: 0 }} />
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {videoError}
                      </span>
                    </div>
                    <div className="error-actions">
                      <button
                        onClick={() => {
                          setVideoError(null);
                          setUseConvertedVideo(false);
                          if (videoRef.current) videoRef.current.load();
                        }}
                        className="error-action-btn retry-btn"
                      >
                        <RefreshCw />
                        Retry Stream
                      </button>
                      <button
                        onClick={() => downloadRecording(selectedRecording)}
                        className="error-action-btn download-btn"
                      >
                        <Download />
                        Download File
                      </button>
                      <button
                        onClick={handleConvertVideo}
                        disabled={isConverting}
                        className="error-action-btn convert-btn"
                      >
                        <Film />
                        {isConverting ? 'Converting...' : 'Convert Format'}
                      </button>
                    </div>
                  </div>
                </div>
              ) : isAutoConverting ? (
                <div className="video-error-enhanced">
                  <div className="video-error-content">
                    <div className="error-icon-container" style={{ background: 'rgba(59,130,246,0.1)', borderColor: 'rgba(59,130,246,0.3)' }}>
                      <RefreshCw style={{ color: '#3b82f6', animation: 'spin 1s linear infinite' }} />
                    </div>
                    <h3>Preparing Video</h3>
                    <p className="error-subtitle">
                      Converting to browser-compatible format for playback. Please wait...
                    </p>
                  </div>
                </div>
              ) : isConverting ? (
                <div className="video-error-enhanced">
                  <div className="video-error-content">
                    <div className="error-icon-container" style={{ background: 'rgba(59,130,246,0.1)', borderColor: 'rgba(59,130,246,0.3)' }}>
                      <RefreshCw style={{ color: '#3b82f6', animation: 'spin 1s linear infinite' }} />
                    </div>
                    <h3>Converting Video</h3>
                    <p className="error-subtitle">
                      Converting to browser-compatible format. This may take a moment...
                    </p>
                  </div>
                </div>
              ) : (
                <video
                  key={`${selectedRecording?.filename || 'none'}-${useConvertedVideo ? 'converted' : 'raw'}`}
                  ref={videoRef}
                  style={{ width: '100%', minHeight: '320px', maxHeight: '480px', objectFit: 'contain', background: '#000' }}
                  onPlay={() => { setIsPlaying(true); }}
                  onPause={() => { setIsPlaying(false); }}
                  onTimeUpdate={handleVideoTimeUpdate}
                  onLoadedMetadata={handleVideoLoadedMetadata}
                  onError={handleVideoError}
                  onCanPlay={() => { setVideoError(null); }}
                  onLoadStart={() => { setVideoError(null); }}
                  controls
                  preload="metadata"
                  crossOrigin="anonymous"
                >
                  {getVideoSources(selectedRecording).map((src, index) => (
                    <source key={index} src={src} type="video/mp4" />
                  ))}
                  Your browser does not support the video tag.
                </video>
              )}
            </div>

            {/* Camera Metadata Bar */}
            <div className="camera-meta-bar">
              <div className="camera-meta-item">
                <div className="camera-meta-icon">
                  <Camera />
                </div>
                <div className="camera-meta-info">
                  <span className="camera-meta-label">Camera</span>
                  <span className="camera-meta-value">{getRecordingCameraInfo(selectedRecording.stream_id).name}</span>
                </div>
              </div>
              <div className="camera-meta-item">
                <div className="camera-meta-icon">
                  <MapPin />
                </div>
                <div className="camera-meta-info">
                  <span className="camera-meta-label">Location</span>
                  <span className="camera-meta-value">{getRecordingCameraInfo(selectedRecording.stream_id).location}</span>
                </div>
              </div>
              <div className="camera-meta-item">
                <div className="camera-meta-icon">
                  <Monitor />
                </div>
                <div className="camera-meta-info">
                  <span className="camera-meta-label">IP Address</span>
                  <span className="camera-meta-value">{getRecordingCameraInfo(selectedRecording.stream_id).ip}</span>
                </div>
              </div>
              <div className="camera-meta-item">
                <div className="camera-meta-icon">
                  <Calendar />
                </div>
                <div className="camera-meta-info">
                  <span className="camera-meta-label">Date & Time</span>
                  <span className="camera-meta-value">{formatDate(selectedRecording.timestamp)}</span>
                </div>
              </div>
              <div className="camera-meta-item">
                <div className="camera-meta-icon">
                  <Film />
                </div>
                <div className="camera-meta-info">
                  <span className="camera-meta-label">Codec</span>
                  <span className="camera-meta-value">H.264 MP4</span>
                </div>
              </div>
              <div className="camera-meta-item">
                <div className="camera-meta-icon">
                  <HardDrive />
                </div>
                <div className="camera-meta-info">
                  <span className="camera-meta-label">File Size</span>
                  <span className="camera-meta-value">
                    {selectedRecording.size_bytes ? `${Math.round(selectedRecording.size_bytes / 1024)} KB` : 'Unknown'}
                  </span>
                </div>
              </div>
            </div>

            {/* Enhanced Video Details Section */}
            <div className="video-details-section">
              {/* Camera Title and Action Buttons */}
              <div className="video-header">
                <div className="camera-info">
                  <h3 className="camera-title">
                    {getRecordingCameraInfo(selectedRecording.stream_id).name}
                  </h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '4px' }}>
                    <span style={{ fontSize: '13px', color: '#4b5563', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <MapPin style={{ width: '14px', height: '14px', color: '#ef4444' }} />
                      {getRecordingCameraInfo(selectedRecording.stream_id).location}
                    </span>
                    <span style={{ fontSize: '13px', color: '#4b5563', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Monitor style={{ width: '14px', height: '14px', color: '#3b82f6' }} />
                      {getRecordingCameraInfo(selectedRecording.stream_id).ip}
                    </span>
                  </div>
                </div>
                <div className="action-buttons-group">
                  <button
                    onClick={captureVideoFrame}
                    className="action-btn capture-btn"
                    title="Capture Frame"
                    style={{ background: 'linear-gradient(135deg, #14b8a6, #0d9488)', color: '#fff' }}
                  >
                    <Camera className="btn-icon" />
                    <span className="btn-text">Capture Frame</span>
                  </button>
                  <button
                    onClick={() => setShowVideoEditor(true)}
                    className="action-btn extract-btn"
                    title="Extract & Crop Video"
                  >
                    <Scissors className="btn-icon" />
                    <span className="btn-text">Extract & Crop</span>
                  </button>
                  <button
                    onClick={() => downloadRecording(selectedRecording)}
                    className="action-btn download-btn"
                    title="Download Full Video"
                  >
                    <Download className="btn-icon" />
                    <span className="btn-text">Download Full</span>
                  </button>
                </div>
              </div>

              {/* Video Metadata Grid */}
              <div className="video-metadata-grid">
                <div className="metadata-item">
                  <div className="metadata-icon">
                    <Calendar className="icon" />
                  </div>
                  <div className="metadata-content">
                    <span className="metadata-label">Date & Time</span>
                    <span className="metadata-value">{formatDate(selectedRecording.timestamp)}</span>
                  </div>
                </div>
                <div className="metadata-item">
                  <div className="metadata-icon">
                    <Clock className="icon" />
                  </div>
                  <div className="metadata-content">
                    <span className="metadata-label">Duration</span>
                    <span className="metadata-value">{formatTime(duration)}</span>
                  </div>
                </div>
                <div className="metadata-item">
                  <div className="metadata-icon">
                    <HardDrive className="icon" />
                  </div>
                  <div className="metadata-content">
                    <span className="metadata-label">File Size</span>
                    <span className="metadata-value">
                      {selectedRecording.size_bytes ? `${Math.round(selectedRecording.size_bytes / 1024)} KB` : 'Unknown Size'}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Time Range Selector Quick Tool */}
            {showTimeRangeSelector && (
              <TimeRangeSelector
                videoDuration={duration}
                currentTime={currentTime}
                onTimeRangeChange={handleTimeRangeChange}
                onDownload={handleSegmentDownload}
                isExtracting={isExtracting}
              />
            )}

            {/* Extraction Progress */}
            {extractionProgress && (
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
                <div className="flex items-center">
                  <RefreshCw className={`w-4 h-4 mr-2 ${isExtracting ? 'animate-spin' : ''} text-blue-600`} />
                  <span className="text-sm text-blue-700">{extractionProgress}</span>
                </div>
              </div>
            )}
          </div>

          {/* AI Video Analytics Panel */}
          <VideoAnalyticsPanel
            recording={selectedRecording}
            onExportEvidence={() => {
              console.log('Export evidence for:', selectedRecording.filename);
              downloadRecording(selectedRecording);
            }}
            onExtractSegment={() => {
              setShowVideoEditor(true);
            }}
          />

          {/* Interactive Video Editing Studio Modal */}
          {showVideoEditor && (
            <VideoEditorModal
              recording={selectedRecording}
              videoDuration={duration}
              videoSrc={getVideoSources(selectedRecording)[0]}
              cameraInfo={getRecordingCameraInfo(selectedRecording.stream_id)}
              onClose={() => setShowVideoEditor(false)}
              onSaveSuccess={(res) => {
                if (onViewChange) {
                  onViewChange('extracted-videos');
                }
              }}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="archive-playback-content">
      <div className="recordings-container">
        <div className="archive-header">
          <div>
            <h1 className="archive-title">Archive Playback</h1>
            <div className="archive-retention-badge">
              <HardDrive style={{ width: '14px', height: '14px', color: '#3b82f6' }} />
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#2563eb', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Archive Playback Available: Last 30 Days (720 Hours)
              </span>
            </div>
          </div>
        </div>

        {/* Filters */}
        {!isLoading && !error && recordings.length > 0 && (
          <div className="archive-filters">
            <div className="filter-group">
              {/* Search Bar Row */}
              <div className="filter-item search-bar-container" style={{ width: '100%', marginBottom: '4px' }}>
                <div style={{ position: 'relative', width: '100%', maxWidth: '600px' }}>
                  <input
                    type="text"
                    placeholder="Search by camera name, location, IP or filename..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 16px 10px 40px',
                      borderRadius: '8px',
                      border: '1px solid #d1d5db',
                      background: '#ffffff',
                      fontSize: '14px',
                      color: '#1f2937',
                      outline: 'none',
                      transition: 'all 0.2s ease',
                      boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)'
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = '#3b82f6';
                      e.target.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)';
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = '#d1d5db';
                      e.target.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)';
                    }}
                  />
                  <div style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af', display: 'flex', alignItems: 'center' }}>
                    <Search style={{ width: '18px', height: '18px' }} />
                  </div>
                  {searchTerm && (
                    <button
                      onClick={() => setSearchTerm('')}
                      style={{
                        position: 'absolute',
                        right: '12px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        color: '#9ca3af',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        padding: 0
                      }}
                      title="Clear search"
                    >
                      <X style={{ width: '16px', height: '16px' }} />
                    </button>
                  )}
                </div>
              </div>

              {/* Select Dropdowns Row */}
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'center' }}>
                {/* Location Filter */}
                <div className="filter-item">
                  <MapPin className="filter-icon" />
                  <label htmlFor="location-filter" className="filter-label">
                    Location:
                  </label>
                  <select
                    id="location-filter"
                    value={selectedLocationFilter}
                    onChange={(e) => setSelectedLocationFilter(e.target.value)}
                    className="filter-select"
                  >
                    <option value="all">All Locations</option>
                    {availableLocations.map(loc => (
                      <option key={loc} value={loc}>{loc}</option>
                    ))}
                  </select>
                  {selectedLocationFilter !== 'all' && (
                    <button
                      onClick={() => setSelectedLocationFilter('all')}
                      className="filter-clear-button"
                      title="Clear Location filter"
                    >
                      <X className="clear-icon" />
                    </button>
                  )}
                </div>

                {/* Camera Filter */}
                <div className="filter-item">
                  <Camera className="filter-icon" />
                  <label htmlFor="camera-filter" className="filter-label">
                    Camera:
                  </label>
                  <select
                    id="camera-filter"
                    value={selectedCameraFilter}
                    onChange={(e) => setSelectedCameraFilter(e.target.value)}
                    className="filter-select"
                  >
                    <option value="all">All Cameras</option>
                    {filteredAvailableCameras.map(cam => (
                      <option key={cam.streamId} value={cam.streamId}>{cam.name}</option>
                    ))}
                  </select>
                  {selectedCameraFilter !== 'all' && (
                    <button
                      onClick={() => setSelectedCameraFilter('all')}
                      className="filter-clear-button"
                      title="Clear Camera filter"
                    >
                      <X className="clear-icon" />
                    </button>
                  )}
                </div>

                {/* IP Address Filter */}
                <div className="filter-item">
                  <Filter className="filter-icon" />
                  <label htmlFor="ip-filter" className="filter-label">
                    IP Address:
                  </label>
                  <select
                    id="ip-filter"
                    value={selectedIpFilter}
                    onChange={(e) => setSelectedIpFilter(e.target.value)}
                    className="filter-select"
                  >
                    <option value="all">All IP Addresses</option>
                    {availableIPs.map(ip => {
                      const count = recordings.filter(recording => {
                        if (recording.stream_id) {
                          const info = getRecordingCameraInfo(recording.stream_id);
                          return info.ip === ip;
                        }
                        return false;
                      }).length;
                      return (
                        <option key={ip} value={ip}>
                          {ip} ({count} recordings)
                        </option>
                      );
                    })}
                  </select>
                  {selectedIpFilter !== 'all' && (
                    <button
                      onClick={() => setSelectedIpFilter('all')}
                      className="filter-clear-button"
                      title="Clear IP filter"
                    >
                      <X className="clear-icon" />
                    </button>
                  )}
                </div>

                {/* Date Filter */}
                <div className="filter-item">
                  <Calendar className="filter-icon" />
                  <label htmlFor="date-filter" className="filter-label">
                    Date:
                  </label>
                  <select
                    id="date-filter"
                    value={selectedDateFilter}
                    onChange={(e) => setSelectedDateFilter(e.target.value)}
                    className="filter-select"
                  >
                    <option value="all">All Dates</option>
                    <option value="today">Today</option>
                    <option value="yesterday">Yesterday</option>
                    <option value="week">Last 7 Days</option>
                    <option value="month">Last 30 Days</option>
                    <option value="custom">Custom Date Range</option>
                  </select>
                  {selectedDateFilter !== 'all' && (
                    <button
                      onClick={() => {
                        setSelectedDateFilter('all');
                        setCustomStartDate('');
                        setCustomEndDate('');
                      }}
                      className="filter-clear-button"
                      title="Clear date filter"
                    >
                      <X className="clear-icon" />
                    </button>
                  )}
                </div>
              </div>

              {/* Custom Date Range Inputs */}
              {selectedDateFilter === 'custom' && (
                <div className="filter-item custom-date-range">
                  <div className="date-range-inputs">
                    <div className="date-input-group">
                      <label htmlFor="start-date" className="date-label">From:</label>
                      <input
                        id="start-date"
                        type="date"
                        value={customStartDate}
                        onChange={(e) => setCustomStartDate(e.target.value)}
                        className="date-input"
                      />
                    </div>
                    <div className="date-input-group">
                      <label htmlFor="end-date" className="date-label">To:</label>
                      <input
                        id="end-date"
                        type="date"
                        value={customEndDate}
                        onChange={(e) => setCustomEndDate(e.target.value)}
                        className="date-input"
                        min={customStartDate}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Filter Results Summary */}
              {(selectedIpFilter !== 'all' || selectedLocationFilter !== 'all' || selectedCameraFilter !== 'all' || searchTerm !== '' || selectedDateFilter !== 'all') && (
                <div className="filter-results">
                  Showing {filteredRecordings.length} of {recordings.length} recordings
                  {selectedLocationFilter !== 'all' && ` • Location: ${selectedLocationFilter}`}
                  {selectedCameraFilter !== 'all' && ` • Camera: ${getRecordingCameraInfo(selectedCameraFilter).name}`}
                  {selectedIpFilter !== 'all' && ` • IP: ${selectedIpFilter}`}
                  {searchTerm !== '' && ` • Search: "${searchTerm}"`}
                  {selectedDateFilter !== 'all' && ` • Date: ${selectedDateFilter === 'custom' ? 'Custom Range' : selectedDateFilter}`}
                </div>
              )}
            </div>
          </div>
        )}

        {isLoading && (
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <h3>Loading Archive</h3>
            <p>Fetching recordings from all cameras...</p>
          </div>
        )}

        {error && (
          <div className="error-container">
            <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
            <h3>Unable to Load Archive</h3>
            <p className="error-message">{error}</p>
            <button onClick={handleRefresh} className="retry-button">
              Try Again
            </button>
          </div>
        )}

        {!isLoading && !error && (
          <div className="archive-recordings-grid">
            {recordings.length === 0 ? (
              <div className="col-span-full">
                <div className="no-recordings">
                  <div className="no-recordings-icon">📁</div>
                  <h3>No archived recordings found</h3>
                  <p>No recordings are currently available from any camera.</p>
                </div>
              </div>
            ) : filteredRecordings.length === 0 ? (
              <div className="col-span-full">
                <div className="no-recordings">
                  <div className="no-recordings-icon">🔍</div>
                  <h3>No recordings found for selected filters</h3>
                  <p>No recordings match the selected IP address and date filters.</p>
                  <button
                    onClick={() => {
                      setSelectedIpFilter('all');
                      setSelectedLocationFilter('all');
                      setSelectedCameraFilter('all');
                      setSearchTerm('');
                      setSelectedDateFilter('all');
                      setCustomStartDate('');
                      setCustomEndDate('');
                    }}
                    className="refresh-button"
                  >
                    <X className="refresh-icon" />
                    Clear All Filters
                  </button>
                </div>
              </div>
            ) : (
              filteredRecordings.map(recording => (
                <div
                  key={`${recording.stream_id || ''}-${recording.filename}`}
                  className="archive-recording-card"
                  onClick={() => handlePlayRecording(recording)}
                >
                  {/* Thumbnail Section */}
                  <div className="recording-thumbnail">
                    <div className="thumbnail-placeholder">
                      <Video className="thumbnail-icon" />
                    </div>
                    <div className="recording-status">
                      <div className="status-dot archived"></div>
                    </div>
                    <div className="recording-size">
                      {recording.size_bytes ? `${Math.round(recording.size_bytes / 1024)} KB` : 'N/A'}
                    </div>
                  </div>

                  {/* Content Section */}
                  <div className="recording-content">
                    {/* Header */}
                    <div className="recording-header">
                      <h4 className="recording-title">
                        {getRecordingCameraInfo(recording.stream_id).name}
                      </h4>
                      <div className="recording-time" style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px', marginBottom: '4px' }}>
                        <MapPin className="time-icon" style={{ width: '12px', height: '12px', color: '#ef4444' }} />
                        <span style={{ fontSize: '11px', color: '#4b5563', fontWeight: '500' }}>
                          {getRecordingCameraInfo(recording.stream_id).location}
                        </span>
                      </div>
                      <div className="recording-time">
                        <Clock className="time-icon" />
                        {formatDate(recording.timestamp)}
                      </div>
                    </div>

                    {/* Metadata */}
                    <div className="recording-metadata">
                      <div className="metadata-item">
                        <HardDrive className="metadata-icon" />
                        <span className="metadata-text">{recording.filename}</span>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="recording-actions">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePlayRecording(recording);
                        }}
                        className="action-button primary"
                      >
                        <Play className="action-icon" />
                        Play
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          downloadRecording(recording);
                        }}
                        className="action-button secondary"
                      >
                        <Download className="action-icon" />
                        Download
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default React.memo(FixedArchivePlayback);
