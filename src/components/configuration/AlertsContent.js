import React from 'react';
import SenderConfiguration from './alerts/SenderConfiguration';
import './AlertsContent.css';

const AlertsContent = ({ selectedMenu }) => {
  // Render the appropriate alerts content based on the selected menu
  return (
    <div className="alerts-content">
      <SenderConfiguration selectedMenu={selectedMenu} />
      {/* Add other alert-related components here as needed */}
      {/* For example: ReceiverConfiguration, EventDistribution */}
    </div>
  );
};

export default AlertsContent;
