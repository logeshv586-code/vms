import React, { useState, useEffect, useMemo } from 'react';
import { eventService } from '../../services/eventService';
import { fetchEventRules } from '../../services/eventsService';
import { useCameraStore } from '../../store/cameraStore';
import './EventsContent.css'; // Reuse or create new css
import EventDetailsPanel from './EventDetailsPanel';
import FilterCard from './FilterCard';

function CurrentEvents() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState(null);

  // Dynamic filter state
  const [availableRules, setAvailableRules] = useState([]);
  const [cameraRules, setCameraRules] = useState({});
  
  // Get camera and location data from store
  const cameras = useCameraStore(state => state.cameras || []);
  const cameraLocations = useCameraStore(state => state.cameraLocations?.locations || {});

  const [filters, setFilters] = useState({
    category: 'All Categories',
    rule: 'All Rules',
    priority: 'All Priorities',
    location: 'All Locations',
    camera: 'All Cameras'
  });

  // Fetch dynamic rules and camera rules from the backend
  useEffect(() => {
    const loadData = async () => {
      try {
        const [rulesRes, cameraRulesRes] = await Promise.all([
          fetchEventRules(),
          import('../../services/eventsService').then(m => m.fetchCameraRules())
        ]);
        
        if (rulesRes.success && rulesRes.data && rulesRes.data.rules) {
          // Map hardcoded categories to rules since backend config might lack them
          const categoryMap = {
            'Appearance Search': 'Face Analytics',
            'Face Capture': 'Face Analytics',
            'Face Recognition': 'Face Analytics',
            'Intrusion Detection': 'Security Analytics',
            'Zone Monitoring': 'Security Analytics',
            'Lakshmanrekha Crossing': 'Security Analytics',
            'Loitering': 'Security Analytics',
            'Camera Tamper': 'Security Analytics',
            'Unattended Object': 'Security Analytics',
            'Chain/Handbag Snatching': 'Crime Detection',
            'Mobile Snatching': 'Crime Detection',
            'People Fighting': 'Crime Detection',
            'Eve Teasing': 'Crime Detection',
            'Women/Infant Abduction': 'Crime Detection',
            'Women Surrounded by Men': 'Crime Detection',
            'Suspected Appearance': 'Crime Detection',
            'Crowd Detection': 'Crowd & Public Safety',
            'Person Collapsing': 'Crowd & Public Safety',
            'Strike / Morcha / Hartal / Procession': 'Crowd & Public Safety',
            'Vehicle Monitoring': 'Vehicle Analytics'
          };
          
          const enrichedRules = rulesRes.data.rules.map(r => ({
            ...r,
            category: categoryMap[r.name] || 'Other'
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
  }, []);

  // Compute dynamic options
  const dynamicCategories = useMemo(() => {
    const cats = new Set(availableRules.map(r => r.category).filter(Boolean));
    return ['All Categories', ...Array.from(cats).sort()];
  }, [availableRules]);

  const dynamicRules = useMemo(() => {
    let filteredRules = availableRules;
    
    // Filter by category if set
    if (filters.category !== 'All Categories') {
      filteredRules = filteredRules.filter(r => r.category === filters.category);
    }
    
    // Filter by active camera rules
    if (Object.keys(cameraRules).length > 0) {
      let activeRuleIds = new Set();
      if (filters.camera === 'All Cameras') {
        Object.values(cameraRules).forEach(rules => {
          if (Array.isArray(rules)) rules.forEach(id => activeRuleIds.add(id));
        });
      } else {
        const selectedCam = cameras.find(c => c.name === filters.camera);
        if (selectedCam) {
          const backendId = selectedCam.name.replace(' (', '_').replace(')', '');
          const rules = cameraRules[backendId] || cameraRules[selectedCam.id] || [];
          if (Array.isArray(rules)) rules.forEach(id => activeRuleIds.add(id));
        }
      }
      filteredRules = filteredRules.filter(r => activeRuleIds.has(r.id));
    }

    const ruleNames = new Set(filteredRules.map(r => r.name).filter(Boolean));
    return ['All Rules', ...Array.from(ruleNames).sort()];
  }, [availableRules, filters.category, filters.camera, cameraRules, cameras]);

  const dynamicCameras = useMemo(() => {
    const camNames = new Set(cameras.map(c => c.name).filter(Boolean));
    return ['All Cameras', ...Array.from(camNames)];
  }, [cameras]);

  const dynamicLocations = useMemo(() => {
    const locNames = new Set(Object.values(cameraLocations).map(loc => loc.customName).filter(Boolean));
    return ['All Locations', ...Array.from(locNames)];
  }, [cameraLocations]);

  const priorities = ['All Priorities', 'Critical', 'High', 'Medium', 'Low'];

  const fetchEvents = async () => {
    setLoading(true);
    const data = await eventService.getCurrentEvents();
    setEvents(data);
    setLoading(false);
  };

  useEffect(() => {
    fetchEvents();
    // Poll every 5 seconds for live events
    const interval = setInterval(fetchEvents, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleFilterChange = (filterType, value) => {
    setFilters(prev => {
      const newFilters = { ...prev, [filterType]: value };
      if (filterType === 'category') {
        newFilters.rule = 'All Rules';
      }
      return newFilters;
    });
  };

  const handleEventClick = (event) => {
    setSelectedEvent(event);
  };

  const handleClosePanel = () => {
    setSelectedEvent(null);
  };

  const handleAcknowledge = async (e, eventId) => {
    if (e) e.stopPropagation();
    
    const success = await eventService.acknowledgeEvent(eventId);
    if (success) {
      setEvents(events.map(evt => 
        evt.event_id === eventId ? { ...evt, acknowledged: true, status: 'Acknowledged' } : evt
      ));
      if (selectedEvent && selectedEvent.event_id === eventId) {
        setSelectedEvent({ ...selectedEvent, acknowledged: true, status: 'Acknowledged' });
      }
    }
  };

  const formatTime = (isoString) => {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

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

  // Apply filters client-side for live events
  const filteredEvents = useMemo(() => {
    return events.filter(event => {
      if (!categoriesMatch(filters.category, event.category)) return false;
      if (!rulesMatch(filters.rule, event.rule_name || event.rule)) return false;
      if (filters.priority !== 'All Priorities' && filters.priority !== 'all') {
        if (event.priority?.toLowerCase() !== filters.priority.toLowerCase()) return false;
      }
      if (filters.location !== 'All Locations' && filters.location !== 'all') {
        if (!event.location?.toLowerCase().includes(filters.location.toLowerCase())) return false;
      }
      
      if (filters.camera !== 'All Cameras' && filters.camera !== 'all') {
        const backendCamName = filters.camera.replace(' (', '_').replace(')', '').toLowerCase();
        const evtCam = (event.camera_name || event.camera_id || '').toLowerCase();
        if (!evtCam.includes(backendCamName) && !evtCam.includes(filters.camera.toLowerCase())) return false;
      }
      return true;
    });
  }, [events, filters]);

  return (
    <div className="current-events-container">
      <div className="events-header">
        <h2>Live Active Events</h2>
        <span className="live-indicator">● LIVE</span>
      </div>

      <div className="events-filters-grid" style={{ marginBottom: '20px' }}>
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
      </div>

      {loading && filteredEvents.length === 0 ? (
        <div className="loading-state">Loading active events...</div>
      ) : filteredEvents.length === 0 ? (
        <div className="empty-state">No active events matching your filters.</div>
      ) : (
        <div className="events-table-wrapper">
          <table className="events-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Camera</th>
                <th>Location</th>
                <th>Event Rule</th>
                <th>Category</th>
                <th>Priority</th>
                <th>Confidence</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvents.map(event => (
                <tr key={event.event_id} onClick={() => setSelectedEvent(event)} className={selectedEvent?.event_id === event.event_id ? 'selected' : ''}>
                  <td>{formatTime(event.created_at)}</td>
                  <td>{event.camera_name}</td>
                  <td>{event.location}</td>
                  <td>{event.rule_name}</td>
                  <td>{event.category}</td>
                  <td><span className={`priority-badge ${event.priority?.toLowerCase()}`}>{event.priority}</span></td>
                  <td>{Math.round(event.confidence * 100)}%</td>
                  <td><span className={`status-badge ${event.status?.toLowerCase().replace(' ', '-')}`}>{event.status}</span></td>
                  <td>
                    {event.status === 'Active' && !event.acknowledged ? (
                      <button className="action-btn ack-btn" onClick={(e) => handleAcknowledge(e, event.event_id)}>Acknowledge</button>
                    ) : (
                      <span style={{ color: '#4caf50', fontSize: '12px' }}>✓ Acknowledged</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      
      {selectedEvent && (
        <EventDetailsPanel 
          event={selectedEvent} 
          onClose={() => setSelectedEvent(null)}
          onAcknowledge={(id) => {
             handleAcknowledge({stopPropagation:()=>{}}, id);
          }}
        />
      )}
    </div>
  );
}

export default CurrentEvents;

