import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useCameraStore } from '../../store/cameraStore';
import { API_BASE_URL } from '../../utils/apiConfig';
import { getCameraStreamId } from '../../utils/cameraUtils';
import './AIDetectionTab.css';
import { 
    MdPersonSearch, MdVideocamOff, MdLocalMall, MdGroups, MdWarning, 
    MdFace, MdVerifiedUser, MdPanTool, MdBrush, MdNoTransfer, 
    MdFence, MdDirectionsWalk, MdPhonelinkErase, MdCategory, 
    MdSportsKabaddi, MdHealthAndSafety, MdRecordVoiceOver, MdVisibility, 
    MdWork, MdPolicy, MdError, MdDirectionsCar, MdMap,
    MdPerson, MdWidgets, MdNotificationsActive, MdBolt, MdCameraAlt, MdRule,
    MdSearch, MdPsychology, MdYoutubeSearchedFor, MdSettings
} from 'react-icons/md';
import ZoneManagement from '../configuration/ZoneManagement';

// ─── All 23 Detection Rules ─────────────────────────────────────
const ALL_RULES = [
    { id: 1, name: 'Appearance Search', icon: <MdPersonSearch />, category: 'identity' },
    { id: 2, name: 'Camera Tamper', icon: <MdVideocamOff />, category: 'system' },
    { id: 3, name: 'Chain/Handbag Snatching', icon: <MdLocalMall />, category: 'crime' },
    { id: 4, name: 'Crowd Detection', icon: <MdGroups />, category: 'crowd' },
    { id: 5, name: 'Eve Teasing', icon: <MdWarning />, category: 'crime' },
    { id: 6, name: 'Face Capture', icon: <MdFace />, category: 'identity' },
    { id: 7, name: 'Face Recognition', icon: <MdVerifiedUser />, category: 'identity' },
    { id: 8, name: 'Gesture Detection', icon: <MdPanTool />, category: 'behavior' },
    { id: 9, name: 'Graffiti / Vandalism', icon: <MdBrush />, category: 'crime' },
    { id: 10, name: 'Intrusion Detection', icon: <MdNoTransfer />, category: 'perimeter' },
    { id: 11, name: 'Lakshmanrekha Crossing', icon: <MdFence />, category: 'perimeter' },
    { id: 12, name: 'Loitering', icon: <MdDirectionsWalk />, category: 'behavior' },
    { id: 13, name: 'Mobile Snatching', icon: <MdPhonelinkErase />, category: 'crime' },
    { id: 14, name: 'Object Classification', icon: <MdCategory />, category: 'detection' },
    { id: 15, name: 'People Fighting', icon: <MdSportsKabaddi />, category: 'crime' },
    { id: 16, name: 'Person Collapsing', icon: <MdHealthAndSafety />, category: 'emergency' },
    { id: 17, name: 'Strike / Procession', icon: <MdRecordVoiceOver />, category: 'crowd' },
    { id: 18, name: 'Suspected Appearance', icon: <MdVisibility />, category: 'identity' },
    { id: 19, name: 'Unattended Object', icon: <MdWork />, category: 'detection' },
    { id: 20, name: 'Women Surrounded', icon: <MdPolicy />, category: 'crime' },
    { id: 21, name: 'Abduction Detection', icon: <MdError />, category: 'emergency' },
    { id: 22, name: 'Vehicle Monitoring', icon: <MdDirectionsCar />, category: 'detection' },
    { id: 23, name: 'Zone Monitoring', icon: <MdMap />, category: 'perimeter' },
];

const RULE_COLORS = {
    1: { color: '#6366f1' },  // Appearance Search: Royal Violet Indigo
    2: { color: '#ef4444' },  // Camera Tamper: Crimson Red
    3: { color: '#d946ef' },  // Chain/Handbag Snatching: Magenta Pink
    4: { color: '#0f766e' },  // Crowd Detection: Deep Teal
    5: { color: '#f97316' },  // Eve Teasing: Sunset Amber
    6: { color: '#10b981' },  // Face Capture: Emerald Green
    7: { color: '#2563eb' },  // Face Recognition: Electric Blue
    8: { color: '#8b5cf6' },  // Gesture Detection: Purple Grape
    9: { color: '#f43f5e' },  // Graffiti / Vandalism: Coral Orange
    10: { color: '#dc2626' }, // Intrusion Detection: High Alert Red
    11: { color: '#ea580c' }, // Lakshmanrekha Crossing: Boundary Orange
    12: { color: '#a21caf' }, // Loitering: Antique Plum
    13: { color: '#6d28d9' }, // Mobile Snatching: Electric Violet
    14: { color: '#64748b' }, // Object Classification: Slate Grey
    15: { color: '#e11d48' }, // People Fighting: Crimson Rose
    16: { color: '#06b6d4' }, // Person Collapsing: Cyber Cyan
    17: { color: '#b45309' }, // Strike / Procession: Burnt Ochre
    18: { color: '#701a75' }, // Suspected Appearance: Amethyst Purple
    19: { color: '#ca8a04' }, // Unattended Object: Gold Bronze
    20: { color: '#ec4899' }, // Women Surrounded: Lavender Rose
    21: { color: '#991b1b' }, // Abduction Detection: Dark Cherry Red
    22: { color: '#0284c7' }, // Vehicle Monitoring: Deep Sea Blue
    23: { color: '#16a34a' }  // Zone Monitoring: Vivid Green
};

const getRuleColors = (color) => {
    return {
        '--rule-color': color,
        '--rule-bg': `${color}0b`,        // ~4% opacity
        '--rule-active-bg': `${color}14`, // ~8% opacity
        '--rule-border': `${color}59`,    // ~35% opacity
        '--rule-glow': `${color}33`       // ~20% opacity
    };
};

// Detailed descriptions for the 23 detection rules
const RULE_DESCRIPTIONS = {
    1: "Track and search individuals across multiple camera feeds using clothing color, gender, and hair characteristics.",
    2: "Detects physical disruption of the camera, including redirection, defocusing, covering, or spray-painting.",
    3: "Flags sudden grabbing motions and high-speed running behaviors characteristic of bag theft.",
    4: "Monitors density thresholds to identify heavy pedestrian build-up, unauthorized assemblies, or congestion.",
    5: "AI behavioral heuristic to detect harassment, stalking, and uncomfortable proximity to women.",
    6: "Optimized high-resolution portrait capture of all faces entering the field of view for database entry.",
    7: "Matches captured faces against known white/blacklists in real-time to alert security.",
    8: "Detects hand signals, raised arms, waves, or threat gestures to trigger automated responses.",
    9: "Identifies spray painting, marker defacement, or structural damage as it happens.",
    10: "Triggers an alarm when any person or vehicle enters a strictly defined restricted area.",
    11: "Line-crossing trigger that alerts security if a virtual boundary is crossed in a specific direction.",
    12: "Flags individuals who remain within a specified zone for longer than a predefined threshold.",
    13: "Detects sudden hand snatching actions targeting phones and rapid flight behavior.",
    14: "Categorizes all detected assets into precise groups like bags, boxes, gear, and animals.",
    15: "Identifies aggressive physical violence, pushing, shoving, and high-energy combat poses.",
    16: "Emergency alert for medical crises, slips, trips, or individuals falling and remaining on the ground.",
    17: "Flags organized marches, protests, shouting groups, and banners blocking public pathways.",
    18: "Automatically tags and tracks persons matching suspicious behavior profiles or blacklists.",
    19: "Detects luggage, bags, or items left behind in public transit or secure areas without an owner.",
    20: "Behavioral model to alert when a lone woman is clustered or cornered by multiple individuals.",
    21: "High-priority threat alert for struggle, forced movement, or grabbing in public areas.",
    22: "Tracks vehicles, detects illegal parking, speed violations, or wrong-way driving.",
    23: "Full visual boundary analysis that tracks and logs all occupancy and dwell times in target zones."
};

const SEVERITY_ORDER = { critical: 4, high: 3, medium: 2, low: 1 };
const SEVERITY_COLORS = {
    critical: '#ff2d55',
    high: '#ff6b35',
    medium: '#ffaa00',
    low: '#00d4ff',
};

const AIDetectionTab = () => {
    const { selectedAiCamera } = useCameraStore();
    const [streamUrl, setStreamUrl] = useState('');
    const [events, setEvents] = useState([]);
    const [detections, setDetections] = useState({ detections: [], counts: {} });
    const [activeRules, setActiveRules] = useState([]);
    const [globalRules, setGlobalRules] = useState([]);
    const [selectedRuleId, setSelectedRuleId] = useState(null);
    const [aiStatus, setAiStatus] = useState(null);
    const [streamKey, setStreamKey] = useState(0);
    const [streamError, setStreamError] = useState(false);
    const [ruleFilter, setRuleFilter] = useState('all');
    const [showZoneConfig, setShowZoneConfig] = useState(false);
    const [togglingRuleId, setTogglingRuleId] = useState(null);
    const [hoveredRule, setHoveredRule] = useState(null);
    const [tooltipPos, setTooltipPos] = useState({ top: 0, left: 0 });
    const prevCameraRef = useRef(null);
    const eventsEndRef = useRef(null);
    const imgRef = useRef(null);
    const canvasRef = useRef(null);
    const activeRulesRef = useRef(activeRules);
    const [cameraZones, setCameraZones] = useState([]);
    const cameraZonesRef = useRef(cameraZones);

    // Keep activeRulesRef and cameraZonesRef in sync
    useEffect(() => {
        activeRulesRef.current = activeRules;
    }, [activeRules]);

    useEffect(() => {
        cameraZonesRef.current = cameraZones;
    }, [cameraZones]);

    // Fetch camera zones for selected camera
    useEffect(() => {
        if (!selectedAiCamera) {
            setCameraZones([]);
            return;
        }
        const streamId = getCameraStreamId(selectedAiCamera);

        fetch(`/api/augment/camera-zones/${streamId}`)
            .then(res => res.json())
            .then(data => {
                if (data && data.success && data.data) {
                    setCameraZones(data.data.zones || []);
                } else {
                    setCameraZones([]);
                }
            })
            .catch(() => setCameraZones([]));
    }, [selectedAiCamera]);

    // Auto-scroll events panel
    useEffect(() => {
        if (eventsEndRef.current) {
            eventsEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [events]);

    // Fetch AI engine status
    useEffect(() => {
        const fetchStatus = async () => {
            try {
                const response = await fetch('/api/ai/status');
                const data = await response.json();
                setAiStatus(data);
            } catch (error) { /* silent */ }
        };
        fetchStatus();
        const interval = setInterval(fetchStatus, 10000);
        return () => clearInterval(interval);
    }, []);

    // Fetch active rules and global rules for this camera
    useEffect(() => {
        if (!selectedAiCamera) {
            setActiveRules([]);
            return;
        }
        const fetchRules = async () => {
            try {
                // Fetch global rules definitions
                const globalRulesResponse = await fetch('/api/augment/events/rules');
                const globalRulesData = await globalRulesResponse.json();
                if (globalRulesData.success) {
                    setGlobalRules(globalRulesData.data.rules || []);
                }

                // Fetch active camera rules
                const response = await fetch('/api/augment/camera-rules');
                const data = await response.json();
                if (data.success) {
                    const cameraMap = data.data.cameraRules || {};
                    setActiveRules(cameraMap[selectedAiCamera.id] || []);
                }
            } catch (error) { /* silent */ }
        };
        fetchRules();
        const interval = setInterval(fetchRules, 8000);
        return () => clearInterval(interval);
    }, [selectedAiCamera]);

    // Main camera selection handler
    useEffect(() => {
        setSelectedRuleId(null);
        if (!selectedAiCamera) {
            setStreamUrl('');
            setEvents([]);
            setDetections({ detections: [], counts: {} });
            return;
        }

        const streamId = getCameraStreamId(selectedAiCamera);

        // Stop old detection
        if (prevCameraRef.current && prevCameraRef.current !== streamId) {
            fetch(`/api/stream/detection/stop/${prevCameraRef.current}`, { method: 'POST' }).catch(() => {});
        }
        prevCameraRef.current = streamId;

        setStreamError(false);
        setStreamKey(Date.now());
        // Use the raw MJPEG stream (no backend annotations, extremely low CPU)
        if (streamId === 'webcam') {
            setStreamUrl(`${API_BASE_URL}/api/video_feed/webcam/raw`);
        } else {
            setStreamUrl(`${API_BASE_URL}/api/video_feed/${streamId}`);
        }
        
        // Poll events + detections (for sidebar updates and count badges every 2s)
        const fetchData = async () => {
            try {
                const [eventsRes, detectionsRes] = await Promise.all([
                    fetch(`/api/stream/events/${streamId}`),
                    fetch(`/api/stream/detections/${streamId}`)
                ]);
                const eventsData = await eventsRes.json();
                const detectionsData = await detectionsRes.json();
                setEvents(eventsData.events || []);
                setDetections(detectionsData || { detections: [], counts: {} });
            } catch (error) { /* silent */ }
        };

        const intervalId = setInterval(fetchData, 2000);
        fetchData();

        return () => {
            clearInterval(intervalId);
            fetch(`/api/stream/detection/stop/${streamId}`, { method: 'POST' }).catch(() => {});
        };
    }, [selectedAiCamera]);

    // Sync backend detection state with active rules count
    useEffect(() => {
        if (!selectedAiCamera) return;
        const streamId = getCameraStreamId(selectedAiCamera);
        
        if (activeRules && activeRules.length > 0) {
            console.log('Enabling AI detection for stream:', streamId);
            fetch(`/api/stream/detection/start/${streamId}`, { method: 'POST' }).catch(() => {});
        } else {
            console.log('Disabling AI detection for stream:', streamId);
            fetch(`/api/stream/detection/stop/${streamId}`, { method: 'POST' }).catch(() => {});
        }
        
        return () => {
            fetch(`/api/stream/detection/stop/${streamId}`, { method: 'POST' }).catch(() => {});
        };
    }, [selectedAiCamera, activeRules]);

    // Canvas dynamic overlay and 150ms polling loop
    useEffect(() => {
        if (!selectedAiCamera || streamError) return;

        const streamId = getCameraStreamId(selectedAiCamera);

        let isMounted = true;
        let detectionsCache = [];
        let frameWidth = 640;
        let frameHeight = 480;
        let aiFps = 0;
        let lastFpsTime = Date.now();
        let fpsCounter = 0;

        // Poll detections at 150ms (ultra low latency and highly performant)
        const pollInterval = setInterval(async () => {
            if (!isMounted) return;

            // Only poll and update if AI rules are active
            if (!activeRulesRef.current || activeRulesRef.current.length === 0) {
                detectionsCache = [];
                aiFps = 0;
                return;
            }

            try {
                const response = await fetch(`/api/stream/detections/${streamId}`);
                const data = await response.json();
                if (data && isMounted) {
                    detectionsCache = data.detections || [];
                    if (data.frame_width) frameWidth = data.frame_width;
                    if (data.frame_height) frameHeight = data.frame_height;
                    
                    fpsCounter++;
                    const now = Date.now();
                    if (now - lastFpsTime >= 1000) {
                        aiFps = Math.round((fpsCounter * 1000) / (now - lastFpsTime));
                        if (aiFps > 4) aiFps = 4; // Caps FPS indicator to processed rate
                        fpsCounter = 0;
                        lastFpsTime = now;
                    }
                }
            } catch (err) { /* silent */ }
        }, 150);

        // Frame rendering loop using requestAnimationFrame to prevent blocks
        let animFrameId;
        const draw = () => {
            if (!isMounted) return;
            const canvas = canvasRef.current;
            const img = imgRef.current;

            if (canvas && img && img.complete && img.naturalWidth) {
                // Resize canvas resolution to match its CSS rendering area size
                if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
                    canvas.width = canvas.clientWidth;
                    canvas.height = canvas.clientHeight;
                }

                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                // Math to align with object-fit: contain
                const imgWidth = img.naturalWidth;
                const imgHeight = img.naturalHeight;
                const containerWidth = canvas.width;
                const containerHeight = canvas.height;

                const imgRatio = imgWidth / imgHeight;
                const containerRatio = containerWidth / containerHeight;

                let renderWidth, renderHeight, offsetX, offsetY;
                if (containerRatio > imgRatio) {
                    renderHeight = containerHeight;
                    renderWidth = containerHeight * imgRatio;
                    offsetX = (containerWidth - renderWidth) / 2;
                    offsetY = 0;
                } else {
                    renderWidth = containerWidth;
                    renderHeight = containerWidth / imgRatio;
                    offsetX = 0;
                    offsetY = (containerHeight - renderHeight) / 2;
                }

                const scaleX = renderWidth / frameWidth;
                const scaleY = renderHeight / frameHeight;

                // Color mappings based on classes
                const classColors = {
                    person: '#00ffcc',       // Neon Mint
                    car: '#0088ff',          // Blue
                    truck: '#0088ff',
                    bus: '#0088ff',
                    motorcycle: '#0088ff',
                    bicycle: '#0088ff',
                    bag: '#ffa500',          // Orange
                    backpack: '#ffa500',
                    suitcase: '#ffa500',
                    handbag: '#ffa500',
                    umbrella: '#ffa500',
                    weapon: '#ff3366',       // Red alert
                    fire: '#ff3366',
                    smoke: '#ff3366'
                };

                // Draw bounding boxes on canvas layer
                if (activeRulesRef.current && activeRulesRef.current.length > 0 && detectionsCache && detectionsCache.length > 0) {
                    detectionsCache.forEach((det) => {
                        let box = det.box || [];
                        if (box.length === 4) {
                            const [x1, y1, x2, y2] = box;
                            const rx1 = x1 * scaleX + offsetX;
                            const ry1 = y1 * scaleY + offsetY;
                            const rx2 = x2 * scaleX + offsetX;
                            const ry2 = y2 * scaleY + offsetY;
                            const rw = rx2 - rx1;
                            const rh = ry2 - ry1;

                            const label = (det.label || 'unknown').toLowerCase();
                            const conf = det.confidence || 0;
                            const color = classColors[label] || '#ffa500';

                            // Bounding box border
                            ctx.strokeStyle = color;
                            ctx.lineWidth = 2.5;
                            ctx.strokeRect(rx1, ry1, rw, rh);

                            // Label background badge
                            ctx.fillStyle = color;
                            ctx.font = 'bold 11px sans-serif';
                            const labelText = `${label.toUpperCase()} ${(conf * 100).toFixed(0)}%`;
                            const textWidth = ctx.measureText(labelText).width;
                            ctx.fillRect(rx1 - 1, ry1 - 18, textWidth + 12, 18);

                            // Label text
                            ctx.fillStyle = '#000000';
                            ctx.fillText(labelText, rx1 + 5, ry1 - 5);
                        }
                    });
                }

                // Render Camera Zones if Zone Monitoring (23), Intrusion (10), or Lakshmanrekha (11) is active
                const isZoneMonitoringActive = activeRulesRef.current.some(id => [10, 11, 23].includes(id));
                if (isZoneMonitoringActive && cameraZonesRef.current && cameraZonesRef.current.length > 0) {
                    cameraZonesRef.current.forEach((zone) => {
                        const isIntrusion = activeRulesRef.current.includes(10);
                        const isLakshman = activeRulesRef.current.includes(11);
                        const zColor = isIntrusion ? '#dc2626' : isLakshman ? '#ea580c' : '#16a34a';
                        const zFill = isIntrusion ? 'rgba(220, 38, 38, 0.22)' : isLakshman ? 'rgba(234, 88, 12, 0.22)' : 'rgba(22, 163, 74, 0.22)';

                        ctx.save();
                        ctx.strokeStyle = zColor;
                        ctx.fillStyle = zFill;
                        ctx.lineWidth = 2.5;

                        if (zone.type === 'circle' && zone.center && zone.radius) {
                            const cx = zone.center[0] * renderWidth + offsetX;
                            const cy = zone.center[1] * renderHeight + offsetY;
                            const r = zone.radius * Math.min(renderWidth, renderHeight);

                            ctx.beginPath();
                            ctx.arc(cx, cy, r, 0, 2 * Math.PI);
                            ctx.fill();
                            ctx.stroke();

                            // Label badge
                            const labelText = `ZONE: ${(zone.name || 'Circle').toUpperCase()}`;
                            ctx.font = 'bold 11px sans-serif';
                            const tw = ctx.measureText(labelText).width;
                            ctx.fillStyle = zColor;
                            ctx.fillRect(cx - (tw / 2) - 5, Math.max(0, cy - r - 20), tw + 10, 18);
                            ctx.fillStyle = '#ffffff';
                            ctx.fillText(labelText, cx - (tw / 2), Math.max(12, cy - r - 6));
                        } else if (zone.polygon && zone.polygon.length > 0) {
                            const pts = zone.polygon.map(([px, py]) => [
                                px * renderWidth + offsetX,
                                py * renderHeight + offsetY
                            ]);

                            ctx.beginPath();
                            ctx.moveTo(pts[0][0], pts[0][1]);
                            for (let i = 1; i < pts.length; i++) {
                                ctx.lineTo(pts[i][0], pts[i][1]);
                            }
                            if (pts.length > 2) {
                                ctx.closePath();
                                ctx.fill();
                            }
                            ctx.stroke();

                            // Label badge
                            const minX = Math.min(...pts.map(p => p[0]));
                            const minY = Math.min(...pts.map(p => p[1]));
                            const labelText = `ZONE: ${(zone.name || 'Zone').toUpperCase()}`;
                            ctx.font = 'bold 11px sans-serif';
                            const tw = ctx.measureText(labelText).width;
                            ctx.fillStyle = zColor;
                            ctx.fillRect(minX, Math.max(0, minY - 20), tw + 10, 18);
                            ctx.fillStyle = '#ffffff';
                            ctx.fillText(labelText, minX + 5, Math.max(12, minY - 6));
                        }
                        ctx.restore();
                    });
                }

                // Render dynamic FPS counter overlay
                ctx.fillStyle = 'rgba(0, 0, 0, 0.75)';
                ctx.fillRect(canvas.width - 210, 10, 200, 32);
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
                ctx.lineWidth = 1;
                ctx.strokeRect(canvas.width - 210, 10, 200, 32);

                ctx.fillStyle = '#ffffff';
                ctx.font = 'bold 10px monospace';
                const streamFps = img.complete ? 25 : 0;
                const displayAiFps = (activeRulesRef.current.length > 0 && detectionsCache.length > 0) ? (aiFps || 4) : 0;
                ctx.fillText(`STREAM FPS: ${streamFps} | AI FPS: ${displayAiFps}`, canvas.width - 195, 29);
            }

            animFrameId = requestAnimationFrame(draw);
        };

        animFrameId = requestAnimationFrame(draw);

        return () => {
            isMounted = false;
            clearInterval(pollInterval);
            cancelAnimationFrame(animFrameId);
        };
    }, [selectedAiCamera, streamError]);

    // Handle rule toggling
    const handleToggleRule = async (ruleId) => {
        if (!selectedAiCamera || togglingRuleId) return;

        const isCurrentlyActive = activeRules.includes(ruleId);
        const newActiveRules = isCurrentlyActive 
            ? activeRules.filter(id => id !== ruleId)
            : [...activeRules, ruleId];

        // Optimistic update
        setActiveRules(newActiveRules);
        setTogglingRuleId(ruleId);

        try {
            const response = await fetch(`${API_BASE_URL}/api/augment/apply-camera-rules`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cameraIds: [selectedAiCamera.id],
                    ruleIds: newActiveRules
                })
            });
            const data = await response.json();
            if (!data.success) {
                // Rollback on failure
                setActiveRules(activeRules);
                console.error('Failed to update rules:', data.error);
            }
        } catch (error) {
            setActiveRules(activeRules);
            console.error('Error toggling rule:', error);
        } finally {
            setTogglingRuleId(null);
        }
    };

    // Build rule status map from events
    const ruleStatusMap = {};
    events.forEach(evt => {
        const ruleId = evt.id;
        if (!ruleStatusMap[ruleId] || SEVERITY_ORDER[evt.severity] > SEVERITY_ORDER[ruleStatusMap[ruleId].severity]) {
            ruleStatusMap[ruleId] = evt;
        }
    });

    // Stats (only updated if rules are active)
    const personCount = activeRules.length > 0 ? (detections.counts?.person || 0) : 0;
    const vehicleCount = activeRules.length > 0 
        ? Object.entries(detections.counts || {})
            .filter(([cls]) => ['car', 'truck', 'bus', 'motorcycle', 'bicycle'].includes(cls))
            .reduce((sum, [, count]) => sum + count, 0)
        : 0;
    const objectCount = activeRules.length > 0
        ? Object.entries(detections.counts || {})
            .filter(([cls]) => !['person', 'car', 'truck', 'bus', 'motorcycle', 'bicycle'].includes(cls))
            .reduce((sum, [, count]) => sum + count, 0)
        : 0;
    const alertCount = activeRules.length > 0
        ? events.filter(e => ['critical', 'high'].includes(e.severity)).length
        : 0;

    // Filter rules for display
    const filteredRules = ALL_RULES.filter(rule => {
        if (ruleFilter === 'all') return true;
        if (ruleFilter === 'active') return activeRules.includes(rule.id);
        if (ruleFilter === 'detecting') return !!ruleStatusMap[rule.id];
        return rule.category === ruleFilter;
    });

    // Filter events by selectedRuleId
    const filteredEvents = selectedRuleId
        ? events.filter(evt => {
            const ruleObj = ALL_RULES.find(r => r.id === selectedRuleId);
            if (!ruleObj) return true;
            const eventName = (evt.type || evt.name || '').toLowerCase();
            const ruleName = ruleObj.name.toLowerCase();
            const msg = (evt.message || evt.msg || '').toLowerCase();
            return eventName.includes(ruleName) || 
                   ruleName.includes(eventName) || 
                   msg.includes(ruleName) ||
                   evt.id === ruleObj.id;
          })
        : events;

    const streamId = selectedAiCamera ? prevCameraRef.current : null;

    return (
        <div className="ai-detection-lab">
            <div className="lab-main">
                {/* ─── LEFT COLUMN: Video + Stats ─── */}
                <div className="lab-left-column">
                    {/* Engine Status Bar */}
                    <div className="engine-status-bar">
                        <div className="status-group">
                            <span className="status-label">ENGINE</span>
                            <span className={`status-chip ${aiStatus?.gemma?.initialized ? 'active' : 'inactive'}`}>
                                {aiStatus?.gemma?.initialized ? <><MdBolt style={{ marginRight: '4px' }} /> GEMMA 4</> : 'OFFLINE'}
                            </span>
                            <span className="status-chip mode">
                                {aiStatus?.gemma?.mode || 'CPU'}
                            </span>
                        </div>
                        <div className="status-group">
                            <span className="status-label">YOLO</span>
                            <span className="status-chip active"><MdCameraAlt style={{ marginRight: '4px' }} /> ACTIVE</span>
                        </div>
                        <div className="status-group">
                            <span className="status-label">RULES</span>
                            <span className="status-chip rules"><MdRule style={{ marginRight: '4px' }} /> {activeRules.length}/23</span>
                        </div>
                    </div>

                    {/* Video Viewport */}
                    <div className="viewport-container">
                        <div className="viewport-header">
                            <h3>{selectedAiCamera?.name || 'No Camera Selected'}</h3>
                            <div className="status-badges">
                                <span className="badge layer1">L1 YOLO</span>
                                <span className="badge layer2">L2 PATTERN</span>
                                {aiStatus?.gemma?.initialized && (
                                    <span className="badge layer3">L3 GEMMA</span>
                                )}
                                <button 
                                    className="configure-zones-btn"
                                    onClick={() => setShowZoneConfig(true)}
                                    title="Configure Zones & Boundaries"
                                >
                                    <MdSettings style={{ marginRight: '4px' }} /> Zones
                                </button>
                            </div>
                        </div>

                        <div className="video-viewport">
                            {selectedAiCamera ? (
                                streamError ? (
                                    <div className="no-camera-placeholder">
                                        <p>Stream connection lost. Retrying...</p>
                                        <button 
                                            className="retry-btn"
                                            onClick={() => { setStreamError(false); setStreamKey(Date.now()); }}
                                        >
                                            Reconnect
                                        </button>
                                    </div>
                                ) : (
                                    <>
                                        <img 
                                            ref={imgRef}
                                            key={streamKey}
                                            src={streamUrl} 
                                            alt="AI Detection Stream" 
                                            className="detection-image"
                                            style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }}
                                            onError={(e) => {
                                                // Only show error if the img actually failed to load
                                                // Don't set error on first mount (stream may need time to start)
                                                console.warn('Detection stream img error:', e.target.src);
                                                if (!streamError) {
                                                    setTimeout(() => setStreamError(true), 8000);
                                                }
                                            }}
                                        />
                                        <canvas 
                                            ref={canvasRef}
                                            style={{
                                                position: 'absolute',
                                                top: 0,
                                                left: 0,
                                                width: '100%',
                                                height: '100%',
                                                pointerEvents: 'none',
                                                zIndex: 5
                                            }}
                                        />
                                    </>
                                )
                            ) : (
                                <div className="no-camera-placeholder">
                                    <div className="placeholder-icon">LIVE</div>
                                    <p>Select a camera from the sidebar to start AI analysis</p>
                                </div>
                            )}
                            
                            {selectedAiCamera && !streamError && (
                                activeRules.length > 0 ? (
                                    <div className="ai-overlay-tag">
                                        <span className="pulse-dot"></span>
                                        LIVE AI ANALYSIS
                                    </div>
                                ) : (
                                    <div className="ai-overlay-tag standby">
                                        <span className="standby-dot"></span>
                                        AI STANDBY
                                    </div>
                                )
                            )}
                        </div>
                    </div>

                    {/* Detection Stats Bar */}
                    <div className="detection-stats-bar">
                        <div className="stat-card persons">
                            <span className="stat-icon"><MdPerson /></span>
                            <div className="stat-data">
                                <span className="stat-value">{personCount}</span>
                                <span className="stat-label">Persons</span>
                            </div>
                        </div>
                        <div className="stat-card vehicles">
                            <span className="stat-icon"><MdDirectionsCar /></span>
                            <div className="stat-data">
                                <span className="stat-value">{vehicleCount}</span>
                                <span className="stat-label">Vehicles</span>
                            </div>
                        </div>
                        <div className="stat-card objects">
                            <span className="stat-icon"><MdWidgets /></span>
                            <div className="stat-data">
                                <span className="stat-value">{objectCount}</span>
                                <span className="stat-label">Objects</span>
                            </div>
                        </div>
                        <div className={`stat-card alerts ${alertCount > 0 ? 'has-alerts' : ''}`}>
                            <span className="stat-icon"><MdNotificationsActive /></span>
                            <div className="stat-data">
                                <span className="stat-value">{alertCount}</span>
                                <span className="stat-label">Alerts</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* ─── RIGHT COLUMN: Rules + Events ─── */}
                <div className="lab-right-column">
                    {/* Detection Rules Grid */}
                    <div className="rules-dashboard">
                        <div className="rules-header">
                            <h4>Detection Rules ({activeRules.length} Active)</h4>
                            <div className="rule-filters">
                                <button className={`filter-btn ${ruleFilter === 'all' ? 'active' : ''}`} onClick={() => setRuleFilter('all')}>All</button>
                                <button className={`filter-btn ${ruleFilter === 'active' ? 'active' : ''}`} onClick={() => setRuleFilter('active')}>Active</button>
                                <button className={`filter-btn ${ruleFilter === 'detecting' ? 'active' : ''}`} onClick={() => setRuleFilter('detecting')}>Detecting</button>
                            </div>
                        </div>
                        <div className="rules-grid">
                            {filteredRules.map(rule => {
                                const isActive = activeRules.includes(rule.id);
                                const event = ruleStatusMap[rule.id];
                                const isDetecting = !!event;
                                const isFiltering = selectedRuleId === rule.id;
                                
                                // Determine if this rule is globally enabled
                                const globalRule = globalRules.find(r => r.id === rule.id);
                                const isGloballyEnabled = globalRules.length === 0 || (globalRule ? globalRule.enabled : true);
                                
                                const ruleColorSet = RULE_COLORS[rule.id] || { color: '#0070f3' };
                                const dynamicStyles = getRuleColors(ruleColorSet.color);
                                const cardStyle = {
                                    ...dynamicStyles,
                                    ...(isDetecting ? { borderColor: SEVERITY_COLORS[event.severity], "--detect-color": SEVERITY_COLORS[event.severity] } : {})
                                };

                                return (
                                    <div 
                                        key={rule.id} 
                                        className={`rule-card ${isActive ? 'active' : 'inactive'} ${isDetecting ? 'detecting' : ''} ${togglingRuleId === rule.id ? 'toggling' : ''} ${isFiltering ? 'selected-filter' : ''} ${!isGloballyEnabled ? 'globally-disabled' : ''}`}
                                        style={cardStyle}
                                        onClick={() => {
                                            if (!isGloballyEnabled) return;
                                            handleToggleRule(rule.id);
                                            setSelectedRuleId(isFiltering ? null : rule.id);
                                        }}
                                        onMouseEnter={(e) => {
                                            const rect = e.currentTarget.getBoundingClientRect();
                                            const parentElement = document.querySelector('.rules-dashboard');
                                            if (parentElement) {
                                                const parentRect = parentElement.getBoundingClientRect();
                                                setTooltipPos({
                                                    top: rect.top - parentRect.top + (rect.height / 2),
                                                    left: -265
                                                });
                                            }
                                            setHoveredRule(rule);
                                        }}
                                        onMouseLeave={() => {
                                            setHoveredRule(null);
                                        }}
                                        title={!isGloballyEnabled 
                                            ? "This rule is disabled in global Detection Rule Set" 
                                            : `${isActive ? 'Turn OFF' : 'Turn ON'} & ${isFiltering ? 'Clear' : 'Apply'} Filter`}
                                    >
                                        <div className="rule-card-top">
                                            <span className="rule-icon">{rule.icon}</span>
                                            <div 
                                                className={`rule-toggle-switch ${isActive ? 'on' : 'off'}`}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    if (!isGloballyEnabled) return;
                                                    handleToggleRule(rule.id);
                                                }}
                                                title={!isGloballyEnabled 
                                                    ? "This rule is disabled in global Detection Rule Set" 
                                                    : (isActive ? "Disable Rule on Camera" : "Enable Rule on Camera")}
                                            >
                                                <span className="switch-slider"></span>
                                            </div>
                                        </div>
                                        <span className="rule-name">{rule.name}</span>
                                        {isDetecting && (
                                            <span className="rule-severity" style={{ color: SEVERITY_COLORS[event.severity] }}>
                                                {event.severity?.toUpperCase()}
                                            </span>
                                        )}
                                        {isActive ? (
                                            <span className="rule-active-label">
                                                {isDetecting ? 'DETECTING' : 'ON'}
                                            </span>
                                        ) : (
                                            !isDetecting && (
                                                <span className="rule-inactive-label">
                                                    {!isGloballyEnabled ? 'DISABLED' : (togglingRuleId === rule.id ? '...' : 'OFF')}
                                                </span>
                                            )
                                        )}
                                    </div>
                                );
                            })}
                        </div>

                        {/* SINGLE FLOATING UNCLIPPED TOOLTIP */}
                        {hoveredRule && (() => {
                            const hoveredGlobalRule = globalRules.find(r => r.id === hoveredRule.id);
                            const isHoveredGloballyEnabled = globalRules.length === 0 || (hoveredGlobalRule ? hoveredGlobalRule.enabled : true);
                            
                            const hoveredColorSet = RULE_COLORS[hoveredRule.id] || { color: '#0070f3' };
                            const tooltipDynamicStyles = getRuleColors(hoveredColorSet.color);

                            return (
                                <div 
                                    className="rule-card-tooltip floating-portal" 
                                    style={{ 
                                        top: `${tooltipPos.top}px`, 
                                        left: `${tooltipPos.left}px`,
                                        opacity: 1,
                                        visibility: 'visible',
                                        transform: 'translateY(-50%)',
                                        position: 'absolute',
                                        ...tooltipDynamicStyles
                                    }}
                                >
                                    <div className="tooltip-header">
                                        <span className="tooltip-icon">{hoveredRule.icon}</span>
                                        <div className="tooltip-title-wrap">
                                            <span className="tooltip-title">{hoveredRule.name}</span>
                                            <span className={`tooltip-badge ${hoveredRule.category}`}>{hoveredRule.category.toUpperCase()}</span>
                                        </div>
                                    </div>
                                    <p className="tooltip-description">{RULE_DESCRIPTIONS[hoveredRule.id]}</p>
                                    <div className="tooltip-footer">
                                        <span className="tooltip-status-label">STATUS:</span>
                                        {!isHoveredGloballyEnabled ? (
                                            <span className="tooltip-status-val globally-disabled-label" style={{ color: '#ff2d55', fontWeight: 'bold' }}>
                                                GLOBALLY DISABLED
                                            </span>
                                        ) : (
                                            <span className={`tooltip-status-val ${activeRules.includes(hoveredRule.id) ? 'active' : 'inactive'}`}>
                                                {activeRules.includes(hoveredRule.id) ? 'ACTIVE' : 'INACTIVE'}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
 
                    {/* Stream Intelligence Panel */}
                    <div className="lab-alerts-panel">
                        <div className="panel-header">
                            <h4>Stream Intelligence</h4>
                            <div className="panel-header-right">
                                {selectedRuleId && (
                                    <span className="filter-badge">
                                        Filtered by {ALL_RULES.find(r => r.id === selectedRuleId)?.name}
                                        <button className="clear-filter-btn" onClick={() => setSelectedRuleId(null)}>×</button>
                                    </span>
                                )}
                                <span className="event-count">{filteredEvents.length} events</span>
                            </div>
                        </div>
                        <div className="events-stream">
                            {filteredEvents.length === 0 ? (
                                <div className="empty-events">
                                    <div className="empty-icon"><MdYoutubeSearchedFor /></div>
                                    <p>{selectedRuleId ? "No events match the selected rule filter." : "Analyzing feed for suspicious patterns..."}</p>
                                </div>
                            ) : (
                                filteredEvents
                                    .sort((a, b) => (SEVERITY_ORDER[b.severity] || 0) - (SEVERITY_ORDER[a.severity] || 0))
                                    .map((event, idx) => (
                                        <div key={idx} className={`lab-event-card ${event.severity?.toLowerCase()}`}>
                                            <div className="event-top">
                                                <div className="event-type-wrap">
                                                    <span className="event-severity-dot" style={{ background: SEVERITY_COLORS[event.severity] }}></span>
                                                    <strong>{event.type || event.name}</strong>
                                                </div>
                                                <span className="event-time">{new Date(event.timestamp).toLocaleTimeString()}</span>
                                            </div>
                                            <p className="event-message">{event.message || event.msg}</p>
                                            {event.deep_reasoning && (
                                                <div className="gemma-validation">
                                                    <div className="gemma-header">
                                                        <span className="gemma-label"><MdPsychology style={{ verticalAlign: 'middle', marginRight: '4px' }} /> Gemma 4</span>
                                                        <span className="gemma-threat">{event.deep_reasoning.threat_type}</span>
                                                    </div>
                                                    <p className="gemma-desc">{event.deep_reasoning.short_description}</p>
                                                    <div className="confidence-bar-wrap">
                                                        <div className="confidence-bar">
                                                            <div 
                                                                className="confidence-fill" 
                                                                style={{ 
                                                                    width: `${(event.deep_reasoning.confidence_score || 0) * 100}%`,
                                                                    background: event.deep_reasoning.event_validated 
                                                                        ? 'linear-gradient(90deg, #ff2d55, #ff6b35)' 
                                                                        : 'linear-gradient(90deg, #00d4ff, #00ffaa)'
                                                                }}
                                                            ></div>
                                                        </div>
                                                        <span className="confidence-text">
                                                            {((event.deep_reasoning.confidence_score || 0) * 100).toFixed(0)}%
                                                        </span>
                                                    </div>
                                                    {event.deep_reasoning.event_validated && (
                                                        <span className="validated-badge"><MdError style={{ verticalAlign: 'middle', marginRight: '4px' }} /> VALIDATED THREAT</span>
                                                    )}
                                                </div>
                                            )}
                                        </div>
                                    ))
                            )}
                            <div ref={eventsEndRef} />
                        </div>
                    </div>
                </div>
            </div>

            {/* Zone Configuration Modal */}
            {showZoneConfig && (
                <div className="zone-config-modal-overlay">
                    <div className="zone-config-modal-content">
                        <button className="close-modal-btn" onClick={() => setShowZoneConfig(false)}>×</button>
                        <ZoneManagement 
                            preselectedCamera={selectedAiCamera} 
                            onClose={() => setShowZoneConfig(false)} 
                        />
                    </div>
                </div>
            )}
        </div>
    );
};

export default AIDetectionTab;
