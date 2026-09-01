import React, { useState, useEffect } from 'react';
import { eventService } from '../../services/eventService';
import './EventStatistics.css';

const EventStatistics = ({ refreshKey }) => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [refreshKey]);

  const loadData = async () => {
    setLoading(true);
    const data = await eventService.searchEvents({});
    setEvents(data);
    setLoading(false);
  };

  if (loading) {
    return <div className="event-statistics-loading">Loading event statistics...</div>;
  }

  // Calculate statistics
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const todaysEvents = events.filter(e => new Date(e.created_at) >= today).length;
  const activeEvents = events.filter(e => e.status === 'Active').length;
  const criticalEvents = events.filter(e => e.priority === 'Critical').length;
  const resolvedEvents = events.filter(e => e.status === 'Resolved').length;
  const falsePositives = events.filter(e => e.status === 'False Positive').length;
  const acknowledgedEvents = events.filter(e => e.acknowledged).length;

  // Aggregate for charts
  const eventsByRule = {};
  const eventsByCategory = {};
  const eventsByCamera = {};
  const eventsByPriority = {};

  events.forEach(e => {
    eventsByRule[e.rule_name] = (eventsByRule[e.rule_name] || 0) + 1;
    eventsByCategory[e.category] = (eventsByCategory[e.category] || 0) + 1;
    eventsByCamera[e.camera_name] = (eventsByCamera[e.camera_name] || 0) + 1;
    eventsByPriority[e.priority] = (eventsByPriority[e.priority] || 0) + 1;
  });

  const renderBarChart = (dataObj, title, colorClass) => {
    const maxVal = Math.max(...Object.values(dataObj), 1);
    const entries = Object.entries(dataObj).sort((a, b) => b[1] - a[1]).slice(0, 5); // Top 5

    return (
      <div className="stat-chart-card">
        <h3>{title}</h3>
        <div className="bar-chart-simple">
          {entries.map(([label, count]) => (
            <div key={label} className="bar-row">
              <div className="bar-label" title={label}>{label}</div>
              <div className="bar-track">
                <div className={`bar-fill ${colorClass}`} style={{ width: `${(count / maxVal) * 100}%` }}></div>
              </div>
              <div className="bar-count">{count}</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="event-statistics">
      <div className="event-statistics-header">
        <h2>Events Dashboard</h2>
      </div>

      <div className="stats-cards-grid">
        <div className="stat-card total">
          <h4>Today's Events</h4>
          <div className="stat-value">{todaysEvents}</div>
        </div>
        <div className="stat-card active">
          <h4>Active Events</h4>
          <div className="stat-value">{activeEvents}</div>
        </div>
        <div className="stat-card critical">
          <h4>Critical Events</h4>
          <div className="stat-value">{criticalEvents}</div>
        </div>
        <div className="stat-card resolved">
          <h4>Resolved Events</h4>
          <div className="stat-value">{resolvedEvents}</div>
        </div>
        <div className="stat-card acknowledged">
          <h4>Acknowledged Events</h4>
          <div className="stat-value">{acknowledgedEvents}</div>
        </div>
        <div className="stat-card fp">
          <h4>False Positives</h4>
          <div className="stat-value">{falsePositives}</div>
        </div>
      </div>

      <div className="charts-grid">
        {renderBarChart(eventsByCategory, 'Events by Category', 'fill-blue')}
        {renderBarChart(eventsByRule, 'Top Detection Rules', 'fill-purple')}
        {renderBarChart(eventsByCamera, 'Top Cameras', 'fill-green')}
        {renderBarChart(eventsByPriority, 'Events by Priority', 'fill-orange')}
      </div>
    </div>
  );
};

export default EventStatistics;
