'use strict';

const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path   = require('path');
const { EngineClient } = require('./ipc/client');

const IS_DEV = process.argv.includes('--dev');

// ── Engine sidecar ────────────────────────────────────────────────────────────

const engine = new EngineClient();

function getEnginePaths() {
  if (IS_DEV) {
    // Dev: engine/ lives one directory above electron/
    return {
      pythonCmd:   'python3',
      projectRoot: path.join(__dirname, '..'),
    };
  }
  // Packaged: engine bundled into extraResources (Task 2.10)
  return {
    pythonCmd:   path.join(process.resourcesPath, 'python', 'bin', 'python3'),
    projectRoot: path.join(process.resourcesPath, 'engine'),
  };
}

function startEngine() {
  const { pythonCmd, projectRoot } = getEnginePaths();
  console.log(`[main] starting engine: ${pythonCmd} -m engine.main serve (cwd=${projectRoot})`);
  engine.start(pythonCmd, projectRoot);

  // Forward all engine events to the renderer.
  engine.on('event', msg => {
    if (mainWindow) mainWindow.webContents.send('engine-event', msg);
  });

  engine.on('crash', info => {
    console.error('[main] engine crashed:', info);
    if (mainWindow) {
      mainWindow.webContents.send('engine-event', {
        id: 'crash', type: 'event', name: 'engine_crash',
        payload: info, ts: new Date().toISOString(),
      });
    }
  });

  engine.on('stderr', text => {
    if (mainWindow) {
      mainWindow.webContents.send('engine-event', {
        id: 'stderr', type: 'event', name: 'engine_stderr',
        payload: { text }, ts: new Date().toISOString(),
      });
    }
  });
}

// ── Window management ─────────────────────────────────────────────────────────

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width:     1200,
    height:    800,
    minWidth:  1000,
    minHeight: 680,
    backgroundColor: '#0F0D0A',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      nodeIntegration:  false,
      contextIsolation: true,
      sandbox:          true,
      preload: path.join(__dirname, 'preload.js'),
    },
    show: false,
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (IS_DEV) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  startEngine();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  engine.stop();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => engine.stop());

// ── IPC handlers ──────────────────────────────────────────────────────────────

// Renderer → main → engine (proxied command)
ipcMain.handle('engine-send', async (_event, name, payload, timeoutMs) => {
  try {
    const result = await engine.send(name, payload ?? {}, timeoutMs ?? 30_000);
    return { ok: true, payload: result };
  } catch (err) {
    return { ok: false, error: err.message, payload: err.payload ?? {} };
  }
});

// Engine alive check
ipcMain.handle('engine-alive', () => engine.alive);

// Restart sidecar (e.g. after crash)
ipcMain.handle('engine-restart', () => {
  engine.stop();
  setTimeout(() => startEngine(), 500);
  return { ok: true };
});

// App info
ipcMain.handle('get-version', () => app.getVersion());

// Shell helpers
ipcMain.handle('open-external', (_event, url) => {
  const allowed = ['https://stake.com', 'https://console.anthropic.com'];
  if (allowed.some(prefix => url.startsWith(prefix))) shell.openExternal(url);
});

ipcMain.handle('open-data-dir', () => shell.openPath(app.getPath('userData')));
