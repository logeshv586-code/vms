import React, { useState, useEffect } from 'react';
import './LiveAIAlerts.css';

const LiveAIAlerts = () => {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchEvents = async () => {
            try {
                const response = await fetch('/api/webcam/events');
                const data = await response.json();
                if (data.events) {
                    setEvents(data.events);
                }
            } catch (error) {
                console.error("Error fetching AI events:", error);
            } finally {
                setLoading(false);
            }
        };

        // Poll every 1 second for live alerts
        const intervalId = setInterval(fetchEvents, 1000);
        return () => clearInterval(intervalId);
    }, []);

    const getSeverityClass = (severity) => {
        switch(severity.toLowerCase()) {
            case 'critical': return 'severity-critical';
            case 'high': return 'severity-high';
            case 'medium': return 'severity-medium';
            case 'low': return 'severity-low';
            default: return '';
        }
    };

    return (
        <div className="live-ai-alerts">
            <div className="alerts-header">
                <h3>Live AI Detection Hub (Hybrid)</h3>
                <span className="live-indicator">LIVE</span>
            </div>
            
            <div className="alerts-container">
                {events.length === 0 ? (
                    <div className="no-alerts">
                        <p>No active security threats detected by Layer 1/2.</p>
                    </div>
                ) : (
                    events.map((event, index) => (
                        <div key={index} className={`alert-card ${getSeverityClass(event.severity)}`}>
                            <div className="alert-main">
                                <span className="alert-type">{event.type}</span>
                                <span className="alert-time">
                                    {new Date(event.timestamp).toLocaleTimeString()}
                                </span>
                            </div>
                            <p className="alert-message">{event.message}</p>
                            
                            {/* Gemma 4 (Layer 3) Deep Reasoning Data */}
                            {event.deep_reasoning && (
                                <div className="deep-reasoning-panel">
                                    <div className="deep-header">
                                        <span className="gemma-icon">🧠</span>
                                        <strong>Gemma 4 Validation:</strong>
                                        <span className="reasoning-type"> {event.deep_reasoning.threat_type}</span>
                                    </div>
                                    <p className="reasoning-summary">{event.deep_reasoning.short_description}</p>
                                    <div className="confidence-bar">
                                        <div 
                                            className="confidence-fill" 
                                            style={{width: `${event.deep_reasoning.confidence_score * 100}%`}}
                                        ></div>
                                        <span className="confidence-text">
                                            Confidence: {(event.deep_reasoning.confidence_score * 100).toFixed(0)}%
                                        </span>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};

export default LiveAIAlerts;
