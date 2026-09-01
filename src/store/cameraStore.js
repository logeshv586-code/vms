
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import collectionsApi from '../services/collectionsApi';
import mapApi from '../services/mapApi';
import { generateCameraId, normalizeCollectionName, denormalizeCollectionName, parseCameraId } from '../utils/cameraUtils';
import { ipcRenderer } from '../services/electronService';

const STORAGE_KEY = 'vms_cameras';
const LAYOUT_STORAGE_KEY = 'vms_layout';
const COLLECTIONS_STORAGE_KEY = 'vms_collections';
const BOOKMARKS_STORAGE_KEY = 'vms_bookmarks';

export const useCameraStore = create(
  persist(
    (set, get) => ({
      cameras: [],
      bookmarks: [],
      collections: [],
      activeCollection: null,
      currentLayout: 'grid',
      cameraJson: {},
      selectedAiCamera: null,
      cameraLocations: {
        settings: {
          defaultProvider: 'leaflet',
          center: [12.9716, 77.5946],
          zoom: 13
        },
        locations: {}
      },

      // Camera actions
      setCameras: (cameras) => set({ cameras }),
      setSelectedAiCamera: (camera) => set({ selectedAiCamera: camera }),

      // Map & Location Actions
      loadCameraLocations: async () => {
        try {
          const locationsData = await mapApi.getCameraLocations();
          if (locationsData && locationsData.settings && locationsData.locations) {
            set({ cameraLocations: locationsData });
          }
          return locationsData;
        } catch (error) {
          console.error('Failed to load camera locations:', error);
        }
      },

      saveCameraLocations: async (locations, settings) => {
        try {
          const currentState = get().cameraLocations;
          const updatedState = {
            settings: settings || currentState.settings,
            locations: locations || currentState.locations
          };
          
          set({ cameraLocations: updatedState });
          await mapApi.saveCameraLocations(updatedState);
        } catch (error) {
          console.error('Failed to save camera locations:', error);
          throw error;
        }
      },

      updateCameraLocation: async (cameraId, lat, lng, customName = '') => {
        try {
          const currentState = get().cameraLocations;
          const updatedLocations = {
            ...currentState.locations,
            [cameraId]: {
              lat: parseFloat(lat),
              lng: parseFloat(lng),
              customName: customName || (currentState.locations[cameraId]?.customName || '')
            }
          };
          
          await get().saveCameraLocations(updatedLocations, currentState.settings);
        } catch (error) {
          console.error('Failed to update camera location:', error);
          throw error;
        }
      },
      addCamera: (name, streamUrl, collectionId = null, analyticUrl = '') => {
        const newCamera = {
          id: `camera-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          name,
          streamUrl,
          analyticUrl,
          position: get().cameras.length,
          collectionId
        };

        set((state) => {
          const updatedCameras = [...state.cameras, newCamera];
          let updatedCollections = state.collections;

          if (collectionId) {
            updatedCollections = state.collections.map(collection => {
              if (collection.id === collectionId) {
                return {
                  ...collection,
                  cameras: [...collection.cameras, newCamera.id]
                };
              }
              return collection;
            });
          }

          return {
            cameras: updatedCameras,
            collections: updatedCollections,
            activeCollection: collectionId
          };
        });

        return newCamera.id;
      },

      // Helper function to check if an IP exists in any collection
      isIpExists: (ip) => {
        const state = get();
        return Object.values(state.cameraJson).some(collection =>
          Object.hasOwn(collection, ip)
        );
      },

      // Update camera configuration
      updateCameraConfig: async (collectionName, ip, streamUrl) => {
        try {
          console.log(`Updating camera configuration for ${ip} in collection ${collectionName}`);

          // Check if the collection exists in the backend
          let collectionExists = false;
          try {
            await collectionsApi.getCollection(collectionName);
            collectionExists = true;
          } catch (error) {
            if (error.response && error.response.status === 404) {
              console.log(`Collection ${collectionName} does not exist, creating it`);
              await collectionsApi.createCollection(collectionName);
            } else {
              throw error;
            }
          }

          // Add or update the camera in the collection
          if (collectionExists) {
            try {
              // Try to update the camera first
              await collectionsApi.updateCameraInCollection(collectionName, ip, streamUrl);
              console.log(`Updated camera ${ip} in collection ${collectionName}`);
            } catch (error) {
              if (error.response && error.response.status === 404) {
                // Camera doesn't exist, add it
                await collectionsApi.addCameraToCollection(collectionName, ip, streamUrl);
                console.log(`Added camera ${ip} to collection ${collectionName}`);
              } else {
                // Handle validation and duplicate errors
                console.error('Error updating/adding camera:', error);

                let errorMessage = 'Failed to update camera configuration';

                if (error.response && error.response.data) {
                  const errorData = error.response.data;

                  if (typeof errorData === 'object' && errorData.detail) {
                    const detail = errorData.detail;

                    if (detail.type === 'duplicate') {
                      errorMessage = `${detail.message}\n\nExisting camera found in collection: ${detail.existingCollection}`;
                    } else if (detail.type === 'validation') {
                      errorMessage = `Validation Error: ${detail.message}`;
                    } else if (detail.message) {
                      errorMessage = detail.message;
                    } else if (detail.error) {
                      errorMessage = detail.error;
                    }
                  } else if (typeof errorData === 'string') {
                    errorMessage = errorData;
                  } else if (errorData.message) {
                    errorMessage = errorData.message;
                  }
                }

                const enhancedError = new Error(errorMessage);
                enhancedError.type = error.response?.data?.detail?.type || 'unknown';
                enhancedError.statusCode = error.response?.status;
                enhancedError.originalError = error;
                throw enhancedError;
              }
            }
          } else {
            // Collection was just created, add the camera
            try {
              await collectionsApi.addCameraToCollection(collectionName, ip, streamUrl);
              console.log(`Added camera ${ip} to new collection ${collectionName}`);
            } catch (error) {
              // Handle validation and duplicate errors for new collections too
              console.error('Error adding camera to new collection:', error);

              let errorMessage = 'Failed to add camera to collection';

              if (error.response && error.response.data) {
                const errorData = error.response.data;

                if (typeof errorData === 'object' && errorData.detail) {
                  const detail = errorData.detail;

                  if (detail.type === 'duplicate') {
                    errorMessage = `${detail.message}\n\nExisting camera found in collection: ${detail.existingCollection}`;
                  } else if (detail.type === 'validation') {
                    errorMessage = `Validation Error: ${detail.message}`;
                  } else if (detail.message) {
                    errorMessage = detail.message;
                  } else if (detail.error) {
                    errorMessage = detail.error;
                  }
                } else if (typeof errorData === 'string') {
                  errorMessage = errorData;
                } else if (errorData.message) {
                  errorMessage = errorData.message;
                }
              }

              const enhancedError = new Error(errorMessage);
              enhancedError.type = error.response?.data?.detail?.type || 'unknown';
              enhancedError.statusCode = error.response?.status;
              enhancedError.originalError = error;
              throw enhancedError;
            }
          }

          // Update the local state
          set((state) => {
            // Create a deep copy of the existing configuration
            const updatedJson = JSON.parse(JSON.stringify(state.cameraJson));

            // Initialize collection if not exists
            if (!updatedJson[collectionName]) {
              updatedJson[collectionName] = {};
            }

            // Add the new camera while preserving existing ones
            updatedJson[collectionName] = {
              ...updatedJson[collectionName],
              [ip]: streamUrl
            };

            // Find the collection
            const collection = state.collections.find(c => c.name === collectionName);
            if (!collection) return { cameraJson: updatedJson };

            // Create or update camera in the cameras array
            const cameraId = generateCameraId(collectionName, ip);
            const existingCamera = state.cameras.find(c => c.id === cameraId);

            let updatedCameras = [...state.cameras];
            if (!existingCamera) {
              updatedCameras.push({
                id: cameraId,
                name: `${collectionName} (${ip})`,
                streamUrl,
                ip: ip, // Add IP information
                collection: collectionName, // Add collection name
                collectionName: collectionName, // Add collection name for compatibility
                position: state.cameras.length,
                collectionId: collection.id
              });
            }

            // Update collection's cameras array
            const updatedCollections = state.collections.map(c => {
              if (c.id === collection.id) {
                return {
                  ...c,
                  cameras: [...new Set([...c.cameras, cameraId])]
                };
              }
              return c;
            });

            return {
              cameraJson: updatedJson,
              cameras: updatedCameras,
              collections: updatedCollections
            };
          });

          // Note: Removed loadCameraConfig() call to prevent state rebuild that causes
          // cameras to be incorrectly added to multiple collections
        } catch (error) {
          console.error(`Error updating camera configuration:`, error);
          throw new Error(`Failed to update camera configuration: ${error.message}`);
        }
      },

      // Save camera configuration to file
      saveCameraConfig: () => {
        const state = get();
        const configToSave = JSON.stringify(state.cameraJson, null, 2);
        console.log('Saving camera config to file. Collections:', Object.keys(state.cameraJson));
        console.log('Config data:', configToSave);

        // Add a timestamp to help track when the save operation occurs
        console.log(`Saving camera configuration at ${new Date().toISOString()}`);

        // Send the configuration to the main process
        ipcRenderer.send('save-camera-config', configToSave);

        // Add a listener for the save response if it doesn't exist
        if (!window._saveConfigListenerAdded) {
          ipcRenderer.once('save-camera-config-reply', (_, response) => {
            if (response.success) {
              console.log('Camera configuration saved successfully');
            } else {
              console.error('Error saving camera configuration:', response.error);
            }
          });
          window._saveConfigListenerAdded = true;
        }
      },

      // Load camera configuration from backend API
      loadCameraConfig: async () => {
        try {
          console.log('Loading camera configuration from backend API');

          // Get all collections from the backend
          const collections = await collectionsApi.getCollections();
          console.log('Collections from backend:', collections);

          // Initialize an empty configuration object
          const config = {};

          // For each collection, get its cameras
          for (const collectionName of collections) {
            try {
              const collectionData = await collectionsApi.getCollection(collectionName);
              config[collectionName] = collectionData.cameras;
            } catch (error) {
              console.error(`Error loading cameras for collection ${collectionName}:`, error);
            }
          }

          console.log('Loaded camera configuration:', config);

          // Initialize the camera configuration with the loaded data
          get().initializeCameraConfig(config);
        } catch (error) {
          console.error('Error loading camera configuration from backend:', error);
        }
      },

      // Initialize camera configuration
      initializeCameraConfig: (config) => {
        console.log('Initializing camera configuration with:', config);
        console.log('Collections in config:', Object.keys(config));

        set((state) => {
          // Update cameraJson with the new config
          const updatedCameraJson = config;

          // Create a map of IP addresses to their collection names from the config
          const ipToCollection = {};
          Object.entries(updatedCameraJson).forEach(([collectionName, cameras]) => {
            Object.keys(cameras).forEach(ip => {
              ipToCollection[ip] = collectionName;
            });
          });
          console.log('IP to collection mapping created:', ipToCollection);

          // Rebuild cameras array from the backend configuration to ensure accuracy
          const updatedCameras = [];
          const processedCameraIds = new Set();

          // Process cameras from the configuration
          Object.entries(updatedCameraJson).forEach(([collectionName, cameras]) => {
            let collection = state.collections.find(c => c.name === collectionName);

            // Create collection if it doesn't exist
            if (!collection) {
              console.log(`Creating new collection: ${collectionName}`);
              const newCollectionId = `collection-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
              collection = {
                id: newCollectionId,
                name: collectionName,
                cameras: []
              };
              state.collections.push(collection);
            }

            console.log(`Processing cameras for collection: ${collectionName}`);
            Object.entries(cameras).forEach(([ip, streamUrl]) => {
              const cameraName = `${collectionName} (${ip})`;
              const cameraId = generateCameraId(collectionName, ip);

              // Only add camera if it hasn't been processed yet
              if (!processedCameraIds.has(cameraId)) {
                updatedCameras.push({
                  id: cameraId,
                  name: cameraName,
                  streamUrl,
                  ip: ip, // Add IP information
                  collection: collectionName, // Add collection name
                  collectionName: collectionName, // Add collection name for compatibility
                  position: updatedCameras.length,
                  collectionId: collection.id
                });
                processedCameraIds.add(cameraId);
                console.log(`Added camera ${cameraId} to collection ${collectionName} with IP ${ip}`);
              } else {
                console.log(`Camera ${cameraId} already processed, skipping duplicate`);
              }
            });
          });
          console.log(`Rebuilt cameras array with ${updatedCameras.length} cameras`);

          // Update collections to include only cameras that belong to them
          const updatedCollections = state.collections.map(collection => {
            const collectionCameras = updatedCameras
              .filter(camera => camera.collectionId === collection.id)
              .map(camera => camera.id);

            return {
              ...collection,
              cameras: collectionCameras
            };
          });
          console.log(`Updated collections:`, updatedCollections);

          return {
            cameraJson: updatedCameraJson,
            cameras: updatedCameras,
            collections: updatedCollections
          };
        });
      },

      updateCamera: async (cameraId, updates) => {
        try {
          // First, find the camera to update
          const state = get();
          const camera = state.cameras.find(c => c.id === cameraId);
          if (!camera) {
            console.error(`Camera with ID ${cameraId} not found`);
            throw new Error(`Camera with ID ${cameraId} not found`);
          }

          // Find the collection this camera belongs to
          const collection = state.collections.find(c => c.id === camera.collectionId);
          if (!collection) {
            console.error(`Collection for camera ${cameraId} not found`);
            throw new Error(`Collection for camera ${cameraId} not found`);
          }

          // Parse the camera ID to extract the IP
          const { collectionName, ip } = parseCameraId(cameraId, state.collections);

          if (!ip) {
            console.error(`Could not extract IP from camera ID: ${cameraId}`);
            throw new Error(`Could not extract IP from camera ID: ${cameraId}`);
          }

          console.log(`Extracted IP from camera ID: ${ip}`);

          // Update the camera in the backend first
          if (updates.streamUrl && updates.streamUrl !== camera.streamUrl) {
            console.log(`Updating camera ${ip} in collection ${collection.name} with new URL: ${updates.streamUrl}`);

            try {
              const response = await collectionsApi.updateCameraInCollection(collection.name, ip, updates.streamUrl);
              console.log('Camera updated in backend:', response);
            } catch (error) {
              console.error('Error updating camera in backend:', error);

              // Parse the structured error response from our new validation endpoints
              let errorMessage = 'Failed to update camera';

              if (error.response && error.response.data) {
                const errorData = error.response.data;

                // Handle structured error responses from our new validation endpoints
                if (typeof errorData === 'object' && errorData.detail) {
                  const detail = errorData.detail;

                  if (detail.type === 'duplicate') {
                    errorMessage = `${detail.message}\n\nExisting camera found in collection: ${detail.existingCollection}`;
                  } else if (detail.type === 'validation') {
                    errorMessage = `Validation Error: ${detail.message}`;
                  } else if (detail.message) {
                    errorMessage = detail.message;
                  } else if (detail.error) {
                    errorMessage = detail.error;
                  }
                } else if (typeof errorData === 'string') {
                  errorMessage = errorData;
                } else if (errorData.message) {
                  errorMessage = errorData.message;
                }
              } else if (error.message) {
                errorMessage = error.message;
              }

              // Throw a user-friendly error that can be caught by the UI
              const enhancedError = new Error(errorMessage);
              enhancedError.type = error.response?.data?.detail?.type || 'unknown';
              enhancedError.statusCode = error.response?.status;
              enhancedError.originalError = error;
              throw enhancedError;
            }
          }

          // Only update the frontend state if backend update was successful
          set((state) => ({
            cameras: state.cameras.map(c =>
              c.id === cameraId ? { ...c, ...updates } : c
            )
          }));

          return { success: true, message: 'Camera updated successfully' };
        } catch (error) {
          console.error('Error in updateCamera:', error);
          throw error; // Re-throw so the UI can handle it
        }
      },
      removeCamera: (cameraId) =>
        set((state) => ({
          cameras: state.cameras.filter(camera => camera.id !== cameraId),
          bookmarks: state.bookmarks.filter(id => id !== cameraId),
          collections: state.collections.map(collection => ({
            ...collection,
            cameras: collection.cameras.filter(id => id !== cameraId)
          }))
        })),
      updateCameraPosition: (dragIndex, hoverIndex) => {
        const cameras = get().cameras;
        const draggedCamera = cameras[dragIndex];
        const updatedCameras = [...cameras];
        updatedCameras.splice(dragIndex, 1);
        updatedCameras.splice(hoverIndex, 0, draggedCamera);

        // Update positions
        updatedCameras.forEach((camera, index) => {
          camera.position = index;
        });

        set({ cameras: updatedCameras });
      },

      // Swap two cameras by their indices in the cameras array
      swapCameras: (sourceIndex, targetIndex) => {
        const cameras = get().cameras;
        if (sourceIndex < 0 || sourceIndex >= cameras.length ||
            targetIndex < 0 || targetIndex >= cameras.length ||
            sourceIndex === targetIndex) {
          return; // Invalid indices or same position
        }

        const updatedCameras = [...cameras];
        // Swap the cameras
        [updatedCameras[sourceIndex], updatedCameras[targetIndex]] =
        [updatedCameras[targetIndex], updatedCameras[sourceIndex]];

        // Update positions to match array indices
        updatedCameras.forEach((camera, index) => {
          camera.position = index;
        });

        set({ cameras: updatedCameras });
      },

      // Swap cameras within a specific collection
      swapCamerasInCollection: (collectionId, sourceIndex, targetIndex) => {
        const state = get();
        const collectionCameras = state.cameras.filter(camera => camera.collectionId === collectionId);

        if (sourceIndex < 0 || sourceIndex >= collectionCameras.length ||
            targetIndex < 0 || targetIndex >= collectionCameras.length ||
            sourceIndex === targetIndex) {
          return; // Invalid indices or same position
        }

        // Get the actual camera objects to swap
        const sourceCamera = collectionCameras[sourceIndex];
        const targetCamera = collectionCameras[targetIndex];

        // Find their indices in the main cameras array
        const sourceCameraIndex = state.cameras.findIndex(camera => camera.id === sourceCamera.id);
        const targetCameraIndex = state.cameras.findIndex(camera => camera.id === targetCamera.id);

        // Swap them in the main array
        const updatedCameras = [...state.cameras];
        [updatedCameras[sourceCameraIndex], updatedCameras[targetCameraIndex]] =
        [updatedCameras[targetCameraIndex], updatedCameras[sourceCameraIndex]];

        // Update positions
        updatedCameras.forEach((camera, index) => {
          camera.position = index;
        });

        set({ cameras: updatedCameras });
      },

      // Bookmark actions
      toggleBookmark: (cameraId) =>
        set((state) => {
          const isBookmarked = state.bookmarks.includes(cameraId);
          const newBookmarks = isBookmarked
            ? state.bookmarks.filter(id => id !== cameraId)
            : [...state.bookmarks, cameraId];

          console.log('Toggling bookmark for camera:', cameraId);
          console.log('Current bookmarks:', state.bookmarks);
          console.log('New bookmarks:', newBookmarks);
          console.log('Camera exists in store:', state.cameras.some(cam => cam.id === cameraId));

          return {
            bookmarks: newBookmarks
          };
        }),
      isBookmarked: (cameraId) => {
        const result = get().bookmarks.includes(cameraId);
        console.log('Checking if bookmarked:', cameraId, result);
        return result;
      },
      getBookmarkedCameras: () => {
        const bookmarks = get().bookmarks;
        const cameras = get().cameras;
        const collections = get().collections;
        console.log('Getting bookmarked cameras. Total bookmarks:', bookmarks.length);
        console.log('Total cameras in store:', cameras.length);

        const bookmarkedCameras = cameras.filter(camera => bookmarks.includes(camera.id)).map(camera => {
          // Ensure the camera has proper IP and collection information
          if (!camera.ip && camera.id) {
            const { collectionName, ip } = parseCameraId(camera.id, collections);
            return {
              ...camera,
              ip: ip || camera.ip,
              collection: collectionName || camera.collection,
              collectionName: collectionName || camera.collectionName
            };
          }
          return camera;
        });

        console.log('Found bookmarked cameras:', bookmarkedCameras.length);
        console.log('Bookmarked cameras with IPs:', bookmarkedCameras.map(c => ({ id: c.id, ip: c.ip, collection: c.collection })));
        return bookmarkedCameras;
      },

      // Collection actions
      setCollections: (collections) => set({ collections }),
      createCollection: async (name) => {
        try {
          console.log(`Creating collection with name: ${name}`);

          // Create a new collection ID
          const newCollectionId = `collection-${Date.now()}`;

          // Create the collection in the backend
          await collectionsApi.createCollection(name);

          // Update the local state
          const newCollection = {
            id: newCollectionId,
            name,
            cameras: []
          };

          set((state) => ({
            collections: [...state.collections, newCollection]
          }));

          // Reload the camera configuration to ensure consistency
          get().loadCameraConfig();

          return newCollectionId;
        } catch (error) {
          console.error(`Error creating collection ${name}:`, error);
          throw new Error(`Failed to create collection: ${error.message}`);
        }
      },
      renameCollection: async (collectionId, newName) => {
        try {
          console.log(`Renaming collection with ID: ${collectionId} to ${newName}`);

          // Find the collection in the state
          const collections = get().collections;
          const collection = collections.find(col => col.id === collectionId);

          if (!collection) {
            throw new Error(`Collection with ID ${collectionId} not found`);
          }

          // Check if a collection with the new name already exists
          const existingCollection = collections.find(
            c => c.id !== collectionId && c.name.toLowerCase() === newName.trim().toLowerCase()
          );

          if (existingCollection) {
            throw new Error('A collection with this name already exists');
          }

          // Update the collection in the backend
          await collectionsApi.updateCollection(collection.name, newName.trim());

          // Update the local state
          set((state) => ({
            collections: state.collections.map(col =>
              col.id === collectionId
                ? { ...col, name: newName.trim() }
                : col
            )
          }));

          // Reload the camera configuration to ensure consistency
          get().loadCameraConfig();
        } catch (error) {
          console.error(`Error renaming collection ${collectionId}:`, error);
          throw new Error(`Failed to rename collection: ${error.message}`);
        }
      },
      deleteCollection: async (collectionId) => {
        try {
          console.log(`Deleting collection with ID: ${collectionId}`);

          // Find the collection in the state
          const state = get();
          const collection = state.collections.find(col => col.id === collectionId);

          if (!collection) {
            console.error(`Collection with ID ${collectionId} not found in state`);
            return;
          }

          console.log(`Found collection to delete: ${collection.name} (${collectionId})`);

          // Delete the collection from the backend
          await collectionsApi.deleteCollection(collection.name);

          // Update the local state
          set((state) => {
            // Create a deep copy of the cameraJson to avoid direct state mutation
            let updatedCameraJson = JSON.parse(JSON.stringify(state.cameraJson));
            console.log(`Current collections in cameraJson:`, Object.keys(updatedCameraJson));

            if (updatedCameraJson[collection.name]) {
              console.log(`Removing collection '${collection.name}' from cameraJson`);
              // Remove the collection from cameraJson
              const { [collection.name]: _, ...rest } = updatedCameraJson;
              updatedCameraJson = rest;
              console.log(`Collections after removal:`, Object.keys(updatedCameraJson));
            } else {
              console.log(`Collection '${collection.name}' not found in cameraJson`);
            }

            const camerasInCollection = state.cameras.filter(camera => camera.collectionId === collectionId);
            console.log(`Removing ${camerasInCollection.length} cameras from the collection`);

            const updatedCameras = state.cameras.filter(camera => camera.collectionId !== collectionId);
            const updatedCollections = state.collections.filter(collection => collection.id !== collectionId);

            return {
              cameras: updatedCameras,
              collections: updatedCollections,
              activeCollection: state.activeCollection === collectionId ? null : state.activeCollection,
              cameraJson: updatedCameraJson
            };
          });

          // Reload the camera configuration to ensure consistency
          get().loadCameraConfig();
        } catch (error) {
          console.error('Unexpected error in deleteCollection:', error);
          throw new Error(`Failed to delete collection: ${error.message}`);
        }
      },
      addCameraToCollection: (cameraId, collectionId) => {
        set((state) => ({
          collections: state.collections.map(collection => {
            if (collection.id === collectionId) {
              return {
                ...collection,
                cameras: [...collection.cameras, cameraId]
              };
            }
            return collection;
          }),
          cameras: state.cameras.map(camera => {
            if (camera.id === cameraId) {
              return {
                ...camera,
                collectionId
              };
            }
            return camera;
          })
        }));
      },
      removeCameraFromCollection: async (cameraId, collectionId) => {
        try {
          // Find the camera and collection in the state
          const state = get();
          const camera = state.cameras.find(cam => cam.id === cameraId);
          const collection = state.collections.find(col => col.id === collectionId);

          if (!camera || !collection) {
            console.error(`Camera or collection not found: camera=${cameraId}, collection=${collectionId}`);
            return;
          }

          console.log(`Removing camera ${cameraId} from collection ${collection.name}`);

          // Extract IP from camera ID using the parseCameraId utility
          let ipToRemove = null;

          // Use the parseCameraId utility function for consistent parsing
          const { collectionName: parsedCollection, ip: parsedIp } = parseCameraId(camera.id, state.collections);
          if (parsedIp) {
            ipToRemove = parsedIp;
            console.log(`Extracted IP from camera ID using parseCameraId: ${ipToRemove}`);
          }

          // If that fails, try to find by matching stream URL in the cameraJson
          if (!ipToRemove && state.cameraJson[collection.name]) {
            console.log(`Trying to find IP by matching stream URL`);
            ipToRemove = Object.keys(state.cameraJson[collection.name]).find(ip => {
              return state.cameraJson[collection.name][ip] === camera.streamUrl;
            });
            console.log(`Found IP by stream URL: ${ipToRemove}`);
          }

          // If we found the IP, remove it from the collection in the backend
          if (ipToRemove) {
            console.log(`Removing IP ${ipToRemove} from collection ${collection.name} in backend`);
            await collectionsApi.removeCameraFromCollection(collection.name, ipToRemove);
          } else {
            console.warn(`Could not find IP for camera ${cameraId} in collection ${collection.name}`);
          }

          // Update the local state
          set((state) => {
            // Create a deep copy of the cameraJson to avoid direct state mutation
            let updatedCameraJson = JSON.parse(JSON.stringify(state.cameraJson));

            if (updatedCameraJson[collection.name] && ipToRemove) {
              // Create a new object without the camera to be removed
              const updatedCollectionCameras = {};
              Object.keys(updatedCameraJson[collection.name]).forEach(ip => {
                if (ip !== ipToRemove) {
                  updatedCollectionCameras[ip] = updatedCameraJson[collection.name][ip];
                }
              });

              // Update the collection in cameraJson
              updatedCameraJson[collection.name] = updatedCollectionCameras;

              console.log(`Updated collection cameras:`, Object.keys(updatedCameraJson[collection.name]));
            }

            // Update the collections and cameras arrays
            return {
              collections: state.collections.map(col => {
                if (col.id === collectionId) {
                  return {
                    ...col,
                    cameras: col.cameras.filter(id => id !== cameraId)
                  };
                }
                return col;
              }),
              cameras: state.cameras.map(cam => {
                if (cam.id === cameraId) {
                  return {
                    ...cam,
                    collectionId: null
                  };
                }
                return cam;
              }),
              cameraJson: updatedCameraJson
            };
          });

          // Reload the camera configuration to ensure consistency
          get().loadCameraConfig();
        } catch (error) {
          console.error(`Error removing camera from collection:`, error);
          throw new Error(`Failed to remove camera from collection: ${error.message}`);
        }
      },
      setCollectionActive: (collectionId) => set({ activeCollection: collectionId }),
      getCamerasByCollection: (collectionId) =>
        get().cameras.filter(camera => camera.collectionId === collectionId),

      // Layout actions
      updateLayout: (layout) => set({ currentLayout: layout })
    }),
    {
      name: 'camera-storage',
      getStorage: () => localStorage,
      partialize: (state) => ({
        cameras: state.cameras,
        bookmarks: state.bookmarks,
        collections: state.collections,
        currentLayout: state.currentLayout
      })
    }
  )
);
