import React, { useState, useEffect } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  AreaChart,
  Area,
  ResponsiveContainer
} from 'recharts';
import {
  Refresh as RefreshIcon,
  Computer as SystemIcon,
  Videocam as CameraIcon,
  Storage as StorageIcon,
  Event as EventIcon,
  People as UsersIcon,
  TrendingUp as TrendingUpIcon,
  Dashboard as DashboardIcon
} from '@mui/icons-material';
import { useSystemMetrics } from '../../hooks/useDashboardAnalytics';
import ActivityFeed from './ActivityFeed';
import './DashboardAnalytics.css';

const DashboardAnalytics = ({ refreshKey }) => {
  const [selectedTimeRange, setSelectedTimeRange] = useState('today');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [loadingTimeout, setLoadingTimeout] = useState(false);

  // Simplified state management
  const [analyticsData, setAnalyticsData] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [analyticsError, setAnalyticsError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  // Direct fetch function
  const fetchAnalytics = async () => {
    try {
      console.log('Direct fetch - Starting...');
      setAnalyticsLoading(true);
      setAnalyticsError(null);

      const response = await fetch('http://localhost:8000/api/dashboard/analytics');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      console.log('Direct fetch - Success:', data);

      setAnalyticsData(data);
      setLastUpdated(new Date());
    } catch (error) {
      console.error('Direct fetch - Error:', error);
      setAnalyticsError(error.message);
    } finally {
      setAnalyticsLoading(false);
    }
  };

  // Initial fetch & respond to global header refresh
  React.useEffect(() => {
    fetchAnalytics();
  }, [refreshKey]);


  // Auto refresh
  React.useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchAnalytics, 30000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const refreshAnalytics = () => {
    fetchAnalytics();
  };

  // Debug logging
  React.useEffect(() => {
    console.log('DashboardAnalytics - Loading:', analyticsLoading);
    console.log('DashboardAnalytics - Error:', analyticsError);
    console.log('DashboardAnalytics - Data:', analyticsData);
  }, [analyticsLoading, analyticsError, analyticsData]);

  // Add timeout for loading state
  React.useEffect(() => {
    let timeoutId;
    if (analyticsLoading && !analyticsData) {
      timeoutId = setTimeout(() => {
        console.log('Loading timeout reached');
        setLoadingTimeout(true);
      }, 15000); // 15 second timeout
    } else {
      setLoadingTimeout(false);
    }

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [analyticsLoading, analyticsData]);

  const {
    metrics: systemMetrics,
    loading: metricsLoading,
    error: metricsError
  } = useSystemMetrics(5000);

  // Color schemes for charts
  const COLORS = {
    primary: '#132447',
    secondary: '#7A869A',
    success: '#4CAF50',
    warning: '#FF9800',
    error: '#F44336',
    info: '#2196F3'
  };

  const PIE_COLORS = [COLORS.primary, COLORS.secondary, COLORS.success, COLORS.warning, COLORS.error, COLORS.info];

  // Format data for charts
  const formatSystemMetricsData = () => {
    if (!systemMetrics && !displayData?.system_metrics) return [];
    const metrics = systemMetrics || displayData.system_metrics;
    return [
      { name: 'CPU', value: metrics.cpu_usage, color: COLORS.primary },
      { name: 'Memory', value: metrics.memory_usage, color: COLORS.secondary },
      { name: 'Disk', value: metrics.disk_usage, color: COLORS.warning }
    ];
  };

  const formatCameraStatusData = () => {
    if (!displayData?.camera_stats) return [];
    const { active_cameras, inactive_cameras } = displayData.camera_stats;
    return [
      { name: 'Active', value: active_cameras, color: COLORS.success },
      { name: 'Inactive', value: inactive_cameras, color: COLORS.error }
    ];
  };

  const formatRecordingTrendsData = () => {
    if (!displayData?.recording_stats) return [];
    const { recordings_today, recordings_this_week, recordings_this_month } = displayData.recording_stats;
    return [
      { name: 'Today', recordings: recordings_today },
      { name: 'This Week', recordings: recordings_this_week },
      { name: 'This Month', recordings: recordings_this_month }
    ];
  };

  const formatStorageByCamera = () => {
    if (!displayData?.recording_stats?.storage_usage_by_camera) return [];
    return Object.entries(displayData.recording_stats.storage_usage_by_camera).map(([camera, size]) => ({
      camera: camera.replace(/_/g, ' '),
      size: size
    }));
  };

  const formatUserRolesData = () => {
    if (!displayData?.user_stats?.user_roles) return [];
    return Object.entries(displayData.user_stats.user_roles).map(([role, count]) => ({
      name: role,
      value: count
    }));
  };

  const handleRefresh = () => {
    console.log('Manual refresh triggered');
    setLoadingTimeout(false);
    refreshAnalytics();
  };

  // Fallback mock data for testing
  const getMockData = () => ({
    system_metrics: {
      cpu_usage: 15.2,
      memory_usage: 68.5,
      disk_usage: 45.3,
      uptime: "2:15:30"
    },
    camera_stats: {
      total_cameras: 3,
      active_cameras: 3,
      inactive_cameras: 0,
      collections_count: 1
    },
    recording_stats: {
      total_recordings: 25,
      total_size_gb: 1.8,
      recordings_today: 5,
      recordings_this_week: 25,
      recordings_this_month: 25,
      storage_usage_by_camera: {
        "Eagle 192.168.4.242": 0.8,
        "Eagle 192.168.4.243": 0.6,
        "Eagle 192.168.4.244": 0.4
      }
    },
    event_stats: {
      total_events: 12,
      events_today: 3,
      events_this_week: 12,
      events_by_type: {
        "Motion Detection": 8,
        "Camera Tamper": 2,
        "Face Recognition": 2
      },
      recent_events: []
    },
    user_stats: {
      total_users: 2,
      active_sessions: 1,
      user_roles: {
        "SuperAdmin": 1,
        "Admin": 1
      }
    }
  });

  // Use mock data if real data is not available after timeout
  const displayData = analyticsData || (loadingTimeout ? getMockData() : null);

  const handleTimeRangeChange = (range) => {
    setSelectedTimeRange(range);
    // In a real implementation, this would filter data by time range
  };



  if (analyticsLoading && !analyticsData && !loadingTimeout) {
    return (
      <div className="dashboard-analytics-loading">
        <div className="loading-spinner"></div>
        <p>Loading dashboard analytics...</p>
        <p style={{ fontSize: '0.875rem', color: '#7A869A', marginTop: '1rem' }}>
          This may take a few moments...
        </p>
      </div>
    );
  }

  if (loadingTimeout && !analyticsData) {
    return (
      <div className="dashboard-analytics-error">
        <h3>Loading Timeout</h3>
        <p>The dashboard is taking longer than expected to load. This might be due to:</p>
        <ul style={{ textAlign: 'left', margin: '1rem 0' }}>
          <li>Backend server connection issues</li>
          <li>Network connectivity problems</li>
          <li>Server performance issues</li>
        </ul>
        <button onClick={handleRefresh} className="retry-button">
          <RefreshIcon /> Try Again
        </button>
        <p style={{ fontSize: '0.75rem', color: '#7A869A', marginTop: '1rem' }}>
          Check browser console for detailed error information
        </p>
      </div>
    );
  }

  if (analyticsError) {
    return (
      <div className="dashboard-analytics-error">
        <h3>Error Loading Analytics</h3>
        <p>{analyticsError}</p>
        <button onClick={handleRefresh} className="retry-button">
          <RefreshIcon /> Retry
        </button>
        <p style={{ fontSize: '0.75rem', color: '#7A869A', marginTop: '1rem' }}>
          Check browser console for detailed error information
        </p>
      </div>
    );
  }

  return (
    <div className="dashboard-analytics">
      {/* Header */}
      <div className="analytics-header">
        <div className="header-left">
          <DashboardIcon className="header-icon" />
          <h1>Dashboard Analytics</h1>
          {lastUpdated && (
            <span className="last-updated">
              Last updated: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
        <div className="header-controls">
          <div className="time-range-selector">
            <select 
              value={selectedTimeRange} 
              onChange={(e) => handleTimeRangeChange(e.target.value)}
              className="time-range-select"
            >
              <option value="today">Today</option>
              <option value="week">This Week</option>
              <option value="month">This Month</option>
              <option value="year">This Year</option>
            </select>
          </div>
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            Auto Refresh
          </label>
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="metrics-cards">
        <div className="metric-card">
          <div className="metric-icon">
            <CameraIcon />
          </div>
          <div className="metric-content">
            <h3>Total Cameras</h3>
            <div className="metric-value">{displayData?.camera_stats?.total_cameras || 0}</div>
            <div className="metric-subtitle">
              {displayData?.camera_stats?.active_cameras || 0} active, {displayData?.camera_stats?.inactive_cameras || 0} inactive
            </div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon">
            <StorageIcon />
          </div>
          <div className="metric-content">
            <h3>Storage Used</h3>
            <div className="metric-value">{displayData?.recording_stats?.total_size_gb?.toFixed(1) || 0} GB</div>
            <div className="metric-subtitle">
              {displayData?.recording_stats?.total_recordings || 0} recordings
            </div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon">
            <EventIcon />
          </div>
          <div className="metric-content">
            <h3>Events Today</h3>
            <div className="metric-value">{displayData?.event_stats?.events_today || 0}</div>
            <div className="metric-subtitle">
              {displayData?.event_stats?.total_events || 0} total events
            </div>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon">
            <UsersIcon />
          </div>
          <div className="metric-content">
            <h3>Active Users</h3>
            <div className="metric-value">{displayData?.user_stats?.active_sessions || 0}</div>
            <div className="metric-subtitle">
              {displayData?.user_stats?.total_users || 0} total users
            </div>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="charts-grid">
        {/* System Performance */}
        <div className="chart-card">
          <div className="chart-header">
            <SystemIcon />
            <h3>System Performance</h3>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={formatSystemMetricsData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 100]} />
                <Tooltip formatter={(value) => [`${value}%`, 'Usage']} />
                <Bar dataKey="value" fill={COLORS.primary} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Camera Status */}
        <div className="chart-card">
          <div className="chart-header">
            <CameraIcon />
            <h3>Camera Status</h3>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={formatCameraStatusData()}
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {formatCameraStatusData().map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recording Trends */}
        <div className="chart-card">
          <div className="chart-header">
            <TrendingUpIcon />
            <h3>Recording Trends</h3>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={formatRecordingTrendsData()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="recordings" stroke={COLORS.primary} fill={COLORS.primary} fillOpacity={0.6} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Storage by Camera */}
        <div className="chart-card">
          <div className="chart-header">
            <StorageIcon />
            <h3>Storage by Camera</h3>
          </div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={formatStorageByCamera()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="camera" angle={-45} textAnchor="end" height={80} />
                <YAxis />
                <Tooltip formatter={(value) => [`${value} GB`, 'Storage']} />
                <Bar dataKey="size" fill={COLORS.secondary} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Activity Feed */}
        <div className="activity-feed-container">
          <ActivityFeed data={displayData} />
        </div>
      </div>
    </div>
  );
};

export default DashboardAnalytics;
