import React, { useState, useEffect, useMemo } from 'react';
import {
  eventService,
  fetchCameraRules,
  fetchEventRules
} from '../../services/eventService';
import { useCameraStore } from '../../store/cameraStore';
import {
  categoryMatches,
  enrichRule,
  eventMatchesCamera,
  getConfiguredRuleIds,
  getRuleMeta,
  getRulesForCamera,
  ruleNameMatches
} from '../../utils/detectionRules';
import './EventsContent.css';
import EventDetailsPanel from './EventDetailsPanel';
import FilterCard from './FilterCard';

const ALL = {
  category: 'All Categories',
  rule: 'All Rules',
  priority: 'All Priorities',
  location: 'All Locations',
  camera: 'All Cameras'
};

function CurrentEvents() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [configLoading, setConfigLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [availableRules, setAvailableRules] = useState([]);
  const [cameraRules, setCameraRules] = useState({});

  const cameras = useCameraStore(state => state.cameras || []);
  const cameraLocations = useCameraStore(state => state.cameraLocations?.locations || {});

  const [filters, setFilters] = useState({ ...ALL });

  const loadConfiguration = async () => {
    setConfigLoading(true);
    try {
      const [rulesRes, cameraRulesRes] = await Promise.all([
        fetchEventRules(),
        fetchCameraRules()
      ]);
      if (!rulesRes?.success) throw new Error(rulesRes?.error || 'Failed to load detection rules');
      if (!cameraRulesRes?.success) throw new Error(cameraRulesRes?.error || 'Failed to load camera rules');

      setAvailableRules((rulesRes.data?.rules || []).map(enrichRule));
      setCameraRules(cameraRulesRes.data?.cameraRules || {});
    } catch (err) {
      setError(err.message || 'Failed to load event filter configuration');
    } finally {
      setConfigLoading(false);
    }
  };

  useEffect(() => {
    loadConfiguration();
  }, []);

  const globallyEnabledRules = useMemo(
    () => availableRules.filter(rule => rule.enabled),
    [availableRules]
  );

  const configuredRuleIds = useMemo(
    () => getConfiguredRuleIds(cameraRules, cameras),
    [cameraRules, cameras]
  );

  const configuredCameraCount = useMemo(
    () => cameras.filter(camera => getRulesForCamera(cameraRules, camera).length > 0).length,
    [cameraRules, cameras]
  );

  const selectedCamera = useMemo(
    () => cameras.find(camera => camera.name === filters.camera) || null,
    [cameras, filters.camera]
  );

  const effectiveRuleIds = useMemo(() => {
    const globalIds = new Set(globallyEnabledRules.map(rule => Number(rule.id)));
    const assignedIds = selectedCamera
      ? new Set(getRulesForCamera(cameraRules, selectedCamera))
      : configuredRuleIds;
    return new Set([...assignedIds].filter(id => globalIds.has(Number(id))).map(Number));
  }, [globallyEnabledRules, cameraRules, selectedCamera, configuredRuleIds]);

  const dynamicCategories = useMemo(() => {
    const categories = new Set(
      globallyEnabledRules
        .filter(rule => effectiveRuleIds.has(Number(rule.id)))
        .map(rule => rule.category)
        .filter(Boolean)
    );
    return [ALL.category, ...Array.from(categories).sort()];
  }, [globallyEnabledRules, effectiveRuleIds]);

  const dynamicRules = useMemo(() => {
    let rules = globallyEnabledRules.filter(rule => effectiveRuleIds.has(Number(rule.id)));
    if (filters.category !== ALL.category) {
      rules = rules.filter(rule => rule.category === filters.category);
    }
    return [ALL.rule, ...Array.from(new Set(rules.map(rule => rule.name))).sort()];
  }, [globallyEnabledRules, effectiveRuleIds, filters.category]);

  useEffect(() => {
    if (!dynamicRules.includes(filters.rule)) {
      setFilters(previous => ({ ...previous, rule: ALL.rule }));
    }
  }, [dynamicRules, filters.rule]);

  useEffect(() => {
    if (!dynamicCategories.includes(filters.category)) {
      setFilters(previous => ({ ...previous, category: ALL.category, rule: ALL.rule }));
    }
  }, [dynamicCategories, filters.category]);

  const dynamicCameras = useMemo(
    () => [ALL.camera, ...Array.from(new Set(cameras.map(camera => camera.name).filter(Boolean)))],
    [cameras]
  );

  const dynamicLocations = useMemo(() => {
    const names = new Set(Object.values(cameraLocations).map(location => location?.customName).filter(Boolean));
    return [ALL.location, ...Array.from(names).sort()];
  }, [cameraLocations]);

  const priorities = [ALL.priority, 'Critical', 'High', 'Medium', 'Low'];

  const fetchEvents = async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    try {
      const data = await eventService.getCurrentEvents();
      setEvents(Array.isArray(data) ? data : []);
      setError('');
    } catch (err) {
      setError(err.message || 'Unable to load live events');
    } finally {
      if (showSpinner) setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents(true);
    const interval = setInterval(() => fetchEvents(false), 5000);
    return () => clearInterval(interval);
  }, []);

  const handleFilterChange = (filterType, value) => {
    setFilters(previous => {
      const next = { ...previous, [filterType]: value };
      if (filterType === 'category' || filterType === 'camera') next.rule = ALL.rule;
      if (filterType === 'camera') next.category = ALL.category;
      return next;
    });
  };

  const handleAcknowledge = async (e, eventId) => {
    if (e) e.stopPropagation();
    try {
      const success = await eventService.acknowledgeEvent(eventId);
      if (!success) return;
      setEvents(previous => previous.map(event =>
        event.event_id === eventId
          ? { ...event, acknowledged: true, status: 'Acknowledged' }
          : event
      ));
      if (selectedEvent?.event_id === eventId) {
        setSelectedEvent(previous => ({ ...previous, acknowledged: true, status: 'Acknowledged' }));
      }
    } catch (err) {
      setError(err.message || 'Unable to acknowledge event');
    }
  };

  const getEventCategory = (event) =>
    event.category || getRuleMeta(event.rule_name || event.rule)?.category || 'Other';

  const filteredEvents = useMemo(() => events.filter(event => {
    const category = getEventCategory(event);
    if (!categoryMatches(filters.category, category)) return false;
    if (!ruleNameMatches(filters.rule, event.rule_name || event.rule)) return false;

    if (filters.priority !== ALL.priority && filters.priority !== 'all') {
      if (String(event.priority || '').toLowerCase() !== filters.priority.toLowerCase()) return false;
    }
    if (filters.location !== ALL.location && filters.location !== 'all') {
      if (!String(event.location || '').toLowerCase().includes(filters.location.toLowerCase())) return false;
    }
    if (selectedCamera && !eventMatchesCamera(event, selectedCamera)) return false;
    return true;
  }), [events, filters, selectedCamera]);

  const formatTime = (isoString) => {
    const date = new Date(isoString);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  };

  const confidenceText = (confidence) => {
    const value = Number(confidence);
    if (!Number.isFinite(value)) return '—';
    const normalized = value > 1 ? value : value * 100;
    return `${Math.round(normalized)}%`;
  };

  return (
    <div className="current-events-container">
      <div className="events-header">
        <div>
          <h2>Live Active Events</h2>
          <div style={{ fontSize: 12, color: '#64748b', marginTop: 5 }}>
            {configLoading ? 'Reading camera configuration…' :
              `${effectiveRuleIds.size} effective rules · ${configuredCameraCount}/${cameras.length} cameras configured`}
          </div>
        </div>
        <span className="live-indicator">● LIVE</span>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: 12 }}>
          {error} <button onClick={() => { loadConfiguration(); fetchEvents(true); }}>Retry</button>
        </div>
      )}

      <div className="events-filters-grid" style={{ marginBottom: '20px' }}>
        <FilterCard title="Category" type="select" value={filters.category}
          onChange={value => handleFilterChange('category', value)}
          options={dynamicCategories.map(value => ({ value, label: value }))}
          isActive={filters.category !== ALL.category} />
        <FilterCard title="Detection Rule" type="select" value={filters.rule}
          onChange={value => handleFilterChange('rule', value)}
          options={dynamicRules.map(value => ({ value, label: value }))}
          isActive={filters.rule !== ALL.rule} />
        <FilterCard title="Camera" type="select" value={filters.camera}
          onChange={value => handleFilterChange('camera', value)}
          options={dynamicCameras.map(value => ({ value, label: value }))}
          isActive={filters.camera !== ALL.camera} />
        <FilterCard title="Location" type="select" value={filters.location}
          onChange={value => handleFilterChange('location', value)}
          options={dynamicLocations.map(value => ({ value, label: value }))}
          isActive={filters.location !== ALL.location} />
        <FilterCard title="Priority" type="select" value={filters.priority}
          onChange={value => handleFilterChange('priority', value)}
          options={priorities.map(value => ({ value, label: value }))}
          isActive={filters.priority !== ALL.priority} />
      </div>

      {!configLoading && effectiveRuleIds.size === 0 ? (
        <div className="empty-state">
          No detection rules are assigned to {selectedCamera ? selectedCamera.name : 'the configured cameras'}.
          Enable a rule globally, then assign it under <strong>Rules On Camera</strong>.
        </div>
      ) : loading && filteredEvents.length === 0 ? (
        <div className="loading-state">Loading active events...</div>
      ) : filteredEvents.length === 0 ? (
        <div className="empty-state">No active events matching your filters.</div>
      ) : (
        <div className="events-table-wrapper">
          <table className="events-table">
            <thead><tr>
              <th>Time</th><th>Camera</th><th>Location</th><th>Event Rule</th>
              <th>Category</th><th>Priority</th><th>Confidence</th><th>Status</th><th>Actions</th>
            </tr></thead>
            <tbody>
              {filteredEvents.map(event => (
                <tr key={event.event_id} onClick={() => setSelectedEvent(event)}
                    className={selectedEvent?.event_id === event.event_id ? 'selected' : ''}>
                  <td>{formatTime(event.created_at)}</td>
                  <td>{event.camera_name || event.camera_id || '—'}</td>
                  <td>{event.location || '—'}</td>
                  <td>{event.rule_name || event.rule || '—'}</td>
                  <td>{getEventCategory(event)}</td>
                  <td><span className={`priority-badge ${String(event.priority || '').toLowerCase()}`}>{event.priority || '—'}</span></td>
                  <td>{confidenceText(event.confidence)}</td>
                  <td><span className={`status-badge ${String(event.status || '').toLowerCase().replace(' ', '-')}`}>{event.status || '—'}</span></td>
                  <td>
                    {event.status === 'Active' && !event.acknowledged ? (
                      <button className="action-btn ack-btn" onClick={e => handleAcknowledge(e, event.event_id)}>Acknowledge</button>
                    ) : (
                      <span style={{ color: '#16a34a', fontSize: 12 }}>✓ Acknowledged</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedEvent && (
        <EventDetailsPanel event={selectedEvent} onClose={() => setSelectedEvent(null)}
          onAcknowledge={id => handleAcknowledge({ stopPropagation: () => {} }, id)} />
      )}
    </div>
  );
}

export default CurrentEvents;
