import { useMemo } from 'react';
import { makeConverter } from '../lib/crs';
import { fmtLat, fmtLon, fmtXY } from '../lib/format';
import type { MapPoint } from '../lib/types';
import { useStore } from '../store/useStore';
import { IClose, IDown, IEnd, IRoute, IStart, IUp } from './icons';
import { Button, Label, Spinner } from './ui';

const SOURCE_LABEL: Record<string, string> = {
  auto: 'Auto terrain', ctx: 'CTX · 20 m', hirise_1: 'HiRISE 1 · 1 m', hirise_2: 'HiRISE 2 · 1 m',
};

function PointSlot({ which }: { which: 'start' | 'end' }) {
  const route = useStore((s) => s.route);
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  const setPoint = useStore((s) => s.setRoutePoint);
  const config = useStore((s) => s.config);
  const conv = useMemo(() => (config ? makeConverter(config.crs) : null), [config]);
  const p: MapPoint | null = route[which];
  const label = which === 'start' ? route.startLabel : route.endLabel;
  const color = which === 'start' ? 'text-signal' : 'text-ochre';
  const armed = mode === which;
  const geo = p && conv ? conv.toGeographic(p.x, p.y) : null;
  return (
    <div className={`flex min-w-0 items-center gap-2 rounded-xl px-3 py-2 ${armed ? 'bg-signal/10 ring-1 ring-signal/40' : 'bg-card'}`}>
      <button onClick={() => setMode(armed ? 'inspect' : which)} className={`${color}`} aria-label={`Pick ${which} on map`} title="Pick on map">
        {which === 'start' ? <IStart /> : <IEnd />}
      </button>
      <div className="min-w-0 flex-1">
        {p && geo ? (
          <>
            <div className="truncate text-xs text-ink">{label ?? (which === 'start' ? 'Start' : 'Destination')}</div>
            <div className="truncate font-mono text-[10px] text-faint">{fmtLat(geo.lat)} {fmtLon(geo.lon_e)}</div>
          </>
        ) : (
          <button onClick={() => setMode(which)} className="text-left text-xs text-faint hover:text-dim">
            {armed ? 'Click the map…' : which === 'start' ? 'Start' : 'Destination'}
          </button>
        )}
      </div>
      {p && (
        <button onClick={() => setPoint(which, null)} className="text-faint hover:text-ink" aria-label={`Clear ${which}`}><IClose width={12} height={12} /></button>
      )}
    </div>
  );
}

function Coordinates() {
  const pointer = useStore((s) => s.pointer);
  const config = useStore((s) => s.config);
  const conv = useMemo(() => (config ? makeConverter(config.crs) : null), [config]);
  const g = pointer && conv ? conv.toGeographic(pointer.x, pointer.y) : null;
  return (
    <div className="hidden min-w-[190px] px-1 text-right text-[11px] text-faint tabular-nums lg:block" title={pointer ? `x ${fmtXY(pointer.x)} · y ${fmtXY(pointer.y)}` : undefined}>
      {pointer && g ? <>{fmtLat(g.lat)} · {fmtLon(g.lon_e)}</> : null}
    </div>
  );
}

export default function BottomBar() {
  const config = useStore((s) => s.config);
  const route = useStore((s) => s.route);
  const setOpt = useStore((s) => s.setRouteOption);
  const compute = useStore((s) => s.computeRoute);
  const clear = useStore((s) => s.clearRoute);
  const open = useStore((s) => s.bottomOpen);
  const toggle = useStore((s) => s.togglePanel);
  if (!config) return null;
  const profiles = Object.values(config.routing.profiles);
  const ready = route.start && route.end && !route.loading;
  return (
    <div className="bg-panel">
      <div className="flex items-center gap-2 px-3 py-1.5">
        <IRoute className="text-ochre" />
        <Label>Route</Label>
        <div className="flex-1" />
        <button onClick={() => toggle('bottomOpen')} className="text-faint hover:text-ink" aria-label={open ? 'Collapse route bar' : 'Expand route bar'}>
          {open ? <IDown /> : <IUp />}
        </button>
      </div>
      {open && (
        <div className="flex flex-wrap items-end gap-3 px-3 pb-3">
          <div className="grid min-w-[260px] flex-1 grid-cols-1 gap-2 sm:grid-cols-2 lg:max-w-[520px]">
            <PointSlot which="start" />
            <PointSlot which="end" />
          </div>
          <label className="flex flex-col gap-1">
            <select aria-label="Cost profile"
              value={route.profile}
              onChange={(e) => setOpt({ profile: e.target.value })}
              className="jz-select"
              title={config.routing.profiles[route.profile]?.description}
            >
              {profiles.map((p) => <option key={p.name} value={p.name}>{p.label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <select aria-label="Terrain source" value={route.terrainSource} onChange={(e) => setOpt({ terrainSource: e.target.value })} className="jz-select">
              {config.routing.terrain_sources.map((s) => <option key={s} value={s}>{SOURCE_LABEL[s] ?? s}</option>)}
            </select>
          </label>
          <div className="flex gap-2">
            <Button variant="primary" disabled={!ready} onClick={() => void compute()}>
              {route.loading ? <Spinner /> : <IRoute />} Go
            </Button>
            <Button variant="ghost" onClick={clear} disabled={!route.start && !route.end}>Clear</Button>
          </div>
          <div className="flex-1" />
          <Coordinates />
        </div>
      )}
    </div>
  );
}
