import React, { useState, useEffect, useRef } from 'react';
import './EventsSidebar.css';
import '../sidebar/ModernSidebar.css'; // Import the new modern sidebar styles
import {
  Search as SearchingIcon,
  Event as CurrentIcon,
  Rule as RulesIcon,
  BarChart as StatisticsIcon,
  Perm_Media as MediaIcon,
  Monitor as MonitoringIcon,
  Settings as RulesSetIcon,
  Timeline as TrackIcon,
  Camera as CameraIcon,
  Tune as ParameterIcon,
  Sync as SyncIcon,
  FaceRetouchingNatural as AppearanceIcon
,
  DirectionsCar as VehicleIcon
} from '@mui/icons-material';
import { useUserStore } from '../../store/userStore';

function EventsSidebar({ onMenuSelect }) {
  const [showDetectionRules, setShowDetectionRules] = useState(false);
  const currentUser = useUserStore(state => state.currentUser);
  const hasPermission = useUserStore(state => state.hasPermission);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  // Ref for the sidebar element
  const sidebarRef = useRef(null);

  // Check if user is SuperAdmin
  const isSuperAdmin = currentUser && currentUser.role === 'SuperAdmin';

  // Check permissions
  const canSearchEvents = hasPermission('searchEvents');
  const canViewCurrentEvents = hasPermission('currentEvents');
  const canSetDetection = hasPermission('setDetection');
  const canViewEventStatistics = hasPermission('eventStatistics');

  // Handle window resize for responsive design
  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth <= 768;
      setIsMobile(mobile);
      // Reset expanded state when switching between mobile and desktop
      if (!mobile) {
        setSidebarExpanded(false);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Toggle sidebar expansion for mobile view
  const toggleSidebar = () => {
    setSidebarExpanded(prev => !prev);
  };

  const handleMenuSelect = (menuId) => {
    if (onMenuSelect) {
      onMenuSelect(menuId);
    }
  };

  return (
    <>
      {isMobile && (
        <button
          className="sidebar-toggle"
          onClick={toggleSidebar}
          aria-label={sidebarExpanded ? "Collapse sidebar" : "Expand sidebar"}
        >
          {sidebarExpanded ? "✕" : "☰"}
        </button>
      )}
      <div
        ref={sidebarRef}
        className="universal-sidebar-content"
        role="navigation"
        aria-label="Events navigation"
      >
        {canViewCurrentEvents && (
          <div className="sidebar-section">
            <button
              className="sidebar-btn"
              onClick={() => handleMenuSelect('current-events')}
            >
              <CurrentIcon className="sidebar-icon" />
              <span>Current Events</span>
              {isMobile && !sidebarExpanded && (
                <span className="sidebar-tooltip">Current Events</span>
              )}
            </button>
          </div>
        )}
        {canSearchEvents && (
          <div className="sidebar-section">
            <button
              className="sidebar-btn"
              onClick={() => handleMenuSelect('search-events')}
            >
              <SearchingIcon className="sidebar-icon" />
              <span>Search Events</span>
              {isMobile && !sidebarExpanded && (
                <span className="sidebar-tooltip">Search Events</span>
              )}
            </button>
          </div>
        )}
      {canViewEventStatistics && (
        <div className="sidebar-section">
          <button
            className="sidebar-btn"
            onClick={() => handleMenuSelect('events-statistics')}
          >
            <StatisticsIcon className="sidebar-icon" />
            <span>Event Statistics</span>
            {isMobile && !sidebarExpanded && (
              <span className="sidebar-tooltip">Event Statistics</span>
            )}
          </button>
        </div>
      )}
      {canSetDetection && (
        <div className="sidebar-section">
          <button
            className={`sidebar-btn ${showDetectionRules ? 'active' : ''}`}
            onClick={() => setShowDetectionRules((prev) => !prev)}
            aria-expanded={showDetectionRules}
            aria-controls="detection-rules-dropdown"
          >
            <RulesIcon className="sidebar-icon" />
            <span>Set Detection Rules</span>
            <span className={`chevron-icon ${showDetectionRules ? 'expanded' : ''}`}>
              {showDetectionRules ? "↑" : "↓"}
            </span>
            {isMobile && !sidebarExpanded && (
              <span className="sidebar-tooltip">Set Detection Rules</span>
            )}
          </button>
        {showDetectionRules && (
          <div id="detection-rules-dropdown" className="sidebar-dropdown">
            <button
              className="sidebar-btn sidebar-btn-sub"
              onClick={() => handleMenuSelect('detection-rule-set')}
            >
              <MonitoringIcon className="sidebar-icon" />
              <span>Detection Rule Set</span>
            </button>
            <button
              className="sidebar-btn sidebar-btn-sub"
              onClick={() => handleMenuSelect('rules-on-camera')}
            >
              <CameraIcon className="sidebar-icon" />
              <span>Rules On Camera</span>
            </button>
            <button
              className="sidebar-btn sidebar-btn-sub"
              onClick={() => handleMenuSelect('ptz-auto-tour')}
            >
              <TrackIcon className="sidebar-icon" />
              <span>PTZ Auto Tour</span>
            </button>
            <button
              className="sidebar-btn sidebar-btn-sub"
              onClick={() => handleMenuSelect('ptz-auto-track')}
            >
              <VehicleIcon className="sidebar-icon" />
              <span>PTZ Auto Track</span>
            </button>
            <button
              className="sidebar-btn sidebar-btn-sub"
              onClick={() => handleMenuSelect('live-monitoring-rules')}
            >
              <AppearanceIcon className="sidebar-icon" />
              <span>Live Monitoring Rules</span>
            </button>
            <button
              className="sidebar-btn sidebar-btn-sub"
              onClick={() => handleMenuSelect('event-parameters')}
            >
              <RulesIcon className="sidebar-icon" />
              <span>Event Parameters</span>
            </button>
          </div>
        )}
        </div>
      )}
      {/* Uploaded Media Section - Commented out
      <div className="sidebar-section">
        <button className="sidebar-btn">
          <img src={mediaIcon} alt="Media" className="sidebar-icon" style={{ width: '16px', height: '20px' }} />
          Uploaded Media
        </button>
      </div>
      */}
      </div>
    </>
  );
}

export default EventsSidebar;