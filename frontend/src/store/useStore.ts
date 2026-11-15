import { create } from 'zustand';
import { api, ApiError, HAS_API, STATIC_BASE } from '../lib/api';
import { setLocalWaypointCrs } from '../lib/localWaypoints';
import type { AppConfig, InspectResult, MapPoint, RouteResult, Waypoint } from '../lib/types';
import { getWorkspaceKey, newWorkspaceKey, setWorkspaceKey } from '../lib/workspace';

export type ClickMode = 'inspect' | 'start' | 'end' | 'waypoint';
export type RightTab = 'inspect' | 'route' | 'waypoints';
export type View = 'map' | 'images' | 'hub';

export interface LayerState {
  visible: boolean;
  opacity: number;
  order: number;
  showCoverage: boolean;
}

interface RouteState {
  start: MapPoint | null;
  end: MapPoint | null;
  startLabel: string | null;
  endLabel: string | null;
  profile: string;
  terrainSource: string;
  result: RouteResult | null;
  loading: boolean;
  error: string | null;
}

interface State {
  config: AppConfig | null;
  configError: string | null;
  view: View;
  layers: Record<string, LayerState>;
  mode: ClickMode;
  rightTab: RightTab;
  leftOpen: boolean;
  rightOpen: boolean;
  bottomOpen: boolean;
  pointer: MapPoint | null;

  inspectPoint: MapPoint | null;
  inspect: InspectResult | null;
  inspectLoading: boolean;
  inspectError: string | null;

  route: RouteState;

  workspaceKey: string;
  waypoints: Waypoint[];
  waypointsError: string | null;
  selectedWaypoint: string | null;
  waypointDraft: { point: MapPoint; editing: Waypoint | null } | null;
  flyTo: { point: MapPoint; seq: number } | null;
  toast: { text: string; tone: 'info' | 'error' } | null;

  loadConfig(): Promise<void>;
  setLayer(id: string, patch: Partial<LayerState>): void;
  moveLayer(id: string, dir: -1 | 1): void;
  setMode(m: ClickMode): void;
  setRightTab(t: RightTab): void;
  togglePanel(p: 'leftOpen' | 'rightOpen' | 'bottomOpen'): void;
  setPointer(p: MapPoint | null): void;
  runInspect(p: MapPoint): Promise<void>;
  setRoutePoint(which: 'start' | 'end', p: MapPoint | null, label?: string | null): void;
  setRouteOption(patch: Partial<Pick<RouteState, 'profile' | 'terrainSource'>>): void;
  computeRoute(): Promise<void>;
  clearRoute(): void;
  setView(v: View): void;
  applyWorkspaceKey(key: string): Promise<void>;
  resetWorkspaceKey(): Promise<void>;
  loadWaypoints(): Promise<void>;
  openWaypointDraft(point: MapPoint, editing?: Waypoint | null): void;
  closeWaypointDraft(): void;
  saveWaypoint(name: string, description: string): Promise<void>;
  deleteWaypoint(id: string): Promise<void>;
  selectWaypoint(id: string | null, fly?: boolean): void;
  requestFlyTo(p: MapPoint): void;
  notify(text: string, tone?: 'info' | 'error'): void;
}

let inspectAbort: AbortController | null = null;
let routeAbort: AbortController | null = null;

const errText = (e: unknown) => (e instanceof ApiError || e instanceof Error ? e.message : String(e));

export const useStore = create<State>()((set, get) => ({
  config: null,
  configError: null,
  view: 'map',
  layers: {},
  mode: 'inspect',
  rightTab: 'inspect',
  leftOpen: typeof window === 'undefined' || window.innerWidth >= 900,
  rightOpen: typeof window === 'undefined' || window.innerWidth >= 1200,
  bottomOpen: true,
  pointer: null,
  inspectPoint: null,
  inspect: null,
  inspectLoading: false,
  inspectError: null,
  route: {
    start: null, end: null, startLabel: null, endLabel: null, profile: 'balanced', terrainSource: 'auto',
    result: null, loading: false, error: null,
  },
  workspaceKey: getWorkspaceKey(),
  waypoints: [],
  waypointsError: null,
  selectedWaypoint: null,
  waypointDraft: null,
  flyTo: null,
  toast: null,

  async loadConfig() {
    try {
      const config = await api.config();
      setLocalWaypointCrs(config.crs, config.boundary);
      // Free API hosts sleep when idle: wake the API now so the first inspect/route is fast.
      if (STATIC_BASE && HAS_API) api.health().catch(() => undefined);
      const layers: Record<string, LayerState> = {};
      config.layers.forEach((l, i) => {
        layers[l.id] = { visible: l.default_visible, opacity: l.default_opacity, order: i, showCoverage: l.kind === 'authoritative' && l.id !== 'ctx_ortho' && l.id !== 'ctx_dem' };
      });
      set({ config, layers, configError: null, route: { ...get().route, profile: config.routing.default_profile } });
    } catch (e) {
      set({ configError: errText(e) });
    }
  },

  setLayer(id, patch) {
    set((s) => ({ layers: { ...s.layers, [id]: { ...s.layers[id], ...patch } } }));
  },

  moveLayer(id, dir) {
    const entries = Object.entries(get().layers).sort((a, b) => a[1].order - b[1].order);
    const i = entries.findIndex(([k]) => k === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= entries.length) return;
    [entries[i], entries[j]] = [entries[j], entries[i]];
    const layers: Record<string, LayerState> = {};
    entries.forEach(([k, v], idx) => (layers[k] = { ...v, order: idx }));
    set({ layers });
  },

  setMode: (mode) => set({ mode }),
  setRightTab: (rightTab) => set({ rightTab, rightOpen: true }),
  togglePanel: (p) => set((s) => ({ [p]: !s[p] }) as Partial<State>),
  setPointer: (pointer) => set({ pointer }),

  async runInspect(p) {
    inspectAbort?.abort();
    inspectAbort = new AbortController();
    set({ inspectPoint: p, inspectLoading: true, inspectError: null, rightTab: 'inspect', rightOpen: true });
    try {
      const inspect = await api.inspect(p, inspectAbort.signal);
      set({ inspect, inspectLoading: false });
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      set({ inspect: null, inspectLoading: false, inspectError: errText(e) });
    }
  },

  setRoutePoint(which, p, label = null) {
    set((s) => ({
      route: {
        ...s.route,
        [which]: p,
        [which === 'start' ? 'startLabel' : 'endLabel']: label,
        result: null,
        error: null,
      },
      mode: 'inspect',
    }));
  },

  setRouteOption(patch) {
    set((s) => ({ route: { ...s.route, ...patch, result: null } }));
  },

  async computeRoute() {
    const { start, end, profile, terrainSource } = get().route;
    if (!start || !end) return;
    routeAbort?.abort();
    routeAbort = new AbortController();
    set((s) => ({ route: { ...s.route, loading: true, error: null, result: null }, rightTab: 'route', rightOpen: true }));
    try {
      const result = await api.route(start, end, profile, terrainSource, routeAbort.signal);
      set((s) => ({ route: { ...s.route, loading: false, result } }));
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      set((s) => ({ route: { ...s.route, loading: false, error: errText(e) } }));
    }
  },

  clearRoute() {
    routeAbort?.abort();
    set((s) => ({ route: { ...s.route, start: null, end: null, startLabel: null, endLabel: null, result: null, error: null, loading: false } }));
  },

  setView: (view) => set({ view }),

  async applyWorkspaceKey(key) {
    setWorkspaceKey(key);
    set({ workspaceKey: key.trim(), waypoints: [], selectedWaypoint: null });
    await get().loadWaypoints();
  },

  async resetWorkspaceKey() {
    const workspaceKey = newWorkspaceKey();
    set({ workspaceKey, waypoints: [], selectedWaypoint: null });
    await get().loadWaypoints();
  },

  async loadWaypoints() {
    try {
      const waypoints = await api.listWaypoints();
      set({ waypoints, waypointsError: null });
    } catch (e) {
      set({ waypointsError: errText(e) });
    }
  },

  openWaypointDraft(point, editing = null) {
    set({ waypointDraft: { point, editing }, mode: 'inspect' });
  },

  closeWaypointDraft: () => set({ waypointDraft: null }),

  async saveWaypoint(name, description) {
    const draft = get().waypointDraft;
    if (!draft) return;
    const wp = draft.editing
      ? await api.updateWaypoint(draft.editing.id, { name, description })
      : await api.createWaypoint(name, description, draft.point);
    set((s) => ({
      waypoints: draft.editing ? s.waypoints.map((w) => (w.id === wp.id ? wp : w)) : [...s.waypoints, wp],
      waypointDraft: null,
      selectedWaypoint: wp.id,
      rightTab: 'waypoints',
      rightOpen: true,
    }));
  },

  async deleteWaypoint(id) {
    try {
      await api.deleteWaypoint(id);
      set((s) => ({ waypoints: s.waypoints.filter((w) => w.id !== id), selectedWaypoint: s.selectedWaypoint === id ? null : s.selectedWaypoint }));
    } catch (e) {
      get().notify(errText(e), 'error');
    }
  },

  selectWaypoint(id, fly = false) {
    set({ selectedWaypoint: id });
    const wp = get().waypoints.find((w) => w.id === id);
    if (wp && fly) get().requestFlyTo({ x: wp.x, y: wp.y });
  },

  requestFlyTo(point) {
    set((s) => ({ flyTo: { point, seq: (s.flyTo?.seq ?? 0) + 1 } }));
  },

  notify(text, tone = 'info') {
    set({ toast: { text, tone } });
    window.setTimeout(() => {
      if (get().toast?.text === text) set({ toast: null });
    }, 4500);
  },
}));
