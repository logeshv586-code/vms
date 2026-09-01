import React, { useState, useEffect, useMemo } from 'react';
import { eventService } from '../../services/eventService';
import { fetchEventRules } from '../../services/eventsService';
import { useCameraStore } from '../../store/cameraStore';
import FilterCard from './FilterCard';
import EventDetailsPanel from './EventDetailsPanel';
import { TbListSearch } from 'react-icons/tb';

function SearchEvents({ refreshKey }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState(null);

  // Dynamic filter state
  const [availableRules, setAvailableRules] = useState([]);
  const [cameraRules, setCameraRules] = useState({});
  
  // Get camera and location data from store
  const cameras = useCameraStore(state => state.cameras || []);
  const cameraLocations = useCameraStore(state => state.cameraLocations?.locations || {});

  const [filters, setFilters] = useState({
    dateRange: 'all',
    category: 'All Categories',
    rule: 'All Rules',
    priority: 'All Priorities',
    status: 'All Statuses',
    location: 'All Locations',
    camera: 'All Cameras',
    acknowledged: 'all'
  });

  // Default category map for standard 23 detection rules
  const defaultCategoryMap = useMemo(() => ({
    'Appearance Search': 'Face Analytics',
    'Face Capture': 'Face Analytics',
    'Face Recognition': 'Face Analytics',
    'Intrusion Detection': 'Security Analytics',
    'Zone Monitoring': 'Security Analytics',
    'Zone Monitoring (Restricted Area)': 'Security Analytics',
    'Lakshmanrekha Crossing': 'Security Analytics',
    'Loitering': 'Security Analytics',
    'Camera Tamper': 'Security Analytics',
    'Unattended Object': 'Security Analytics',
    'Object Classification': 'Security Analytics',
    'Chain/Handbag Snatching': 'Crime Detection',
    'Mobile Snatching': 'Crime Detection',
    'People Fighting': 'Crime Detection',
    'Eve Teasing': 'Crime Detection',
    'Women/Infant Abduction': 'Crime Detection',
    'Abduction Detection': 'Crime Detection',
    'Women Surrounded by Men': 'Crime Detection',
    'Women Surrounded': 'Crime Detection',
    'Graffiti and Vandalism Detection': 'Crime Detection',
    'Graffiti / Vandalism': 'Crime Detection',
    'Suspected Appearance': 'Crime Detection',
    'Crowd Detection': 'Crowd & Public Safety',
    'Person Collapsing': 'Crowd & Public Safety',
    'Strike / Morcha / Hartal / Procession': 'Crowd & Public Safety',
    'Strike / Procession': 'Crowd & Public Safety',
    'Vehicle Monitoring': 'Vehicle Analytics'
  }), []);

  // Fetch dynamic rules and camera rules from the backend
  useEffect(() => {
    const loadData = async () => {
      try {
        const [rulesRes, cameraRulesRes] = await Promise.all([
          fetchEventRules(),
          import('../../services/eventsService').then(m => m.fetchCameraRules())
        ]);
        
        if (rulesRes.success && rulesRes.data && rulesRes.data.rules) {
          const enrichedRules = rulesRes.data.rules.map(r => ({
            ...r,
            category: defaultCategoryMap[r.name] || 'Security Analytics'
          }));
          setAvailableRules(enrichedRules);
        }
        if (cameraRulesRes.success && cameraRulesRes.data && cameraRulesRes.data.cameraRules) {
          setCameraRules(cameraRulesRes.data.cameraRules);
        }
      } catch (err) {
        console.error('Failed to fetch rules data', err);
      }
    };
    loadData();
  }, [defaultCategoryMap]);

  // Compute dynamic options for Search Events (Search all past records)
  const dynamicCategories = useMemo(() => {
    const defaultCats = ['Crime Detection', 'Crowd & Public Safety', 'Face Analytics', 'Security Analytics', 'Vehicle Analytics'];
    const loadedCats = availableRules.map(r => r.category).filter(Boolean);
    const catSet = new Set([...defaultCats, ...loadedCats]);
    return ['All Categories', ...Array.from(catSet).sort()];
  }, [availableRules]);

  const dynamicRules = useMemo(() => {
    let rulesList = availableRules;
    if (rulesList.length === 0) {
      rulesList = Object.keys(defaultCategoryMap).map((name, id) => ({
        id: id + 1,
        name,
        category: defaultCategoryMap[name]
      }));
    }

    // Filter rules by selected category
    if (filters.category !== 'All Categories') {
      rulesList = rulesList.filter(r => r.category === filters.category);
    }

    const ruleNames = new Set(rulesList.map(r => r.name).filter(Boolean));
    return ['All Rules', ...Array.from(ruleNames).sort()];
  }, [availableRules, filters.category, defaultCategoryMap]);

  const dynamicCameras = useMemo(() => {
    const camNames = new Set(cameras.map(c => c.name).filter(Boolean));
    return ['All Cameras', ...Array.from(camNames)];
  }, [cameras]);

  const dynamicLocations = useMemo(() => {
    const locNames = new Set(Object.values(cameraLocations).map(loc => loc.customName).filter(Boolean));
    return ['All Locations', ...Array.from(locNames)];
  }, [cameraLocations]);

  const priorities = ['All Priorities', 'Critical', 'High', 'Medium', 'Low'];
  const statuses = ['All Statuses', 'Active', 'Acknowledged', 'Resolved', 'False Positive'];

  const rulesMatch = (selectedRule, eventRuleName) => {
    if (!selectedRule || selectedRule === 'All Rules' || selectedRule === 'all') return true;
    if (!eventRuleName) return false;
    const sr = selectedRule.toLowerCase().trim();
    const er = eventRuleName.toLowerCase().trim();
    if (sr === er || sr.includes(er) || er.includes(sr)) return true;
    const cleanEr = er.split('(')[0].trim();
    const cleanSr = sr.split('(')[0].trim();
    return cleanEr.includes(cleanSr) || cleanSr.includes(cleanEr);
  };

  const categoriesMatch = (selectedCat, eventCat) => {
    if (!selectedCat || selectedCat === 'All Categories' || selectedCat === 'all') return true;
    if (!eventCat) return false;
    const sc = selectedCat.toLowerCase().trim();
    const ec = eventCat.toLowerCase().trim();
    return sc === ec || sc.includes(ec) || ec.includes(sc);
  };

  const fetchEvents = async () => {
    setLoading(true);
    try {
      const data = await eventService.searchEvents(filters);
      let filteredData = Array.isArray(data) ? data : [];

      filteredData = filteredData.filter(event => {
        if (!categoriesMatch(filters.category, event.category)) return false;
        if (!rulesMatch(filters.rule, event.rule_name || event.rule)) return false;
        if (filters.priority !== 'All Priorities' && filters.priority !== 'all') {
          if (event.priority?.toLowerCase() !== filters.priority.toLowerCase()) return false;
        }
        if (filters.status !== 'All Statuses' && filters.status !== 'all') {
          if (event.status?.toLowerCase() !== filters.status.toLowerCase()) return false;
        }
        if (filters.location !== 'All Locations' && filters.location !== 'all') {
          if (!event.location?.toLowerCase().includes(filters.location.toLowerCase())) return false;
        }
        if (filters.camera !== 'All Cameras' && filters.camera !== 'all') {
          const backendCamName = filters.camera.replace(' (', '_').replace(')', '').toLowerCase();
          const evtCam = (event.camera_name || event.camera_id || '').toLowerCase();
          if (!evtCam.includes(backendCamName) && !evtCam.includes(filters.camera.toLowerCase())) return false;
        }
        if (filters.acknowledged !== 'all' && filters.acknowledged !== 'All Events') {
          const wantAck = filters.acknowledged === 'acknowledged' || filters.acknowledged === 'true';
          if (Boolean(event.acknowledged) !== wantAck) return false;
        }
        return true;
      });

      setEvents(filteredData);
    } catch (err) {
      console.error('Error in search events fetch:', err);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [filters, refreshKey]);

  const handleFilterChange = (filterType, value) => {
    setFilters(prev => {
      const newFilters = { ...prev, [filterType]: value };
      // Reset rule if category changes
      if (filterType === 'category') {
        newFilters.rule = 'All Rules';
      }
      return newFilters;
    });
  };

  const formatDateTime = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleString([], { 
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit' 
    });
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m > 0 ? m + 'm ' : ''}${s}s`;
  };

  return (
    <div className="search-events-container">
      <div className="events-filters-header">
        <div className="events-title">
          <span className="events-icon"><TbListSearch /></span>
          <h2>Search Events</h2>
        </div>
      </div>

      <div className="events-filters-grid">
        <FilterCard
          title="Category"
          type="select"
          value={filters.category}
          onChange={(value) => handleFilterChange('category', value)}
          options={dynamicCategories.map(c => ({ value: c, label: c }))}
          isActive={filters.category !== 'All Categories'}
        />

        <FilterCard
          title="Detection Rule"
          type="select"
          value={filters.rule}
          onChange={(value) => handleFilterChange('rule', value)}
          options={dynamicRules.map(r => ({ value: r, label: r }))}
          isActive={filters.rule !== 'All Rules'}
        />

        <FilterCard
          title="Camera"
          type="select"
          value={filters.camera}
          onChange={(value) => handleFilterChange('camera', value)}
          options={dynamicCameras.map(c => ({ value: c, label: c }))}
          isActive={filters.camera !== 'All Cameras'}
        />

        <FilterCard
          title="Location"
          type="select"
          value={filters.location}
          onChange={(value) => handleFilterChange('location', value)}
          options={dynamicLocations.map(l => ({ value: l, label: l }))}
          isActive={filters.location !== 'All Locations'}
        />

        <FilterCard
          title="Priority"
          type="select"
          value={filters.priority}
          onChange={(value) => handleFilterChange('priority', value)}
          options={priorities.map(p => ({ value: p, label: p }))}
          isActive={filters.priority !== 'All Priorities'}
        />

        <FilterCard
          title="Event Status"
          type="select"
          value={filters.status}
          onChange={(value) => handleFilterChange('status', value)}
          options={statuses.map(s => ({ value: s, label: s }))}
          isActive={filters.status !== 'All Statuses'}
        />
        
        <FilterCard
          title="Acknowledgment"
          type="select"
          value={filters.acknowledged}
          onChange={(value) => handleFilterChange('acknowledged', value)}
          options={[
            { value: 'all', label: 'All Events' },
            { value: 'acknowledged', label: 'Acknowledged' },
            { value: 'unacknowledged', label: 'Unacknowledged' }
          ]}
          isActive={filters.acknowledged !== 'all'}
        />
      </div>

      <div className="search-results">
        {loading ? (
          <div className="loading-state">Searching events...</div>
        ) : events.length === 0 ? (
          <div className="empty-state">No events found matching your criteria.</div>
        ) : (
          <div className="events-table-wrapper">
            <table className="events-table">
              <thead>
                <tr>
                  <th>Event ID</th>
                  <th>Time</th>
                  <th>Rule</th>
                  <th>Camera</th>
                  <th>Location</th>
                  <th>Priority</th>
                  <th>Duration</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {events.map(event => (
                  <tr key={event.event_id} onClick={() => setSelectedEvent(event)} className={selectedEvent?.event_id === event.event_id ? 'selected' : ''}>
                    <td>{event.event_id}</td>
                    <td>{formatDateTime(event.created_at)}</td>
                    <td>{event.rule_name}</td>
                    <td>{event.camera_name}</td>
                    <td>{event.location}</td>
                    <td><span className={`priority-badge ${event.priority?.toLowerCase()}`}>{event.priority}</span></td>
                    <td>{formatDuration(event.duration)}</td>
                    <td><span className={`status-badge ${event.status?.toLowerCase().replace(' ', '-')}`}>{event.status}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedEvent && (
        <EventDetailsPanel 
          event={selectedEvent} 
          onClose={() => setSelectedEvent(null)}
          onAcknowledge={async (id) => {
            const success = await eventService.acknowledgeEvent(id);
            if (success) {
              fetchEvents();
              setSelectedEvent({...selectedEvent, acknowledged: true, status: selectedEvent.status === 'Active' ? 'Acknowledged' : selectedEvent.status});
            }
          }}
        />
      )}
    </div>
  );
}

export default SearchEvents;

