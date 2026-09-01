import React from 'react';
import ReplicationPolicy from './replication/ReplicationPolicy';
import './DRSitesContent.css';

const DRSitesContent = ({ selectedMenu }) => {
  // Only render content when a DR Sites submenu is selected
  console.log('DRSitesContent checking selectedMenu:', selectedMenu);

  // Check if the selected menu is related to DR Sites
  if (selectedMenu !== 'replication-policy') {
    return null;
  }

  return (
    <div className="dr-sites-content">
      <ReplicationPolicy />
    </div>
  );
};

export default DRSitesContent;
