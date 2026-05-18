'use strict';

/**
 * EngineClient — manages the Python sidecar process and IPC protocol.
 *
 * Protocol: newline-delimited JSON over stdio.
 *   Electron → Python  (stdin):  { id, type:"command",  name, payload, ts }
 *   Python  → Electron (stdout): { id, type:"response", name, ok, payload, ts }
 *                                { id, type:"event",     name, payload, ts }
 *
 * Usage:
 *   const client = new EngineClient();
 *   client.start();
 *   client.on('event', msg => ...);
 *   const result = await client.send('get_status');
 */

const { spawn }      = require('child_process');
const { EventEmitter } = require('events');
const crypto         = require('crypto');
const path           = require('path');

const COMMAND_TIMEOUT_MS = 30_000;  // default per-command timeout

class EngineClient extends EventEmitter {
  constructor() {
    super();
    this._proc       = null;
    this._pending    = new Map();   // id → { resolve, reject, timeoutId }
    this._lineBuf    = '';
    this._started    = false;
  }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  /**
   * Spawn the Python sidecar.
   * @param {string} pythonCmd  - path to python executable
   * @param {string} projectRoot - directory that contains the `engine/` package
   */
  start(pythonCmd, projectRoot) {
    if (this._started) return;
    this._started = true;

    this._proc = spawn(
      pythonCmd,
      ['-m', 'engine.main', 'serve'],
      {
        cwd: projectRoot,
        env: { ...process.env, PYTHONPATH: projectRoot, PYTHONUNBUFFERED: '1' },
        stdio: ['pipe', 'pipe', 'pipe'],
      }
    );

    this._proc.stdout.setEncoding('utf8');
    this._proc.stdout.on('data', chunk => this._onData(chunk));

    this._proc.stderr.on('data', data => {
      const text = data.toString().trim();
      if (text) {
        console.error('[engine stderr]', text);
        this.emit('stderr', text);
      }
    });

    this._proc.on('exit', (code, signal) => {
      console.warn(`[engine] process exited — code=${code} signal=${signal}`);
      this._started = false;

      // Reject all in-flight commands.
      for (const [id, pending] of this._pending) {
        clearTimeout(pending.timeoutId);
        pending.reject(new Error(`Engine process exited (code=${code} signal=${signal})`));
        this._pending.delete(id);
      }

      this.emit('crash', { code, signal });
    });

    this._proc.on('error', err => {
      console.error('[engine] spawn error:', err.message);
      this.emit('spawn_error', err);
    });
  }

  stop() {
    if (this._proc && !this._proc.killed) {
      this._proc.kill('SIGTERM');
    }
  }

  get alive() {
    return !!(this._proc && !this._proc.killed && this._started);
  }

  // ── Sending ────────────────────────────────────────────────────────────────

  /**
   * Send a command and return a Promise that resolves with the response payload.
   * Rejects on timeout, engine crash, or ok=false.
   */
  send(name, payload = {}, timeoutMs = COMMAND_TIMEOUT_MS) {
    if (!this.alive) return Promise.reject(new Error('Engine not running'));

    return new Promise((resolve, reject) => {
      const id = crypto.randomUUID();
      const msg = JSON.stringify({ id, type: 'command', name, payload, ts: new Date().toISOString() });

      const timeoutId = setTimeout(() => {
        this._pending.delete(id);
        reject(new Error(`Command "${name}" timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      this._pending.set(id, { resolve, reject, timeoutId });
      this._proc.stdin.write(msg + '\n');
    });
  }

  // ── Receiving ──────────────────────────────────────────────────────────────

  _onData(chunk) {
    this._lineBuf += chunk;
    const lines = this._lineBuf.split('\n');
    this._lineBuf = lines.pop();            // keep partial last line

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      try {
        this._handleMsg(JSON.parse(trimmed));
      } catch {
        console.warn('[engine] non-JSON stdout:', trimmed.slice(0, 200));
      }
    }
  }

  _handleMsg(msg) {
    if (msg.type === 'response') {
      const pending = this._pending.get(msg.id);
      if (pending) {
        clearTimeout(pending.timeoutId);
        this._pending.delete(msg.id);
        if (msg.ok) {
          pending.resolve(msg.payload);
        } else {
          const err = new Error(msg.payload?.error ?? 'engine error');
          err.payload = msg.payload;
          pending.reject(err);
        }
      }
    } else if (msg.type === 'event') {
      // Emit generic 'event' with full message, and specific 'event:<name>' with payload.
      this.emit('event', msg);
      this.emit(`event:${msg.name}`, msg.payload, msg);
    }
  }
}

module.exports = { EngineClient };
