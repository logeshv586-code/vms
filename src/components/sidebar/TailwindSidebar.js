import React, { useState, useEffect } from 'react';
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
  faExclamationTriangle,
  faBookOpen,
  faBars,
  faTimes
} from '@fortawesome/free-solid-svg-icons';

// Custom styles for animations
const sidebarStyles = `
  @keyframes slideIn {
    from {
      transform: translateX(-100%);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }

  .sidebar-animation {
    animation: slideIn 0.5s ease-out forwards;
  }

  .sidebar-item {
    transition: all 0.3s ease;
    transform-origin: left center;
  }

  .sidebar-item:hover {
    transform: scale(1.05);
  }
`;

const TailwindSidebar = ({
  type = 'main',
  activeItem,
  onItemSelect,
  currentUser
}) => {
  const [sidebarItems, setSidebarItems] = useState([]);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Toggle mobile menu
  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  // Get sidebar items based on type
  useEffect(() => {
    switch (type) {
      case 'main':
        setSidebarItems([
          { id: 'camera', label: 'My Collection', icon: faBoxes, notification: true },
          { id: 'bookmark', label: 'Bookmarks', icon: faBookmark },
          { id: 'map', label: 'Discovery Map', icon: faMapMarkedAlt }
        ]);
        break;
      case 'events':
        setSidebarItems([
          { id: 'search-events', label: 'Search Events', icon: faSearch },
          { id: 'analytics', label: 'Analytics', icon: faChartBar }
        ]);
        break;
      case 'archive':
        setSidebarItems([
          { id: 'recordings', label: 'Recordings', icon: faVideo },
          { id: 'calendar', label: 'Calendar', icon: faCalendarAlt }
        ]);
        break;
      case 'configuration':
        setSidebarItems([
          { id: 'cameras', label: 'Cameras', icon: faVideo },
          { id: 'media-server', label: 'Media Server', icon: faServer },
          { id: 'analytics-server', label: 'Analytics Server', icon: faChartBar },
          { id: 'video-decoder-connector', label: 'Video Decoder', icon: faNetworkWired },
          { id: 'dr-sites', label: 'DR Sites', icon: faDatabase },
          { id: 'alerts', label: 'Alerts', icon: faExclamationTriangle }
        ]);
        break;
      case 'settings':
        setSidebarItems([
          { id: 'software-settings', label: 'Software Settings', icon: faCog },
          { id: 'user-access-management', label: 'User Management', icon: faUsersCog }
        ]);
        break;
      default:
        setSidebarItems([]);
    }
  }, [type]);

  const handleItemClick = (itemId) => {
    if (onItemSelect) {
      onItemSelect(itemId);
    }

    // Close mobile menu after item selection on mobile
    if (isMobile) {
      setIsMobileMenuOpen(false);
    }
  };

  // Recent activity items
  const recentActivity = [
    {
      icon: faPlus,
      title: "Added new camera",
      time: "2 hours ago"
    },
    {
      icon: faBookmark,
      title: "Bookmarked camera feed",
      time: "Yesterday"
    }
  ];

  return (
    <>
      <style>{sidebarStyles}</style>

      {/* Mobile Menu Toggle Button */}
      {isMobile && (
        <button
          onClick={toggleMobileMenu}
          className="fixed top-4 left-4 z-50 bg-ravia-purple-500 text-white p-3 rounded-full shadow-ravia-glow"
        >
          <FontAwesomeIcon icon={isMobileMenuOpen ? faTimes : faBars} />
        </button>
      )}

      {/* Overlay for mobile */}
      {isMobile && isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-30"
          onClick={() => setIsMobileMenuOpen(false)}
        ></div>
      )}

      <div
        className={`sidebar-animation w-64 bg-ravia-gradient-vertical text-white shadow-ravia-glow overflow-y-auto h-screen fixed left-0 top-0 z-40 transition-transform duration-300 ease-in-out ${
          isMobile && !isMobileMenuOpen ? '-translate-x-full' : 'translate-x-0'
        }`}
      >
        {/* Logo Section */}
        <div className="p-6 flex items-center space-x-3 border-b border-ravia-purple-600">
          <div className="w-8 h-8 rounded-ravia bg-ravia-purple-500 flex items-center justify-center shadow-ravia-glow">
            <FontAwesomeIcon icon={faVideo} className="text-lg" />
          </div>
          <h1 className="text-2xl font-bold text-white">VMS</h1>
        </div>

        {/* Navigation Items */}
        <div className="p-4 space-y-2">
          {sidebarItems.map((item) => (
            <div
              key={item.id}
              className={`sidebar-item rounded-ravia p-3 flex items-center space-x-3 cursor-pointer ${
                activeItem === item.id 
                  ? 'bg-ravia-purple-500 bg-opacity-40 border-l-4 border-ravia-cyan-500' 
                  : 'hover:bg-ravia-purple-700 hover:bg-opacity-30'
              }`}
              onClick={() => handleItemClick(item.id)}
            >
              <div className="w-6 h-6 rounded-full bg-ravia-cyan-500 bg-opacity-20 flex items-center justify-center">
                <FontAwesomeIcon icon={item.icon} className="text-ravia-cyan-300 text-sm" />
              </div>
              <span className="font-medium">{item.label}</span>
              {item.notification && (
                <div className="ml-auto w-2 h-2 rounded-full bg-ravia-cyan-500 animate-pulse"></div>
              )}
            </div>
          ))}
        </div>

        {/* Divider */}
        <div className="border-t border-ravia-purple-600 mx-4 my-4"></div>

        {/* Recent Activity */}
        <div className="p-4">
          <h3 className="text-sm uppercase tracking-wider text-ravia-cyan-300 mb-3">Recent Activity</h3>
          <div className="space-y-3">
            {recentActivity.map((activity, index) => (
              <div key={index} className="flex items-start space-x-3 p-2 rounded-ravia hover:bg-ravia-purple-700 hover:bg-opacity-30 transition-colors">
                <div className="w-6 h-6 rounded-full bg-ravia-purple-500 bg-opacity-30 flex items-center justify-center mt-1">
                  <FontAwesomeIcon icon={activity.icon} className="text-xs text-ravia-cyan-300" />
                </div>
                <div>
                  <p className="text-sm">{activity.title}</p>
                  <p className="text-xs text-ravia-cyan-200">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* User Profile */}
        {currentUser && (
          <div className="mt-auto p-4 border-t border-ravia-purple-600">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-full bg-ravia-purple-500 bg-opacity-30 flex items-center justify-center">
                <FontAwesomeIcon icon={faUser} className="text-ravia-cyan-300 text-sm" />
              </div>
              <div>
                <p className="font-medium">{currentUser.username}</p>
                <p className="text-xs text-ravia-cyan-200">{currentUser.role}</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
};

export default TailwindSidebar;