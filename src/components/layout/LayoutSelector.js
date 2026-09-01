import React, { useState } from 'react';
import { SYMMETRICAL_LAYOUTS, FOCUS_LAYOUTS, CUSTOM_LAYOUTS, LAYOUT_CATEGORIES } from './LayoutModes';
import './LayoutSelector.css';

const LayoutSelector = ({ currentLayoutId, onLayoutChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('symmetrical');

  const getCurrentLayout = () => {
    // First check in SYMMETRICAL_LAYOUTS
    const symmetricalLayout = SYMMETRICAL_LAYOUTS.find(layout => layout.id === currentLayoutId);
    if (symmetricalLayout) return symmetricalLayout;

    // Then check in FOCUS_LAYOUTS
    const focusLayout = FOCUS_LAYOUTS[currentLayoutId];
    if (focusLayout) return focusLayout;

    // Finally check in CUSTOM_LAYOUTS
    const customLayout = CUSTOM_LAYOUTS[currentLayoutId];
    if (customLayout) return customLayout;

    return null;
  };

  const renderGridPreview = (layout) => {
    if (layout.type === 'focus') {
      return (
        <div className="custom-preview">
          {layout.layout.map((cell, index) => (
            <div 
              key={index} 
              className="custom-cell"
              style={{
                position: 'absolute',
                left: `${cell.x * 100}%`,
                top: `${cell.y * 100}%`,
                width: `${cell.w * 100}%`,
                height: `${cell.h * 100}%`
              }}
            />
          ))}
        </div>
      );
    }

    if (layout.type === 'custom') {
      return (
        <div className="custom-preview">
          {layout.layout.map((cell, index) => (
            <div 
              key={index} 
              className="custom-cell"
              style={{
                position: 'absolute',
                left: `${cell.x * 100}%`,
                top: `${cell.y * 100}%`,
                width: `${cell.w * 100}%`,
                height: `${cell.h * 100}%`
              }}
            />
          ))}
        </div>
      );
    }

    // Default grid layout
    return (
      <div 
        className="grid-preview"
        style={{
          display: 'grid',
          gridTemplateRows: `repeat(${layout.rows}, 1fr)`,
          gridTemplateColumns: `repeat(${layout.cols}, 1fr)`,
          gap: '2px'
        }}
      >
        {Array(layout.cameraCount || 4).fill(0).map((_, i) => (
          <div key={i} className="grid-cell" />
        ))}
      </div>
    );
  };

  return (
    <div className="layout-selector-dropdown">
      <button 
        className="layout-dropdown-trigger"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className="current-layout">
          {getCurrentLayout()?.name || 'Select Layout'}
        </span>
        <span className="dropdown-arrow">{isOpen ? '▲' : '▼'}</span>
      </button>

      {isOpen && (
        <div className="layout-dropdown-content">
          <div className="layout-categories">
            {Object.entries(LAYOUT_CATEGORIES).map(([key, { title }]) => (
              <button
                key={key}
                className={`category-button ${selectedCategory === key ? 'active' : ''}`}
                onClick={() => setSelectedCategory(key)}
              >
                {title}
              </button>
            ))}
          </div>

          <div className="layout-options">
            {LAYOUT_CATEGORIES[selectedCategory].layouts.map((layout) => (
              <button
                key={layout.id}
                className={`layout-option ${layout.id === currentLayoutId ? 'active' : ''}`}
                onClick={() => {
                  onLayoutChange(layout.id);
                  setIsOpen(false);
                }}
                title={layout.name}
              >
                <div className="layout-preview">
                  {renderGridPreview(layout)}
                </div>
                <span className="layout-name">{layout.name}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default LayoutSelector; 