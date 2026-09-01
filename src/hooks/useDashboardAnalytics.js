import { useState, useEffect, useCallback, useRef } from 'react';
import dashboardAnalyticsApi from '../services/dashboardAnalyticsApi';

/**
 * Custom hook for managing dashboard analytics data with real-time updates
 * @param {Object} options - Configuration options
 * @param {number} options.refreshInterval - Refresh interval in milliseconds (default: 30000)
 * @param {boolean} options.autoRefresh - Whether to auto-refresh data (default: true)
 * @param {boolean} options.fetchOnMount - Whether to fetch data on component mount (default: true)
 * @returns {Object} Dashboard analytics state and methods
 */
export const useDashboardAnalytics = (options = {}) => {
  const {
    refreshInterval = 30000, // 30 seconds
    autoRefresh = true,
    fetchOnMount = true
  } = options;

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  
  const intervalRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    if (!mountedRef.current) return;

    try {
      setLoading(true);
      setError(null);

      console.log('useDashboardAnalytics - Starting fetch...');
      const analyticsData = await dashboardAnalyticsApi.getDashboardAnalytics();
      console.log('useDashboardAnalytics - Fetch successful:', analyticsData);

      if (mountedRef.current) {
        console.log('useDashboardAnalytics - Setting data:', analyticsData);
        setData(analyticsData);
        setLastUpdated(new Date());
        console.log('useDashboardAnalytics - Data set successfully');
      } else {
        console.log('useDashboardAnalytics - Component unmounted, not setting data');
      }
    } catch (err) {
      console.error('useDashboardAnalytics - Fetch error:', err);
      if (mountedRef.current) {
        setError(err.message || 'Failed to fetch dashboard analytics');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  const startAutoRefresh = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
    
    if (autoRefresh && refreshInterval > 0) {
      intervalRef.current = setInterval(fetchData, refreshInterval);
    }
  }, [fetchData, autoRefresh, refreshInterval]);

  const stopAutoRefresh = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const refresh = useCallback(() => {
    fetchData();
  }, [fetchData]);

  // Initial data fetch and auto-refresh setup
  useEffect(() => {
    if (fetchOnMount) {
      fetchData();
    }
    
    if (autoRefresh) {
      startAutoRefresh();
    }

    return () => {
      stopAutoRefresh();
    };
  }, [fetchOnMount, autoRefresh, startAutoRefresh, stopAutoRefresh, fetchData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      mountedRef.current = false;
      stopAutoRefresh();
    };
  }, [stopAutoRefresh]);

  return {
    data,
    loading,
    error,
    lastUpdated,
    refresh,
    startAutoRefresh,
    stopAutoRefresh
  };
};

/**
 * Custom hook for system metrics with high-frequency updates
 * @param {number} refreshInterval - Refresh interval in milliseconds (default: 5000)
 * @returns {Object} System metrics state and methods
 */
export const useSystemMetrics = (refreshInterval = 5000) => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const intervalRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchMetrics = useCallback(async () => {
    if (!mountedRef.current) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const metricsData = await dashboardAnalyticsApi.getSystemMetrics();
      
      if (mountedRef.current) {
        setMetrics(metricsData);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'Failed to fetch system metrics');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    
    intervalRef.current = setInterval(fetchMetrics, refreshInterval);

    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchMetrics, refreshInterval]);

  return {
    metrics,
    loading,
    error,
    refresh: fetchMetrics
  };
};

/**
 * Custom hook for camera statistics
 * @param {number} refreshInterval - Refresh interval in milliseconds (default: 15000)
 * @returns {Object} Camera stats state and methods
 */
export const useCameraStats = (refreshInterval = 15000) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const intervalRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchStats = useCallback(async () => {
    if (!mountedRef.current) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const statsData = await dashboardAnalyticsApi.getCameraStats();
      
      if (mountedRef.current) {
        setStats(statsData);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'Failed to fetch camera stats');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchStats();
    
    intervalRef.current = setInterval(fetchStats, refreshInterval);

    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchStats, refreshInterval]);

  return {
    stats,
    loading,
    error,
    refresh: fetchStats
  };
};

/**
 * Custom hook for storage usage data
 * @param {number} refreshInterval - Refresh interval in milliseconds (default: 60000)
 * @returns {Object} Storage usage state and methods
 */
export const useStorageUsage = (refreshInterval = 60000) => {
  const [usage, setUsage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const intervalRef = useRef(null);
  const mountedRef = useRef(true);

  const fetchUsage = useCallback(async () => {
    if (!mountedRef.current) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const usageData = await dashboardAnalyticsApi.getStorageUsage();
      
      if (mountedRef.current) {
        setUsage(usageData);
      }
    } catch (err) {
      if (mountedRef.current) {
        setError(err.message || 'Failed to fetch storage usage');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchUsage();
    
    intervalRef.current = setInterval(fetchUsage, refreshInterval);

    return () => {
      mountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [fetchUsage, refreshInterval]);

  return {
    usage,
    loading,
    error,
    refresh: fetchUsage
  };
};
