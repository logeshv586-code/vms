import React, { useState, useRef, useEffect } from 'react';

/**
 * SidebarDropdownItem - A consistent dropdown item component for the sidebar
 *
 * Features:
 * - Consistent styling for dropdown items with Ravia theme
 * - Support for icons and labels
 * - Support for count badges
 * - Keyboard accessibility
 * - Tooltips for collapsed state
 * - Hover animations and effects
 */
const SidebarDropdownItem = ({
  icon,
  label,
  isActive = false,
  onClick,
  className = '',
  count,
  isSidebarExpanded = false,
  ...props
}) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const tooltipTimeoutRef = useRef(null);

  // Handle tooltip display with delay
  const handleMouseEnter = () => {
    if (!isSidebarExpanded) {
      tooltipTimeoutRef.current = setTimeout(() => {
        setShowTooltip(true);
      }, 300); // 300ms delay before showing tooltip
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
      className={`universal-sidebar-dropdown-item ${isActive ? 'active' : ''} ${className}`}
      onClick={onClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="menuitem"
      {...props}
    >
      {/* Icon */}
      {icon && (
        <div className="universal-sidebar-dropdown-icon">
          {typeof icon === 'string' ? (
            <img src={icon} alt="" />
          ) : (
            icon
          )}
        </div>
      )}

      {/* Label */}
      <div className="universal-sidebar-dropdown-label">
        {label}
      </div>

      {/* Count Badge */}
      {count !== undefined && (
        <div className="universal-sidebar-dropdown-count">
          <span className="count-badge">({count})</span>
        </div>
      )}

      {/* Tooltip - Only visible when sidebar is collapsed */}
      {!isSidebarExpanded && showTooltip && (
        <div className="sidebar-tooltip">
          {label}
          {count !== undefined && <span className="tooltip-count"> ({count})</span>}
        </div>
      )}
    </div>
  );
};

export default SidebarDropdownItem;
