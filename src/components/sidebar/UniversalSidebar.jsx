import React, { useState, useEffect, useRef, useCallback } from 'react';
import './UniversalSidebar.css';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faThumbtack } from '@fortawesome/free-solid-svg-icons';
import {
  ThemeProvider,
  createTheme
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Event as EventIcon,
  Archive as ArchiveIcon,
  Settings as SettingsIcon,
  Build as ConfigIcon
} from '@mui/icons-material';
import { MdMenu, MdClose } from 'react-icons/md';
import useSidebarStore from '../../store/sidebarStore';
import SidebarToggleButton from './SidebarToggleButton';

// Create a custom theme with purple/violet colors like in the image
const sidebarTheme = createTheme({
  palette: {
    primary: {
      main: '#6366f1', // Indigo-500
      dark: '#4f46e5', // Indigo-600
      light: '#818cf8', // Indigo-400
    },
    secondary: {
      main: '#8b5cf6', // Violet-500
      dark: '#7c3aed', // Violet-600
      light: '#a78bfa', // Violet-400
    },
  },
  components: {
    MuiSvgIcon: {
      styleOverrides: {
        root: {
          fontSize: '1rem', // Consistent small icon size
        }
      }
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          padding: '6px', // Smaller padding for compact look
        }
      }
    }
  }
});

/**
 * UniversalSidebar - A wrapper component that adds hover-to-expand functionality to any sidebar
 *
 * Features:
 * - Hover-to-expand: Expands from 70px to 240px on hover
 * - Pin/unpin: Locks the sidebar in expanded state
 * - Keyboard accessibility: Expands when any menu item receives focus
 * - Tooltips: Shows tooltips for menu items when collapsed
 * - Responsive design: Becomes a full-screen drawer on mobile
 * - Consistent styling: Applies the same styling to all sidebars
 *
 * Animation timings:
 * - Expand animation: 220ms ease-in-out
 * - Collapse delay: 300ms
 * - Collapse animation: 220ms ease-in-out
 * - Label fade-in: 255ms
 * - Tooltip delay: 400ms
 */
const UniversalSidebar = ({ children, title = "VMS", theme = "dark" }) => {
  // Use the centralized sidebar store for expanded and pinned state
  const { isExpanded, isPinned, setExpanded, setPinned, togglePinned } = useSidebarStore();

  // Local state for UI-specific features
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [isTablet, setIsTablet] = useState(window.innerWidth > 768 && window.innerWidth <= 1024);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  const sidebarRef = useRef(null);
  const collapseTimeoutRef = useRef(null);

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      setIsMobile(width <= 768);
      setIsTablet(width > 768 && width <= 1024);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Initialize sidebar state based on stored pin state
  useEffect(() => {
    // If sidebar is pinned, ensure it's expanded
    if (isPinned) {
      setExpanded(true);
    }
  }, [isPinned, setExpanded]);

  // Handle initial load animation - remove class after animation completes
  useEffect(() => {
    if (isInitialLoad) {
      const timer = setTimeout(() => {
        setIsInitialLoad(false);
      }, 500); // Match the animation duration
      return () => clearTimeout(timer);
    }
  }, [isInitialLoad]);

  // Handle hover events for desktop
  const handleMouseEnter = useCallback(() => {
    if (!isPinned && !isMobile) {
      if (collapseTimeoutRef.current) {
        clearTimeout(collapseTimeoutRef.current);
        collapseTimeoutRef.current = null;
      }
      setExpanded(true);
    }
  }, [isPinned, isMobile, setExpanded]);

  const handleMouseLeave = useCallback(() => {
    if (!isPinned && !isMobile) {
      collapseTimeoutRef.current = setTimeout(() => {
        setExpanded(false);
      }, 300);
    }
  }, [isPinned, isMobile, setExpanded]);

  // Toggle pin state
  const togglePin = useCallback(() => {
    togglePinned();
  }, [togglePinned]);

  // Toggle mobile menu
  const toggleMobileMenu = useCallback(() => {
    if (isMobile) {
      setExpanded(!isExpanded);
    }
  }, [isMobile, isExpanded, setExpanded]);

  // Handle logo click for tablet
  const handleLogoClick = useCallback(() => {
    if (isTablet) {
      setExpanded(!isExpanded);
    }
  }, [isTablet, isExpanded, setExpanded]);



  // Handle keyboard events for accessibility
  useEffect(() => {
    const handleKeyDown = (e) => {
      // If Escape key is pressed and sidebar is expanded but not pinned, collapse it
      if (e.key === 'Escape' && isExpanded && !isPinned) {
        setExpanded(false);
        setShowSearch(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isExpanded, isPinned, setExpanded]);

  // Update main content margin and tab bar positioning
  useEffect(() => {
    const mainContent = document.querySelector('.App-main');
    const tabBar = document.querySelector('.tab-bar');

    if (isExpanded) {
      // Expanded state: 240px
      if (mainContent) {
        mainContent.style.marginLeft = '240px';
        mainContent.style.width = 'calc(100% - 240px)';
      }
      if (tabBar) {
        tabBar.style.marginLeft = '240px';
        tabBar.style.width = 'calc(100% - 240px)';
      }
    } else {
      // Collapsed state: 70px
      if (mainContent) {
        mainContent.style.marginLeft = '70px';
        mainContent.style.width = 'calc(100% - 70px)';
      }
      if (tabBar) {
        tabBar.style.marginLeft = '70px';
        tabBar.style.width = 'calc(100% - 70px)';
      }
    }

    // For mobile, no margin
    if (isMobile) {
      if (mainContent) {
        mainContent.style.marginLeft = '0';
        mainContent.style.width = '100%';
      }
      if (tabBar) {
        tabBar.style.marginLeft = '0';
        tabBar.style.width = '100%';
      }
    }

    // Also update the content-wrapper to ensure no gaps
    const contentWrapper = document.querySelector('.content-wrapper');
    if (contentWrapper) {
      contentWrapper.style.gap = '0';
    }
  }, [isExpanded, isMobile]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (collapseTimeoutRef.current) {
        clearTimeout(collapseTimeoutRef.current);
      }
    };
  }, []);

  return (
    <ThemeProvider theme={sidebarTheme}>
      {/* Mobile toggle button */}
      {isMobile && (
        <button
          className="universal-sidebar-toggle"
          onClick={toggleMobileMenu}
          aria-label={isExpanded ? "Close menu" : "Open menu"}
        >
          <span className="hamburger-icon">{isExpanded ? <MdClose /> : <MdMenu />}</span>
        </button>
      )}

      {/* Mobile overlay */}
      {isMobile && isExpanded && (
        <div
          className="universal-sidebar-overlay"
          onClick={toggleMobileMenu}
          aria-hidden="true"
        />
      )}

      {/* Main sidebar container */}
      <aside
        ref={sidebarRef}
        className={`universal-sidebar ${isExpanded ? 'expanded' : 'collapsed'} ${isPinned ? 'pinned' : ''} ${isInitialLoad ? 'initial-load' : ''} theme-${theme}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        role="navigation"
        aria-expanded={isExpanded}
      >
        {/* Sidebar header */}
        <div className="universal-sidebar-header">
          <div
            className="universal-sidebar-logo"
            onClick={handleLogoClick}
          >
            <img src="/assets/ESIL_LOGO.png" alt="Eagle Software Logo" />
          </div>
          <div className="universal-sidebar-title">
            {title}
          </div>
          <SidebarToggleButton
            onClick={togglePin}
            ariaExpanded={isExpanded}
          />
        </div>



        {/* Sidebar content - wraps the children */}
        <div className="universal-sidebar-content">
          {/* Clone children and pass isSidebarExpanded prop */}
          {React.Children.map(children, child =>
            React.isValidElement(child)
              ? React.cloneElement(child, { isSidebarExpanded: isExpanded })
              : child
          )}
        </div>
      </aside>
    </ThemeProvider>
  );
};

export default UniversalSidebar;
