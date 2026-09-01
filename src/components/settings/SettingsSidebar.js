import React, { useState, useEffect, useRef } from 'react';
import './SettingsSidebar.css';
import '../sidebar/ModernSidebar.css'; // Import the new modern sidebar styles
import {
  Description as LogsIcon,
  Settings as SettingsIcon
} from '@mui/icons-material';

const SettingsSidebar = ({ onMenuSelect }) => {
  const [activeItem, setActiveItem] = useState('camera-settings');
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

  const menuItems = [
    {
      id: 'camera-settings',
      label: 'Camera Settings',
      icon: <SettingsIcon />
    },
    {
      id: 'logs',
      label: 'Logs',
      icon: <LogsIcon />
    }
  ];

  const handleMenuSelect = (itemId) => {
    setActiveItem(itemId);
    if (onMenuSelect) {
      onMenuSelect(itemId);
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
        aria-label="Settings navigation"
      >
        {menuItems.map((item) => (
          <div key={item.id} className="sidebar-section">
            <button
              className={`sidebar-btn ${activeItem === item.id ? 'active' : ''}`}
              onClick={() => handleMenuSelect(item.id)}
            >
              <span className="sidebar-icon">{item.icon}</span>
              <span>{item.label}</span>
              {isMobile && !sidebarExpanded && (
                <span className="sidebar-tooltip">{item.label}</span>
              )}
            </button>
          </div>
        ))}
      </div>
    </>
  );
};

export default SettingsSidebar;