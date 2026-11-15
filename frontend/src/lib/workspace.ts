/**
 * Anonymous workspace key — replaces user accounts.
 *
 * A random 43-character URL-safe key (256 bits) is generated in the browser
 * and sent with waypoint requests as `X-Workspace-Key`. The server stores
 * only its SHA-256 hash. Waypoints themselves live on the server (SQLite); to see the
 * same waypoints on another device, copy this key there ("Use another key").
 */
const KEY = 'jezero.workspaceKey';
const VALID = /^[A-Za-z0-9_-]{32,128}$/;
let memoryKey: string | null = null;

function generate(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  let s = '';
  bytes.forEach((b) => (s += String.fromCharCode(b)));
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function isValidWorkspaceKey(k: string): boolean {
  return VALID.test(k.trim());
}

export function getWorkspaceKey(): string {
  try {
    const stored = localStorage.getItem(KEY);
    if (stored && VALID.test(stored)) return stored;
    const k = generate();
    localStorage.setItem(KEY, k);
    return k;
  } catch {
    memoryKey ??= generate(); // storage blocked: key lasts for this tab only
    return memoryKey;
  }
}

export function setWorkspaceKey(k: string): void {
  const key = k.trim();
  if (!VALID.test(key)) throw new Error('A workspace key is 32–128 letters, digits, "-" or "_".');
  try {
    localStorage.setItem(KEY, key);
  } catch {
    memoryKey = key;
  }
}

export function newWorkspaceKey(): string {
  const k = generate();
  setWorkspaceKey(k);
  return k;
}
