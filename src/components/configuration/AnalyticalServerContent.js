import React from 'react';
import AnalyticalServer from './analytics/AnalyticalServer';
import './AnalyticalServerContent.css';

const AnalyticalServerContent = ({ selectedMenu }) => {
  // Only render content when Analytics Server menu is selected
  if (selectedMenu !== 'analytics-server') {
    return null;
  }

  return (
    <div className="analytical-server-content">
      <AnalyticalServer />
    </div>
  );
};

export default AnalyticalServerContent;
