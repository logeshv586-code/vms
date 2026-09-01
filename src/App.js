// React must be in scope when using JSX
import React, { useState, useEffect } from 'react';
import { DndProvider } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';
import Dashboard from './components/dashboard/Dashboard';
import PerformanceMetrics from './components/events/PerformanceMetrics';
import MainSidebar from './components/sidebar/MainSidebar';
import EventsSidebar from './components/events/EventsSidebar';
import ArchiveSidebar from './components/archive/ArchiveSidebar';
import ConfigurationSidebar from './components/configuration/ConfigurationSidebar';
import SettingsSidebar from './components/settings/SettingsSidebar';
import UniversalSidebar from './components/sidebar/UniversalSidebar';
import EventsContent from './components/events/EventsContent';
import AIDetectionTab from './components/events/AIDetectionTab';
import AIDetectionSidebar from './components/events/AIDetectionSidebar';
import FixedArchivePlayback from './components/archive/FixedArchivePlayback';
import CurrentRecordings from './components/archive/CurrentRecordings';
import ExtractedVideosContent from './components/archive/ExtractedVideosContent';
import RecordingReport from './components/archive/RecordingReport';
import CriticalVideo from './components/archive/CriticalVideo';
import RedundantPlayback from './components/archive/RedundantPlayback';
import SettingsContent from './components/settings/SettingsContent';
import { CameraProvider } from './components/camera/CameraManager';
import CamerasContent from './components/configuration/CamerasContent';
import MediaServerContent from './components/configuration/MediaServerContent';
import AnalyticalServerContent from './components/configuration/AnalyticalServerContent';
import VideoDecoderContent from './components/configuration/VideoDecoderContent';
import DRSitesContent from './components/configuration/DRSitesContent';
import AlertsContent from './components/configuration/AlertsContent';
import UserAccessManagement from './components/users/UserAccessManagement';
import ZoneManagement from './components/configuration/ZoneManagement';
import MapConfigContent from './components/configuration/MapConfigContent';
import IllustratedLogin from './components/auth/IllustratedLogin';
import { useCameraStore } from './store/cameraStore';
import { useUserStore } from './store/userStore';
import ArchiveConfiguration from './components/configuration/ArchiveConfiguration';

function TabBar({ activeTab, onTabChange, onLogout, currentUser, onRefresh, isRefreshing }) {
  // Keep Archive tab for on-demand recordings
  const tabs = ['Dashboard', 'AI Detection', 'Events', 'Archive', 'Configuration', 'Settings'];

  return (
    <div className="tab-bar">
      <div className="tabs-container">
        {tabs.map((tab) => (
          <button
            key={tab}
            className={`tab-button ${activeTab === tab ? 'active' : ''}`}
            onClick={() => onTabChange(tab)}
          >
            {tab}
          </button>
        ))}
      </div>
      <div className="right-controls">
        <button 
          className={`refresh-button ${isRefreshing ? 'refreshing' : ''}`} 
          onClick={onRefresh}
          title="Refresh current page data"
          disabled={isRefreshing}
        >
          <span className={`refresh-icon ${isRefreshing ? 'spinning' : ''}`}>↻</span>
          <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
        </button>
        <div className="user-controls">
          {currentUser && (
            <div className="user-info">
              <span className="username">{currentUser.username}</span>
              <span className="role-badge">{currentUser.role}</span>
              <button className="logout-button" onClick={onLogout}>
                Logout
              </button>
            </div>
          )}
        </div>
        <PerformanceMetrics />
      </div>
    </div>
  );
}

function TabContent({ activeTab, currentView, onViewChange, showCollectionManager, setShowCollectionManager, settingsMenu, selectedRecordingId, selectedRecordingProp, eventsMenu, onSelectRecording, refreshKey }) {
  console.log('TabContent rendering with activeTab:', activeTab, 'currentView:', currentView, 'refreshKey:', refreshKey);
  switch (activeTab) {
    case 'Configuration':
      return (
        <div className="configuration-content" key={`config-${refreshKey}`}>
          {currentView === 'cameras' ? <CamerasContent selectedMenu={currentView} refreshKey={refreshKey} /> : null}
          {currentView === 'zone-management' ? <ZoneManagement refreshKey={refreshKey} /> : null}
          {currentView === 'archive-configuration' ? <ArchiveConfiguration selectedMenu={currentView} refreshKey={refreshKey} /> : null}
          {currentView === 'media-server' ? <MediaServerContent selectedMenu={currentView} refreshKey={refreshKey} /> : null}
          {currentView === 'analytics-server' ? <AnalyticalServerContent selectedMenu={currentView} refreshKey={refreshKey} /> : null}
          {currentView === 'video-decoder-connector' ? <VideoDecoderContent selectedMenu={currentView} refreshKey={refreshKey} /> : null}
          {currentView === 'user-access-levels' ? <UserAccessManagement refreshKey={refreshKey} /> : null}
          {currentView === 'replication-policy' ? <DRSitesContent selectedMenu={currentView} refreshKey={refreshKey} /> : null}
          {currentView === 'sender-configuration' ? <AlertsContent selectedMenu={currentView} refreshKey={refreshKey} /> : null}
          {currentView === 'basic-map' || currentView === 'google-map' ? <MapConfigContent selectedMenu={currentView} refreshKey={refreshKey} /> : null}
        </div>
      );
    case 'Dashboard':
      return (
        <div className="dashboard-content" key={`dash-${refreshKey}`}>
          <Dashboard
            currentView={currentView}
            onViewChange={onViewChange}
            showCollectionManager={showCollectionManager}
            setShowCollectionManager={setShowCollectionManager}
            activeTab={activeTab}
            refreshKey={refreshKey}
          />
        </div>
      );
    case 'Events':
      return (
        <div className="events-content" key={`events-${refreshKey}`}>
          <EventsContent selectedMenu={eventsMenu} refreshKey={refreshKey} />
        </div>
      );
    case 'AI Detection':
      return (
        <div className="ai-detection-content" key={`ai-${refreshKey}`}>
          <AIDetectionTab refreshKey={refreshKey} />
        </div>
      );
    case 'Archive':
      return (
        <div className="archive-content" key={`archive-${refreshKey}`}>
          {currentView === 'current-recordings' && (
            <CurrentRecordings
              refreshKey={refreshKey}
              onViewRecording={(recording) => {
                if (onSelectRecording) {
                  onSelectRecording(recording);
                }
                onViewChange('archive-playback');
              }}
            />
          )}
          {(currentView === 'archive-playback' || (!currentView && activeTab === 'Archive') || currentView === 'camera') && (
            <FixedArchivePlayback
              refreshKey={refreshKey}
              selectedRecordingId={selectedRecordingId}
              selectedRecordingProp={selectedRecordingProp}
              onSelectRecording={onSelectRecording}
              onViewChange={onViewChange}
            />
          )}
          {currentView === 'extracted-videos' && (
            <ExtractedVideosContent refreshKey={refreshKey} />
          )}
          {currentView === 'recording-report' && (
            <RecordingReport refreshKey={refreshKey} />
          )}
          {currentView === 'critical-video' && (
            <CriticalVideo refreshKey={refreshKey} />
          )}
          {currentView === 'redundant-playback' && (
            <RedundantPlayback refreshKey={refreshKey} />
          )}
        </div>
      );
    case 'Settings':
      return (
        <div className="settings-content" key={`settings-${refreshKey}`}>
          <SettingsContent selectedMenu={settingsMenu} refreshKey={refreshKey} />
        </div>
      );
    default:
      return null;
  }
}


function App() {
  const [activeTab, setActiveTab] = useState('Dashboard');
  const [currentView, setCurrentView] = useState('dashboard-analytics');
  const [showCollectionManager, setShowCollectionManager] = useState(false);
  const [settingsMenu, setSettingsMenu] = useState('software-settings');
  const [selectedRecordingId, setSelectedRecordingId] = useState(null);
  const [selectedRecordingProp, setSelectedRecordingProp] = useState(null);
  const [eventsMenu, setEventsMenu] = useState('search-events');
  const [refreshKey, setRefreshKey] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const { loadCameraConfig } = useCameraStore();
  const { isAuthenticated, currentUser, logout, checkSession } = useUserStore();

  // Verify session with backend on mount and periodically to detect backend restarts
  useEffect(() => {
    if (isAuthenticated) {
      checkSession();
      // Periodically check if backend was restarted
      const interval = setInterval(() => {
        checkSession();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, checkSession]);

  // Log authentication state changes
  useEffect(() => {
    console.log("Authentication state:", { isAuthenticated, currentUser });
  }, [isAuthenticated, currentUser]);

  useEffect(() => {
    // Load camera configuration from backend API when app starts
    console.log('Loading camera configuration from backend API');
    loadCameraConfig();
  }, [loadCameraConfig]);

  const handleRefresh = async () => {
    console.log('User triggered manual page data refresh');
    setIsRefreshing(true);
    try {
      if (checkSession) await checkSession();
      if (loadCameraConfig) await loadCameraConfig();
      // Increment refresh key to trigger re-fetch in all active components
      setRefreshKey(prev => prev + 1);
    } catch (err) {
      console.error('Error during refresh:', err);
    } finally {
      setTimeout(() => {
        setIsRefreshing(false);
      }, 600);
    }
  };

  const handleViewChange = (newView) => {
    console.log('Changing view to:', newView);
    setCurrentView(newView);
    // If changing to camera view, don't automatically show collection manager
    if (newView !== 'camera') {
      setShowCollectionManager(false);
    }
    // Clear selected recording when navigating via sidebar
    setSelectedRecordingId(null);
    setSelectedRecordingProp(null);
  };

  const handleTabChange = (newTab) => {
    console.log('Changing tab to:', newTab);
    setActiveTab(newTab);
    // When switching to Dashboard tab, always show dashboard analytics
    if (newTab === 'Dashboard') {
      setCurrentView('dashboard-analytics');
    } else if (newTab === 'Configuration') {
      // Default Configuration tab to Cameras view
      setCurrentView('cameras');
    } else if (newTab === 'Archive') {
      // Default Archive tab to Current Recordings view
      setCurrentView('current-recordings');
    }
  };

  const handleSettingsMenuSelect = (menuId) => {
    setSettingsMenu(menuId);
  };

  const handleEventsMenuSelect = (menuId) => {
    setEventsMenu(menuId);
  };

  const handleLoginSuccess = () => {
    // Set default tab after login
    setActiveTab('Dashboard');
    setCurrentView('dashboard-analytics');
  };

  // If not authenticated, show login screen
  if (!isAuthenticated) {
    return <IllustratedLogin onLoginSuccess={handleLoginSuccess} />;
  }

  return (
    <Router>
      <Routes>
        <Route path="*" element={
          <DndProvider backend={HTML5Backend}>
            <CameraProvider>
              <div className="App">
                <TabBar
                  activeTab={activeTab}
                  onTabChange={handleTabChange}
                  onLogout={logout}
                  currentUser={currentUser}
                  onRefresh={handleRefresh}
                  isRefreshing={isRefreshing}
                />
                <div className="content-wrapper">
                  {/* Single persistent sidebar that changes content based on active tab */}
                  <UniversalSidebar
                    title={
                      activeTab === 'Dashboard' ? 'VMS' :
                      activeTab === 'AI Detection' ? 'AI Lab' :
                      activeTab === 'Events' ? 'Events' :
                      activeTab === 'Archive' ? 'Archive' :
                      activeTab === 'Configuration' ? 'Configuration' :
                      activeTab === 'Settings' ? 'Settings' : 'VMS'
                    }
                  >
                    {activeTab === 'Dashboard' && (
                      <MainSidebar
                        onViewChange={handleViewChange}
                      />
                    )}
                    {activeTab === 'AI Detection' && (
                      <AIDetectionSidebar />
                    )}
                    {activeTab === 'Events' && (
                      <EventsSidebar onMenuSelect={handleEventsMenuSelect} />
                    )}
                    {activeTab === 'Archive' && (
                      <ArchiveSidebar 
                        onMenuSelect={handleViewChange} 
                        currentView={currentView}
                      />
                    )}
                    {activeTab === 'Configuration' && (
                      <ConfigurationSidebar
                        onViewChange={handleViewChange}
                        currentUser={currentUser}
                      />
                    )}
                    {activeTab === 'Settings' && (
                      <SettingsSidebar onMenuSelect={handleSettingsMenuSelect} />
                    )}
                  </UniversalSidebar>
                  <main className="App-main">
                    <TabContent
                      activeTab={activeTab}
                      currentView={currentView}
                      onViewChange={handleViewChange}
                      showCollectionManager={showCollectionManager}
                      setShowCollectionManager={setShowCollectionManager}
                      settingsMenu={settingsMenu}
                      selectedRecordingId={selectedRecordingId}
                      selectedRecordingProp={selectedRecordingProp}
                      eventsMenu={eventsMenu}
                      refreshKey={refreshKey}
                      onSelectRecording={(rec) => {
                        if (rec === null) {
                          setSelectedRecordingId(null);
                          setSelectedRecordingProp(null);
                        } else if (typeof rec === 'object') {
                          setSelectedRecordingId(rec.filename);
                          setSelectedRecordingProp(rec);
                        } else {
                          setSelectedRecordingId(rec);
                          setSelectedRecordingProp(null);
                        }
                      }}
                    />
                  </main>
                </div>
              </div>
            </CameraProvider>
          </DndProvider>
        } />
      </Routes>
    </Router>
  );
}


export default App;