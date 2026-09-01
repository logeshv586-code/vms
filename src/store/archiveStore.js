import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import archiveApi from '../services/archiveApi';

const STORAGE_KEY = 'vms_archive';

export const useArchiveStore = create(
  persist(
    (set, get) => ({
      // State
      recordings: [],
      availableStreams: [],
      selectedStreamId: null,
      selectedRecording: null,
      isLoading: false,
      error: null,
      archiveStatus: null,
      recordingStatus: {}, // { streamId: { isRecording: boolean, lastUpdate: timestamp } }
      statusPollingInterval: null,
      
      // Filters
      filters: {
        dateRange: 'today',
        streamId: 'all',
        sortBy: 'newest'
      },

      // Actions
      setLoading: (loading) => set({ isLoading: loading }),
      
      setError: (error) => set({ error }),
      
      clearError: () => set({ error: null }),

      setFilters: (newFilters) => set((state) => ({
        filters: { ...state.filters, ...newFilters }
      })),

      setSelectedStreamId: (streamId) => set({ selectedStreamId: streamId }),

      setSelectedRecording: (recording) => set({ selectedRecording: recording }),

      /**
       * Load recordings for a specific stream
       */
      loadRecordings: async (streamId) => {
        if (!streamId) {
          // If no streamId provided, load all recordings
          return get().loadAllRecordings();
        }

        set({ isLoading: true, error: null });

        try {
          const response = await archiveApi.getRecordings(streamId);
          set({
            recordings: response.recordings || [],
            selectedStreamId: streamId,
            isLoading: false
          });
        } catch (error) {
          console.error('Error loading recordings:', error);
          set({
            recordings: [],
            error: error.message || 'Failed to load recordings',
            isLoading: false
          });
        }
      },

      /**
       * Load all recordings from all streams
       */
      loadAllRecordings: async (forceRefresh = false) => {
        set({ isLoading: true, error: null });

        try {
          const response = await archiveApi.getAllRecordings(forceRefresh);
          set({
            recordings: response.recordings || [],
            selectedStreamId: null, // Clear specific stream selection
            isLoading: false
          });
        } catch (error) {
          console.error('Error loading all recordings:', error);
          set({
            recordings: [],
            error: error.message || 'Failed to load recordings',
            isLoading: false
          });
        }
      },

      /**
       * Load recordings for a camera by collection and IP
       */
      loadRecordingsForCamera: async (collectionName, cameraIp) => {
        if (!collectionName || !cameraIp) {
          set({ error: 'Collection name and camera IP are required' });
          return;
        }

        const streamId = `${collectionName}_${cameraIp}`;
        return get().loadRecordings(streamId);
      },

      /**
       * Load recordings filtered by date range
       */
      loadRecordingsByDateRange: async (streamId, startDate, endDate) => {
        if (!streamId || !startDate || !endDate) {
          set({ error: 'Stream ID and date range are required' });
          return;
        }

        set({ isLoading: true, error: null });

        try {
          const response = await archiveApi.getRecordingsByDateRange(streamId, startDate, endDate);
          set({
            recordings: response.recordings || [],
            selectedStreamId: streamId,
            isLoading: false
          });
        } catch (error) {
          console.error('Error loading recordings by date range:', error);
          set({
            recordings: [],
            error: error.message || 'Failed to load recordings',
            isLoading: false
          });
        }
      },

      /**
       * Load all available streams that have recordings
       */
      loadAvailableStreams: async () => {
        set({ isLoading: true, error: null });

        try {
          const response = await archiveApi.getAvailableStreams();
          set({
            availableStreams: response.streams || [],
            isLoading: false
          });

          // Also load all recordings to populate the recordings list
          try {
            const allRecordingsResponse = await archiveApi.getAllRecordings();
            set({
              recordings: allRecordingsResponse.recordings || []
            });
            console.log(`Loaded ${allRecordingsResponse.recordings?.length || 0} recordings from all streams`);
          } catch (recordingsError) {
            console.warn('Failed to load all recordings:', recordingsError);
            // Don't set error state for this, as streams loaded successfully
          }
        } catch (error) {
          console.error('Error loading available streams:', error);

          // If backend is not available, still try to show some information
          // This allows the UI to show that recordings might exist even if backend is down
          set({
            availableStreams: [],
            error: 'Archive backend is not available. Recordings may exist but cannot be accessed.',
            isLoading: false
          });
        }
      },

      /**
       * Initialize recording status for all configured cameras
       */
      initializeRecordingStatus: async () => {
        try {
          // Get camera configuration to initialize status for all cameras
          const response = await fetch('http://localhost:8000/cameras');
          if (response.ok) {
            const cameraData = await response.json();
            const currentTime = Date.now();
            const newRecordingStatus = {};

            // Initialize status for all configured cameras
            if (cameraData.cameras) {
              Object.entries(cameraData.cameras).forEach(([collectionName, cameras]) => {
                Object.keys(cameras).forEach(cameraIp => {
                  const streamId = `${collectionName}_${cameraIp}`;
                  newRecordingStatus[streamId] = {
                    isRecording: false,
                    lastUpdate: currentTime,
                    processActive: false,
                    status: 'unknown'
                  };
                });
              });
            }

            // Merge with existing status
            const currentStatus = get().recordingStatus;
            const mergedStatus = { ...newRecordingStatus, ...currentStatus };
            set({ recordingStatus: mergedStatus });

            console.log(`Initialized recording status for ${Object.keys(newRecordingStatus).length} cameras`);
          }
        } catch (error) {
          console.error('Error initializing recording status:', error);
        }
      },

      /**
       * Load archive system status and update recording status
       */
      loadArchiveStatus: async () => {
        try {
          const status = await archiveApi.getArchiveStatus();
          set({ archiveStatus: status });

          // Update recording status based on active recordings
          if (status && status.stream_ids) {
            const currentTime = Date.now();
            const currentStatus = get().recordingStatus;
            const newRecordingStatus = { ...currentStatus };

            // Mark active streams as recording
            status.stream_ids.forEach(streamId => {
              newRecordingStatus[streamId] = {
                isRecording: true,
                lastUpdate: currentTime,
                processActive: true
              };
            });

            // Mark inactive streams as stopped (only if we already know about them)
            Object.keys(currentStatus).forEach(streamId => {
              if (!status.stream_ids.includes(streamId)) {
                newRecordingStatus[streamId] = {
                  ...currentStatus[streamId],
                  isRecording: false,
                  lastUpdate: currentTime,
                  processActive: false
                };
              }
            });

            set({ recordingStatus: newRecordingStatus });
            console.log(`Archive status updated: ${status.stream_ids.length} active recordings`);
          } else {
            // If no active recordings, mark all known streams as stopped
            const currentStatus = get().recordingStatus;
            const currentTime = Date.now();
            const newRecordingStatus = {};

            Object.keys(currentStatus).forEach(streamId => {
              newRecordingStatus[streamId] = {
                ...currentStatus[streamId],
                isRecording: false,
                lastUpdate: currentTime,
                processActive: false
              };
            });

            set({ recordingStatus: newRecordingStatus });
            console.log('Archive status updated: No active recordings');
          }
        } catch (error) {
          console.error('Error loading archive status:', error);

          // If backend is not available, mark all streams as backend unavailable
          const currentStatus = get().recordingStatus;
          const currentTime = Date.now();
          const newRecordingStatus = {};

          Object.keys(currentStatus).forEach(streamId => {
            newRecordingStatus[streamId] = {
              ...currentStatus[streamId],
              isRecording: false,
              lastUpdate: currentTime,
              processActive: false,
              backendUnavailable: true
            };
          });

          set({
            archiveStatus: null,
            recordingStatus: newRecordingStatus
          });
        }
      },

      /**
       * Get recording status for a specific stream
       */
      getRecordingStatus: (streamId) => {
        const state = get();
        const status = state.recordingStatus[streamId];

        if (!status) {
          return {
            isRecording: false,
            lastUpdate: null,
            processActive: false,
            status: 'unknown'
          };
        }

        // Check if backend is unavailable
        if (status.backendUnavailable) {
          return {
            ...status,
            status: 'backend_unavailable'
          };
        }

        // Check if status is stale (older than 2 minutes)
        const isStale = status.lastUpdate && (Date.now() - status.lastUpdate) > 120000;

        return {
          ...status,
          status: isStale ? 'stale' : (status.isRecording ? 'recording' : 'stopped')
        };
      },

      /**
       * Get count of active recordings
       */
      getActiveRecordingCount: () => {
        const state = get();
        return Object.values(state.recordingStatus).filter(status => status.isRecording).length;
      },

      /**
       * Check if there are any active recordings
       */
      hasActiveRecordings: () => {
        const state = get();
        return Object.values(state.recordingStatus).some(status => status.isRecording);
      },

      /**
       * Check if any streams are recording
       */
      hasActiveRecordings: () => {
        const state = get();
        return Object.values(state.recordingStatus).some(status => status.isRecording);
      },

      /**
       * Get count of active recordings
       */
      getActiveRecordingCount: () => {
        const state = get();
        return Object.values(state.recordingStatus).filter(status => status.isRecording).length;
      },

      /**
       * Start periodic status updates
       */
      startStatusPolling: () => {
        const state = get();

        // Clear existing interval if any
        if (state.statusPollingInterval) {
          clearInterval(state.statusPollingInterval);
        }

        // Poll every 30 seconds
        const interval = setInterval(() => {
          get().loadArchiveStatus();
        }, 30000);

        set({ statusPollingInterval: interval });

        // Initialize recording status for all configured cameras first
        get().initializeRecordingStatus().then(() => {
          // Then load current archive status
          get().loadArchiveStatus();

          // Also load available streams
          get().loadAvailableStreams();
        });
      },

      /**
       * Stop periodic status updates
       */
      stopStatusPolling: () => {
        const state = get();
        if (state.statusPollingInterval) {
          clearInterval(state.statusPollingInterval);
          set({ statusPollingInterval: null });
        }
      },

      /**
       * Delete a recording
       */
      deleteRecording: async (streamId, filename) => {
        if (!streamId || !filename) {
          set({ error: 'Stream ID and filename are required' });
          return false;
        }

        set({ isLoading: true, error: null });

        try {
          await archiveApi.deleteRecording(streamId, filename);
          
          // Remove the recording from the current list
          set((state) => ({
            recordings: state.recordings.filter(r => r.filename !== filename),
            isLoading: false
          }));

          return true;
        } catch (error) {
          console.error('Error deleting recording:', error);
          set({
            error: error.message || 'Failed to delete recording',
            isLoading: false
          });
          return false;
        }
      },

      /**
       * Get filtered recordings based on current filters
       */
      getFilteredRecordings: () => {
        const state = get();
        let filtered = [...state.recordings];

        // Apply date range filter
        if (state.filters.dateRange !== 'all') {
          const now = new Date();
          let startDate;

          switch (state.filters.dateRange) {
            case 'today':
              startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
              break;
            case 'yesterday':
              startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1);
              const endDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
              filtered = filtered.filter(recording => {
                if (!recording.timestamp) return false;
                const recordingDate = new Date(recording.timestamp);
                return recordingDate >= startDate && recordingDate < endDate;
              });
              break;
            case 'week':
              startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
              break;
            case 'month':
              startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
              break;
            default:
              startDate = null;
          }

          if (startDate && state.filters.dateRange !== 'yesterday') {
            filtered = filtered.filter(recording => {
              if (!recording.timestamp) return false;
              const recordingDate = new Date(recording.timestamp);
              return recordingDate >= startDate;
            });
          }
        }

        // Apply sorting
        filtered.sort((a, b) => {
          if (!a.timestamp || !b.timestamp) return 0;
          
          const dateA = new Date(a.timestamp);
          const dateB = new Date(b.timestamp);

          switch (state.filters.sortBy) {
            case 'newest':
              return dateB - dateA;
            case 'oldest':
              return dateA - dateB;
            case 'largest':
              return (b.size_bytes || 0) - (a.size_bytes || 0);
            case 'smallest':
              return (a.size_bytes || 0) - (b.size_bytes || 0);
            default:
              return dateB - dateA;
          }
        });

        return filtered;
      },

      /**
       * Get recording stream URL
       */
      getRecordingStreamUrl: (streamId, filename) => {
        if (!streamId || !filename) return null;
        return archiveApi.getRecordingStreamUrl(streamId, filename);
      },

      /**
       * Refresh current recordings
       */
      refreshRecordings: async () => {
        const state = get();
        if (state.selectedStreamId) {
          await get().loadRecordings(state.selectedStreamId);
        }
      },

      /**
       * Restart failed recording processes
       */
      restartRecordings: async () => {
        set({ isLoading: true, error: null });

        try {
          const response = await archiveApi.restartRecordings();

          // Update status after restart
          await get().loadArchiveStatus();

          set({ isLoading: false });
          return response;
        } catch (error) {
          console.error('Error restarting recordings:', error);
          set({
            error: error.message || 'Failed to restart recordings',
            isLoading: false
          });
          throw error;
        }
      },

      /**
       * Clear all data
       */
      clearData: () => {
        const state = get();

        // Stop polling if active
        if (state.statusPollingInterval) {
          clearInterval(state.statusPollingInterval);
        }

        set({
          recordings: [],
          availableStreams: [],
          selectedStreamId: null,
          selectedRecording: null,
          error: null,
          recordingStatus: {},
          statusPollingInterval: null
        });
      },

      /**
       * Extract and download a video segment
       */
      extractVideoSegment: async (streamId, filename, startTime, endTime, outputFilename = null) => {
        try {
          set({ isLoading: true, error: null });

          const result = await archiveApi.extractVideoSegment(streamId, filename, startTime, endTime, outputFilename);

          set({ isLoading: false });
          return result;
        } catch (error) {
          console.error('Error extracting video segment:', error);
          set({
            error: error.message || 'Failed to extract video segment',
            isLoading: false
          });
          throw error;
        }
      },

      /**
       * Download an extracted video segment
       */
      downloadExtractedSegment: async (filename) => {
        try {
          const blob = await archiveApi.downloadExtractedSegment(filename);
          return blob;
        } catch (error) {
          console.error('Error downloading extracted segment:', error);
          set({ error: error.message || 'Failed to download extracted segment' });
          throw error;
        }
      },

      /**
       * Get recording statistics
       */
      getRecordingStats: () => {
        const state = get();
        const recordings = state.recordings;

        if (!recordings.length) {
          return {
            totalRecordings: 0,
            totalSize: 0,
            totalSizeFormatted: '0 B',
            dateRange: null
          };
        }

        const totalSize = recordings.reduce((sum, recording) => sum + (recording.size_bytes || 0), 0);
        const timestamps = recordings
          .map(r => r.timestamp)
          .filter(Boolean)
          .map(t => new Date(t))
          .sort();

        return {
          totalRecordings: recordings.length,
          totalSize,
          totalSizeFormatted: archiveApi.formatFileSize(totalSize),
          dateRange: timestamps.length > 0 ? {
            earliest: timestamps[0],
            latest: timestamps[timestamps.length - 1]
          } : null
        };
      }
    }),
    {
      name: STORAGE_KEY,
      getStorage: () => localStorage,
      partialize: (state) => ({
        filters: state.filters,
        selectedStreamId: state.selectedStreamId
      })
    }
  )
);

export default useArchiveStore;
