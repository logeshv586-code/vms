// React must be in scope when using JSX
import React, { useState, useEffect, useRef } from 'react';
import './ArchiveSidebar.css';
import '../sidebar/ModernSidebar.css'; // Import the new modern sidebar styles
import {
  Archive as ArchiveIcon,
  Assessment as RecReportIcon,
  Warning as CriticalIcon,
  PlayArrow as PlaybackIcon,
  FiberManualRecord as CurrentIcon,
  ContentCut as CutIcon
} from '@mui/icons-material';
import { useUserStore } from '../../store/userStore';

const ArchiveSidebar = ({ onMenuSelect, currentView }) => {
  const hasPermission = useUserStore(state => state.hasPermission);
  const [activeItem, setActiveItem] = useState(currentView || 'current-recordings');

  // Keep activeItem synchronized with currentView prop if it changes from outside
  useEffect(() => {
    if (currentView && currentView !== activeItem) {
      setActiveItem(currentView);
    }
  }, [currentView, activeItem]);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  // Ref for the sidebar element
  const sidebarRef = useRef(null);

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

  // Check permissions for each menu item
  const allMenuItems = [
    { id: 'current-recordings', label: 'Current Recordings', icon: <CurrentIcon />, permission: 'currentRecordings' },
    { id: 'archive-playback', label: 'Archive Playback', icon: <ArchiveIcon />, permission: 'archivePlayback' },
    { id: 'extracted-videos', label: 'Extracted Videos', icon: <CutIcon />, permission: 'extractedVideos' },
    { id: 'recording-report', label: 'Recording Report', icon: <RecReportIcon />, permission: 'recordingReport' },
    { id: 'critical-video', label: 'Critical Video', icon: <CriticalIcon />, permission: 'criticalVideo' },
    { id: 'redundant-playback', label: 'Redundant Playback', icon: <PlaybackIcon />, permission: 'redundantPlayback' }
  ];

  const menuItems = allMenuItems.filter(item => {
    if (item.id === 'extracted-videos') return true; // Always allow Extracted Videos
    return hasPermission(item.permission);
  });

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
        aria-label="Archive navigation"
      >
        {/* Menu items */}
        {menuItems.map((item) => (
          <div key={item.id} className="sidebar-section">
            <button
              className={`sidebar-btn ${activeItem === item.id ? 'active' : ''}`}
              onClick={() => {
                setActiveItem(item.id);
                if (onMenuSelect) {
                  onMenuSelect(item.id);
                }
              }}
            >
              <span className="sidebar-icon">{item.icon}</span>
              <span>{item.label}</span>
              {isMobile && !sidebarExpanded && (
                <span className="sidebar-tooltip">{item.label}</span>
              )}
            </button>
          </div>
        ))}

      {/* No recordings section in sidebar anymore */}
      </div>
    </>
  );
};

// Use React.memo to optimize rendering
export default React.memo(ArchiveSidebar);