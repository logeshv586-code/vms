import React from 'react';
import './Dashboard.css';

function EventsContent() {
  return (
    <div className="events-content">
      <div className="events-filters-bar">
        <button className="events-filter-btn events-filter-btn-main">
          <span style={{ color: '#b6e14b', marginRight: 6 }}>🗂️</span>
          Search Events
        </button>
        <button className="events-filter-btn events-filter-btn-refresh">⟳ Refresh</button>
        <button className="events-filter-btn events-filter-btn-active">Time</button>
        <button className="events-filter-btn">Rule</button>
        <button className="events-filter-btn">Priority</button>
        <button className="events-filter-btn">Acknowlodge</button>
        <button className="events-filter-btn">Location</button>
        <button className="events-filter-btn">
          Camera
          <input type="text" className="events-filter-input" style={{ marginLeft: 6, width: 60, background: 'transparent', border: '1px solid #444', color: '#fff', borderRadius: 2, height: 20 }} />
        </button>
      </div>
      {/* ...rest of your Events content... */}
    </div>
  );
}

export default EventsContent;