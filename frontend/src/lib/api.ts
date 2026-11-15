import type { AppConfig, CameraGroup, InspectResult, LayerInfo, MapPoint, RawImagePage, RawImageQuery, RouteResult, Waypoint } from './types';
import { getWorkspaceKey } from './workspace';
import { localWaypoints } from './localWaypoints';

const RAW_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/+$/, '') ?? '';

/**
 * Static map data (config.json, coverage, pre-rendered tiles) written by
 * backend/scripts/export_static.py, e.g. "/map". When set, the map loads with
 * no API at all; the API is only needed for inspect, routing and raw images.
 */
export const STATIC_BASE = (import.meta.env.VITE_STATIC_BASE as string | undefined)?.replace(/\/+$/, '') ?? '';

/** 'local' keeps waypoints in this browser (for API hosts without a persistent disk). */
export const WAYPOINT_STORE: 'api' | 'local' =
  ((import.meta.env.VITE_WAYPOINTS as string | undefined) ?? (STATIC_BASE ? 'local' : 'api')) === 'local' ? 'local' : 'api';

if (import.meta.env.PROD && RAW_BASE && /localhost|127\.0\.0\.1/.test(RAW_BASE)) {
  // Brief §17.9 — a production build must never depend on localhost.
  throw new Error('VITE_API_BASE must point at the deployed API in production builds, not localhost');
}
if (import.meta.env.PROD && !RAW_BASE && !STATIC_BASE) {
  throw new Error('Set VITE_API_BASE (deployed API) and/or VITE_STATIC_BASE (static map data) for production builds');
}

export const API_BASE = RAW_BASE;
export const HAS_API = Boolean(RAW_BASE) || !import.meta.env.PROD;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit & { workspace?: boolean } = {}, signal?: AbortSignal): Promise<T> {
  if (!HAS_API) throw new ApiError(0, 'This deployment has no API configured (VITE_API_BASE), so this feature is unavailable.');
  const { workspace, ...rest } = init;
  const headers = new Headers(rest.headers);
  if (rest.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (workspace) headers.set('X-Workspace-Key', getWorkspaceKey());
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...rest, headers, signal });
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e;
    throw new ApiError(0, STATIC_BASE
      ? 'Cannot reach the Jezero API. The free API host sleeps when idle and can take up to a minute to wake — please try again.'
      : 'Cannot reach the Jezero API. Check that the backend is running.');
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const body = text ? safeJson(text) : null;
  if (!res.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? (body as { detail: unknown }).detail : null;
    const msg = typeof detail === 'string'
      ? detail
      : Array.isArray(detail) ? detail.map((d: { msg?: string }) => d.msg ?? '').join('; ') : `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

async function staticJson<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${STATIC_BASE}/${path}`);
  } catch {
    throw new ApiError(0, 'Cannot load the map data. Check your connection and retry.');
  }
  const body = res.ok ? safeJson(await res.text()) : null;
  if (!body) throw new ApiError(res.status, `Map data ${path} is missing from this deployment (run backend/scripts/export_static.py)`);
  return body as T;
}

export const tileUrl = (layer: LayerInfo, config: AppConfig) =>
  STATIC_BASE && config.static
    ? `${STATIC_BASE}/${config.static.tile_template.replace('{layer}', encodeURIComponent(layer.id))}`
    : `${API_BASE}/api/v1/tiles/${encodeURIComponent(layer.id)}/{z}/{x}/{y}.png?v=${encodeURIComponent(config.catalog_version)}`;

/** Deepest zoom level that has tiles for this layer (beyond it OpenLayers up-samples). */
export const tileMaxZoom = (layer: LayerInfo, config: AppConfig) =>
  STATIC_BASE && config.static && layer.static_max_zoom != null ? layer.static_max_zoom : config.tilegrid.resolutions.length - 1;

function qs(params: Record<string, string | number | null | undefined>): string {
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== null && v !== undefined && v !== '') u.set(k, String(v));
  });
  return u.toString();
}

export const api = {
  config: () => (STATIC_BASE ? staticJson<AppConfig>('config.json') : request<AppConfig>('/api/v1/config')),
  health: () => request<{ status: string; version: string }>('/healthz'),
  coverage: (layer: LayerInfo) =>
    STATIC_BASE && layer.coverage_geojson
      ? staticJson<object>(layer.coverage_geojson)
      : request<object>(`/api/v1/layers/${encodeURIComponent(layer.id)}/coverage`),
  inspect: (p: MapPoint, signal?: AbortSignal) => request<InspectResult>(`/api/v1/inspect?x=${p.x}&y=${p.y}`, {}, signal),
  route: (start: MapPoint, end: MapPoint, profile: string, terrainSource: string, signal?: AbortSignal) =>
    request<RouteResult>(
      '/api/v1/route',
      { method: 'POST', body: JSON.stringify({ start, end, profile, terrain_source: terrainSource }) },
      signal,
    ),

  // waypoints — scoped by the anonymous workspace key (no accounts); in 'local'
  // mode they live in this browser's storage under the same key
  listWaypoints: () =>
    WAYPOINT_STORE === 'local' ? localWaypoints.list() : request<Waypoint[]>('/api/v1/waypoints', { workspace: true }),
  createWaypoint: (name: string, description: string, p: MapPoint) =>
    WAYPOINT_STORE === 'local'
      ? localWaypoints.create(name, description, p)
      : request<Waypoint>('/api/v1/waypoints', { method: 'POST', workspace: true, body: JSON.stringify({ name, description, location: p }) }),
  updateWaypoint: (id: string, patch: { name?: string; description?: string; location?: MapPoint }) =>
    WAYPOINT_STORE === 'local'
      ? localWaypoints.update(id, patch)
      : request<Waypoint>(`/api/v1/waypoints/${id}`, { method: 'PATCH', workspace: true, body: JSON.stringify(patch) }),
  deleteWaypoint: (id: string) =>
    WAYPOINT_STORE === 'local' ? localWaypoints.remove(id) : request<void>(`/api/v1/waypoints/${id}`, { method: 'DELETE', workspace: true }),

  // NASA Mars 2020 raw images (proxied by the backend)
  rawImages: (q: RawImageQuery, signal?: AbortSignal) =>
    request<RawImagePage>(`/api/v1/raw-images?${qs({ ...q })}`, {}, signal),
  rawCameras: () => request<{ cameras: CameraGroup[] }>('/api/v1/raw-images/cameras'),
};
