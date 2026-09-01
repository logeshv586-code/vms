import React, { useState } from 'react';
import '../components/Dashboard.css';

function EventsSidebar() {
  const [showDetectionRules, setShowDetectionRules] = useState(false);

  return (
    <div className="sidebar">
      <div className="sidebar-section">
        <button className="sidebar-btn">Search Events</button>
      </div>
      <div className="sidebar-section">
        <button className="sidebar-btn">Current Events</button>
      </div>
      <div className="sidebar-section">
        <button
          className="sidebar-btn"
          onClick={() => setShowDetectionRules((prev) => !prev)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
        >
          Set Detection Rules
          <span style={{ marginLeft: 'auto', fontWeight: 'bold', fontSize: '16px' }}>
            {showDetectionRules ? '▲' : '▼'}
          </span>
        </button>
        {showDetectionRules && (
          <div className="sidebar-dropdown">
            <button className="sidebar-btn sidebar-btn-sub">Detection Rule Set</button>
            <button className="sidebar-btn sidebar-btn-sub">Rules On Camera</button>
            <button className="sidebar-btn sidebar-btn-sub">PTZ Auto Tour</button>
            <button className="sidebar-btn sidebar-btn-sub">PTZ Auto Track</button>
            <button className="sidebar-btn sidebar-btn-sub">Live Monitoring Rules</button>
            <button className="sidebar-btn sidebar-btn-sub">Event Parameters</button>
          </div>
        )}
      </div>
      <div className="sidebar-section">
        <button className="sidebar-btn">Events Statistics</button>
      </div>
      <div className="sidebar-section">
        <button className="sidebar-btn">Uploaded Media</button>
      </div>
    </div>
  );
}

export default EventsSidebar;