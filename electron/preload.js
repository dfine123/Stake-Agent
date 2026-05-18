'use strict';

const { contextBridge, ipcRenderer } = require('electron');

// Safe surface exposed to renderer — no direct Node/Electron access.
// Expanded with engine IPC methods in Task 2.2.
contextBridge.exposeInMainWorld('gambleAgent', {

  // ── App info ──────────────────────────────────────────────────────────────
  getVersion: () => ipcRenderer.invoke('get-version'),

  // ── Shell helpers ─────────────────────────────────────────────────────────
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  openDataDir:  ()    => ipcRenderer.invoke('open-data-dir'),

  // ── Engine IPC (stubs — wired in Task 2.2) ───────────────────────────────
  sendCommand: (_name, _payload) => Promise.resolve({ ok: false, error: 'IPC not yet wired' }),
  onEngineEvent: (_callback) => {},
  offEngineEvent: (_callback) => {},
});
