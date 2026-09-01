import React, { useState, useRef, useEffect } from 'react';
import './FilterCard.css';

const FilterCard = ({
  title,
  type = 'select',
  value,
  onChange,
  options = [],
  placeholder = '',
  isActive = false,
  disabled = false,
  inputClassName = ''
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const dropdownRef = useRef(null);
  const inputRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = (event) => {
    if (type === 'select') {
      switch (event.key) {
        case 'Enter':
        case ' ':
          event.preventDefault();
          setIsOpen(!isOpen);
          break;
        case 'Escape':
          setIsOpen(false);
          break;
        case 'ArrowDown':
          event.preventDefault();
          if (!isOpen) {
            setIsOpen(true);
          }
          break;
        case 'ArrowUp':
          event.preventDefault();
          if (isOpen) {
            setIsOpen(false);
          }
          break;
        default:
          break;
      }
    }
  };

  const handleOptionSelect = (optionValue) => {
    onChange(optionValue);
    setIsOpen(false);
  };

  const handleInputChange = (event) => {
    onChange(event.target.value);
  };

  const handleInputFocus = () => {
    setIsFocused(true);
  };

  const handleInputBlur = () => {
    setIsFocused(false);
  };

  const getSelectedLabel = () => {
    if (type === 'input') return value;
    const selectedOption = options.find(option => option.value === value);
    return selectedOption ? selectedOption.label : 'Select...';
  };

  return (
    <div
      className={`filter-card ${isActive ? 'active' : ''} ${disabled ? 'disabled' : ''} ${isFocused ? 'focused' : ''} ${isOpen ? 'dropdown-open' : ''}`}
      ref={dropdownRef}
    >
      <div className="filter-card-header">
        <h3 className="filter-card-title">{title}</h3>
      </div>

      <div className="filter-card-content">
        {type === 'select' ? (
          <>
            <button
              className={`filter-select-button ${isOpen ? 'open' : ''}`}
              onClick={() => !disabled && setIsOpen(!isOpen)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              aria-expanded={isOpen}
              aria-haspopup="listbox"
              aria-label={`${title} filter`}
            >
              <span className="filter-select-value">{getSelectedLabel()}</span>
              <span className={`filter-select-arrow ${isOpen ? 'rotated' : ''}`}>
                ▼
              </span>
            </button>

            {isOpen && (
              <div
                className="filter-dropdown"
                role="listbox"
                aria-label={`${title} options`}
              >
                {options.map((option) => (
                  <button
                    key={option.value}
                    className={`filter-option ${value === option.value ? 'selected' : ''}`}
                    onClick={() => handleOptionSelect(option.value)}
                    role="option"
                    aria-selected={value === option.value}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <input
            ref={inputRef}
            type="text"
            className={`filter-input ${inputClassName}`.trim()}
            value={value}
            onChange={handleInputChange}
            onFocus={handleInputFocus}
            onBlur={handleInputBlur}
            placeholder={placeholder}
            disabled={disabled}
            aria-label={`${title} filter input`}
          />
        )}
      </div>

      {isActive && (
        <div className="filter-card-indicator" aria-hidden="true">
          <span className="indicator-dot"></span>
        </div>
      )}
    </div>
  );
};

export default FilterCard;
