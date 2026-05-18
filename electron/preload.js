'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('gambleAgent', {

  // ── App info ──────────────────────────────────────────────────────────────
  getVersion: () => ipcRenderer.invoke('get-version'),

  // ── Shell helpers ─────────────────────────────────────────────────────────
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  openDataDir:  ()    => ipcRenderer.invoke('open-data-dir'),

  // ── Keychain ──────────────────────────────────────────────────────────────
  keychain: {
    get:    (account)           => ipcRenderer.invoke('keychain-get', account),
    set:    (account, password) => ipcRenderer.invoke('keychain-set', account, password),
    delete: (account)           => ipcRenderer.invoke('keychain-delete', account),
  },

  // ── Engine IPC ────────────────────────────────────────────────────────────

  /**
   * Send a command to the Python engine and await the response.
   * Returns { ok: bool, payload: dict } — never throws.
   */
  engineSend: (name, payload, timeoutMs) =>
    ipcRenderer.invoke('engine-send', name, payload, timeoutMs),

  /** Is the engine process alive? */
  engineAlive: () => ipcRenderer.invoke('engine-alive'),

  /** Restart the engine after a crash. */
  engineRestart: () => ipcRenderer.invoke('engine-restart'),

  /**
   * Subscribe to events emitted by the engine.
   * Returns an unsubscribe function.
   *
   * handler receives the full message object:
   *   { id, type: "event", name, payload, ts }
   */
  onEngineEvent: (handler) => {
    const wrapper = (_ipc, msg) => handler(msg);
    ipcRenderer.on('engine-event', wrapper);
    return () => ipcRenderer.removeListener('engine-event', wrapper);
  },
});
