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
import FilterCard from './FilterCard';
import EventDetailsPanel from './EventDetailsPanel';
import { TbListSearch } from 'react-icons/tb';

const ALL = {
  category: 'All Categories',
  rule: 'All Rules',
  priority: 'All Priorities',
  status: 'All Statuses',
  location: 'All Locations',
  camera: 'All Cameras'
};

const DATE_RANGES = [
  { value: 'all', label: 'All Time', hours: null },
  { value: '24h', label: 'Last 24 Hours', hours: 24 },
  { value: '7d', label: 'Last 7 Days', hours: 24 * 7 },
  { value: '30d', label: 'Last 30 Days', hours: 24 * 30 }
];

function SearchEvents({ refreshKey }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [configLoading, setConfigLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [availableRules, setAvailableRules] = useState([]);
  const [cameraRules, setCameraRules] = useState({});

  const cameras = useCameraStore(state => state.cameras || []);
  const cameraLocations = useCameraStore(state => state.cameraLocations?.locations || {});

  const [filters, setFilters] = useState({
    dateRange: 'all',
    category: ALL.category,
    rule: ALL.rule,
    priority: ALL.priority,
    status: ALL.status,
    location: ALL.location,
    camera: ALL.camera,
    acknowledged: 'all'
  });

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
      setError('');
    } catch (err) {
      setError(err.message || 'Failed to load search configuration');
    } finally {
      setConfigLoading(false);
    }
  };

  useEffect(() => { loadConfiguration(); }, []);

  const globallyEnabledRules = useMemo(
    () => availableRules.filter(rule => rule.enabled),
    [availableRules]
  );

  const selectedCamera = useMemo(
    () => cameras.find(camera => camera.name === filters.camera) || null,
    [cameras, filters.camera]
  );

  const configuredRuleIds = useMemo(
    () => getConfiguredRuleIds(cameraRules, cameras),
    [cameraRules, cameras]
  );

  const visibleRuleIds = useMemo(() => {
    const globallyEnabled = new Set(globallyEnabledRules.map(rule => Number(rule.id)));
    const configured = selectedCamera
      ? new Set(getRulesForCamera(cameraRules, selectedCamera))
      : configuredRuleIds;
    return new Set([...configured].filter(id => globallyEnabled.has(Number(id))).map(Number));
  }, [globallyEnabledRules, selectedCamera, cameraRules, configuredRuleIds]);

  const dynamicCategories = useMemo(() => {
    const categories = new Set(
      globallyEnabledRules
        .filter(rule => visibleRuleIds.has(Number(rule.id)))
        .map(rule => rule.category)
        .filter(Boolean)
    );
    return [ALL.category, ...Array.from(categories).sort()];
  }, [globallyEnabledRules, visibleRuleIds]);

  const dynamicRules = useMemo(() => {
    let rules = globallyEnabledRules.filter(rule => visibleRuleIds.has(Number(rule.id)));
    if (filters.category !== ALL.category) rules = rules.filter(rule => rule.category === filters.category);
    return [ALL.rule, ...Array.from(new Set(rules.map(rule => rule.name))).sort()];
  }, [globallyEnabledRules, visibleRuleIds, filters.category]);

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
  const statuses = [ALL.status, 'Active', 'Acknowledged', 'Resolved', 'False Positive'];

  const eventDateMatches = event => {
    const range = DATE_RANGES.find(item => item.value === filters.dateRange);
    if (!range?.hours) return true;
    const createdAt = new Date(event.created_at).getTime();
    if (!Number.isFinite(createdAt)) return false;
    return createdAt >= Date.now() - range.hours * 60 * 60 * 1000;
  };

  const getEventCategory = event =>
    event.category || getRuleMeta(event.rule_name || event.rule)?.category || 'Other';

  const fetchEvents = async () => {
    setLoading(true);
    try {
      // Keep exact status/priority/location/ack filtering server-side, but fetch camera,
      // rule, category and date broadly. Historic records use several legacy names;
      // the shared client matcher knows all aliases and prevents valid records being
      // discarded before they reach the screen.
      const serverFilters = {
        ...filters,
        camera: ALL.camera,
        rule: ALL.rule,
        category: ALL.category,
        dateRange: 'all'
      };
      const data = await eventService.searchEvents(serverFilters);
      const filteredData = (Array.isArray(data) ? data : []).filter(event => {
        const category = getEventCategory(event);
        if (!eventDateMatches(event)) return false;
        if (!categoryMatches(filters.category, category)) return false;
        if (!ruleNameMatches(filters.rule, event.rule_name || event.rule)) return false;
        if (filters.priority !== ALL.priority && filters.priority !== 'all' &&
            String(event.priority || '').toLowerCase() !== filters.priority.toLowerCase()) return false;
        if (filters.status !== ALL.status && filters.status !== 'all' &&
            String(event.status || '').toLowerCase() !== filters.status.toLowerCase()) return false;
        if (filters.location !== ALL.location && filters.location !== 'all' &&
            !String(event.location || '').toLowerCase().includes(filters.location.toLowerCase())) return false;
        if (selectedCamera && !eventMatchesCamera(event, selectedCamera)) return false;
        if (filters.acknowledged !== 'all' && filters.acknowledged !== 'All Events') {
          const wantAcknowledged = filters.acknowledged === 'acknowledged' || filters.acknowledged === 'true';
          if (Boolean(event.acknowledged) !== wantAcknowledged) return false;
        }
        return true;
      });
      setEvents(filteredData);
      setError('');
    } catch (err) {
      setEvents([]);
      setError(err.message || 'Unable to search events');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchEvents(); }, [filters, refreshKey]);

  const handleFilterChange = (filterType, value) => {
    setFilters(previous => {
      const next = { ...previous, [filterType]: value };
      if (filterType === 'category' || filterType === 'camera') next.rule = ALL.rule;
      if (filterType === 'camera') next.category = ALL.category;
      return next;
    });
  };

  const formatDateTime = isoString => {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleString([], {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  };

  const formatDuration = seconds => {
    const value = Number(seconds);
    if (!Number.isFinite(value) || value <= 0) return 'N/A';
    const minutes = Math.floor(value / 60);
    const remaining = Math.round(value % 60);
    return `${minutes > 0 ? `${minutes}m ` : ''}${remaining}s`;
  };

  return (
    <div className="search-events-container">
      <div className="events-filters-header">
        <div className="events-title">
          <span className="events-icon"><TbListSearch /></span>
          <div>
            <h2>Search Events</h2>
            <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
              {configLoading ? 'Reading camera configuration…' : `${visibleRuleIds.size} configured rules available for this camera selection`}
            </div>
          </div>
        </div>
      </div>

      {error && <div className="error-message" style={{ marginBottom: 12 }}>{error} <button onClick={() => { loadConfiguration(); fetchEvents(); }}>Retry</button></div>}

      <div className="events-filters-grid">
        <FilterCard title="Date Range" type="select" value={filters.dateRange} onChange={value => handleFilterChange('dateRange', value)} options={DATE_RANGES.map(item => ({ value: item.value, label: item.label }))} isActive={filters.dateRange !== 'all'} />
        <FilterCard title="Category" type="select" value={filters.category} onChange={value => handleFilterChange('category', value)} options={dynamicCategories.map(value => ({ value, label: value }))} isActive={filters.category !== ALL.category} />
        <FilterCard title="Detection Rule" type="select" value={filters.rule} onChange={value => handleFilterChange('rule', value)} options={dynamicRules.map(value => ({ value, label: value }))} isActive={filters.rule !== ALL.rule} />
        <FilterCard title="Camera" type="select" value={filters.camera} onChange={value => handleFilterChange('camera', value)} options={dynamicCameras.map(value => ({ value, label: value }))} isActive={filters.camera !== ALL.camera} />
        <FilterCard title="Location" type="select" value={filters.location} onChange={value => handleFilterChange('location', value)} options={dynamicLocations.map(value => ({ value, label: value }))} isActive={filters.location !== ALL.location} />
        <FilterCard title="Priority" type="select" value={filters.priority} onChange={value => handleFilterChange('priority', value)} options={priorities.map(value => ({ value, label: value }))} isActive={filters.priority !== ALL.priority} />
        <FilterCard title="Event Status" type="select" value={filters.status} onChange={value => handleFilterChange('status', value)} options={statuses.map(value => ({ value, label: value }))} isActive={filters.status !== ALL.status} />
        <FilterCard title="Acknowledgment" type="select" value={filters.acknowledged} onChange={value => handleFilterChange('acknowledged', value)} options={[
          { value: 'all', label: 'All Events' },
          { value: 'acknowledged', label: 'Acknowledged' },
          { value: 'unacknowledged', label: 'Unacknowledged' }
        ]} isActive={filters.acknowledged !== 'all'} />
      </div>

      <div className="search-results">
        {loading ? <div className="loading-state">Searching events...</div> : events.length === 0 ? (
          <div className="empty-state">No events found matching your criteria.</div>
        ) : (
          <div className="events-table-wrapper">
            <table className="events-table">
              <thead><tr><th>Event ID</th><th>Time</th><th>Rule</th><th>Category</th><th>Camera</th><th>Location</th><th>Priority</th><th>Duration</th><th>Status</th></tr></thead>
              <tbody>{events.map(event => (
                <tr key={event.event_id} onClick={() => setSelectedEvent(event)} className={selectedEvent?.event_id === event.event_id ? 'selected' : ''}>
                  <td>{event.event_id}</td><td>{formatDateTime(event.created_at)}</td><td>{event.rule_name || event.rule || '—'}</td><td>{getEventCategory(event)}</td>
                  <td>{event.camera_name || event.camera_id || '—'}</td><td>{event.location || '—'}</td>
                  <td><span className={`priority-badge ${String(event.priority || '').toLowerCase()}`}>{event.priority || '—'}</span></td>
                  <td>{formatDuration(event.duration)}</td><td><span className={`status-badge ${String(event.status || '').toLowerCase().replace(' ', '-')}`}>{event.status || '—'}</span></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>

      {selectedEvent && <EventDetailsPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} onAcknowledge={async id => {
        const success = await eventService.acknowledgeEvent(id);
        if (success) {
          fetchEvents();
          setSelectedEvent(previous => ({ ...previous, acknowledged: true, status: previous.status === 'Active' ? 'Acknowledged' : previous.status }));
        }
      }} />}
    </div>
  );
}

export default SearchEvents;
