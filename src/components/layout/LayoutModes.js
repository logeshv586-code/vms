export const LAYOUT_MODES = {
  GRID: 'grid',
  FOCUS: 'focus',
  PIP: 'pip',
  CUSTOM: 'custom'
};

export const SYMMETRICAL_LAYOUTS = [
  { id: '1x1', name: '1×1 (Single)', rows: 1, cols: 1, cameraCount: 1, type: 'grid' },
  { id: '2x2', name: '2×2 (Quad)', rows: 2, cols: 2, cameraCount: 4, type: 'grid' },
  { id: '3x3', name: '3×3 (9)', rows: 3, cols: 3, cameraCount: 9, type: 'grid' },
  { id: '4x4', name: '4×4 (16)', rows: 4, cols: 4, cameraCount: 16, type: 'grid' },
  { id: '5x5', name: '5×5 (25)', rows: 5, cols: 5, cameraCount: 25, type: 'grid' },
  { id: '6x6', name: '6×6 (36)', rows: 6, cols: 6, cameraCount: 36, type: 'grid' },
  { id: '8x8', name: '8×8 (64)', rows: 8, cols: 8, cameraCount: 64, type: 'grid' },
];

export const GRID_LAYOUTS = {
  '2x2': {
    name: '2x2 Grid',
    rows: 2,
    cols: 2,
    type: LAYOUT_MODES.GRID
  },
  '3x3': {
    name: '3x3 Grid',
    rows: 3,
    cols: 3,
    type: LAYOUT_MODES.GRID
  },
  '4x4': {
    name: '4x4 Grid',
    rows: 4,
    cols: 4,
    type: LAYOUT_MODES.GRID
  }
};

export const FOCUS_LAYOUTS = {
  '1+5': { 
    id: '1+5', 
    name: '1 + 5', 
    description: 'One main camera, five smaller ones',
    type: 'focus',
    layout: [
      { x: 0, y: 0, w: 0.5, h: 0.5 }, // Main camera (top-left)
      { x: 0.5, y: 0, w: 0.5, h: 0.33 }, // Small camera 1 (top-right)
      { x: 0.5, y: 0.33, w: 0.5, h: 0.33 }, // Small camera 2 (middle-right)
      { x: 0.5, y: 0.66, w: 0.5, h: 0.33 }, // Small camera 3 (bottom-right)
      { x: 0, y: 0.5, w: 0.5, h: 0.25 }, // Small camera 4 (bottom-left-top)
      { x: 0, y: 0.75, w: 0.5, h: 0.25 }, // Small camera 5 (bottom-left-bottom)
    ]
  },
  '1+7': { 
    id: '1+7', 
    name: '1 + 7', 
    description: 'One main camera, seven smaller ones',
    type: 'focus',
    layout: [
      { x: 0, y: 0, w: 0.5, h: 0.5 }, // Main camera (top-left)
      { x: 0.5, y: 0, w: 0.5, h: 0.25 }, // Small camera 1 (top-right-top)
      { x: 0.5, y: 0.25, w: 0.5, h: 0.25 }, // Small camera 2 (top-right-bottom)
      { x: 0.5, y: 0.5, w: 0.5, h: 0.25 }, // Small camera 3 (middle-right)
      { x: 0.5, y: 0.75, w: 0.5, h: 0.25 }, // Small camera 4 (bottom-right)
      { x: 0, y: 0.5, w: 0.25, h: 0.25 }, // Small camera 5 (bottom-left-top)
      { x: 0.25, y: 0.5, w: 0.25, h: 0.25 }, // Small camera 6 (bottom-left-middle)
      { x: 0, y: 0.75, w: 0.5, h: 0.25 }, // Small camera 7 (bottom-left-bottom)
    ]
  },
  '1+9': { 
    id: '1+9', 
    name: '1 + 9', 
    description: 'One main camera, nine smaller ones',
    type: 'focus',
    layout: [
      { x: 0, y: 0, w: 0.5, h: 0.5 }, // Main camera (top-left)
      { x: 0.5, y: 0, w: 0.25, h: 0.25 }, // Small camera 1 (top-right-top-left)
      { x: 0.75, y: 0, w: 0.25, h: 0.25 }, // Small camera 2 (top-right-top-right)
      { x: 0.5, y: 0.25, w: 0.25, h: 0.25 }, // Small camera 3 (top-right-middle-left)
      { x: 0.75, y: 0.25, w: 0.25, h: 0.25 }, // Small camera 4 (top-right-middle-right)
      { x: 0.5, y: 0.5, w: 0.25, h: 0.25 }, // Small camera 5 (top-right-bottom-left)
      { x: 0.75, y: 0.5, w: 0.25, h: 0.25 }, // Small camera 6 (top-right-bottom-right)
      { x: 0, y: 0.5, w: 0.25, h: 0.25 }, // Small camera 7 (bottom-left-top)
      { x: 0.25, y: 0.5, w: 0.25, h: 0.25 }, // Small camera 8 (bottom-left-middle)
      { x: 0, y: 0.75, w: 0.5, h: 0.25 }, // Small camera 9 (bottom-left-bottom)
    ]
  },
  '1+12+1': { 
    id: '1+12+1', 
    name: '1 + 12 + 1', 
    description: 'One main camera, twelve smaller ones, one bottom',
    type: 'focus',
    layout: [
      { x: 0, y: 0, w: 0.5, h: 0.4 }, // Main camera (top-left)
      { x: 0.5, y: 0, w: 0.25, h: 0.2 }, // Small camera 1 (top-right-top-left)
      { x: 0.75, y: 0, w: 0.25, h: 0.2 }, // Small camera 2 (top-right-top-right)
      { x: 0.5, y: 0.2, w: 0.25, h: 0.2 }, // Small camera 3 (top-right-middle-left)
      { x: 0.75, y: 0.2, w: 0.25, h: 0.2 }, // Small camera 4 (top-right-middle-right)
      { x: 0.5, y: 0.4, w: 0.25, h: 0.2 }, // Small camera 5 (top-right-bottom-left)
      { x: 0.75, y: 0.4, w: 0.25, h: 0.2 }, // Small camera 6 (top-right-bottom-right)
      { x: 0, y: 0.4, w: 0.25, h: 0.2 }, // Small camera 7 (bottom-left-top)
      { x: 0.25, y: 0.4, w: 0.25, h: 0.2 }, // Small camera 8 (bottom-left-middle)
      { x: 0, y: 0.6, w: 0.25, h: 0.2 }, // Small camera 9 (bottom-left-bottom-top)
      { x: 0.25, y: 0.6, w: 0.25, h: 0.2 }, // Small camera 10 (bottom-left-bottom-middle)
      { x: 0.5, y: 0.6, w: 0.25, h: 0.2 }, // Small camera 11 (bottom-right-top)
      { x: 0.75, y: 0.6, w: 0.25, h: 0.2 }, // Small camera 12 (bottom-right-bottom)
      { x: 0, y: 0.8, w: 1, h: 0.2 }, // Bottom camera (full width)
    ]
  },
  '1+16+1': { 
    id: '1+16+1', 
    name: '1 + 16 + 1', 
    description: 'One main camera, sixteen smaller ones, one bottom',
    type: 'focus',
    layout: [
      { x: 0, y: 0, w: 0.5, h: 0.4 }, // Main camera (top-left)
      { x: 0.5, y: 0, w: 0.25, h: 0.2 }, // Small camera 1 (top-right-top-left)
      { x: 0.75, y: 0, w: 0.25, h: 0.2 }, // Small camera 2 (top-right-top-right)
      { x: 0.5, y: 0.2, w: 0.25, h: 0.2 }, // Small camera 3 (top-right-middle-left)
      { x: 0.75, y: 0.2, w: 0.25, h: 0.2 }, // Small camera 4 (top-right-middle-right)
      { x: 0.5, y: 0.4, w: 0.25, h: 0.2 }, // Small camera 5 (top-right-bottom-left)
      { x: 0.75, y: 0.4, w: 0.25, h: 0.2 }, // Small camera 6 (top-right-bottom-right)
      { x: 0, y: 0.4, w: 0.25, h: 0.2 }, // Small camera 7 (bottom-left-top)
      { x: 0.25, y: 0.4, w: 0.25, h: 0.2 }, // Small camera 8 (bottom-left-middle)
      { x: 0, y: 0.6, w: 0.25, h: 0.2 }, // Small camera 9 (bottom-left-bottom-top)
      { x: 0.25, y: 0.6, w: 0.25, h: 0.2 }, // Small camera 10 (bottom-left-bottom-middle)
      { x: 0.5, y: 0.6, w: 0.25, h: 0.2 }, // Small camera 11 (bottom-right-top)
      { x: 0.75, y: 0.6, w: 0.25, h: 0.2 }, // Small camera 12 (bottom-right-bottom)
      { x: 0, y: 0.8, w: 0.25, h: 0.2 }, // Small camera 13 (bottom-full-top-left)
      { x: 0.25, y: 0.8, w: 0.25, h: 0.2 }, // Small camera 14 (bottom-full-top-right)
      { x: 0.5, y: 0.8, w: 0.25, h: 0.2 }, // Small camera 15 (bottom-full-bottom-left)
      { x: 0.75, y: 0.8, w: 0.25, h: 0.2 }, // Small camera 16 (bottom-full-bottom-right)
      { x: 0, y: 1, w: 1, h: 0.2 }, // Bottom camera (full width)
    ]
  }
};

export const PIP_LAYOUTS = {
  'pip-small': {
    name: 'Small PiP',
    type: LAYOUT_MODES.PIP,
    pipSize: 0.25,
    pipPosition: 'bottom-right'
  },
  'pip-large': {
    name: 'Large PiP',
    type: LAYOUT_MODES.PIP,
    pipSize: 0.4,
    pipPosition: 'bottom-right'
  }
};

export const CUSTOM_LAYOUTS = {
  '2x3': { 
    id: '2x3', 
    name: '2×3', 
    rows: 2, 
    cols: 3, 
    cameraCount: 6,
    type: 'grid'
  },
  '2x4': { 
    id: '2x4', 
    name: '2×4', 
    rows: 2, 
    cols: 4, 
    cameraCount: 8,
    type: 'grid'
  },
  '3x2': { 
    id: '3x2', 
    name: '3×2', 
    rows: 3, 
    cols: 2, 
    cameraCount: 6,
    type: 'grid'
  },
  '3x4': { 
    id: '3x4', 
    name: '3×4', 
    rows: 3, 
    cols: 4, 
    cameraCount: 12,
    type: 'grid'
  },
  '4x2': { 
    id: '4x2', 
    name: '4×2', 
    rows: 4, 
    cols: 2, 
    cameraCount: 8,
    type: 'grid'
  },
  '4x3': { 
    id: '4x3', 
    name: '4×3', 
    rows: 4, 
    cols: 3, 
    cameraCount: 12,
    type: 'grid'
  }
};

export const LAYOUT_CATEGORIES = {
  symmetrical: { title: 'Symmetrical', layouts: SYMMETRICAL_LAYOUTS },
  focus: { title: 'Single Video Focus', layouts: Object.values(FOCUS_LAYOUTS) },
  custom: { title: 'Custom', layouts: Object.values(CUSTOM_LAYOUTS) }
};

export const getLayoutConfig = (layoutId) => {
  // Check in symmetrical layouts
  const symmetricalLayout = SYMMETRICAL_LAYOUTS.find(layout => layout.id === layoutId);
  if (symmetricalLayout) return symmetricalLayout;

  // Check in focus layouts
  if (FOCUS_LAYOUTS[layoutId]) return FOCUS_LAYOUTS[layoutId];

  // Check in custom layouts
  if (CUSTOM_LAYOUTS[layoutId]) return CUSTOM_LAYOUTS[layoutId];

  // Default to 2x2 if not found
  return SYMMETRICAL_LAYOUTS[1]; // 2x2 layout
};

export const getLayoutById = (layoutId) => {
  return getLayoutConfig(layoutId);
}; 