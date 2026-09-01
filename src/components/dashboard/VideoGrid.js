import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import './VideoGrid.css';
import DraggableVideoGridCell from './DraggableVideoGridCell';
import { getLayoutConfig } from '../layout/LayoutModes';

const VideoGrid = ({ layout, cameras, cellCount, onCameraClick, onCameraSwap, onCameraAssign, activeTab }) => {
  const [gridKey, setGridKey] = useState(Date.now());

  // Force re-render of the grid when layout or activeTab changes
  useEffect(() => {
    setGridKey(Date.now());
  }, [layout, activeTab]);

  // Get grid dimensions from layout config
  const layoutConfig = getLayoutConfig(layout);
  const columns = layoutConfig?.cols || 2;
  const rows = layoutConfig?.rows || 2;

  // Handle camera swapping
  const handleSwap = (sourceIndex, targetIndex) => {
    // If no swap function is provided, don't allow swapping
    if (!onCameraSwap) {
      return;
    }

    // Validate indices
    if (sourceIndex < 0 || sourceIndex >= cellCount ||
        targetIndex < 0 || targetIndex >= cellCount ||
        sourceIndex === targetIndex) {
      return;
    }

    // Get the actual cameras at these positions
    const sourceCamera = cameras[sourceIndex] || null;
    const targetCamera = cameras[targetIndex] || null;

    // If both positions have cameras, swap them
    if (sourceCamera && targetCamera) {
      onCameraSwap(sourceIndex, targetIndex);
    }
    // If source has camera but target is empty, we could implement move logic here
    // For now, we only support swapping between two cameras
  };

  const renderCell = (camera, idx) => {
    return (
      <DraggableVideoGridCell
        key={camera ? `${camera.id}-${gridKey}` : `placeholder-${idx}-${gridKey}`}
        camera={camera}
        index={idx}
        onSwap={handleSwap}
        onCameraClick={onCameraClick}
        onCameraAssign={onCameraAssign}
        isPlaceholder={!camera}
        gridKey={gridKey}
      />
    );
  };

  const getGridClass = () => {
    switch (layout) {
      case '1x1':
        return 'layout-1x1';
      case '2x2':
        return 'symmetrical';
      case '3x3':
        return 'symmetrical';
      case '4x4':
        return 'symmetrical';
      case 'focus':
        return 'focus';
      case 'custom':
        return 'custom';
      default:
        return 'symmetrical';
    }
  };

  // Always render cellCount cells (cameras + placeholders)
  const cells = [];
  for (let i = 0; i < cellCount; i++) {
    const camera = i < cameras.length ? cameras[i] : null;
    cells.push(renderCell(camera, i));
  }

  return (
    <div
      className="video-grid-container"
      style={{ overflowX: 'auto' }}
      role="grid"
      aria-label={`Video grid with ${cameras.length} cameras in ${layout} layout`}
    >
      <div
        key={gridKey}
        className={`video-grid ${getGridClass()}`}
        style={{
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gridTemplateRows: `repeat(${rows}, 1fr)`,
          minWidth: columns * 320, // Ensures each card has a minimum width
        }}
        role="presentation"
      >
        {cells}
      </div>
    </div>
  );
};

VideoGrid.propTypes = {
  layout: PropTypes.oneOf(['1x1', '2x2', '3x3', '4x4', 'focus', 'custom']).isRequired,
  cameras: PropTypes.arrayOf(
    PropTypes.shape({
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
      streamUrl: PropTypes.string,
      ip: PropTypes.string,
    })
  ).isRequired,
  cellCount: PropTypes.number.isRequired,
  onCameraClick: PropTypes.func,
  onCameraSwap: PropTypes.func,
  onCameraAssign: PropTypes.func,
  activeTab: PropTypes.string,
};

export default VideoGrid;