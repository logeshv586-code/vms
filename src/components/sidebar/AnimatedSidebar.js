import React, { useState, useEffect, useRef } from 'react';
import './AnimatedSidebar.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { 
  faBoxes, 
  faBookmark, 
  faMapMarkedAlt, 
  faPlus, 
  faUser,
  faCog,
  faVideo,
  faCalendarAlt,
  faArchive,
  faSearch,
  faChartBar,
  faServer,
  faNetworkWired,
  faUsersCog,
  faDatabase,
  faExclamationTriangle
} from '@fortawesome/free-solid-svg-icons';

const AnimatedSidebar = ({ 
  type = 'main', 
  activeItem, 
  onItemSelect, 
  currentUser,
  menuItems = [],
  children 
}) => {
  const [sidebarExpanded, setSidebarExpanded] = useState(true);
  const sidebarRef = useRef(null);
  const isMobile = window.innerWidth <= 768;

  useEffect(() => {
    if (isMobile) {
      setSidebarExpanded(false);
    }

    const handleResize = () => {
      if (window.innerWidth <= 768) {
        setSidebarExpanded(false);
      } else {
        setSidebarExpanded(true);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isMobile]);

  const handleItemClick = (itemId) => {
    if (onItemSelect) {
      onItemSelect(itemId);
    }
  };

  // Default menu items based on sidebar type
  const getDefaultMenuItems = () => {
    switch (type) {
      case 'main':
        return [
          { id: 'camera', label: 'My Collection', icon: faBoxes },
          { id: 'bookmark', label: 'Bookmarks', icon: faBookmark },
          { id: 'map', label: 'Discovery Map', icon: faMapMarkedAlt }
        ];
      case 'events':
        return [
          { id: 'search-events', label: 'Search Events', icon: faSearch },
          { id: 'analytics', label: 'Analytics', icon: faChartBar }
        ];
      case 'archive':
        return [
          { id: 'recordings', label: 'Recordings', icon: faVideo },
          { id: 'calendar', label: 'Calendar', icon: faCalendarAlt }
        ];
      case 'configuration':
        return [
          { id: 'cameras', label: 'Cameras', icon: faVideo },
          { id: 'media-server', label: 'Media Server', icon: faServer },
          { id: 'analytics-server', label: 'Analytics Server', icon: faChartBar },
          { id: 'video-decoder-connector', label: 'Video Decoder', icon: faNetworkWired },
          { id: 'dr-sites', label: 'DR Sites', icon: faDatabase },
          { id: 'alerts', label: 'Alerts', icon: faExclamationTriangle }
        ];
      case 'settings':
        return [
          { id: 'software-settings', label: 'Software Settings', icon: faCog },
          { id: 'user-access-management', label: 'User Management', icon: faUsersCog }
        ];
      default:
        return [];
    }
  };

  const items = menuItems.length > 0 ? menuItems : getDefaultMenuItems();

  return (
    <div 
      ref={sidebarRef}
      className={`sidebar ${sidebarExpanded ? 'expanded' : ''}`}
    >
      <div className="sidebar-header">
        <div className="logo-container">
          <FontAwesomeIcon icon={faVideo} />
        </div>
        <div className="logo-text">VMS</div>
      </div>

      <div className="sidebar-nav">
        {items.map((item) => (
          <div 
            key={item.id} 
            className={`sidebar-item ${activeItem === item.id ? 'active' : ''}`}
            onClick={() => handleItemClick(item.id)}
          >
            <div className="icon-container">
              <FontAwesomeIcon icon={item.icon} />
            </div>
            <span className="sidebar-item-text">{item.label}</span>
            {item.notification && <div className="notification-dot"></div>}
          </div>
        ))}

        {children}
      </div>

      {currentUser && (
        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">
              <FontAwesomeIcon icon={faUser} />
            </div>
            <div className="user-info">
              <div className="user-name">{currentUser.username}</div>
              <div className="user-role">{currentUser.role}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnimatedSidebar;
