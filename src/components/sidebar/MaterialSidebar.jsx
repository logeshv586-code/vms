import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Drawer,
  Box,
  Typography,
  useTheme,
  styled,
  ThemeProvider,
  createTheme,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Collapse
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Event as EventIcon,
  Archive as ArchiveIcon,
  Settings as SettingsIcon,
  Build as ConfigIcon,
  Menu as MenuIcon,
  ExpandLess,
  ExpandMore
} from '@mui/icons-material';
import useSidebarStore from '../../store/sidebarStore';

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
    background: {
      default: '#f8fafc', // Slate-50
      paper: '#ffffff',
    },
    text: {
      primary: '#1e293b', // Slate-800
      secondary: '#64748b', // Slate-500
    }
  },
  components: {
    MuiDrawer: {
      styleOverrides: {
        paper: {
          background: 'linear-gradient(180deg, #6366f1 0%, #8b5cf6 100%)',
          color: '#ffffff',
          borderRight: 'none',
          boxShadow: '4px 0 20px rgba(99, 102, 241, 0.15)',
        }
      }
    },
    MuiListItemIcon: {
      styleOverrides: {
        root: {
          color: '#ffffff',
          minWidth: '28px',
          '& .MuiSvgIcon-root': {
            fontSize: '1rem',
          }
        }
      }
    },
    MuiListItemText: {
      styleOverrides: {
        primary: {
          color: '#ffffff',
          fontWeight: 500,
        }
      }
    }
  }
});

const StyledDrawer = styled(Drawer)(({ theme, open }) => ({
  width: open ? 240 : 60,
  flexShrink: 0,
  whiteSpace: 'nowrap',
  boxSizing: 'border-box',
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  '& .MuiDrawer-paper': {
    width: open ? 240 : 60,
    transition: theme.transitions.create('width', {
      easing: theme.transitions.easing.sharp,
      duration: theme.transitions.duration.enteringScreen,
    }),
    overflowX: 'hidden',
    background: 'linear-gradient(180deg, #6366f1 0%, #8b5cf6 100%)',
    color: '#ffffff',
    borderRight: 'none',
    boxShadow: '4px 0 20px rgba(99, 102, 241, 0.15)',
  },
}));

const SidebarHeader = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: theme.spacing(2),
  minHeight: '64px',
  borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
}));

const LogoContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  gap: theme.spacing(1),
}));

const StyledListItem = styled(ListItem)(({ theme, active }) => ({
  margin: theme.spacing(0.5, 1),
  borderRadius: theme.spacing(1),
  transition: 'all 0.2s ease-in-out',
  cursor: 'pointer',
  backgroundColor: active ? 'rgba(255, 255, 255, 0.15)' : 'transparent',
  '&:hover': {
    backgroundColor: 'transparent',
    transform: 'translateX(4px)',
  },
  '& .MuiListItemIcon-root': {
    color: '#ffffff',
  },
  '& .MuiListItemText-primary': {
    color: '#ffffff',
    fontWeight: active ? 600 : 500,
  }
}));

const MaterialSidebar = ({ children, title = "VMS", onTabChange }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isPinned, setIsPinned] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const sidebarRef = useRef(null);
  const hoverTimeoutRef = useRef(null);
  const collapseTimeoutRef = useRef(null);

  const { sidebarState, setSidebarState } = useSidebarStore();

  // Determine if sidebar should be open
  const isOpen = isPinned || isHovered || isExpanded;

  const handleMouseEnter = useCallback(() => {
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current);
    }
    if (collapseTimeoutRef.current) {
      clearTimeout(collapseTimeoutRef.current);
    }
    setIsHovered(true);
    setIsExpanded(true);
  }, []);

  const handleMouseLeave = useCallback(() => {
    if (!isPinned) {
      setIsHovered(false);
      collapseTimeoutRef.current = setTimeout(() => {
        setIsExpanded(false);
      }, 300);
    }
  }, [isPinned]);

  const togglePin = useCallback(() => {
    setIsPinned(prev => !prev);
    if (!isPinned) {
      setIsExpanded(true);
    }
  }, [isPinned]);

  const handleLogoClick = () => {
    // Handle logo click if needed
  };

  // Navigation items
  const navigationItems = [
    { id: 'Dashboard', label: 'Dashboard', icon: <DashboardIcon />, active: title === 'VMS' },
    { id: 'Events', label: 'Events', icon: <EventIcon />, active: title === 'Events' },
    { id: 'Archive', label: 'Archive', icon: <ArchiveIcon />, active: title === 'Archive' },
    { id: 'Configuration', label: 'Configuration', icon: <ConfigIcon />, active: title === 'Configuration' },
    { id: 'Settings', label: 'Settings', icon: <SettingsIcon />, active: title === 'Settings' },
  ];

  const handleNavItemClick = (itemId) => {
    if (onTabChange) {
      onTabChange(itemId);
    }
  };

  return (
    <ThemeProvider theme={sidebarTheme}>
      <StyledDrawer
        variant="permanent"
        open={isOpen}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        ref={sidebarRef}
      >
        <SidebarHeader>
          <LogoContainer onClick={handleLogoClick}>
            <img 
              src="/assets/ESIL_LOGO.png" 
              alt="Eagle Software Logo" 
              style={{ 
                width: '32px', 
                height: '32px', 
                borderRadius: '6px',
                objectFit: 'cover'
              }} 
            />
            {isOpen && (
              <Typography variant="h6" sx={{ fontWeight: 600, color: '#ffffff' }}>
                {title}
              </Typography>
            )}
          </LogoContainer>
          {isOpen && (
            <SidebarToggleButton
              onClick={togglePin}
              ariaExpanded={isOpen}
            />
          )}
        </SidebarHeader>

        <Box sx={{ flex: 1, overflowY: 'auto', overflowX: 'hidden' }}>
          {/* Navigation Items */}
          <List sx={{ pt: 1 }}>
            {navigationItems.map((item) => (
              <Tooltip
                key={item.id}
                title={!isOpen ? item.label : ''}
                placement="right"
                arrow
              >
                <StyledListItem
                  active={item.active}
                  onClick={() => handleNavItemClick(item.id)}
                >
                  <ListItemIcon>
                    {item.icon}
                  </ListItemIcon>
                  {isOpen && <ListItemText primary={item.label} />}
                </StyledListItem>
              </Tooltip>
            ))}
          </List>

          {/* Sidebar Content - wraps the children */}
          <Box sx={{ px: 1 }}>
            {React.Children.map(children, child =>
              React.isValidElement(child)
                ? React.cloneElement(child, { isSidebarExpanded: isOpen })
                : child
            )}
          </Box>
        </Box>
      </StyledDrawer>
    </ThemeProvider>
  );
};

export default MaterialSidebar;
