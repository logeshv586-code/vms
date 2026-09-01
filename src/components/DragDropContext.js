import React, { createContext, useContext, useState } from 'react';

const DragDropContext = createContext();

export function DragDropProvider({ children }) {
  const [draggedItem, setDraggedItem] = useState(null);

  const handleDragStart = (e, item) => {
    e.dataTransfer.setData('text/plain', ''); // Required for Firefox
    setDraggedItem(item);
  };

  const handleDragOver = (e) => {
    e.preventDefault(); // Necessary to allow dropping
  };

  const handleDrop = (e, targetId) => {
    e.preventDefault();
    if (draggedItem) {
      // Handle the drop logic here
      setDraggedItem(null);
    }
  };

  return (
    <DragDropContext.Provider value={{ handleDragStart, handleDragOver, handleDrop, draggedItem }}>
      {children}
    </DragDropContext.Provider>
  );
}

export function useDragDrop() {
  const context = useContext(DragDropContext);
  if (!context) {
    throw new Error('useDragDrop must be used within a DragDropProvider');
  }
  return context;
}