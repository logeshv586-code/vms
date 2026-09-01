import React from 'react';
import CameraSettings from './settings/CameraSettings';
import './SettingsContent.css';

const SettingsContent = ({ selectedMenu }) => {
  const renderContent = () => {
    switch (selectedMenu) {
      case 'camera-settings':
        return <CameraSettings />;
      case 'logs':
        return <div className="logs-content">Logs content will be displayed here.</div>;
      default:
        return <CameraSettings />;
    }
  };

  return (
    <div className="settings-content-container">
      {renderContent()}
    </div>
  );
};

export default SettingsContent;