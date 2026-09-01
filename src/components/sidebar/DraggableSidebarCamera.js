import React, { useRef } from 'react';
import { useDrag } from 'react-dnd';
import { Videocam as StreamIcon } from '@mui/icons-material';
import './DraggableSidebarCamera.css';

/**
 * DraggableSidebarCamera - A draggable camera item for the sidebar
 * 
 * Features:
 * - Drag functionality to drop cameras into video grid cells
 * - Visual feedback during drag operations
 * - Accessibility support with ARIA labels
 * - Professional styling consistent with sidebar design
 */
const DraggableSidebarCamera = ({
  camera,
  isBookmarked = false,
  onClick,
  className = '',
  ...props
}) => {
  const ref = useRef(null);

  // Drag configuration
  const [{ isDragging }, drag] = useDrag({
    type: 'SIDEBAR_CAMERA',
    item: () => ({
      camera,
      sourceType: 'sidebar'
    }),
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
  });

  // Attach drag ref
  drag(ref);

  const handleClick = (e) => {
    e.preventDefault();
    if (onClick) {
      onClick(camera);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleClick(e);
    }
  };

  return (
    <li className="subsubmenu-item">
      <a
        ref={ref}
        href="#"
        className={`camera-link draggable-camera ${isBookmarked ? 'bookmarked' : ''} ${isDragging ? 'dragging' : ''} ${className}`}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="button"
        aria-label={`Drag ${camera.name} to video grid or click to select`}
        aria-grabbed={isDragging}
        {...props}
      >
        <div className="camera-icon">
          <StreamIcon />
        </div>
        <span className="camera-name">{camera.name}</span>
        
        {/* Drag indicator */}
        {isDragging && (
          <div className="drag-indicator">
            <span>Dragging camera...</span>
          </div>
        )}
      </a>
    </li>
  );
};

export default DraggableSidebarCamera;
