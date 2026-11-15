/**
 * Browser-local waypoint store (VITE_WAYPOINTS=local).
 *
 * Used on free API hosts that have no persistent disk, where the server's
 * SQLite file would be wiped whenever the instance sleeps or redeploys.
 * Waypoints are kept in localStorage under the current workspace key, with the
 * same shape and validation as the API, so the rest of the app is unchanged.
 * Use the Survival Hub export to keep an offline copy.
 */
import { makeConverter, type Converter } from './crs';
import type { CrsInfo, MapPoint, Waypoint } from './types';
import { getWorkspaceKey } from './workspace';

let conv: Converter | null = null;
let crsInfo: CrsInfo | null = null;
let boundary: [number, number, number, number] | null = null;

export function setLocalWaypointCrs(crs: CrsInfo, bounds: [number, number, number, number]): void {
  crsInfo = crs;
  conv = makeConverter(crs);
  boundary = bounds;
}

const storageKey = () => `jezero.waypoints.${getWorkspaceKey()}`;
const memory = new Map<string, Waypoint[]>();

function read(): Waypoint[] {
  try {
    const raw = localStorage.getItem(storageKey());
    if (!raw) return [];
    const list = JSON.parse(raw) as unknown;
    return Array.isArray(list) ? (list as Waypoint[]) : [];
  } catch {
    return memory.get(storageKey()) ?? [];
  }
}

function write(list: Waypoint[]): void {
  try {
    localStorage.setItem(storageKey(), JSON.stringify(list));
  } catch {
    memory.set(storageKey(), list); // storage blocked: keep for this tab only
  }
}

function validate(name: string | undefined, description: string | undefined): void {
  if (name !== undefined && (name.trim().length < 1 || name.length > 120)) throw new Error('Name must be 1–120 characters.');
  if (description !== undefined && description.length > 4000) throw new Error('Description must be at most 4000 characters.');
}

function locate(p: MapPoint) {
  if (!conv || !crsInfo || !boundary) throw new Error('Map configuration not loaded yet.');
  const [x0, y0, x1, y1] = boundary;
  if (!(p.x >= x0 && p.x <= x1 && p.y >= y0 && p.y <= y1)) throw new Error('Waypoint is outside the Jezero project boundary');
  const { lon_e, lat } = conv.toGeographic(p.x, p.y);
  return { x: p.x, y: p.y, lon_e, lat, crs_id: crsInfo.id, crs_version: crsInfo.version };
}

export const localWaypoints = {
  async list(): Promise<Waypoint[]> {
    return read();
  },

  async create(name: string, description: string, p: MapPoint): Promise<Waypoint> {
    validate(name, description);
    const now = new Date().toISOString();
    const wp: Waypoint = {
      id: crypto.randomUUID(), workspace_id: 'local', name: name.trim(), description,
      ...locate(p), created_at: now, updated_at: now,
    };
    write([...read(), wp]);
    return wp;
  },

  async update(id: string, patch: { name?: string; description?: string; location?: MapPoint }): Promise<Waypoint> {
    validate(patch.name, patch.description);
    const list = read();
    const i = list.findIndex((w) => w.id === id);
    if (i < 0) throw new Error('Waypoint not found');
    const wp: Waypoint = {
      ...list[i],
      ...(patch.name !== undefined ? { name: patch.name.trim() } : {}),
      ...(patch.description !== undefined ? { description: patch.description } : {}),
      ...(patch.location ? locate(patch.location) : {}),
      updated_at: new Date().toISOString(),
    };
    list[i] = wp;
    write(list);
    return wp;
  },

  async remove(id: string): Promise<void> {
    write(read().filter((w) => w.id !== id));
  },
};
