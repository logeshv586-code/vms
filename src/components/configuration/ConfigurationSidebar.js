import React, { useState, useEffect, useRef } from 'react';
import './ConfigurationSidebar.css';
import '../sidebar/ModernSidebar.css'; // Import the new modern sidebar styles
import {
  Storage as StorageIcon,
  Videocam as CctvIcon,
  Notifications as AlertIcon,
  Map as MapIcon,
  Link as ExternalIcon,
  CloudSync as DrSitesIcon,
  Settings as TrackSettingsIcon,
  Event as EventIcon,
  Mail as MailIcon,
  Send as SenderIcon,
  VideoSettings as VideoDecoderIcon,
  Analytics as AnalyticIcon,
  Computer as MediaServerIcon,
  Folder as Storage2Icon,
  PushPin as PinIcon,
  Security as SecureAccessIcon
} from '@mui/icons-material';
import { useUserStore } from '../../store/userStore';

import addIcon from '../../icon/add-icon.png';
import AddCollectionModal from './AddCollectionModal';

const ConfigurationSidebar = ({ onViewChange, currentUser }) => {
  const hasPermission = useUserStore(state => state.hasPermission);
  const [activeItem, setActiveItem] = useState(null);
  const [expandedItems, setExpandedItems] = useState({});
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [sidebarExpanded, setSidebarExpanded] = useState(false);
  // Track the "bookmarked" submenu (last selected submenu item)
  const [bookmarkedSubmenu, setBookmarkedSubmenu] = useState(null);

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

  // Note: We don't auto-expand the bookmarked submenu's parent
  // The dropdown will close after clicking a submenu item, but the view remains active

  // Toggle sidebar expansion for mobile view
  const toggleSidebar = () => {
    setSidebarExpanded(prev => !prev);
  };

  const toggleDropdown = (itemId) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId]
    }));
  };

  const handleMenuItemClick = (itemId) => {
    const menuItem = menuItems.find(item => item.id === itemId);
    
    // For items without dropdown, change view immediately and clear bookmarked submenu
    if (!menuItem?.hasDropdown) {
      setActiveItem(itemId);
      setBookmarkedSubmenu(null); // Clear bookmarked submenu when selecting non-dropdown item
      if (itemId === 'cameras') {
        onViewChange('cameras');
      } else if (itemId === 'zone-management') {
        onViewChange('zone-management');
      } else if (itemId === 'user-access-levels') {
        onViewChange('user-access-levels');
      } else {
        onViewChange(null);
      }
      return;
    }

    // For items with dropdown, only toggle the dropdown
    // Don't change view if there's a bookmarked submenu (like dashboard behavior)
    if (menuItem.hasDropdown) {
      toggleDropdown(itemId);
      
      // If there's a bookmarked submenu, keep showing that view
      // The dropdown will toggle normally, but view won't change
      if (bookmarkedSubmenu) {
        // Don't change the view - keep the bookmarked submenu's view active
        // The dropdown toggle happens above, so it will open/close normally
        return;
      }
      
      // If no bookmarked submenu, handle special cases
      // For map, auto-open Basic Map if no bookmark
      if (itemId === 'map') {
        onViewChange('basic-map');
        setActiveItem('map-basic-map');
        // Set as bookmarked submenu
        setBookmarkedSubmenu({
          parentId: 'map',
          viewId: 'basic-map',
          activeItem: 'map-basic-map'
        });
      } else if (menuItem.dropdownItems && menuItem.dropdownItems.length === 1) {
        // If submenu has only one item, auto-select it (like dashboard behavior)
        const singleItem = menuItem.dropdownItems[0];
        const viewId = singleItem.label.toLowerCase().replace(/\s+/g, '-');
        const activeItemId = `${itemId}-${viewId}`;
        onViewChange(viewId);
        setActiveItem(activeItemId);
        // Set as bookmarked submenu
        setBookmarkedSubmenu({
          parentId: itemId,
          viewId: viewId,
          activeItem: activeItemId
        });
      } else {
        // For other dropdown items with multiple submenus, just toggle dropdown without changing view
        setActiveItem(itemId);
      }
    }
  };

  const handleDropdownItemClick = (parentId, dropdownItem) => {
    // Convert dropdown item label to a view identifier
    const viewId = dropdownItem.label.toLowerCase().replace(/\s+/g, '-');
    console.log('Dropdown item clicked:', viewId);
    
    // Set as the bookmarked submenu
    const activeItemId = `${parentId}-${viewId}`;
    setBookmarkedSubmenu({
      parentId: parentId,
      viewId: viewId,
      activeItem: activeItemId
    });
    
    // Change view and set active item
    onViewChange(viewId);
    setActiveItem(activeItemId);
    
    // Keep the dropdown open after selecting a submenu item
    // User can close it by clicking the main menu heading again
    setExpandedItems(prev => ({
      ...prev,
      [parentId]: true
    }));
  };

  // Check if user has permission to manage users
  console.log('Current user in ConfigurationSidebar:', currentUser);

  // Always allow Admin users to manage users (Supervisors)
  const canManageUsers = currentUser && (
    currentUser.role === 'SuperAdmin' ||
    currentUser.role === 'Admin'
  );

  const menuItems = [
    {
      id: 'cameras',
      label: 'Cameras',
      icon: <CctvIcon />,
      hasDropdown: false
    },
    {
      id: 'zone-management',
      label: 'Zone Management',
      icon: <VideoDecoderIcon />,
      hasDropdown: false
    },
    {
      id: 'user-access-levels',
      label: 'User Access Levels',
      icon: <SecureAccessIcon />,
      hasDropdown: false
    },
    {
      id: 'storage-server',
      label: 'Storage & Server',
      icon: <StorageIcon />,
      hasDropdown: true,
      dropdownItems: [
        { label: 'Storage', icon: <Storage2Icon /> },
        { label: 'Archive Configuration', icon: <Storage2Icon /> },
        { label: 'Media Server', icon: <MediaServerIcon /> },
        { label: 'Analytics Server', icon: <AnalyticIcon /> },
        { label: 'Video Decoder Connector', icon: <VideoDecoderIcon /> }
      ]
    },
    
    {
      id: 'alerts',
      label: 'Alerts',
      icon: <AlertIcon />,
      hasDropdown: true,
      dropdownItems: [
        { label: 'Sender Configuration', icon: <SenderIcon /> },
        { label: 'Receiver Configuration', icon: <MailIcon /> },
        { label: 'Event Distribution', icon: <EventIcon /> }
      ]
    },
    {
      id: 'map',
      label: 'Map',
      icon: <MapIcon />,
      hasDropdown: true,
      dropdownItems: [
        { label: 'Basic Map', icon: <MapIcon /> },
        { label: 'Google Map', icon: <PinIcon /> }
      ]
    },
    ...(hasPermission('drSites') ? [{
      id: 'dr-sites',
      label: 'DR Sites',
      icon: <DrSitesIcon />,
      hasDropdown: true,
      dropdownItems: [
        { label: 'Replication Policy', icon: <DrSitesIcon /> }
      ]
    }] : []),
    // {
    //   id: 'track-settings',
    //   label: 'Track Settings',
    //   icon: <TrackSettingsIcon />,
    //   hasDropdown: false
    // }
  ];

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
        aria-label="Configuration navigation"
      >
        {menuItems.map((item) => {
          // Skip the User Access Levels section if user doesn't have permission to manage users
          if (item.id === 'user-access-levels' && !canManageUsers) {
            return null;
          }

          // Check if this item or its submenu is active
          const isItemActive = activeItem === item.id || 
            (bookmarkedSubmenu && bookmarkedSubmenu.parentId === item.id);

          return (
            <div key={item.id} className="sidebar-section">
              <button
                className={`sidebar-btn ${isItemActive ? 'active' : ''}`}
                onClick={() => handleMenuItemClick(item.id)}
                aria-expanded={item.hasDropdown ? !!expandedItems[item.id] : undefined}
                aria-controls={item.hasDropdown ? `${item.id}-dropdown` : undefined}
              >
                <span className="sidebar-icon">{item.icon}</span>
                <span>{item.label}</span>
                {item.hasDropdown && (
                  <span className={`chevron-icon ${expandedItems[item.id] ? 'expanded' : ''}`}>
                    {expandedItems[item.id] ? "↑" : "↓"}
                  </span>
                )}
                {isMobile && !sidebarExpanded && (
                  <span className="sidebar-tooltip">{item.label}</span>
                )}
              </button>
            {item.hasDropdown && expandedItems[item.id] && (
              <div id={`${item.id}-dropdown`} className="sidebar-dropdown">
                {item.dropdownItems.map((dropdownItem, index) => {
                  const viewId = dropdownItem.label.toLowerCase().replace(/\s+/g, '-');
                  const dropdownItemId = `${item.id}-${viewId}`;
                  const isDropdownItemActive = activeItem === dropdownItemId || 
                    (bookmarkedSubmenu && bookmarkedSubmenu.activeItem === dropdownItemId);
                  
                  return (
                    <div
                      key={index}
                      className={`dropdown-item ${isDropdownItemActive ? 'active' : ''}`}
                      onClick={() => handleDropdownItemClick(item.id, dropdownItem)}
                      role="button"
                      tabIndex={0}
                    >
                      <span className="sidebar-icon">{dropdownItem.icon}</span>
                      <span>{dropdownItem.label}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
      </div>
    </>
  );
};

export default ConfigurationSidebar;