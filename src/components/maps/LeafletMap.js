import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import './LeafletMap.css';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import { useCameraStore } from '../../store/cameraStore';
import cameraApi from '../../services/cameraApi';
import MJPEGStreamPlayer from '../camera/MJPEGStreamPlayer';

// ─── Pure helper: build a Leaflet divIcon for a camera marker ─────────────────
const buildMarkerIcon = (isActive, isSelected) => {
  const pinColor = isSelected ? '#f59e0b' : (isActive ? '#10b981' : '#ef4444');
  const markerClass = isSelected
    ? 'marker-pin-wrapper marker-pin-dragging'
    : `marker-pin-wrapper ${isActive ? 'marker-pin-active' : 'marker-pin-inactive'}`;

  return L.divIcon({
    html: `
      <div class="${markerClass}">
        <div class="marker-pulse"></div>
        <svg class="marker-drop-svg" viewBox="0 0 24 24" width="40" height="40" style="display:block;">
          <path d="M12 2C8.14 2 5 5.14 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.86-3.14-7-7-7z"
                fill="${pinColor}" stroke="#18191f" stroke-width="0.75"/>
          <path d="M8.5 5.5l1-1.5h5l1 1.5H19c0.55 0 1 0.45 1 1v8c0 0.55-0.45 1-1 1H5c-0.55 0-1-0.45-1-1v-8c0-0.55 0.45-1 1-1h3.5z"
                fill="#ffffff"/>
          <circle cx="12" cy="10.5" r="2.8" fill="${pinColor}"/>
        </svg>
      </div>`,
    className: 'custom-camera-marker',
    iconSize: [40, 40],
    iconAnchor: [20, 37],
    popupAnchor: [0, -37]
  });
};

// ─── Component ────────────────────────────────────────────────────────────────
const LeafletMap = ({
  mode = 'view',
  selectedCameraId = null,
  onCameraSelect = null,
  onLocationChange = null,
  customLocations = null
}) => {

  // ── Leaflet / DOM refs ────────────────────────────────────────────────────
  const mapContainerRef  = useRef(null);
  const mapRef           = useRef(null);
  const markersRef       = useRef({});
  const clusterGroupRef  = useRef(null);

  // ── Data refs — intentionally NOT React state so polling never re-renders ─
  const camerasRef      = useRef([]);    // latest cameras from API
  const syncMarkersRef  = useRef(null);  // pointer to current doSync()

  // ── The ONLY React state: which camera's overlay is visible ───────────────
  // setOverlayCamera is only ever called from user-initiated click handlers.
  // Polling / marker sync can NEVER close or reset it.
  const [overlayCamera, setOverlayCamera] = useState(null);
  const overlayCameraRef = useRef(null);
  useEffect(() => { overlayCameraRef.current = overlayCamera; }, [overlayCamera]);

  // ── Store ─────────────────────────────────────────────────────────────────
  const { cameraLocations: storeLocations, loadCameraLocations } = useCameraStore();
  const cameraLocations = customLocations || storeLocations;

  // ── Stable prop refs (avoid stale closures in Leaflet event handlers) ─────
  const onCameraSelectRef   = useRef(onCameraSelect);
  const onLocationChangeRef = useRef(onLocationChange);
  const selectedCameraIdRef = useRef(selectedCameraId);
  const modeRef             = useRef(mode);
  const cameraLocationsRef  = useRef(cameraLocations);

  useEffect(() => { onCameraSelectRef.current   = onCameraSelect;   }, [onCameraSelect]);
  useEffect(() => { onLocationChangeRef.current = onLocationChange;  }, [onLocationChange]);
  useEffect(() => { selectedCameraIdRef.current = selectedCameraId;  }, [selectedCameraId]);
  useEffect(() => { modeRef.current             = mode;              }, [mode]);
  useEffect(() => { cameraLocationsRef.current  = cameraLocations;   }, [cameraLocations]);

  // ─── 1. Load locations on mount ───────────────────────────────────────────
  useEffect(() => { loadCameraLocations(); }, [loadCameraLocations]);

  // ─── 2. Initialise Leaflet map ────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current && mapContainerRef.current) {
      const loc    = cameraLocationsRef.current;
      const center = loc?.settings?.center || [12.9716, 77.5946];
      const zoom   = loc?.settings?.zoom   || 13;

      const map = L.map(mapContainerRef.current, {
        center,
        zoom,
        zoomControl: true,
        closePopupOnClick: false,
        doubleClickZoom: mode === 'edit' ? false : true
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap contributors'
      }).addTo(map);

      mapRef.current = map;

      if (mode === 'edit') {
        map.on('dblclick', (e) => {
          const camId = selectedCameraIdRef.current;
          if (camId && onLocationChangeRef.current) {
            onLocationChangeRef.current(camId, e.latlng.lat, e.latlng.lng);
          }
        });
      }
    }
    return () => {
      if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; }
      clusterGroupRef.current = null;
    };
  }, [mode]);

  // ─── 3. Keep center / zoom in sync ───────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !cameraLocations?.settings) return;
    const { center, zoom } = cameraLocations.settings;
    const cur  = mapRef.current.getCenter();
    const latD = Math.abs(cur.lat - center[0]);
    const lngD = Math.abs(cur.lng - center[1]);
    if (latD > 0.0001 || lngD > 0.0001 || mapRef.current.getZoom() !== zoom) {
      mapRef.current.setView(center, zoom);
    }
  }, [cameraLocations?.settings]);

  // ─── 4. Marker sync ───────────────────────────────────────────────────────
  // Key design: doSync reads everything from REFS (never closed-over state).
  // This lets the polling effect call doSync() directly without any React
  // state change — so polling can NEVER trigger re-renders or close the overlay.
  useEffect(() => {

    const doSync = () => {
      if (!mapRef.current) return;

      const cameras   = camerasRef.current;
      const locs      = cameraLocationsRef.current;
      const selId     = selectedCameraIdRef.current;
      const curMode   = modeRef.current;

      if (!locs?.locations) return;

      // ── Initialise cluster group once ───────────────────────────────────
      if (!clusterGroupRef.current) {
        clusterGroupRef.current = L.markerClusterGroup({
          spiderfyOnMaxZoom : true,
          showCoverageOnHover: false,
          zoomToBoundsOnClick: true,
          maxClusterRadius  : 40,
          iconCreateFunction: (cluster) => {
            const childs = cluster.getAllChildMarkers();
            let active   = 0;
            childs.forEach(m => { if (m.options.isActive) active++; });
            const total = childs.length;
            const cls =
              active === total ? 'cluster-all-active'   :
              active === 0     ? 'cluster-all-inactive' :
                                 'cluster-mixed-status';
            return L.divIcon({
              html: `<div class="custom-cluster-marker ${cls}">
                       <div class="cluster-pulse"></div>
                       <span class="cluster-count">${total}</span>
                     </div>`,
              className: 'custom-leaflet-cluster',
              iconSize : [44, 44],
              iconAnchor: [22, 22]
            });
          }
        });
        mapRef.current.addLayer(clusterGroupRef.current);
      }

      // ── Edit-mode info popup (no stream — just drag hint) ────────────────
      const setupEditPopup = (m, cam, dName, lat, lng) => {
        const el = document.createElement('div');
        el.className = 'map-popup-container';
        el.innerHTML = `
          <div class="map-popup-header">
            <div class="map-popup-title" title="${dName}">${dName}</div>
            <span class="map-popup-status ${cam.isActive ? 'active' : 'inactive'}">
              ${cam.isActive ? 'Active' : 'Offline'}
            </span>
          </div>
          <div class="map-popup-footer">
            <div class="map-popup-metadata"><strong>IP:</strong> ${cam.ip} | <strong>Col:</strong> ${cam.collection}</div>
            <div class="map-popup-metadata"><strong>Coords:</strong> ${lat.toFixed(6)}, ${lng.toFixed(6)}</div>
            <div style="margin-top:6px;font-size:11px;color:#10b981;font-weight:500;text-align:center;">
              📍 Drag marker to reposition
            </div>
          </div>`;
        m.bindPopup(el, { maxWidth: 280, minWidth: 280, autoClose: false, closeOnClick: false });
      };

      const seenIds = new Set();

      cameras.forEach(camera => {
        const loc = locs.locations[camera.id];
        if (!loc) return;
        const { lat, lng, customName } = loc;
        if (lat == null || lng == null || isNaN(lat) || isNaN(lng)) return;

        seenIds.add(camera.id);

        const isActive    = camera.isActive;
        const displayName = customName || camera.name;
        const isSelected  = curMode === 'edit' && selId === camera.id;
        const icon        = buildMarkerIcon(isActive, isSelected);

        let marker = markersRef.current[camera.id];

        if (marker) {
          const wasActive   = marker.options.isActive;
          const wasSelected = !!marker.options.draggable;

          marker.options.isActive   = isActive;
          marker.options.customName = displayName;

          if (wasActive !== isActive || wasSelected !== isSelected) {
            marker.setIcon(icon);
          }

          // Use stored backend coordinates instead of getLatLng() because MarkerCluster
          // temporarily alters getLatLng() when spiderfying, which caused false positives.
          const bLat = marker.options.backendLat;
          const bLng = marker.options.backendLng;
          if (bLat !== lat || bLng !== lng) {
            marker.setLatLng([lat, lng]);
            marker.options.backendLat = lat;
            marker.options.backendLng = lng;
            if (curMode === 'edit') setupEditPopup(marker, camera, displayName, lat, lng);
          }

          if (isSelected) {
            if (clusterGroupRef.current.hasLayer(marker)) clusterGroupRef.current.removeLayer(marker);
            if (!mapRef.current.hasLayer(marker))         marker.addTo(mapRef.current);
            marker.dragging.enable();
          } else {
            // Only manipulate layers if it's NOT already in the cluster group
            if (!clusterGroupRef.current.hasLayer(marker)) {
              if (mapRef.current.hasLayer(marker)) mapRef.current.removeLayer(marker);
              clusterGroupRef.current.addLayer(marker);
            }
            if (marker.dragging) marker.dragging.disable();
          }

          if (wasActive !== isActive && clusterGroupRef.current.hasLayer(marker)) {
            clusterGroupRef.current.refreshClusters(marker);
          }

          if (isSelected) {
            setTimeout(() => {
              if (marker && mapRef.current && !marker.isPopupOpen()) marker.openPopup();
            }, 100);
          }

        } else {
          // ── Create new marker ──────────────────────────────────────────────
          marker = L.marker([lat, lng], { 
            icon, 
            draggable: isSelected, 
            isActive, 
            customName: displayName,
            backendLat: lat,
            backendLng: lng
          });

          if (curMode === 'edit') {
            setupEditPopup(marker, camera, displayName, lat, lng);
          }

          marker.on('click', () => {
            if (modeRef.current === 'view') {
              // Open React overlay — the ONLY place setOverlayCamera is called
              const fresh  = camerasRef.current.find(c => c.id === camera.id) || camera;
              const locNow = cameraLocationsRef.current?.locations?.[camera.id] || loc;
              setOverlayCamera({
                ...fresh,
                _displayName: locNow.customName || fresh.name,
                _lat: locNow.lat ?? lat,
                _lng: locNow.lng ?? lng
              });
            } else if (modeRef.current === 'edit' && onCameraSelectRef.current) {
              onCameraSelectRef.current(camera.id, camera.collection);
            }
          });

          if (isSelected) {
            marker.addTo(mapRef.current);
          } else {
            clusterGroupRef.current.addLayer(marker);
          }

          marker.on('dragend', (e) => {
            const { lat: nLat, lng: nLng } = e.target.getLatLng();
            if (onLocationChangeRef.current) onLocationChangeRef.current(camera.id, nLat, nLng);
          });

          markersRef.current[camera.id] = marker;

          if (isSelected) {
            setTimeout(() => {
              if (marker && mapRef.current && !marker.isPopupOpen()) marker.openPopup();
            }, 100);
          }
        }
      });

      // Remove stale markers
      Object.keys(markersRef.current).forEach(camId => {
        if (!seenIds.has(camId)) {
          const m = markersRef.current[camId];
          if (clusterGroupRef.current?.hasLayer(m)) clusterGroupRef.current.removeLayer(m);
          if (mapRef.current?.hasLayer(m)) m.remove();
          delete markersRef.current[camId];
        }
      });
    }; // end doSync

    // Publish so the polling effect can call it directly
    syncMarkersRef.current = doSync;

    // Run once now (camerasRef may be empty on first run if API hasn't responded yet)
    doSync();

  }, [cameraLocations, mode, selectedCameraId]); // triggers on major data / mode changes

  // ─── 5. Camera status polling ─────────────────────────────────────────────
  // CRITICAL: This effect NEVER calls setCameras or any other React state setter.
  // It updates camerasRef and calls doSync() directly.
  // Therefore it can NEVER cause a re-render and can NEVER affect overlayCamera.
  useEffect(() => {
    let isMounted = true;

    const poll = async () => {
      try {
        const cams = await cameraApi.getCamerasWithStatus();
        if (!isMounted) return;
        camerasRef.current = cams;
        syncMarkersRef.current?.(); // direct call — zero React involvement
      } catch (e) {
        console.error('LeafletMap: poll error', e);
      }
    };

    poll();                                    // immediate first fetch
    const interval = setInterval(poll, 5000);
    return () => { isMounted = false; clearInterval(interval); };
  }, []); // ← empty deps: runs once, never triggers re-renders

  // ─── Overlay handlers (user-initiated only) ───────────────────────────────
  const handleCloseOverlay = () => setOverlayCamera(null);

  const handleFocusInGrid = () => {
    if (overlayCamera && onCameraSelectRef.current) {
      onCameraSelectRef.current(overlayCamera.id, overlayCamera.collection);
    }
    handleCloseOverlay();
  };

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <div className="leaflet-map-wrapper">

      {mode === 'edit' && selectedCameraId && (
        <div className="map-instructions-overlay">
          📍 Drag the highlighted marker to position, or <b>double-click</b> on the map to set coordinates.
        </div>
      )}

      {/* Leaflet map canvas */}
      <div ref={mapContainerRef} className="leaflet-map-container" />

      {/* ── React stream overlay ──────────────────────────────────────────────
          Rendered as a sibling div — completely outside Leaflet's DOM tree.
          The ONLY thing that can close it is the user clicking the ✕ button.
          Polling, setIcon, refreshClusters, addLayer — none of these can
          touch this component because they never call setOverlayCamera.      */}
      {overlayCamera && mode === 'view' && (
        <div className="map-stream-overlay">
          <div className="map-popup-container">

            {/* Header */}
            <div className="map-popup-header">
              <div className="map-popup-title" title={overlayCamera._displayName || overlayCamera.name}>
                {overlayCamera._displayName || overlayCamera.name}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className={`map-popup-status ${overlayCamera.isActive ? 'active' : 'inactive'}`}>
                  {overlayCamera.isActive ? 'Active' : 'Offline'}
                </span>
                <button
                  className="map-overlay-close-btn"
                  onClick={handleCloseOverlay}
                  title="Close panel"
                >✕</button>
              </div>
            </div>

            {/* Live stream */}
            <div className="map-popup-video-wrapper">
              <MJPEGStreamPlayer camera={overlayCamera} />
            </div>

            {/* Footer */}
            <div className="map-popup-footer">
              <div className="map-popup-metadata">
                <strong>IP:</strong> {overlayCamera.ip} &nbsp;|&nbsp; <strong>Col:</strong> {overlayCamera.collection}
              </div>
              {overlayCamera._lat !== undefined && (
                <div className="map-popup-metadata">
                  <strong>Coords:</strong> {overlayCamera._lat.toFixed(6)}, {overlayCamera._lng.toFixed(6)}
                </div>
              )}
              <button className="map-popup-btn" onClick={handleFocusInGrid} style={{ marginTop: 6 }}>
                Focus in Grid
              </button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
};

export default LeafletMap;
