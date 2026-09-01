const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const fs = require('fs');
const isDev = require('electron-is-dev');
const { spawn } = require('child_process');

let mainWindow;
let vlcProcess = null;
const configPath = path.join(app.getPath('userData'), 'camera_configuration.json');

// Function to get VLC path based on platform
function getVLCPath() {
  switch (process.platform) {
    case 'win32':
      return 'C:\\Program Files\\VideoLAN\\VLC\\vlc.exe';
    case 'darwin':
      return '/Applications/VLC.app/Contents/MacOS/VLC';
    default:
      return 'vlc'; // Linux usually has it in PATH
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  mainWindow.loadURL(
    isDev
      ? 'http://localhost:3000'
      : `file://${path.join(__dirname, '../build/index.html')}`
  );

  if (isDev) {
    mainWindow.webContents.openDevTools();
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Load camera configuration
ipcMain.on('load-camera-config', (event) => {
  try {
    if (fs.existsSync(configPath)) {
      const configData = fs.readFileSync(configPath, 'utf8');
      // Check if the file is not empty before parsing
      if (configData && configData.trim()) {
        try {
          const config = JSON.parse(configData);
          event.reply('camera-config-loaded', config);
        } catch (parseError) {
          console.error('Error parsing camera configuration:', parseError);
          // If parsing fails, create a new file with empty configuration
          fs.writeFileSync(configPath, JSON.stringify({}, null, 2));
          event.reply('camera-config-loaded', {});
        }
      } else {
        // If file is empty, initialize it with empty JSON object
        fs.writeFileSync(configPath, JSON.stringify({}, null, 2));
        event.reply('camera-config-loaded', {});
      }
    } else {
      // If file doesn't exist, create it with empty configuration
      fs.writeFileSync(configPath, JSON.stringify({}, null, 2));
      event.reply('camera-config-loaded', {});
    }
  } catch (error) {
    console.error('Error loading camera configuration:', error);
    event.reply('camera-config-error', error.message);
  }
});

// Save camera configuration
ipcMain.on('save-camera-config', (event, configData) => {
  try {
    console.log(`Received save-camera-config request at ${new Date().toISOString()}`);

    // Parse the new config data (string or object)
    let newConfig = {};
    if (typeof configData === 'string') {
      newConfig = JSON.parse(configData);
    } else {
      newConfig = configData;
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

    // Return success - the actual deletion from the JSON file happens in the store
    // when it calls saveCameraConfig() after updating the state
    return { success: true };
  } catch (error) {
    console.error('Error deleting collection:', error);
    return { success: false, error: error.message };
  }
});

// Handle starting VLC stream
ipcMain.handle('start-vlc-stream', async (_, streamUrl) => {
  try {
    // Validate streamUrl to prevent argument injection or malicious inputs
    if (typeof streamUrl !== 'string' || !streamUrl.trim()) {
      return { success: false, error: 'Invalid or empty stream URL' };
    }

    const trimmedUrl = streamUrl.trim();
    // Validate protocol (rtsp, http, https, udp, rtmp, file) and disallow command line flags or whitespace injection
    const allowedProtocols = /^(rtsp|http|https|udp|rtmp|file):\/\//i;
    if (!allowedProtocols.test(trimmedUrl) || /\s/.test(trimmedUrl) || trimmedUrl.startsWith('-')) {
      return { success: false, error: 'Unsafe or unsupported stream URL scheme' };
    }

    // Kill any existing VLC process
    if (vlcProcess) {
      vlcProcess.kill();
      vlcProcess = null;
    }

    const vlcPath = getVLCPath();
    
    // VLC command line arguments
    const args = [
      trimmedUrl,
      '--no-video-title-show',  // Don't show the title
      '--fullscreen',           // Start in fullscreen
      '--no-repeat',           // Don't repeat the stream
      '--no-loop',            // Don't loop the stream
      '--play-and-exit',      // Exit when playback ends
      '--quiet',              // Reduce console output
    ];

    console.log(`Starting VLC with command: ${vlcPath} ${args.join(' ')}`);

    vlcProcess = spawn(vlcPath, args, {
      detached: false,        // Keep process attached to parent
      windowsHide: false      // Show VLC window
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