import React, { useState, useRef, useEffect } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faChevronDown, faChevronUp } from '@fortawesome/free-solid-svg-icons';

/**
 * SidebarItem - A consistent menu item component for the sidebar
 *
 * Features:
 * - Consistent styling across all sidebar items
 * - Support for icons, labels, and notifications
 * - Support for expandable sections with chevron indicators
 * - Keyboard accessibility
 * - Tooltips for collapsed state
 */
const SidebarItem = ({
  icon,
  label,
  isActive = false,
  onClick,
  notification = false,
  count,
  isExpandable = false,
  isExpanded = false,
  children,
  isSidebarExpanded = false,
  className = '',
  ...props
}) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const tooltipTimeoutRef = useRef(null);
  const itemRef = useRef(null);

  // Handle tooltip display with delay
  const handleMouseEnter = () => {
    if (!isSidebarExpanded) {
      tooltipTimeoutRef.current = setTimeout(() => {
        setShowTooltip(true);
      }, 400); // 400ms delay before showing tooltip
    }
  };

  const handleMouseLeave = () => {
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current);
      tooltipTimeoutRef.current = null;
    }
    setShowTooltip(false);
  };

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (tooltipTimeoutRef.current) {
        clearTimeout(tooltipTimeoutRef.current);
      }
    };
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick && onClick(e);
    }
  };

  return (
    <div
      ref={itemRef}
      className={`universal-sidebar-item ${isActive ? 'active' : ''} ${className}`}
      role={isExpandable ? 'button' : 'menuitem'}
      aria-expanded={isExpandable ? isExpanded : undefined}
      aria-haspopup={isExpandable ? 'true' : undefined}
      {...props}
    >
      {/* Main item content */}
      <div
        className="universal-sidebar-item-content"
        onClick={onClick}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onKeyDown={handleKeyDown}
        tabIndex={0}
      >
        {/* Icon */}
        <div className="universal-sidebar-icon">
          {typeof icon === 'string' ? (
            <img src={icon} alt="" />
          ) : (
            icon
          )}
        </div>

        {/* Label - Only visible when sidebar is expanded */}
        <div className="universal-sidebar-label">
          {label}
        </div>

        {/* Count badge */}
        {count !== undefined && (
          <div className="universal-sidebar-count">
            {count}
          </div>
        )}

        {/* Notification indicator */}
        {notification && (
          <div className="universal-sidebar-notification" />
        )}

        {/* Chevron for expandable items */}
        {isExpandable && (
          <div className={`universal-sidebar-chevron ${isExpanded ? 'expanded' : ''}`}>
            <FontAwesomeIcon icon={isExpanded ? faChevronUp : faChevronDown} />
          </div>
        )}

        {/* Tooltip - Only visible when sidebar is collapsed */}
        {!isSidebarExpanded && showTooltip && (
          <div className="sidebar-tooltip">
            {label}
          </div>
        )}
      </div>

      {/* Children (dropdown content) - positioned below main content */}
      {isExpandable && isExpanded && children && (
        <div className="universal-sidebar-dropdown">
          {children}
        </div>
      )}
    </div>
  );
};

export default SidebarItem;
