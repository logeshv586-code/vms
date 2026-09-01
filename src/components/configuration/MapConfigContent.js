import React, { useEffect, useState } from 'react';
import { Map, Pin, Settings, Save, HelpCircle, Search, MapPin } from 'lucide-react';
import LeafletMap from '../maps/LeafletMap';
import './MapConfigContent.css';
import { useCameraStore } from '../../store/cameraStore';
import cameraApi from '../../services/cameraApi';
import mapApi from '../../services/mapApi';
import { API_BASE_URL } from '../../utils/apiConfig';
import MJPEGStreamPlayer from '../camera/MJPEGStreamPlayer';

const MapConfigContent = ({ selectedMenu }) => {
  const { cameraLocations, saveCameraLocations, loadCameraLocations } = useCameraStore();
  
  const [cameras, setCameras] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState('');
  
  // Camera coordinate form states
  const [lat, setLat] = useState('12.9716');
  const [lng, setLng] = useState('77.5946');
  const [customName, setCustomName] = useState('');
  
  // Local coordinate states (for real-time preview before saving)
  const [localLocations, setLocalLocations] = useState({});
  
  // Map preferences states
  const [defaultProvider, setDefaultProvider] = useState('leaflet');
  const [centerLat, setCenterLat] = useState('12.9716');
  const [centerLng, setCenterLng] = useState('77.5946');
  const [zoom, setZoom] = useState('13');
  
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Search states
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearchingLoc, setIsSearchingLoc] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [searchWarning, setSearchWarning] = useState('');

  // 1. Fetch cameras and load store state on mount
  useEffect(() => {
    const fetchCameras = async () => {
      try {
        const cams = await cameraApi.getCamerasWithStatus();
        setCameras(cams);
        
        // Auto-select first camera if available
        if (cams.length > 0) {
          setSelectedCameraId(cams[0].id);
          const firstCamLoc = cameraLocations?.locations?.[cams[0].id];
          if (firstCamLoc) {
            setLat(firstCamLoc.lat.toString());
            setLng(firstCamLoc.lng.toString());
            setCustomName(firstCamLoc.customName || '');
          } else {
            // Default center
            const center = cameraLocations?.settings?.center || [12.9716, 77.5946];
            setLat(center[0].toString());
            setLng(center[1].toString());
            setCustomName('');
          }
        }
      } catch (error) {
        console.error('Error loading cameras in MapConfigContent:', error);
      }
    };

    loadCameraLocations().then(() => {
      fetchCameras();
    });
  }, [loadCameraLocations]);

  // 2. Synchronize local states with loaded store state
  useEffect(() => {
    if (cameraLocations) {
      setLocalLocations(cameraLocations.locations || {});
      if (cameraLocations.settings) {
        setDefaultProvider(cameraLocations.settings.defaultProvider || 'leaflet');
        setCenterLat(cameraLocations.settings.center?.[0]?.toString() || '12.9716');
        setCenterLng(cameraLocations.settings.center?.[1]?.toString() || '77.5946');
        setZoom(cameraLocations.settings.zoom?.toString() || '13');
      }
    }
  }, [cameraLocations]);

  // 3. Handle camera selection from the list
  const handleSelectCamera = (cameraId) => {
    setSelectedCameraId(cameraId);
    
    // Check if coordinates exist locally first
    const loc = localLocations[cameraId];
    if (loc) {
      setLat(loc.lat.toString());
      setLng(loc.lng.toString());
      setCustomName(loc.customName || '');
    } else {
      // Check store coordinates
      const storeLoc = cameraLocations?.locations?.[cameraId];
      if (storeLoc) {
        setLat(storeLoc.lat.toString());
        setLng(storeLoc.lng.toString());
        setCustomName(storeLoc.customName || '');
      } else {
        // Fallback to current map center
        setLat(centerLat);
        setLng(centerLng);
        setCustomName('');
      }
    }
  };

  // 4. Handle marker movement (drag or double-click)
  const handleLocationChange = (cameraId, newLat, newLng) => {
    if (cameraId === selectedCameraId) {
      setLat(newLat.toFixed(6));
      setLng(newLng.toFixed(6));
    }

    setLocalLocations(prev => ({
      ...prev,
      [cameraId]: {
        ...prev[cameraId],
        lat: newLat,
        lng: newLng,
        customName: cameraId === selectedCameraId ? customName : (prev[cameraId]?.customName || '')
      }
    }));
  };

  // 5. Update input values on form changes
  const handleLatChange = (e) => {
    const val = e.target.value;
    setLat(val);
    const parsed = parseFloat(val);
    if (!isNaN(parsed) && selectedCameraId) {
      setLocalLocations(prev => {
        const currentLoc = prev[selectedCameraId] || {};
        return {
          ...prev,
          [selectedCameraId]: {
            lat: parsed,
            lng: currentLoc.lng !== undefined ? currentLoc.lng : parseFloat(lng) || parseFloat(centerLng) || 77.5946,
            customName: currentLoc.customName !== undefined ? currentLoc.customName : customName || ''
          }
        };
      });
    }
  };

  const handleLngChange = (e) => {
    const val = e.target.value;
    setLng(val);
    const parsed = parseFloat(val);
    if (!isNaN(parsed) && selectedCameraId) {
      setLocalLocations(prev => {
        const currentLoc = prev[selectedCameraId] || {};
        return {
          ...prev,
          [selectedCameraId]: {
            lat: currentLoc.lat !== undefined ? currentLoc.lat : parseFloat(lat) || parseFloat(centerLat) || 12.9716,
            lng: parsed,
            customName: currentLoc.customName !== undefined ? currentLoc.customName : customName || ''
          }
        };
      });
    }
  };

  const handleCustomNameChange = (e) => {
    const val = e.target.value;
    setCustomName(val);
    if (selectedCameraId) {
      setLocalLocations(prev => {
        const currentLoc = prev[selectedCameraId] || {};
        return {
          ...prev,
          [selectedCameraId]: {
            lat: currentLoc.lat !== undefined ? currentLoc.lat : parseFloat(lat) || parseFloat(centerLat) || 12.9716,
            lng: currentLoc.lng !== undefined ? currentLoc.lng : parseFloat(lng) || parseFloat(centerLng) || 77.5946,
            customName: val
          }
        };
      });
    }
  };

  // 6. Set current map viewport as center/zoom values
  const handleUseCurrentAsCenter = () => {
    setCenterLat(lat);
    setCenterLng(lng);
  };

  // Helper to clean noise words (like "eagle", "tower") and search for the main place
  const cleanAndRelaxQuery = (query) => {
    const noiseWords = ['eagle', 'tower', 'camera', 'cctv', 'pin', 'marker', 'station', 'office', 'building', 'room', 'gate'];
    const words = query.toLowerCase().split(/\s+/);
    const filtered = words.filter(word => !noiseWords.includes(word));
    return filtered.join(' ').trim();
  };

  // Search for custom places using our backend geocoding proxy
  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearchingLoc(true);
    setSearchError('');
    setSearchWarning('');
    setSearchResults([]);

    try {
      const data = await mapApi.geocode(searchQuery);
      
      if (data && data.results && data.results.length > 0) {
        setSearchResults(data.results);
        if (data.is_relaxed) {
          setSearchWarning(`"${searchQuery}" not found. Showing broad matches for "${data.relaxed_query}".`);
        }
      } else {
        setSearchError('No locations found. Try searching for a broader area (e.g. "Thousand Lights Chennai").');
      }
    } catch (err) {
      console.error('Error during location search:', err);
      setSearchError('Error searching location. Check your internet connection.');
    } finally {
      setIsSearchingLoc(false);
    }
  };

  // Center map on search result and automatically position selected camera
  const handleSelectSearchResult = (result) => {
    const latVal = parseFloat(result.lat);
    const lngVal = parseFloat(result.lon);

    if (!isNaN(latVal) && !isNaN(lngVal)) {
      // 1. Center the map at the searched location and zoom in closely
      setCenterLat(latVal.toFixed(6));
      setCenterLng(lngVal.toFixed(6));
      setZoom('16');

      // 2. If a camera is selected, automatically place its marker there too!
      if (selectedCameraId) {
        setLat(latVal.toFixed(6));
        setLng(lngVal.toFixed(6));

        setLocalLocations(prev => ({
          ...prev,
          [selectedCameraId]: {
            ...prev[selectedCameraId],
            lat: latVal,
            lng: lngVal,
            customName: customName || prev[selectedCameraId]?.customName || ''
          }
        }));
      }

      // Clear search results and pre-fill search bar
      setSearchResults([]);
      setSearchQuery(result.display_name.split(',')[0]);
    }
  };

  // 7. Save configuration changes to backend
  const handleSave = async () => {
    setIsSaving(true);
    setSaveSuccess(false);

    try {
      const updatedLocations = { ...localLocations };
      
      // Sync current form state for selected camera before saving
      if (selectedCameraId) {
        const parsedLat = parseFloat(lat);
        const parsedLng = parseFloat(lng);
        
        if (!isNaN(parsedLat) && !isNaN(parsedLng)) {
          updatedLocations[selectedCameraId] = {
            lat: parsedLat,
            lng: parsedLng,
            customName: customName
          };
        }
      }

      const updatedSettings = {
        defaultProvider,
        center: [parseFloat(centerLat), parseFloat(centerLng)],
        zoom: parseInt(zoom)
      };

      await saveCameraLocations(updatedLocations, updatedSettings);
      
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (error) {
      console.error('Failed to save map configuration:', error);
      alert('Error: Failed to save map configuration.');
    } finally {
      setIsSaving(false);
    }
  };

  // Construct locations object for interactive preview map
  const previewLocations = {
    settings: {
      defaultProvider,
      center: [parseFloat(centerLat) || 12.9716, parseFloat(centerLng) || 77.5946],
      zoom: parseInt(zoom) || 13
    },
    locations: localLocations
  };

  return (
    <div className="map-config-container">
      {/* Split Pane: Sidebar Control Panel */}
      <div className="map-config-sidebar">
        <div className="map-config-sidebar-header">
          <h2>
            <Map size={20} /> Map Configuration
          </h2>
          <p>Set GPS coordinates for cameras and customize map layouts</p>
        </div>

        <div className="map-config-sections">
          {/* Location Search Section */}
          <div className="map-config-card" style={{ borderLeft: '3px solid #10b981' }}>
            <h3 className="map-config-card-title" style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Search size={14} /> Search Location on Map
            </h3>
            <form onSubmit={handleSearch} className="map-search-form">
              <div className="map-search-input-wrapper">
                <input 
                  type="text" 
                  className="map-form-input map-search-input"
                  placeholder="Search place, e.g. Thousand Lights..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <button 
                  type="submit" 
                  className="map-search-btn"
                  disabled={isSearchingLoc}
                  title="Search"
                >
                  <Search size={14} />
                </button>
              </div>
            </form>
            
            {isSearchingLoc && (
              <div className="map-search-status">Searching locations...</div>
            )}
            
            {searchError && (
              <div className="map-search-error">{searchError}</div>
            )}
            
            {searchWarning && (
              <div className="map-search-warning" style={{ fontSize: '11px', color: '#f59e0b', marginTop: '8px', lineHeight: '1.4' }}>
                ⚠️ {searchWarning}
              </div>
            )}
            
            {searchResults.length > 0 && (
              <div className="map-search-results-list">
                {searchResults.map((result, idx) => (
                  <div 
                    key={idx}
                    className="map-search-result-item"
                    onClick={() => handleSelectSearchResult(result)}
                  >
                    <div className="map-search-result-name">
                      {result.display_name.split(',')[0]}
                    </div>
                    <div className="map-search-result-address">
                      {result.display_name.split(',').slice(1).join(',')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Section A: Global Map Settings */}
          <div className="map-config-card">
            <h3 className="map-config-card-title">
              <Settings size={14} style={{ marginRight: '6px', verticalAlign: 'middle' }} /> Global Map Settings
            </h3>
            
            <div className="map-form-group">
              <label>Default Map Provider</label>
              <select 
                className="map-form-select"
                value={defaultProvider}
                onChange={(e) => setDefaultProvider(e.target.value)}
              >
                <option value="leaflet">Leaflet Map (OpenStreetMap)</option>
                <option value="google">Google Map (Satellite/Hybrid)</option>
              </select>
            </div>

            <div className="map-form-row">
              <div className="map-form-group">
                <label>Center Lat</label>
                <input 
                  type="number" 
                  step="0.0001"
                  className="map-form-input"
                  value={centerLat}
                  onChange={(e) => setCenterLat(e.target.value)}
                />
              </div>
              <div className="map-form-group">
                <label>Center Lng</label>
                <input 
                  type="number" 
                  step="0.0001"
                  className="map-form-input"
                  value={centerLng}
                  onChange={(e) => setCenterLng(e.target.value)}
                />
              </div>
            </div>

            <div className="map-form-group" style={{ marginTop: '10px' }}>
              <label>Default Zoom Level (0 - 19)</label>
              <input 
                type="number" 
                min="0"
                max="19"
                className="map-form-input"
                value={zoom}
                onChange={(e) => setZoom(e.target.value)}
              />
            </div>
          </div>

          {/* Section B: Camera Selection */}
          <div className="map-config-card">
            <h3 className="map-config-card-title">
              <Pin size={14} style={{ marginRight: '6px', verticalAlign: 'middle' }} /> Select Camera to Configure
            </h3>
            
            <div className="camera-picker-list">
              {cameras.map(camera => {
                const isConfigured = !!localLocations[camera.id];
                return (
                  <div 
                    key={camera.id}
                    className={`camera-picker-item ${selectedCameraId === camera.id ? 'active' : ''}`}
                    onClick={() => handleSelectCamera(camera.id)}
                  >
                    <div className="camera-picker-info">
                      <span className="camera-picker-name" title={camera.name}>
                        {camera.name}
                      </span>
                      <span className="camera-picker-details">
                        {camera.collection} | {camera.ip}
                      </span>
                    </div>
                    <span className={`badge ${isConfigured ? 'badge-configured' : 'badge-unconfigured'}`}>
                      {isConfigured ? 'Set' : 'Missing'}
                    </span>
                  </div>
                );
              })}
              {cameras.length === 0 && (
                <div style={{ padding: '10px', textAlign: 'center', color: '#6b7280', fontSize: '12px' }}>
                  No cameras registered in system.
                </div>
              )}
            </div>
          </div>

          {/* Section C: Selected Camera Details & Coordinates Form */}
          {selectedCameraId && (
            <div className="map-config-card" style={{ borderLeft: '3px solid #3b82f6' }}>
              <h3 className="map-config-card-title" style={{ color: '#3b82f6' }}>
                ✏️ Coordinate Configuration
              </h3>
              
              <div className="map-form-group">
                <label>Custom Marker Display Name</label>
                <input 
                  type="text" 
                  className="map-form-input"
                  placeholder="e.g. Lobby North Entrance"
                  value={customName}
                  onChange={handleCustomNameChange}
                />
              </div>

              <div className="map-form-row">
                <div className="map-form-group">
                  <label>Latitude</label>
                  <input 
                    type="number" 
                    step="0.000001"
                    className="map-form-input"
                    value={lat}
                    onChange={handleLatChange}
                  />
                </div>
                <div className="map-form-group">
                  <label>Longitude</label>
                  <input 
                    type="number" 
                    step="0.000001"
                    className="map-form-input"
                    value={lng}
                    onChange={handleLngChange}
                  />
                </div>
              </div>

              <button 
                type="button"
                className="map-btn map-btn-secondary"
                style={{ width: '100%', marginTop: '12px', fontSize: '11px', padding: '6px' }}
                onClick={handleUseCurrentAsCenter}
              >
                Set Coordinates as Map Center
              </button>

              {/* Selected Camera Live Image Preview */}
              {(() => {
                const selectedCamera = cameras.find(c => c.id === selectedCameraId);
                if (!selectedCamera) return null;
                return (
                  <div className="map-config-preview-container" style={{ marginTop: '16px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '16px' }}>
                    <label style={{ fontSize: '12px', fontWeight: '600', color: '#9ca3af', display: 'block', marginBottom: '8px' }}>
                      📷 Live Camera Preview
                    </label>
                    <div className="map-config-preview-wrapper" style={{ position: 'relative', width: '100%', height: '160px', borderRadius: '6px', overflow: 'hidden', background: '#000' }}>
                      <MJPEGStreamPlayer camera={selectedCamera} />
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>

        {/* Action Panel Footer */}
        <div className="map-config-sidebar-footer">
          <button 
            type="button" 
            className="map-btn map-btn-primary"
            onClick={handleSave}
            disabled={isSaving}
          >
            <Save size={16} />
            {isSaving ? 'Saving...' : saveSuccess ? 'Saved!' : 'Save Configuration'}
          </button>
        </div>
      </div>

      {/* Split Pane: Right Side Leaflet Map Editor */}
      <div className="map-config-main">
        {/* Render LeafletMap in EDIT mode with real-time preview coordinates */}
        <LeafletMap 
          mode="edit"
          selectedCameraId={selectedCameraId}
          onCameraSelect={handleSelectCamera}
          onLocationChange={handleLocationChange}
          customLocations={previewLocations}
        />
        
        <div className="map-overlay-tip">
          <strong>💡 Interactive Map Placement</strong>
          <ul>
            <li>Select a camera on the left panel.</li>
            <li>Double-click anywhere on the map to place its marker instantly.</li>
            <li>Drag the highlighted marker to refine its position precisely.</li>
            <li>Click <b>Save Configuration</b> when done.</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default MapConfigContent;
