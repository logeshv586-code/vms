import React from 'react';
import StorageManager from './storage/StorageManager';
import './MediaServerContent.css';

const MediaServerContent = ({ selectedMenu }) => {
  // Only render content when Media Server menu is selected
  console.log('MediaServerContent checking selectedMenu:', selectedMenu);

  // The view ID will be generated from the dropdown item label "Media Server"
  if (selectedMenu !== 'media-server') {
    return null;
  }

  return (
    <div className="media-server-content">
      <StorageManager />
    </div>
  );
};

export default MediaServerContent;
