import React, { useEffect, useRef, useState, useCallback } from "react";
import { getAugmentUrl, API_BASE_URL } from '../../utils/apiConfig';
import { apiRequest } from '../../utils/api';
import "./CameraStream.css";

/**
 * WebRTCDetectionPlayer
 *
 * Production-quality WebRTC video player with AI detection overlay.
 * Connects once and stays connected — parent re-renders (tool switches,
 * drawing state changes, etc.) never tear down the stream.
 */
const WebRTCDetectionPlayer = ({
  rtspUrl,
  collectionName,
  cameraIp,
  streamId,
  roomId,
  onError,
  onPlay,
  children,
}) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const pcRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true);
  const [error, setError] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  // ── Stable callback refs ─────────────────────────────────────────────────
  // Store callbacks in refs so the WebRTC useEffect never re-fires when the
  // parent re-renders with new inline functions.
  const onErrorRef = useRef(onError);
  const onPlayRef = useRef(onPlay);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);
  useEffect(() => { onPlayRef.current = onPlay; }, [onPlay]);

  // ── Derive collection / IP from whatever props are provided ──────────────
  const actualCollectionName = useRef(collectionName);
  const actualCameraIp = useRef(cameraIp);

  // Derive from roomId or streamId if direct props not given
  if (roomId && !collectionName) {
    const parts = roomId.split('_');
    if (parts.length >= 2) {
      actualCollectionName.current = parts[0];
      actualCameraIp.current = parts.slice(1).join('_');
    }
  } else {
    actualCollectionName.current = collectionName;
    actualCameraIp.current = cameraIp;
  }

  if (streamId && !actualCollectionName.current && streamId !== 'webcam') {
    if (streamId.includes('_')) {
      const parts = streamId.split('_');
      if (parts.length >= 2) {
        actualCollectionName.current = parts[0];
        actualCameraIp.current = parts.slice(1).join('_');
      }
    } else if (streamId.includes('-')) {
      const parts = streamId.split('-');
      if (parts.length >= 5) {
        actualCollectionName.current = parts.slice(0, -4).join('-');
        actualCameraIp.current = parts.slice(-4).join('.');
      } else if (parts.length === 2) {
        actualCollectionName.current = parts[0];
        actualCameraIp.current = parts[1];
      }
    }
  }

  const colName = actualCollectionName.current;
  const camIp = actualCameraIp.current;

  // Stream ID used by backend detections endpoint
  const backendStreamId = (colName && camIp)
    ? `${colName}_${camIp}`
    : (streamId || '');

  // ── Retry handler ────────────────────────────────────────────────────────
  const handleRetry = useCallback(() => {
    setError(null);
    setIsPlaying(false);
    setIsConnecting(true);
    setRetryCount(prev => prev + 1);
  }, []);

  // ── WebRTC Connection ────────────────────────────────────────────────────
  // Dependencies: colName, camIp, retryCount ONLY.
  // Callbacks are accessed via refs — they NEVER trigger reconnection.
  useEffect(() => {
    if (!colName || !camIp) {
      if (streamId !== 'webcam') {
        setError("Missing collection name or camera IP");
        setIsConnecting(false);
      }
      return;
    }

    if (streamId === 'webcam') {
      setIsConnecting(false);
      setIsPlaying(true);
      return;
    }

    let destroyed = false;

    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' },
      ],
    });
    pcRef.current = pc;

    pc.ontrack = (event) => {
      if (destroyed) return;
      console.log('[WebRTCDetectionPlayer] Received track:', event.track.kind);
      if (videoRef.current && event.streams?.[0]) {
        videoRef.current.srcObject = event.streams[0];
      }
    };

    pc.oniceconnectionstatechange = () => {
      if (destroyed) return;
      const state = pc.iceConnectionState;
      console.log('[WebRTCDetectionPlayer] ICE state:', state);
      if (state === 'connected' || state === 'completed') {
        setIsConnecting(false);
        setError(null);
      } else if (state === 'failed') {
        setError('ICE connection failed');
        setIsConnecting(false);
      }
    };

    pc.addTransceiver('video', { direction: 'recvonly' });

    pc.createOffer({ offerToReceiveVideo: true, offerToReceiveAudio: false })
      .then(offer => {
        if (destroyed) throw new DOMException('Cancelled', 'AbortError');
        return pc.setLocalDescription(offer);
      })
      .then(() => {
        if (destroyed) throw new DOMException('Cancelled', 'AbortError');
        // Wait for ICE gathering to complete
        if (pc.iceGatheringState === 'complete') return;
        return new Promise((resolve) => {
          const check = () => {
            if (pc.iceGatheringState === 'complete') {
              pc.removeEventListener('icegatheringstatechange', check);
              resolve();
            }
          };
          pc.addEventListener('icegatheringstatechange', check);
          setTimeout(resolve, 3000); // fallback timeout
        });
      })
      .then(() => {
        if (destroyed) throw new DOMException('Cancelled', 'AbortError');
        console.log('[WebRTCDetectionPlayer] Sending offer for', colName, camIp);
        return fetch(getAugmentUrl("stream"), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sdp: pc.localDescription.sdp,
            type: pc.localDescription.type,
            collection_name: colName,
            camera_ip: camIp,
          }),
        });
      })
      .then(res => res.json())
      .then(answer => {
        if (destroyed) return;
        if (!answer.success) throw new Error(answer.error || 'Server rejected offer');
        if (pc.signalingState !== 'have-local-offer') return;
        return pc.setRemoteDescription(answer.data);
      })
      .catch(err => {
        if (destroyed || err?.name === 'AbortError') return;
        console.error('[WebRTCDetectionPlayer] Error:', err);
        setError(err.message || 'WebRTC connection failed');
        setIsConnecting(false);
        if (onErrorRef.current) onErrorRef.current(err.message);
      });

    return () => {
      destroyed = true;
      pcRef.current = null;
      pc.close();
    };
  }, [colName, camIp, retryCount]);

  // ── Detection overlay ────────────────────────────────────────────────────
  useEffect(() => {
    let animId;
    let intervalId;
    let latestDetections = [];

    const fetchDetections = async () => {
      if (!backendStreamId) return;
      try {
        const data = await apiRequest(`/api/stream/detections/${backendStreamId}`);
        if (data?.detections) latestDetections = data.detections;
      } catch (_) { /* silent */ }
    };

    const draw = () => {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      if (!canvas || !video) { animId = requestAnimationFrame(draw); return; }

      // Auto-sync canvas resolution to container
      const parent = canvas.parentElement;
      if (parent) {
        const pw = parent.clientWidth;
        const ph = parent.clientHeight;
        if (canvas.width !== pw || canvas.height !== ph) {
          canvas.width = pw;
          canvas.height = ph;
        }
      }

      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (video.videoWidth > 0 && video.videoHeight > 0) {
        const cAspect = canvas.width / canvas.height;
        const vAspect = video.videoWidth / video.videoHeight;
        let rw, rh, ox, oy;
        if (cAspect > vAspect) {
          rh = canvas.height; rw = rh * vAspect;
          ox = (canvas.width - rw) / 2; oy = 0;
        } else {
          rw = canvas.width; rh = rw / vAspect;
          ox = 0; oy = (canvas.height - rh) / 2;
        }

        latestDetections.forEach(det => {
          let x1, y1, x2, y2;
          if (det.norm_bbox) {
            x1 = ox + det.norm_bbox[0] * rw; y1 = oy + det.norm_bbox[1] * rh;
            x2 = ox + det.norm_bbox[2] * rw; y2 = oy + det.norm_bbox[3] * rh;
          } else if (det.bbox) {
            x1 = ox + (det.bbox[0] / video.videoWidth) * rw;
            y1 = oy + (det.bbox[1] / video.videoHeight) * rh;
            x2 = ox + (det.bbox[2] / video.videoWidth) * rw;
            y2 = oy + (det.bbox[3] / video.videoHeight) * rh;
          }
          if (x1 === undefined) return;

          const color = det.class === 'person' ? '#00d4ff' : '#00ff00';
          ctx.strokeStyle = color;
          ctx.lineWidth = 2;
          ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

          const label = `${det.class}${det.id ? ' ' + det.id : ''}`;
          ctx.font = '12px Arial';
          const tw = ctx.measureText(label).width;
          ctx.fillStyle = color;
          ctx.fillRect(x1, y1 - 20, tw + 8, 20);
          ctx.fillStyle = '#000';
          ctx.fillText(label, x1 + 4, y1 - 6);
        });
      }

      animId = requestAnimationFrame(draw);
    };

    intervalId = setInterval(fetchDetections, 100);
    animId = requestAnimationFrame(draw);

    return () => {
      clearInterval(intervalId);
      cancelAnimationFrame(animId);
    };
  }, [backendStreamId]);

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <div
      className="webrtc-player-root"
      style={{
        position: 'absolute',
        top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: '#000',
        overflow: 'hidden',
      }}
    >
      {/* Error overlay */}
      {error && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', color: '#fff',
          backgroundColor: 'rgba(0,0,0,0.85)', gap: '10px', zIndex: 10,
        }}>
          <div>❌ {error}</div>
          <button
            onClick={handleRetry}
            style={{
              padding: '8px 16px', background: '#00ffff', color: '#000',
              border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600,
            }}
          >
            Retry
          </button>
        </div>
      )}

      {/* Connecting overlay */}
      {!isPlaying && !error && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', color: '#fff',
          backgroundColor: 'rgba(0,0,0,0.7)', gap: '10px', zIndex: 10,
        }}>
          <div className="loading-spinner" />
          <div>{isConnecting ? "Connecting to stream..." : "Loading video..."}</div>
        </div>
      )}

      {/* Video or MJPEG webcam */}
      {streamId === 'webcam' ? (
        <img
          src={`${API_BASE_URL}/api/video_feed/webcam`}
          alt="Webcam"
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%', objectFit: 'contain',
            zIndex: 1,
          }}
          onLoad={() => {
            setIsPlaying(true);
            setIsConnecting(false);
            if (onPlayRef.current) onPlayRef.current();
          }}
          onError={() => {
            setError('Webcam feed error');
            if (onErrorRef.current) onErrorRef.current('Webcam feed error');
          }}
        />
      ) : (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%', objectFit: 'contain',
            zIndex: 1,
          }}
          onLoadedData={() => {
            console.log('[WebRTCDetectionPlayer] Video loaded');
            setIsPlaying(true);
            setIsConnecting(false);
            setError(null);
            if (onPlayRef.current) onPlayRef.current();
          }}
          onError={(e) => {
            console.error('[WebRTCDetectionPlayer] Video error:', e);
            setError('Video playback error');
            if (onErrorRef.current) onErrorRef.current('Video playback error');
          }}
        />
      )}

      {/* AI detection canvas */}
      <canvas
        ref={canvasRef}
        style={{
          position: 'absolute', top: 0, left: 0,
          width: '100%', height: '100%',
          pointerEvents: 'none', zIndex: 2,
        }}
      />

      {/* Zone drawing overlay (children from ZoneManagement) */}
      {children && (
        <div
          style={{
            position: 'absolute', top: 0, left: 0,
            width: '100%', height: '100%',
            pointerEvents: 'auto', zIndex: 3,
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
};

export default WebRTCDetectionPlayer;
