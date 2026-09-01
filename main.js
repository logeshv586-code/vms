const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');

const { spawn } = require('child_process');

// Use a consistent path for the camera configuration file
const configPath = path.join(app.getPath('userData'), 'camera_configuration.json');
let vlcProcess = null;

function getVLCPath() {
  switch (process.platform) {
    case 'win32':
      return 'C:\\Program Files\\VideoLAN\\VLC\\vlc.exe';
    case 'darwin':
      return '/Applications/VLC.app/Contents/MacOS/VLC';
    default:
      return 'vlc';
  }
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    icon: path.join(__dirname, 'EAGLE.ico'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  const startUrl = process.env.ELECTRON_START_URL || `file://${path.join(__dirname, 'build', 'index.html')}`;

  mainWindow.loadURL(startUrl);

  if (process.env.ELECTRON_START_URL) {
    mainWindow.webContents.openDevTools();
  }
}

// When the app is ready, create the window
app.whenReady().then(createWindow);

// Quit when all windows are closed.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// On macOS, recreate the window when the dock icon is clicked
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// IPC handler for getting camera configuration
ipcMain.on('get-camera-config', (event) => {
  try {
    let config = '';
    if (fs.existsSync(configPath)) {
      config = fs.readFileSync(configPath, 'utf8');
    }
    event.reply('get-camera-config-reply', config);
  } catch (error) {
    event.reply('get-camera-config-reply', '{}');
  }
});

// IPC handler for saving camera configuration
ipcMain.on('save-camera-config', (event, config) => {
  try {
    console.log(`Received save-camera-config request at ${new Date().toISOString()}`);

    // Parse the new config data
    let newConfig = {};
    if (typeof config === 'string') {
      newConfig = JSON.parse(config);
    } else {
      newConfig = config;
    }

    console.log('Saving camera configuration to file:', JSON.stringify(newConfig, null, 2));
    console.log('Collections in new config:', Object.keys(newConfig));
    console.log('Configuration file path:', configPath);

    // Create backup of existing configuration
    if (fs.existsSync(configPath)) {
      const backupPath = `${configPath}.backup`;
      fs.copyFileSync(configPath, backupPath);
      console.log(`Created backup at: ${backupPath}`);

      // Read the existing config for comparison
      try {
        const existingData = fs.readFileSync(configPath, 'utf8');
        const existingConfig = JSON.parse(existingData);
        console.log('Existing collections:', Object.keys(existingConfig));
      } catch (readError) {
        console.error('Error reading existing configuration for comparison:', readError);
      }
    } else {
      console.log('No existing configuration file to backup');
    }

    // Write the new config directly to file without merging
    // This ensures that deleted collections are actually removed from the file
    fs.writeFileSync(configPath, JSON.stringify(newConfig, null, 2));

    // Verify the file was written correctly
    try {
      const verifyData = fs.readFileSync(configPath, 'utf8');
      const verifyConfig = JSON.parse(verifyData);
      console.log('Verified saved collections:', Object.keys(verifyConfig));
    } catch (verifyError) {
      console.error('Error verifying saved configuration:', verifyError);
    }

    console.log('Camera configuration saved successfully to:', configPath);
    event.reply('save-camera-config-reply', { success: true });

    // Also send the generic success event for compatibility
    event.reply('camera-config-saved');
  } catch (error) {
    console.error('Error saving camera configuration:', error);
    event.reply('save-camera-config-reply', { success: false, error: error.message });

    // Also send the generic error event for compatibility
    event.reply('camera-config-error', error.message);
  }
});

// Delete collection handler
ipcMain.handle('delete-collection', async (_, collectionId) => {
  try {
    console.log(`Deleting collection with ID: ${collectionId}`);

    // Read the current configuration
    if (!fs.existsSync(configPath)) {
      console.error('Configuration file not found at:', configPath);
      return { success: false, error: 'Configuration file not found' };
    }

    const configData = fs.readFileSync(configPath, 'utf8');
    if (!configData || !configData.trim()) {
      console.error('Configuration file is empty');
      return { success: false, error: 'Configuration file is empty' };
    }

    // Log the configuration path being used
    console.log(`Using configuration file at: ${configPath}`);

    // The collection ID is passed, but we need to find the collection name
    // to remove it from the configuration
    // This is handled in the cameraStore.js deleteCollection function

    // Return success - the actual deletion from the JSON file happens in the store
    // when it calls saveCameraConfig() after updating the state
    return { success: true };
  } catch (error) {
    console.error('Error deleting collection:', error);
    return { success: false, error: error.message };
  }
});

// Load camera configuration
ipcMain.on('load-camera-config', (event) => {
  try {
    if (fs.existsSync(configPath)) {
      const configData = fs.readFileSync(configPath, 'utf8');
      if (configData && configData.trim()) {
        try {
          const config = JSON.parse(configData);
          event.reply('camera-config-loaded', config);
        } catch (parseError) {
          console.error('Error parsing camera configuration:', parseError);
          fs.writeFileSync(configPath, JSON.stringify({}, null, 2));
          event.reply('camera-config-loaded', {});
        }
      } else {
        fs.writeFileSync(configPath, JSON.stringify({}, null, 2));
        event.reply('camera-config-loaded', {});
      }
    } else {
      fs.writeFileSync(configPath, JSON.stringify({}, null, 2));
      event.reply('camera-config-loaded', {});
    }
  } catch (error) {
    console.error('Error loading camera configuration:', error);
    event.reply('camera-config-error', error.message);
  }
});

// Handle starting VLC stream
ipcMain.handle('start-vlc-stream', async (_, streamUrl) => {
  try {
    if (typeof streamUrl !== 'string' || !streamUrl.trim()) {
      return { success: false, error: 'Invalid or empty stream URL' };
    }

    const trimmedUrl = streamUrl.trim();
    const allowedProtocols = /^(rtsp|http|https|udp|rtmp|file):\/\//i;
    if (!allowedProtocols.test(trimmedUrl) || /\s/.test(trimmedUrl) || trimmedUrl.startsWith('-')) {
      return { success: false, error: 'Unsafe or unsupported stream URL scheme' };
    }

    if (vlcProcess) {
      vlcProcess.kill();
      vlcProcess = null;
    }

    const vlcPath = getVLCPath();
    const args = [
      trimmedUrl,
      '--no-video-title-show',
      '--fullscreen',
      '--no-repeat',
      '--no-loop',
      '--play-and-exit',
      '--quiet',
    ];

    console.log(`Starting VLC with command: ${vlcPath} ${args.join(' ')}`);

    vlcProcess = spawn(vlcPath, args, {
      detached: false,
      windowsHide: false
    });

    vlcProcess.on('error', (err) => {
      console.error('Failed to start VLC:', err);
      return { success: false, error: err.message };
    });

    vlcProcess.on('exit', (code) => {
      console.log(`VLC process exited with code ${code}`);
      vlcProcess = null;
    });

    return { success: true };
  } catch (error) {
    console.error('Error starting VLC:', error);
    return { success: false, error: error.message };
  }
});

// Handle stopping VLC stream
ipcMain.handle('stop-vlc-stream', async () => {
  try {
    if (vlcProcess) {
      vlcProcess.kill();
      vlcProcess = null;
    }
    return { success: true };
  } catch (error) {
    console.error('Error stopping VLC:', error);
    return { success: false, error: error.message };
  }
});

// Ensure VLC process is killed when app exits
app.on('before-quit', () => {
  if (vlcProcess) {
    vlcProcess.kill();
  }
});
