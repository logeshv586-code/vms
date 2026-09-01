import React, { useState, useEffect } from 'react';
import {
  Videocam as CameraIcon,
  Storage as RecordingIcon,
  Event as EventIcon,
  Person as UserIcon,
  AccessTime as TimeIcon
} from '@mui/icons-material';
import './ActivityFeed.css';

const ActivityFeed = ({ data }) => {
  const [activities, setActivities] = useState([]);

  useEffect(() => {
    if (data) {
      generateActivities(data);
    }
  }, [data]);

  const generateActivities = (analyticsData) => {
    const newActivities = [];
    const now = new Date();

    // Generate mock activities based on real data
    if (analyticsData.recording_stats?.recordings_today > 0) {
      newActivities.push({
        id: 1,
        type: 'recording',
        icon: <RecordingIcon />,
        title: 'New Recordings',
        description: `${analyticsData.recording_stats.recordings_today} recordings created today`,
        timestamp: new Date(now - Math.random() * 3600000), // Random time within last hour
        color: '#4CAF50'
      });
    }

    if (analyticsData.camera_stats?.active_cameras > 0) {
      newActivities.push({
        id: 2,
        type: 'camera',
        icon: <CameraIcon />,
        title: 'Camera Status',
        description: `${analyticsData.camera_stats.active_cameras} cameras are currently active`,
        timestamp: new Date(now - Math.random() * 1800000), // Random time within last 30 minutes
        color: '#2196F3'
      });
    }

    if (analyticsData.event_stats?.events_today > 0) {
      newActivities.push({
        id: 3,
        type: 'event',
        icon: <EventIcon />,
        title: 'Events Detected',
        description: `${analyticsData.event_stats.events_today} events detected today`,
        timestamp: new Date(now - Math.random() * 7200000), // Random time within last 2 hours
        color: '#FF9800'
      });
    }

    if (analyticsData.user_stats?.active_sessions > 0) {
      newActivities.push({
        id: 4,
        type: 'user',
        icon: <UserIcon />,
        title: 'User Activity',
        description: `${analyticsData.user_stats.active_sessions} active user sessions`,
        timestamp: new Date(now - Math.random() * 900000), // Random time within last 15 minutes
        color: '#9C27B0'
      });
    }

    // Sort by timestamp (newest first)
    newActivities.sort((a, b) => b.timestamp - a.timestamp);
    setActivities(newActivities);
  };

  const formatTimestamp = (timestamp) => {
    const now = new Date();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);

    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return timestamp.toLocaleDateString();
  };

  if (!data || activities.length === 0) {
    return (
      <div className="activity-feed">
        <div className="activity-header">
          <TimeIcon />
          <h3>Recent Activity</h3>
        </div>
        <div className="no-activity">
          <p>No recent activity to display</p>
        </div>
      </div>
    );
  }

  return (
    <div className="activity-feed">
      <div className="activity-header">
        <TimeIcon />
        <h3>Recent Activity</h3>
      </div>
      <div className="activity-list">
        {activities.map((activity) => (
          <div key={activity.id} className="activity-item">
            <div 
              className="activity-icon" 
              style={{ backgroundColor: activity.color }}
            >
              {activity.icon}
            </div>
            <div className="activity-content">
              <div className="activity-title">{activity.title}</div>
              <div className="activity-description">{activity.description}</div>
              <div className="activity-timestamp">
                {formatTimestamp(activity.timestamp)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ActivityFeed;
