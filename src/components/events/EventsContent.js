import React, { useEffect, useState } from 'react';
import './EventsContent.css';
import DetectionRuleSet from './DetectionRuleSet';
import EventStatistics from './EventStatistics';
import RulesOnCamera from './RulesOnCamera';
import CurrentEvents from './CurrentEvents';
import SearchEvents from './SearchEvents';
import PTZAutoTour from './PTZAutoTour';
import PTZAutoTrack from './PTZAutoTrack';
import { useUserStore } from '../../store/userStore';

function EventsContent({ selectedMenu }) {
  const [activeContent, setActiveContent] = useState('current-events');
  const currentUser = useUserStore(state => state.currentUser);
  const isSuperAdmin = currentUser && currentUser.role === 'SuperAdmin';

  useEffect(() => {
    const known = new Set([
      'detection-rule-set',
      'events-statistics',
      'rules-on-camera',
      'search-events',
      'current-events',
      'ptz-auto-tour',
      'ptz-auto-track'
    ]);

    if (selectedMenu === 'detection-rule-set' && !isSuperAdmin) {
      setActiveContent('search-events');
    } else if (known.has(selectedMenu)) {
      setActiveContent(selectedMenu);
    } else {
      setActiveContent('current-events');
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
      case 'ptz-auto-tour':
        return <PTZAutoTour />;
      case 'ptz-auto-track':
        return <PTZAutoTrack />;
      case 'search-events':
        return <SearchEvents />;
      case 'current-events':
      default:
        return <CurrentEvents />;
    }
  };

  return <div className="events-content">{renderContent()}</div>;
}

export default EventsContent;
