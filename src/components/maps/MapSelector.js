import React, { useState } from 'react';
import BasicMap from './BasicMap';
import GlobalMap from './GlobalMap';
import './Maps.css';
import { Map as MapIcon, Place as PlaceIcon } from '@mui/icons-material';

const MapSelector = ({ onMapSelect, selectedMap }) => {
  return (
    <div className="map-selector">
      <button
        className={`sidebar-btn sidebar-btn-sub ${selectedMap === 'basic' ? 'active' : ''}`}
        onClick={() => onMapSelect('basic')}
      >
        <MapIcon className="sidebar-icon" />
        Basic Map
      </button>
      <button
        className={`sidebar-btn sidebar-btn-sub ${selectedMap === 'global' ? 'active' : ''}`}
        onClick={() => onMapSelect('global')}
      >
        <PlaceIcon className="sidebar-icon" />
        Global Map
      </button>
    </div>
  );
};

export default MapSelector;