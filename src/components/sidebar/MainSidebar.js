import React, { useState, useEffect, useCallback } from 'react';
import './MainSidebar.css';
import './ModernSidebar.css';
import MapSelector from '../maps/MapSelector';
import { useCameraStore } from '../../store/cameraStore';

import DraggableSidebarCamera from './DraggableSidebarCamera';
import {
  Videocam as CctvIcon,
  Bookmark as BookmarkIcon,
  Monitor as CollectionIcon,
  LocationOn as LocationIcon,
  VideoLibrary as StreamIcon,
  Assessment as AnalyticsIcon
} from '@mui/icons-material';

function MainSidebar({ onViewChange, isSidebarExpanded = false }) {
  const [collectionsExpanded, setCollectionsExpanded] = useState(true);
  const [showBookmark, setShowBookmark] = useState(false);
  const [showMap, setShowMap] = useState(false);
  const [selectedMap, setSelectedMap] = useState(null);
  const [showDashboardAnalytics, setShowDashboardAnalytics] = useState(false);
  const [expandedCollections, setExpandedCollections] = useState({});

  const {
    collections,
    activeCollection,
    setCollectionActive,
    getCamerasByCollection,
    getBookmarkedCameras,
    isBookmarked,
    cameras
  } = useCameraStore();

  useEffect(() => {
    setCollectionsExpanded(prev => prev);
  }, [cameras, collections]);

  useEffect(() => {
    if (collections.length > 0) {
      const initialExpandedState = {};
      collections.forEach(collection => {
        initialExpandedState[collection.id] = true;
      });
      setExpandedCollections(initialExpandedState);
    }
  }, [collections]);

  const handleMapSelect = (mapType) => {
    setSelectedMap(mapType);
    onViewChange(mapType === 'basic' ? 'basic-map' : 'global-map');
  };

  const handleSelectCollection = (collectionId) => {
    setCollectionActive(collectionId);
    onViewChange('camera');
  };

  const toggleCollectionExpand = (collectionId, event) => {
    event.stopPropagation();
    setExpandedCollections(prev => ({
      ...prev,
      [collectionId]: !prev[collectionId]
    }));
  };

  const handleBookmarkClick = useCallback((camera) => {
    if (camera) {
      console.log('Clicked on bookmarked camera:', camera.name, camera.id);
    }
    setCollectionActive(null);
    setShowBookmark(false);
    onViewChange('bookmark');
  }, [onViewChange, setCollectionActive]);

  const handleBookmarkSectionClick = useCallback(() => {
    setShowBookmark((prev) => !prev);
    if (!showBookmark) {
      onViewChange('bookmark');
    }
  }, [showBookmark, onViewChange]);

  const handleDashboardAnalyticsClick = () => {
    setShowDashboardAnalytics(true);
    onViewChange('dashboard-analytics');
  };

  return (
    <div className="universal-sidebar-content">
      {/* Dashboard Analytics Section */}
      <ul className="sidebar-menu">
        <li className="menu-item">
          <button
            className="menu-label"
            onClick={handleDashboardAnalyticsClick}
            aria-expanded={false}
          >
            <div className="menu-icon">
              <AnalyticsIcon />
            </div>
            <span>Dashboard Analytics</span>
          </button>
        </li>
      </ul>

      {/* Collections Section */}
      <ul className="sidebar-menu">
        <li className={`menu-item has-children ${collectionsExpanded ? 'expanded' : ''}`}>
          <button
            className="menu-label"
            onClick={() => {
              setCollectionsExpanded(prev => !prev);
              setShowDashboardAnalytics(false);
              onViewChange('camera');
            }}
            aria-expanded={collectionsExpanded}
            aria-haspopup="true"
          >
            <div className="menu-icon">
              <CollectionIcon />
            </div>
            <span>Collections</span>
            <span className="chevron">▾</span>
          </button>
          <ul className="submenu">
            {collections.map(collection => {
              const cameras = getCamerasByCollection(collection.id);
              return (
                <li key={collection.id} className={`submenu-item has-children ${expandedCollections[collection.id] ? 'expanded' : ''}`}>
                  <button
                    className={`submenu-label ${activeCollection === collection.id ? 'active' : ''}`}
                    onClick={() => handleSelectCollection(collection.id)}
                    aria-expanded={expandedCollections[collection.id]}
                    aria-haspopup={cameras.length > 0 ? "true" : undefined}
                  >
                    <div className="submenu-icon">
                      <CollectionIcon />
                    </div>
                    <span>{collection.name}</span>
                    {cameras.length > 0 && (
                      <span className="submenu-count">({cameras.length})</span>
                    )}
                    {cameras.length > 0 && (
                      <span
                        className="chevron"
                        onClick={(e) => toggleCollectionExpand(collection.id, e)}
                      >▾</span>
                    )}
                  </button>
                  {cameras.length > 0 && (
                    <ul className="subsubmenu">
                      {cameras.map(camera => (
                        <DraggableSidebarCamera
                          key={camera.id}
                          camera={camera}
                          isBookmarked={isBookmarked(camera.id)}
                          onClick={(camera) => {
                            console.log('Camera selected:', camera.name);
                            handleSelectCollection(collection.id);
                          }}
                        />
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        </li>
      </ul>

      {/* Bookmarks Section */}
      <ul className="sidebar-menu">
        <li className={`menu-item has-children ${showBookmark ? 'expanded' : ''}`}>
          <button
            className="menu-label"
            onClick={handleBookmarkSectionClick}
            aria-expanded={showBookmark}
            aria-haspopup="true"
          >
            <div className="menu-icon">
              <BookmarkIcon />
            </div>
            <span>Bookmarks</span>
            {getBookmarkedCameras().length > 0 && (
              <span className="submenu-count">({getBookmarkedCameras().length})</span>
            )}
            <span className="chevron">▾</span>
          </button>
          <ul className="submenu">
            {getBookmarkedCameras().length === 0 ? (
              <li className="submenu-item">
                <div className="submenu-label">
                  <span>No Bookmarks Yet</span>
                </div>
              </li>
            ) : (
              getBookmarkedCameras().map(camera => (
                <li key={camera.id} className="submenu-item">
                  <button
                    className="submenu-label"
                    onClick={() => handleBookmarkClick(camera)}
                  >
                    <div className="submenu-icon">
                      <CctvIcon />
                    </div>
                    <span>{camera.name}</span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </li>
      </ul>

      {/* Map Section */}
      <ul className="sidebar-menu">
        <li className={`menu-item has-children ${showMap ? 'expanded' : ''}`}>
          <button
            className="menu-label"
            onClick={() => setShowMap((prev) => !prev)}
            aria-expanded={showMap}
            aria-haspopup="true"
          >
            <div className="menu-icon">
              <LocationIcon />
            </div>
            <span>Map</span>
            <span className="chevron">▾</span>
          </button>
          <ul className="submenu">
            <li className="submenu-item">
              <div className="submenu-label">
                <MapSelector onMapSelect={handleMapSelect} selectedMap={selectedMap} />
              </div>
            </li>
          </ul>
        </li>
      </ul>
    </div>
  );
}

export default MainSidebar;
