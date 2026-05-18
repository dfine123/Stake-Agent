'use strict';

const { app, BrowserWindow, ipcMain, shell } = require('electron');
const path = require('path');

const IS_DEV = process.argv.includes('--dev');

// ── Window management ────────────────────────────────────────────────────────

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1000,
    minHeight: 680,
    backgroundColor: '#0F0D0A',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    show: false, // prevent white flash on load
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (IS_DEV) mainWindow.webContents.openDevTools({ mode: 'detach' });
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── App lifecycle ────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  // On macOS, apps stay active until Cmd+Q.
  if (process.platform !== 'darwin') app.quit();
});

// ── IPC handlers (placeholder — expanded in Task 2.2) ───────────────────────

ipcMain.handle('get-version', () => app.getVersion());

ipcMain.handle('open-external', (_event, url) => {
  // Renderer can open URLs (e.g. DevTools link) without full shell access.
  const allowed = ['https://stake.com', 'https://console.anthropic.com'];
  if (allowed.some(prefix => url.startsWith(prefix))) {
    shell.openExternal(url);
  }
});

ipcMain.handle('open-data-dir', () => {
  shell.openPath(app.getPath('userData'));
});
