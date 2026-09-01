import React, { useRef, useState, useEffect } from 'react';
import { useDrag, useDrop } from 'react-dnd';
import PropTypes from 'prop-types';
import CameraCard from '../camera/CameraCard';
import './DraggableVideoGridCell.css';

const DraggableVideoGridCell = ({
  camera,
  index,
  onSwap,
  onCameraClick,
  onCameraAssign,
  isPlaceholder = false,
  gridKey
}) => {
  const ref = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [sidebarCameraOver, setSidebarCameraOver] = useState(false);
  const [rightClickDrag, setRightClickDrag] = useState(false);

  // Drag configuration
  const [{ isDragging }, drag, preview] = useDrag({
    type: 'VIDEO_CELL',
    item: () => ({
      index,
      camera: camera || null,
      isPlaceholder
    }),
    canDrag: () => !isPlaceholder && camera, // Only allow dragging actual cameras
    collect: (monitor) => ({
      isDragging: monitor.isDragging(),
    }),
    end: () => {
      setRightClickDrag(false);
    }
  });

  // Drop configuration
  const [{ isOver, canDrop }, drop] = useDrop({
    accept: ['VIDEO_CELL', 'SIDEBAR_CAMERA'],
    drop: (item) => {
      if (item.sourceType === 'sidebar') {
        // Handle camera assignment from sidebar
        if (onCameraAssign) {
          onCameraAssign(item.camera, index);
        }
      } else if (item.index !== index && onSwap) {
        // Handle video cell swapping
        onSwap(item.index, index);
      }
      setIsDragOver(false);
      setSidebarCameraOver(false);
    },
    hover: (item, monitor) => {
      if (item.sourceType === 'sidebar') {
        setSidebarCameraOver(true);
        setIsDragOver(false);
      } else {
        setIsDragOver(true);
        setSidebarCameraOver(false);
      }
    },
    collect: (monitor) => ({
      isOver: monitor.isOver(),
      canDrop: monitor.canDrop(),
    }),
  });

  // Combine drag and drop refs
  drag(drop(ref));

  // Handle right-click drag initiation
  const handleMouseDown = (e) => {
    if (e.button === 2) { // Right mouse button
      setRightClickDrag(true);
      e.preventDefault();
    }
  };

  const handleContextMenu = (e) => {
    if (rightClickDrag) {
      e.preventDefault(); // Prevent context menu when right-click dragging
    }
  };

  // Keyboard accessibility
  const handleKeyDown = (e) => {
    if (!camera || isPlaceholder) return;

    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        if (index > 0 && onSwap) {
          onSwap(index, index - 1);
        }
        break;
      case 'ArrowRight':
        e.preventDefault();
        if (onSwap) {
          onSwap(index, index + 1);
        }
        break;
      case 'ArrowUp':
        e.preventDefault();
        // Move up one row (assuming grid layout)
        if (index >= 2 && onSwap) { // Assuming 2 columns for simplicity
          onSwap(index, index - 2);
        }
        break;
      case 'ArrowDown':
        e.preventDefault();
        // Move down one row
        if (onSwap) {
          onSwap(index, index + 2);
        }
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (onCameraClick && camera) {
          onCameraClick(camera);
        }
        break;
      default:
        break;
    }
  };

  // Placeholder cell rendering
  if (isPlaceholder) {
    return (
      <div
        ref={ref}
        className={`video-cell placeholder-cell ${isDragOver && canDrop ? 'drag-over' : ''}`}
        role="gridcell"
        aria-label={`Empty camera slot ${index + 1}`}
      >
        <div className="no-cameras">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth="1.5" style={{opacity: 0.5}}>
            <path d="M10.5 15.5L3 8.5"></path>
            <path d="M21 8.5L16.5 13"></path>
            <rect x="3" y="3" width="18" height="12" rx="2"></rect>
            <path d="M7 15v2"></path>
            <path d="M17 15v2"></path>
            <path d="M7 19h10"></path>
          </svg>
          <p>No Camera Feed Available</p>
        </div>
      </div>
    );
  }

  // Camera cell rendering
  return (
    <div
      ref={ref}
      className={`video-cell draggable-cell ${isDragging ? 'dragging' : ''} ${isDragOver && canDrop ? 'drag-over' : ''} ${sidebarCameraOver && canDrop ? 'sidebar-camera-over' : ''}`}
      onMouseDown={handleMouseDown}
      onContextMenu={handleContextMenu}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      role="gridcell"
      aria-label={`${camera ? `Camera ${camera.name}` : 'Empty cell'}, position ${index + 1}. ${camera ? 'Use arrow keys to move, Enter to select.' : 'Drop a camera here or use arrow keys to navigate.'}`}
      aria-grabbed={isDragging}
      aria-dropeffect={canDrop ? 'move' : 'none'}
    >
      <CameraCard
        camera={camera}
        onCameraClick={onCameraClick}
      />

      {/* Drag indicator */}
      {isDragging && (
        <div className="drag-indicator">
          <span>Moving camera...</span>
        </div>
      )}

      {/* Drop indicator */}
      {isDragOver && canDrop && !isDragging && (
        <div className="drop-indicator">
          <span>Drop here to swap</span>
        </div>
      )}
    </div>
  );
};

DraggableVideoGridCell.propTypes = {
  camera: PropTypes.shape({
    id: PropTypes.string.isRequired,
    name: PropTypes.string.isRequired,
    streamUrl: PropTypes.string,
    ip: PropTypes.string,
  }),
  index: PropTypes.number.isRequired,
  onSwap: PropTypes.func.isRequired,
  onCameraClick: PropTypes.func,
  isPlaceholder: PropTypes.bool,
  gridKey: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
};

export default DraggableVideoGridCell;
