import React, { useEffect, useRef, useState, useCallback } from 'react';
import { io } from 'socket.io-client';
import { API_BASE_URL } from '../../utils/apiConfig';
import './CameraStream.css';

const DirectWebRTCPlayer = ({ rtspUrl, onError, onPlay }) => {
  const videoRef = useRef(null);
  const pcRef = useRef(null);
  const containerRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState(null);
  const [isConnecting, setIsConnecting] = useState(true);
  const [retryCount, setRetryCount] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const maxRetries = 3;
  const socketRef = useRef(null);
  const streamIdRef = useRef(null);

  const handleError = useCallback((error) => {
    console.error('WebRTC error:', error);
    const errorMessage = typeof error === 'string' ? error : (error.message || 'Unknown error');
    setError(errorMessage);
    setIsConnecting(false);
    if (onError) onError(errorMessage);
  }, [onError]);

  const playVideo = useCallback(async () => {
    try {
      if (videoRef.current) {
        console.log('Attempting to play video...');
        
        // Make video element visible
        videoRef.current.style.display = 'block';
        
        // Force autoplay with sound muted
        videoRef.current.muted = true;
        videoRef.current.playsInline = true;
        
        const playPromise = videoRef.current.play();
        
        if (playPromise !== undefined) {
          await playPromise.then(() => {
            console.log('Video playback started successfully');
            setIsPlaying(true);
            setError(null);
            setIsConnecting(false);
            if (onPlay) onPlay();
          }).catch(error => {
            console.error('Error playing video:', error);
            // Try again with user interaction
            document.addEventListener('click', async function onClick() {
              document.removeEventListener('click', onClick);
              try {
                await videoRef.current.play();
                setIsPlaying(true);
                setError(null);
                setIsConnecting(false);
                if (onPlay) onPlay();
              } catch (e) {
                handleError('Error playing video: ' + e.message);
              }
            }, { once: true });
          });
        }
      }
    } catch (playError) {
      console.error('Error in playVideo:', playError);
      handleError('Error playing video: ' + playError.message);
    }
  }, [onPlay, handleError]);

  const setupWebRTC = useCallback(async () => {
    console.log('setupWebRTC called with rtspUrl:', rtspUrl);
    
    if (!rtspUrl) {
      const errorMsg = 'No RTSP URL provided';
      console.error(errorMsg);
      handleError(errorMsg);
      return;
    }

    let cleanupPeerConnection = () => {};

    try {
      setIsConnecting(true);
      setError(null);

      // Clean up any existing connection
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }

      // Generate a unique ID for this stream
      streamIdRef.current = `stream_${Date.now()}`;

      // Connect to WebSocket server
      if (!socketRef.current) {
        const wsUrl = new URL(API_BASE_URL);
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsPath = '/ws/socket.io';
        
        console.log('Connecting to WebSocket server at:', `${wsProtocol}//${wsUrl.host}${wsPath}`);
        
        try {
          socketRef.current = io(API_BASE_URL, {
            path: wsPath,
            transports: ['websocket'],
            reconnectionAttempts: 5,
            reconnectionDelay: 1000,
            timeout: 20000,
            autoConnect: true,
            forceNew: true,
            withCredentials: false,
            extraHeaders: {}
          });
          
          // Add WebSocket event listeners for debugging
          socketRef.current.on('connect', () => {
            console.log('✅ WebSocket connected, socket ID:', socketRef.current.id);
          });
          
          socketRef.current.on('disconnect', (reason) => {
            console.warn('❌ WebSocket disconnected:', reason);
          });
          
          socketRef.current.on('connect_error', (error) => {
            console.error('WebSocket connection error:', error);
            handleError('Connection error. Please check your network and try again.');
          });
          
          socketRef.current.on('error', (error) => {
            console.error('WebSocket error:', error);
          });
          
          socketRef.current.on('reconnect_attempt', (attempt) => {
            console.log(`Attempting to reconnect (${attempt})...`);
          });
          
        } catch (error) {
          console.error('Failed to initialize WebSocket:', error);
          throw new Error('Failed to connect to the server');
        }

        // Set up socket event handlers
        socketRef.current.on('connect', async () => {
          console.log('Connected to signaling server');
          try {
            cleanupPeerConnection = await setupPeerConnection();
          } catch (error) {
            console.error('Failed to set up peer connection:', error);
            handleError('Failed to set up video connection');
          }
        });

        socketRef.current.on('disconnect', () => {
          console.log('Disconnected from signaling server');
          handleError('Disconnected from server. Reconnecting...');
        });

        socketRef.current.on('error', (error) => {
          console.error('Socket error:', error);
          handleError(`Connection error: ${error}`);
        });
      } else {
        cleanupPeerConnection = await setupPeerConnection();
      }

      // Return cleanup function
      return () => {
        cleanupPeerConnection();
        if (socketRef.current) {
          socketRef.current.off('connect');
          socketRef.current.off('disconnect');
          socketRef.current.off('error');
        }
      };

    } catch (error) {
      console.error('WebRTC setup error:', error);
      handleError(error);
      
      // Retry logic
      if (retryCount < maxRetries) {
        const delay = Math.pow(2, retryCount) * 1000;
        console.log(`Retrying in ${delay}ms (attempt ${retryCount + 1}/${maxRetries})`);
        setTimeout(() => {
          setRetryCount(prev => prev + 1);
          setupWebRTC();
        }, delay);
      }
    }
  }, [rtspUrl, retryCount, maxRetries]);

  const setupPeerConnection = useCallback(async () => {
    console.log('Setting up peer connection for RTSP URL:', rtspUrl);
    
    try {
      // Create a new RTCPeerConnection with STUN servers
      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' },
          { urls: 'stun:stun2.l.google.com:19302' },
          { urls: 'stun:stun3.l.google.com:19302' },
          { urls: 'stun:stun4.l.google.com:19302' },
          { urls: 'stun:global.stun.twilio.com:3478' }
        ],
        iceTransportPolicy: 'all',
        bundlePolicy: 'max-bundle',
        rtcpMuxPolicy: 'require',
        iceCandidatePoolSize: 10,
        sdpSemantics: 'unified-plan'
      });
      
      console.log('Created RTCPeerConnection with configuration:', pc.getConfiguration());

      pcRef.current = pc;

      // Set up event handlers
      pc.ontrack = (event) => {
        console.log('Received track:', event.track.kind);
        if (videoRef.current && event.streams && event.streams[0]) {
          console.log('Setting video source from stream');
          videoRef.current.srcObject = event.streams[0];
          playVideo().catch(err => {
            console.error('Error playing video:', err);
            handleError('Failed to play video stream');
          });
        } else {
          console.warn('Received track but no valid stream available');
        }
      };

      pc.onicecandidate = (event) => {
        if (event.candidate) {
          console.log('Local ICE candidate:', event.candidate);
          socketRef.current.emit('ice_candidate', {
            candidate: event.candidate.toJSON(),
            streamId: streamIdRef.current
          });
        } else {
          console.log('All ICE candidates have been generated');
        }
      };

      pc.oniceconnectionstatechange = () => {
        const state = pc.iceConnectionState;
        console.log('ICE connection state changed to:', state);
        
        switch (state) {
          case 'connected':
            console.log('✅ ICE connection established successfully');
            break;
          case 'disconnected':
            console.warn('⚠️ ICE connection disconnected');
            // Try to recover the connection
            setTimeout(() => {
              if (pc.iceConnectionState === 'disconnected') {
                handleError('Connection lost. Attempting to reconnect...');
                setupWebRTC();
              }
            }, 5000);
            break;
          case 'failed':
            console.error('❌ ICE connection failed');
            handleError('Connection failed. Please check your network and try again.');
            break;
          case 'closed':
            console.log('ℹ️ ICE connection closed');
            break;
          default:
            console.log(`ICE connection state: ${state}`);
        }
      };

      pc.onsignalingstatechange = () => {
        console.log('Signaling state changed to:', pc.signalingState);
        if (pc.signalingState === 'closed') {
          handleError('Connection closed. Please try again.');
        }
      };
      
      pc.onconnectionstatechange = () => {
        console.log('Connection state changed to:', pc.connectionState);
        if (pc.connectionState === 'failed') {
          handleError('Connection failed. Please check your network and try again.');
        }
      };

      // Add video transceiver with specific encoding parameters
      const transceiver = pc.addTransceiver('video', {
        direction: 'recvonly',
        streams: [],
        sendEncodings: [
          {
            maxBitrate: 1500000, // 1.5 Mbps
            maxFramerate: 30,
            scaleResolutionDownBy: 1
          }
        ]
      });

      // Create and send offer
      console.log('Creating offer...');
      const offer = await pc.createOffer({
        offerToReceiveVideo: true,
        offerToReceiveAudio: false,
        voiceActivityDetection: false
      });
      
      console.log('Offer created:', {
        type: offer.type,
        sdp: offer.sdp ? offer.sdp.substring(0, 100) + '...' : 'No SDP'
      });
      
      // Modify SDP to force H.264 if available
      if (offer.sdp) {
        offer.sdp = offer.sdp.replace(/m=video .+ VP8/g, 'm=video $1 H264');
      }
      
      console.log('Setting local description...');
      try {
        await pc.setLocalDescription(offer);
        console.log('Local description set successfully');
      } catch (e) {
        console.error('Failed to set local description:', e);
        throw e;
      }

      // Join the room with offer details
      console.log('Joining room with stream ID:', streamIdRef.current);
      
      try {
        socketRef.current.emit('join_room', {
          room: streamIdRef.current,
          rtspUrl: rtspUrl,
          sdp: {
            sdp: pc.localDescription.sdp,
            type: pc.localDescription.type
          }
        });
        console.log('join_room event emitted');
      } catch (e) {
        console.error('Failed to emit join_room:', e);
        throw e;
      }

      // Set up answer handler
      const handleAnswer = async (data) => {
        if (data.streamId === streamIdRef.current) {
          try {
            console.log('Received answer:', data.sdp);
            await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
          } catch (error) {
            console.error('Error setting remote description:', error);
            handleError('Failed to set up video stream');
          }
        }
      };

      // Set up ICE candidate handler
      const handleIceCandidate = async (data) => {
        if (data.streamId === streamIdRef.current && data.candidate) {
          try {
            console.log('Adding remote ICE candidate:', data.candidate);
            await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
          } catch (error) {
            console.error('Error adding ICE candidate:', error);
          }
        }
      };

      // Set up room joined handler
      const handleRoomJoined = (data) => {
        console.log('Successfully joined room:', data.room);
      };

      // Add event listeners
      socketRef.current.on('answer', handleAnswer);
      socketRef.current.on('ice_candidate', handleIceCandidate);
      socketRef.current.on('room_joined', handleRoomJoined);

      // Cleanup function
      return () => {
        console.log('Cleaning up peer connection...');
        socketRef.current.off('answer', handleAnswer);
        socketRef.current.off('ice_candidate', handleIceCandidate);
        socketRef.current.off('room_joined', handleRoomJoined);
        
        if (socketRef.current && streamIdRef.current) {
          socketRef.current.emit('leave_room', { streamId: streamIdRef.current });
        }
        
        if (pcRef.current) {
          pcRef.current.close();
          pcRef.current = null;
        }
        
        setIsConnecting(false);
      };

    } catch (error) {
      console.error('Peer connection setup error:', error);
      handleError('Failed to set up peer connection');
      throw error; // Re-throw to trigger retry logic
    }
  }, [rtspUrl, handleError, playVideo]);

  const handleRetry = useCallback(() => {
    setRetryCount(0);
    setupWebRTC();
  }, [setupWebRTC]);

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const delta = e.deltaY * -0.01;
    const newZoom = Math.min(Math.max(zoomLevel + delta, 1), 5);
    setZoomLevel(newZoom);
  }, [zoomLevel]);

  const handleMouseDown = useCallback((e) => {
    if (zoomLevel > 1) {
      setIsDragging(true);
      setDragStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  }, [zoomLevel, position]);

  const handleMouseMove = useCallback((e) => {
    if (isDragging && zoomLevel > 1) {
      const maxOffset = (zoomLevel - 1) * 100;
      const newX = Math.min(Math.max(e.clientX - dragStart.x, -maxOffset), maxOffset);
      const newY = Math.min(Math.max(e.clientY - dragStart.y, -maxOffset), maxOffset);
      setPosition({ x: newX, y: newY });
    }
  }, [isDragging, zoomLevel, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleDoubleClick = useCallback(() => {
    setZoomLevel(zoomLevel === 1 ? 2 : 1);
    setPosition({ x: 0, y: 0 });
  }, [zoomLevel]);

  return (
    <div 
      ref={containerRef}
      className={`video-container ${zoomLevel > 1 ? 'zoomed' : ''}`}
      style={{ 
        width: '100%', 
        height: '100%', 
        position: 'relative',
        overflow: 'hidden',
        cursor: isDragging ? 'grabbing' : (zoomLevel > 1 ? 'grab' : 'default')
      }}
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onDoubleClick={handleDoubleClick}
    >
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        style={{ 
          width: '100%', 
          height: '100%', 
          backgroundColor: '#000',
          display: isPlaying ? 'block' : 'none',
          objectFit: 'contain',
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          transform: `scale(${zoomLevel}) translate(${position.x / zoomLevel}px, ${position.y / zoomLevel}px)`,
          transition: isDragging ? 'none' : 'transform 0.2s ease-out',
          transformOrigin: 'center'
        }}
        onLoadedData={() => {
          console.log('Video loaded');
          setIsPlaying(true);
          setError(null);
          if (onPlay) onPlay();
        }}
        onError={(e) => {
          console.error('Video error:', e);
          handleError('Failed to load video stream');
        }}
      />
      {isPlaying && (
        <div className="zoom-controls">
          <button 
            className="zoom-button"
            onClick={() => {
              const newZoom = Math.max(zoomLevel - 0.5, 1);
              setZoomLevel(newZoom);
              if (newZoom === 1) setPosition({ x: 0, y: 0 });
            }}
            disabled={zoomLevel <= 1}
          >
            −
          </button>
          <button 
            className="zoom-button"
            onClick={() => setZoomLevel(Math.min(zoomLevel + 0.5, 5))}
            disabled={zoomLevel >= 5}
          >
            +
          </button>
          {zoomLevel > 1 && (
            <button 
              className="zoom-button"
              onClick={() => {
                setZoomLevel(1);
                setPosition({ x: 0, y: 0 });
              }}
            >
              ↺
            </button>
          )}
        </div>
      )}
      {!isPlaying && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#000',
          color: '#fff',
          flexDirection: 'column',
          gap: '10px'
        }}>
          {isConnecting ? (
            <>
              <div className="spinner"></div>
              <div>Connecting to stream...</div>
            </>
          ) : error ? (
            <>
              <div>❌ {error}</div>
              <button 
                onClick={handleRetry}
                style={{
                  padding: '8px 16px',
                  background: '#007bff',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  marginTop: '10px'
                }}
              >
                Retry
              </button>
            </>
          ) : (
            <div>Loading video stream...</div>
          )}
        </div>
      )}
      {isConnecting && !error && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <div>Connecting to stream...</div>
        </div>
      )}
      {error && (
        <div className="error-overlay">
          <div className="error-message">
            {error}
            <button 
              onClick={handleRetry} 
              className="retry-button"
              disabled={isConnecting}
            >
              {isConnecting ? 'Connecting...' : 'Retry'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DirectWebRTCPlayer;
