import React, { useState, useEffect } from 'react';
import './EventsContent.css';
import DetectionRuleSet from './DetectionRuleSet';
import EventStatistics from './EventStatistics';
import RulesOnCamera from './RulesOnCamera';
import AppearanceSearch from './AppearanceSearch';
import VehicleData from './VehicleData';
import CurrentEvents from './CurrentEvents';
import SearchEvents from './SearchEvents';
import LiveAIAlerts from './LiveAIAlerts';
import { useUserStore } from '../../store/userStore';

function EventsContent({ selectedMenu }) {
  const [activeContent, setActiveContent] = useState('current-events');
  const currentUser = useUserStore(state => state.currentUser);

  // Check if user is SuperAdmin
  const isSuperAdmin = currentUser && currentUser.role === 'SuperAdmin';

  useEffect(() => {
    // Update active content based on selected menu
    if (selectedMenu === 'detection-rule-set') {
      if (isSuperAdmin) {
        setActiveContent('detection-rule-set');
      } else {
        setActiveContent('search-events');
      }
    } else if (selectedMenu === 'events-statistics') {
      setActiveContent('events-statistics');
    } else if (selectedMenu === 'rules-on-camera') {
      setActiveContent('rules-on-camera');
    } else if (selectedMenu === 'search-events') {
      setActiveContent('search-events');
    } else if (selectedMenu === 'current-events') {
      setActiveContent('current-events');
    } else {
      setActiveContent('current-events'); // Default to current events
    }
  }, [selectedMenu, isSuperAdmin]);

  const renderContent = () => {
    switch (activeContent) {
      case 'detection-rule-set':
        return isSuperAdmin ? <DetectionRuleSet /> : (
          <div className="unauthorized-access">
            <h3>Unauthorized Access</h3>
            <p>You do not have permission to access Detection Rule Set.</p>
          </div>
        );
      case 'events-statistics':
        return <EventStatistics />;
      case 'rules-on-camera':
        return <RulesOnCamera />;
      case 'search-events':
        return <SearchEvents />;
      case 'current-events':
        return <CurrentEvents />;
      default:
        return <CurrentEvents />;
    }
  };

  return (
    <div className="events-content">
      {renderContent()}
    </div>
  );
}

export default EventsContent;