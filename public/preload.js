const { contextBridge, ipcRenderer } = require('electron');

// Allowed IPC channels for secure communication
const ALLOWED_CHANNELS = {
  send: [
    'save-camera-config',
    'load-camera-config',
    'get-camera-config'
  ],
  receive: [
    'camera-config-loaded',
    'save-camera-config-reply',
    'camera-config-saved',
    'camera-config-error',
    'get-camera-config-reply'
  ],
  invoke: [
    'delete-collection',
    'start-vlc-stream',
    'stop-vlc-stream'
  ]
};

// Expose secure electronAPI interface to renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  send: (channel, data) => {
    if (ALLOWED_CHANNELS.send.includes(channel)) {
      ipcRenderer.send(channel, data);
    } else {
      console.warn(`Blocked unauthorized IPC send channel: ${channel}`);
    }
  },

  on: (channel, callback) => {
    if (ALLOWED_CHANNELS.receive.includes(channel)) {
      const subscription = (event, ...args) => callback(event, ...args);
      ipcRenderer.on(channel, subscription);
      return subscription;
    } else {
      console.warn(`Blocked unauthorized IPC listener channel: ${channel}`);
    }
  },

  once: (channel, callback) => {
    if (ALLOWED_CHANNELS.receive.includes(channel)) {
      ipcRenderer.once(channel, (event, ...args) => callback(event, ...args));
    } else {
      console.warn(`Blocked unauthorized IPC listener channel: ${channel}`);
    }
  },

  removeListener: (channel, callback) => {
    if (ALLOWED_CHANNELS.receive.includes(channel)) {
      ipcRenderer.removeListener(channel, callback);
    }
  },

  removeAllListeners: (channel) => {
    if (ALLOWED_CHANNELS.receive.includes(channel)) {
      ipcRenderer.removeAllListeners(channel);
    }
  },

  invoke: (channel, ...args) => {
    if (ALLOWED_CHANNELS.invoke.includes(channel)) {
      return ipcRenderer.invoke(channel, ...args);
    }
    return Promise.reject(new Error(`Unauthorized IPC invoke channel: ${channel}`));
  },

  // Direct convenience methods
  startVLCStream: (streamUrl) => ipcRenderer.invoke('start-vlc-stream', streamUrl),
  stopVLCStream: () => ipcRenderer.invoke('stop-vlc-stream'),
  deleteCollection: (collectionId) => ipcRenderer.invoke('delete-collection', collectionId),
  saveCameraConfig: (configData) => ipcRenderer.send('save-camera-config', configData),
  loadCameraConfig: () => ipcRenderer.send('load-camera-config')
});
