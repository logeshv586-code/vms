import React, { useState, useEffect } from 'react';
import {
    Brain,
    CheckCircle,
    AlertTriangle,
    BarChart3,
    Clock,
    FileDown,
    Scissors,
    Info,
    User,
    ShoppingBag,
    Smartphone,
    Car,
    Users,
    Eye,
    Package,
    Cpu,
    Zap
} from 'lucide-react';
import './VideoAnalyticsPanel.css';

const VideoAnalyticsPanel = ({ recording, onExportEvidence, onExtractSegment }) => {
    const [animateConfidence, setAnimateConfidence] = useState(false);

    useEffect(() => {
        // Trigger confidence bar animation after mount
        const timer = setTimeout(() => setAnimateConfidence(true), 300);
        return () => clearTimeout(timer);
    }, []);

    // Mock AI analytics data (future: comes from backend YOLO-26 engine)
    const detectedObjects = [
        { label: 'Person', confidence: 98, icon: User },
        { label: 'Bag', confidence: 91, icon: ShoppingBag },
        { label: 'Mobile Phone', confidence: 84, icon: Smartphone },
        { label: 'Vehicle', confidence: 87, icon: Car },
    ];

    const detectedEvents = [
        { label: 'Crowd Detection', severity: 'warning' },
        { label: 'Loitering', severity: 'warning' },
        { label: 'Unattended Object', severity: 'high' },
    ];

    const confidenceScores = [
        { label: 'Person', value: 98 },
        { label: 'Bag', value: 91 },
        { label: 'Vehicle', value: 87 },
        { label: 'Mobile Phone', value: 84 },
    ];

    const eventTimeline = [
        { time: '18:24:02', event: 'Person Entered Zone', type: 'info' },
        { time: '18:24:12', event: 'Crowd Forming', type: 'warning' },
        { time: '18:24:20', event: 'Loitering Detected', type: 'warning' },
        { time: '18:24:35', event: 'Bag Left Unattended', type: 'danger' },
        { time: '18:24:48', event: 'Alert Triggered', type: 'danger' },
        { time: '18:25:01', event: 'Zone Monitoring Active', type: 'success' },
    ];

    const getConfidenceClass = (value) => {
        if (value >= 90) return 'confidence-high';
        if (value >= 75) return 'confidence-medium';
        return 'confidence-low';
    };

    return (
        <div className="video-analytics-panel">
            {/* Panel Header */}
            <div className="analytics-panel-header">
                <div className="analytics-panel-title">
                    <div className="analytics-brain-icon">
                        <Brain />
                    </div>
                    <h2>AI Analytics Panel</h2>
                </div>
                <div className="model-badge">
                    <span className="model-label">YOLO-26</span>
                    <span className="model-status">
                        <span className="status-pulse"></span>
                        Ready
                    </span>
                </div>
            </div>

            {/* Detected Objects Card */}
            <div className="analytics-card">
                <div className="analytics-card-header">
                    <CheckCircle />
                    <h3>Detected Objects</h3>
                </div>
                <div className="detected-objects-list">
                    {detectedObjects.map((obj, index) => {
                        const IconComponent = obj.icon;
                        return (
                            <div key={index} className="detected-object-item">
                                <div className="object-check-icon">
                                    <CheckCircle />
                                </div>
                                <span className="object-label">{obj.label}</span>
                                <span className="object-confidence">{obj.confidence}%</span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Detected Events Card */}
            <div className="analytics-card">
                <div className="analytics-card-header">
                    <AlertTriangle />
                    <h3>Detected Events</h3>
                </div>
                <div className="detected-events-list">
                    {detectedEvents.map((evt, index) => (
                        <div key={index} className={`detected-event-item severity-${evt.severity}`}>
                            <div className="event-warning-icon">
                                <AlertTriangle />
                            </div>
                            <span className="event-label">{evt.label}</span>
                            <span className="event-severity-badge">
                                {evt.severity === 'high' ? 'High' : 'Medium'}
                            </span>
                        </div>
                    ))}
                </div>
            </div>

            {/* Confidence Scores Card */}
            <div className="analytics-card">
                <div className="analytics-card-header">
                    <BarChart3 />
                    <h3>Confidence Scores</h3>
                </div>
                <div className="confidence-scores-list">
                    {confidenceScores.map((score, index) => (
                        <div key={index} className="confidence-score-item">
                            <div className="confidence-score-header">
                                <span className="confidence-score-label">{score.label}</span>
                                <span className="confidence-score-value">{score.value}%</span>
                            </div>
                            <div className="confidence-bar-track">
                                <div
                                    className={`confidence-bar-fill ${getConfidenceClass(score.value)}`}
                                    style={{ width: animateConfidence ? `${score.value}%` : '0%' }}
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* AI Optimization & Load Reduction Card */}
            <div className="analytics-card load-reduction-card">
                <div className="analytics-card-header">
                    <Cpu style={{ color: '#06b6d4' }} />
                    <h3>AI Optimization & Load Reduction</h3>
                </div>
                <div className="optimization-status-container">
                    <div className="optimization-active-badge">
                        <span className="optimization-pulse"></span>
                        Computational Reduction Active
                    </div>
                    
                    <div className="optimization-metric-box">
                        <div className="metric-value">66.7%</div>
                        <div className="metric-label">GPU/CPU Cycles Saved</div>
                    </div>
                    
                    <div className="optimization-details-list">
                        <div className="optimization-detail-item">
                            <Zap className="detail-icon" />
                            <div className="detail-info">
                                <span className="detail-title">Frame Skip Processing</span>
                                <span className="detail-desc">Only 1 in 3 frames analyzed (66.7% skip rate) to prevent lag & buffer congestion.</span>
                            </div>
                        </div>
                        <div className="optimization-detail-item">
                            <Zap className="detail-icon" />
                            <div className="detail-info">
                                <span className="detail-title">YOLOv8 Downscaling</span>
                                <span className="detail-desc">Scale 1080p RTSP to 640×640 inference standard to reduce tensor calculation load by 88%.</span>
                            </div>
                        </div>
                        <div className="optimization-detail-item">
                            <Zap className="detail-icon" />
                            <div className="detail-info">
                                <span className="detail-title">H.264 Hardware Acceleration</span>
                                <span className="detail-desc">NVDEC/Intel QuickSync decoding active for zero-CPU video decompression.</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Event Timeline Card */}
            <div className="analytics-card event-timeline-card">
                <div className="analytics-card-header">
                    <Clock />
                    <h3>Event Timeline</h3>
                </div>
                <div className="event-timeline">
                    {eventTimeline.map((item, index) => (
                        <div key={index} className="timeline-item">
                            <div className={`timeline-dot dot-${item.type}`}></div>
                            <div className="timeline-content">
                                <span className="timeline-event-name">{item.event}</span>
                                <span className="timeline-timestamp">{item.time}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* AI Analysis Notice */}
            <div className="ai-analysis-notice">
                <Info />
                <p>
                    <strong>AI analysis can run on raw frames</strong> even when video playback is unavailable.
                    Detection results are generated by the YOLO-26 model on extracted keyframes.
                </p>
            </div>

            {/* Action Buttons */}
            <div className="analytics-actions-row">
                <button
                    className="analytics-action-btn export-evidence-btn"
                    onClick={onExportEvidence}
                >
                    <FileDown />
                    Export Evidence
                </button>
                <button
                    className="analytics-action-btn extract-segment-btn"
                    onClick={onExtractSegment}
                >
                    <Scissors />
                    Extract Segment
                </button>
            </div>
        </div>
    );
};

export default React.memo(VideoAnalyticsPanel);
