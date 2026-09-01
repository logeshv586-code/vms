import React from 'react';
import './Map.css';

const Map = ({ type = 'basic', onCameraSelect }) => {
  return (
    <div className={`map-container ${type}-map`}>
      <div className="map-header">
        <h3>{type.charAt(0).toUpperCase() + type.slice(1)} Map</h3>
      </div>
      <div className="map-content">
        {/* Map implementation would go here - using a placeholder for now */}
        <div className="map-placeholder">
          <div className="map-overlay">
            {/* Example camera markers - in real implementation these would be dynamic */}
            <div className="camera-marker" onClick={() => onCameraSelect('Camera 1')} style={{ left: '20%', top: '30%' }}>
              <span className="marker-label">1</span>
            </div>
            <div className="camera-marker" onClick={() => onCameraSelect('Camera 2')} style={{ left: '45%', top: '50%' }}>
              <span className="marker-label">2</span>
            </div>
            <div className="camera-marker" onClick={() => onCameraSelect('Camera 3')} style={{ left: '70%', top: '25%' }}>
              <span className="marker-label">3</span>
            </div>
            <div className="camera-marker" onClick={() => onCameraSelect('Camera 4')} style={{ left: '60%', top: '75%' }}>
              <span className="marker-label">4</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Map;