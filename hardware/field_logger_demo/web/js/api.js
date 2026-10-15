// The page talks only to its own backend on 127.0.0.1 (same origin). Device events arrive over the WebSocket.
import { bus } from './util.js';

async function handle(r) {
  let body = null;
  try { body = await r.json(); } catch (e) { body = null; }
  if (!r.ok) {
    const msg = body && body.detail ? body.detail : `HTTP ${r.status}`;
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return body;
}

export async function get(path) { return handle(await fetch(path, { cache: 'no-store' })); }

export async function post(path, data = {}) {
  return handle(await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }));
}

let ws = null;
let retry = 0;
export function openSocket() {
  const url = `ws://${location.host}/ws`;
  ws = new WebSocket(url);
  ws.onopen = () => { retry = 0; bus.emit('ws-open'); };
  ws.onmessage = (m) => {
    let ev;
    try { ev = JSON.parse(m.data); } catch (e) { return; }
    bus.emit(`ws:${ev.type}`, ev);
  };
  ws.onclose = () => {
    bus.emit('ws-closed');
    retry = Math.min(retry + 1, 5);
    setTimeout(openSocket, 400 * retry);
  };
}
