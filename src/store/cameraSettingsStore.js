import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useCameraSettingsStore = create(
  persist(
    (set, get) => ({
      // Camera settings state
      cameraSettings: {}, // { cameraIp: { resolution: {width, height}, onvifCredentials: {...} } }
      supportedResolutions: {}, // { cameraIp: [{width, height, label}] }
      currentResolutions: {}, // { cameraIp: {width, height} }
      connectionStatus: {}, // { cameraIp: 'connected' | 'disconnected' | 'connecting' | 'error' }
      
      // New video stream settings state
      currentStreamSettings: {}, // { cameraIp: { frameRate, maxBitrate, videoEncoding } }
      supportedStreamSettings: {}, // { cameraIp: { frameRates, maxBitrates, videoEncodings } }
      
      // Common resolution presets
      commonResolutions: [
        { width: 1920, height: 1080, label: '1080p (1920x1080)' },
        { width: 1280, height: 720, label: '720p (1280x720)' },
        { width: 800, height: 600, label: 'SVGA (800x600)' },
        { width: 640, height: 480, label: 'VGA (640x480)' },
        { width: 320, height: 240, label: 'QVGA (320x240)' },
      ],

      // Common stream settings presets (Hikvision compatible)
      commonStreamSettings: {
        frameRates: [
          { value: '1/16', label: '1/16' },
          { value: '1/8', label: '1/8' },
          { value: '1/4', label: '1/4' },
          { value: '1/2', label: '1/2' },
          { value: 1, label: '1' },
          { value: 2, label: '2' },
          { value: 4, label: '4' },
          { value: 6, label: '6' },
          { value: 8, label: '8' },
          { value: 10, label: '10' },
          { value: 12, label: '12' },
          { value: 15, label: '15' },
          { value: 16, label: '16' },
          { value: 18, label: '18' },
          { value: 20, label: '20' },
          { value: 22, label: '22' },
          { value: 25, label: '25' }
        ],
        maxBitrates: [
          { value: 256, label: '256' },
          { value: 512, label: '512' },
          { value: 1024, label: '1024' },
          { value: 2048, label: '2048' },
          { value: 3072, label: '3072' },
          { value: 4096, label: '4096' },
          { value: 5144, label: '5144' },
          { value: 8192, label: '8192' }
        ],
        videoEncodings: [
          { value: 'H.264', label: 'H.264' },
          { value: 'H.265', label: 'H.265' }
        ]
      },

      // Actions
      setCameraSettings: (cameraIp, settings) =>
        set((state) => ({
          cameraSettings: {
            ...state.cameraSettings,
            [cameraIp]: {
              ...state.cameraSettings[cameraIp],
              ...settings,
            },
          },
        })),

      setSupportedResolutions: (cameraIp, resolutions) =>
        set((state) => ({
          supportedResolutions: {
            ...state.supportedResolutions,
            [cameraIp]: resolutions,
          },
        })),

      setCurrentResolution: (cameraIp, resolution) =>
        set((state) => ({
          currentResolutions: {
            ...state.currentResolutions,
            [cameraIp]: resolution,
          },
        })),

      setConnectionStatus: (cameraIp, status) =>
        set((state) => ({
          connectionStatus: {
            ...state.connectionStatus,
            [cameraIp]: status,
          },
        })),

      // New stream settings actions
      setCurrentStreamSettings: (cameraIp, settings) =>
        set((state) => ({
          currentStreamSettings: {
            ...state.currentStreamSettings,
            [cameraIp]: settings,
          },
        })),

      setSupportedStreamSettings: (cameraIp, settings) =>
        set((state) => ({
          supportedStreamSettings: {
            ...state.supportedStreamSettings,
            [cameraIp]: settings,
          },
        })),

      // Get camera settings for a specific IP
      getCameraSettings: (cameraIp) => {
        const state = get();
        return state.cameraSettings[cameraIp] || {};
      },

      // Get supported resolutions for a camera
      getSupportedResolutions: (cameraIp) => {
        const state = get();
        return state.supportedResolutions[cameraIp] || state.commonResolutions;
      },

      // Get current resolution for a camera
      getCurrentResolution: (cameraIp) => {
        const state = get();
        return state.currentResolutions[cameraIp] || null;
      },

      // Get connection status for a camera
      getConnectionStatus: (cameraIp) => {
        const state = get();
        return state.connectionStatus[cameraIp] || 'disconnected';
      },

      // New stream settings getters
      getCurrentStreamSettings: (cameraIp) => {
        const state = get();
        return state.currentStreamSettings[cameraIp] || null;
      },

      getSupportedStreamSettings: (cameraIp) => {
        const state = get();
        return state.supportedStreamSettings[cameraIp] || state.commonStreamSettings;
      },

      // Update ONVIF credentials for a camera
      updateOnvifCredentials: (cameraIp, credentials) =>
        set((state) => ({
          cameraSettings: {
            ...state.cameraSettings,
            [cameraIp]: {
              ...state.cameraSettings[cameraIp],
              onvifCredentials: credentials,
            },
          },
        })),

      // Clear settings for a camera
      clearCameraSettings: (cameraIp) =>
        set((state) => {
          const newSettings = { ...state.cameraSettings };
          const newSupportedResolutions = { ...state.supportedResolutions };
          const newCurrentResolutions = { ...state.currentResolutions };
          const newConnectionStatus = { ...state.connectionStatus };
          const newCurrentStreamSettings = { ...state.currentStreamSettings };
          const newSupportedStreamSettings = { ...state.supportedStreamSettings };

          delete newSettings[cameraIp];
          delete newSupportedResolutions[cameraIp];
          delete newCurrentResolutions[cameraIp];
          delete newConnectionStatus[cameraIp];
          delete newCurrentStreamSettings[cameraIp];
          delete newSupportedStreamSettings[cameraIp];

          return {
            cameraSettings: newSettings,
            supportedResolutions: newSupportedResolutions,
            currentResolutions: newCurrentResolutions,
            connectionStatus: newConnectionStatus,
            currentStreamSettings: newCurrentStreamSettings,
            supportedStreamSettings: newSupportedStreamSettings,
          };
        }),

      // Reset all settings
      resetAllSettings: () =>
        set({
          cameraSettings: {},
          supportedResolutions: {},
          currentResolutions: {},
          connectionStatus: {},
          currentStreamSettings: {},
          supportedStreamSettings: {},
        }),
    }),
    {
      name: 'camera-settings-storage',
      getStorage: () => localStorage,
    }
  )
);

export default useCameraSettingsStore;
