import React from 'react';
import { GoogleMap, LoadScript } from '@react-google-maps/api';
import './Maps.css';

const containerStyle = {
  width: '100%',
  height: '100%'
};

const center = {
  lat: 0,
  lng: 0
};

const GlobalMap = () => {
  return (
    <div className="map-container">
      <LoadScript googleMapsApiKey={process.env.REACT_APP_GOOGLE_MAPS_API_KEY}>
        <GoogleMap
          mapContainerStyle={containerStyle}
          center={center}
          zoom={2}
          options={{
            mapTypeId: 'satellite',
            mapTypeControl: true,
            zoomControl: true,
            streetViewControl: true,
            tilt: 45, // This adds the 3D effect
          }}
        >
        </GoogleMap>
      </LoadScript>
    </div>
  );
};

export default GlobalMap;