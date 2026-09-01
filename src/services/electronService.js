// This service provides a wrapper around electron functionality
// with fallbacks for web environments using secure contextBridge preload API

const isElectron = () => {
  return typeof window !== 'undefined' && Boolean(window.electronAPI);
};

// Get the ipcRenderer wrapper if we're in Electron contextBridge, otherwise return a safe web mock
const getIpcRenderer = () => {
  if (isElectron()) {
    return {
      send: (channel, data) => window.electronAPI.send(channel, data),
      on: (channel, callback) => window.electronAPI.on(channel, callback),
      once: (channel, callback) => window.electronAPI.once(channel, callback),
      invoke: (channel, ...args) => window.electronAPI.invoke(channel, ...args),
      removeListener: (channel, callback) => window.electronAPI.removeListener(channel, callback),
      removeAllListeners: (channel) => window.electronAPI.removeAllListeners(channel)
    };
  }

  // Return a mock implementation for web environment
  return {
    send: (channel, data) => {
      console.warn(`IPC send "${channel}" not supported in web environment`);
    },
    on: (channel, callback) => {},
    once: (channel, callback) => {},
    invoke: (channel, ...args) => {
      console.warn(`IPC invoke "${channel}" not supported in web environment`);
      return Promise.reject(new Error('This feature is only available in the desktop app'));
    },
    removeListener: (channel, callback) => {},
    removeAllListeners: (channel) => {}
  };
};

export const ipcRenderer = getIpcRenderer();
export default { isElectron, ipcRenderer };