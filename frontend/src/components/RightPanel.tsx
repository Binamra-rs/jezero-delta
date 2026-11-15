import { useState } from 'react';
import { useShallow } from 'zustand/react/shallow';
import type { Sample, Waypoint } from '../lib/types';
import { fmtDistance, fmtLat, fmtLon, fmtRes, fmtValue, fmtXY } from '../lib/format';
import { useStore, type RightTab } from '../store/useStore';
import { IChevronR, ICopy, IEdit, IEnd, IKey, IStart, ITarget, ITrash, IWarn } from './icons';
import { isValidWorkspaceKey } from '../lib/workspace';
import { WAYPOINT_STORE } from '../lib/api';
import { Button, Label, Notice, Row, Spinner } from './ui';

function SampleRow({ name, s, digits = 2 }: { name: string; s: Sample | null; digits?: number }) {
  if (!s) return <Row k={name} v={<span className="text-faint">—</span>} />;
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-rim/60 py-2 last:border-0"
      title={`${s.title} · ${fmtRes(s.resolution_m)} · ${s.kind === 'derived' ? 'derived' : 'measured'}`}>
      <div className="text-xs text-dim">{name}</div>
      <div className={`text-sm tabular-nums ${s.in_coverage ? 'text-ink' : 'text-faint'}`}>
        {s.in_coverage ? fmtValue(s.value, s.unit, digits) : 'No data'}
      </div>
    </div>
  );
}

function InspectTab() {
  const { inspect, inspectLoading, inspectError, inspectPoint } = useStore(useShallow((s) => ({
    inspect: s.inspect, inspectLoading: s.inspectLoading, inspectError: s.inspectError, inspectPoint: s.inspectPoint,
  })));
  const setRoutePoint = useStore((s) => s.setRoutePoint);
  const openDraft = useStore((s) => s.openWaypointDraft);
  const [showAll, setShowAll] = useState(false);
  if (!inspectPoint) {
    return <p className="px-1 text-xs text-faint">Click the map to read values.</p>;
  }
  if (inspectError) return <Notice tone="error">{inspectError}</Notice>;
  if (inspectLoading || !inspect) return <div className="flex items-center gap-2 text-xs text-dim"><Spinner /> Reading…</div>;
  const { location: loc, summary } = inspect;
  return (
    <div className="space-y-4">
      <div className="px-1 text-sm text-ink tabular-nums" title={`x ${fmtXY(loc.x)} · y ${fmtXY(loc.y)} (${loc.crs_id} v${loc.crs_version})`}>
        {fmtLat(loc.lat)} · {fmtLon(loc.lon_e)}
      </div>
      <section>
        <SampleRow name="Elevation" s={summary.elevation} />
        <SampleRow name="Slope" s={summary.slope} digits={1} />
        <SampleRow name="Thermal inertia" s={summary.thermal_inertia} digits={0} />
        <SampleRow name="Roughness" s={summary.roughness} />
      </section>
      <div className="flex flex-wrap gap-1.5">
        <Button onClick={() => setRoutePoint('start', { x: loc.x, y: loc.y })} title="Route start"><IStart /> A</Button>
        <Button onClick={() => setRoutePoint('end', { x: loc.x, y: loc.y })} title="Route destination"><IEnd /> B</Button>
        <Button onClick={() => openDraft({ x: loc.x, y: loc.y })}>Save</Button>
      </div>
      <section>
        <button onClick={() => setShowAll(!showAll)} className="text-2xs font-medium text-faint hover:text-ink">
          {showAll ? 'Fewer' : 'All layers'}
        </button>
        {showAll && (
          <div className="mt-1">
            {Object.values(inspect.layers).map((s) => <SampleRow key={s.layer} name={s.title} s={s} />)}
          </div>
        )}
      </section>
    </div>
  );
}

function RouteTab() {
  const route = useStore((s) => s.route);
  const { result, loading, error } = route;
  if (loading) return <div className="flex items-center gap-2 text-xs text-dim"><Spinner /> Planning…</div>;
  if (error) return <Notice tone="error">{error}</Notice>;
  if (!result) {
    return <p className="px-1 text-xs text-faint">Pick <span className="text-signal">A</span> and <span className="text-ochre">B</span> below.</p>;
  }
  const s = result.stats;
  return (
    <div className="space-y-4">
      <section>
        <Row k="Distance" v={fmtDistance(s.distance_m)} />
        <Row k="Ascent / descent" v={`${s.ascent_m.toFixed(0)} / ${s.descent_m.toFixed(0)} m`} />
        <Row k="Slope avg / max" v={`${s.mean_slope_deg.toFixed(1)}° / ${s.max_slope_deg.toFixed(1)}°`} />
      </section>
      <p className="flex items-start gap-1.5 px-1 text-[11px] leading-relaxed text-faint" title={result.limitations}>
        <IWarn className="mt-0.5 shrink-0 text-caution/70" width={12} height={12} />
        Estimate only, not a safe route · {result.terrain.title}, {fmtRes(result.terrain.resolution_m)} · {result.profile.label}
      </p>
    </div>
  );
}

function WaypointItem({ w }: { w: Waypoint }) {
  const selected = useStore((s) => s.selectedWaypoint === w.id);
  const select = useStore((s) => s.selectWaypoint);
  const setRoutePoint = useStore((s) => s.setRoutePoint);
  const openDraft = useStore((s) => s.openWaypointDraft);
  const del = useStore((s) => s.deleteWaypoint);
  const [confirm, setConfirm] = useState(false);
  return (
    <div className={`mb-1 rounded-xl px-3 py-2 transition-colors ${selected ? 'bg-card' : 'hover:bg-card/60'}`}>
      <button className="w-full text-left" onClick={() => select(w.id, true)}>
        <div className="text-[13px] text-ink">{w.name}</div>
        <div className="font-mono text-[10px] text-faint">{fmtLat(w.lat)} · {fmtLon(w.lon_e)}</div>
      </button>
      {selected && (
        <div className="mt-2 space-y-2">
          {w.description && <p className="whitespace-pre-wrap text-xs leading-relaxed text-dim">{w.description}</p>}
          <div className="flex flex-wrap gap-1.5">
            <Button onClick={() => setRoutePoint('start', { x: w.x, y: w.y }, w.name)}><IStart /> A</Button>
            <Button onClick={() => setRoutePoint('end', { x: w.x, y: w.y }, w.name)}><IEnd /> B</Button>
            <Button variant="ghost" onClick={() => select(w.id, true)} aria-label="Centre map"><ITarget /></Button>
            <Button variant="ghost" onClick={() => openDraft({ x: w.x, y: w.y }, w)} aria-label="Edit"><IEdit /></Button>
            {confirm ? (
              <Button variant="danger" onClick={() => void del(w.id)}>Delete?</Button>
            ) : (
              <Button variant="ghost" onClick={() => setConfirm(true)} aria-label="Delete"><ITrash /></Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function WorkspaceKeyBox() {
  const key = useStore((s) => s.workspaceKey);
  const apply = useStore((s) => s.applyWorkspaceKey);
  const reset = useStore((s) => s.resetWorkspaceKey);
  const notify = useStore((s) => s.notify);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [error, setError] = useState<string | null>(null);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(key);
      notify(WAYPOINT_STORE === 'local' ? 'Workspace key copied.' : 'Workspace key copied. Paste it on another device to see these waypoints there.');
    } catch {
      notify('Copy failed — select the key and copy it manually.', 'error');
    }
  };
  return (
    <div className="rounded-xl bg-card p-3">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 text-left text-xs text-dim hover:text-ink">
        <IKey /> <span className="flex-1">Workspace key</span>
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          {WAYPOINT_STORE === 'local' ? (
            <p className="text-[11px] leading-relaxed text-faint">
              Saved in this browser only. Export a copy from the Hub.
            </p>
          ) : (
            <p className="text-[11px] leading-relaxed text-faint">
              Your private key for these waypoints. Use it on another device to sync; keep it secret.
            </p>
          )}
          <div className="flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded-lg bg-panel px-2 py-1.5 font-mono text-[11px] text-ink">{key}</code>
            <Button variant="ghost" onClick={() => void copy()} aria-label="Copy key"><ICopy /></Button>
          </div>
          <div className="flex gap-2">
            <input className="jz-input min-w-0 flex-1" placeholder="Paste another key" value={draft} onChange={(e) => setDraft(e.target.value)} />
            <Button
              disabled={!draft.trim()}
              onClick={() => {
                if (!isValidWorkspaceKey(draft)) { setError('Keys are 32–128 letters, digits, "-" or "_".'); return; }
                setError(null); setDraft(''); void apply(draft);
              }}
            >Use</Button>
          </div>
          {error && <Notice tone="error">{error}</Notice>}
          <button onClick={() => void reset()} className="text-[11px] text-faint underline-offset-2 hover:text-alert hover:underline">
            New empty workspace
          </button>
        </div>
      )}
    </div>
  );
}

function WaypointsTab() {
  const { waypoints, waypointsError } = useStore(useShallow((s) => ({ waypoints: s.waypoints, waypointsError: s.waypointsError })));
  const setMode = useStore((s) => s.setMode);
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>{waypoints.length || ''}</Label>
        <Button variant="primary" onClick={() => setMode('waypoint')}>+ Add</Button>
      </div>
      {waypointsError && <Notice tone="error">{waypointsError}</Notice>}
      {waypoints.length === 0 && <p className="px-1 text-xs text-faint">None yet.</p>}
      <div>{waypoints.map((w) => <WaypointItem key={w.id} w={w} />)}</div>
      <WorkspaceKeyBox />
    </div>
  );
}

const TABS: { id: RightTab; label: string }[] = [
  { id: 'inspect', label: 'Point' },
  { id: 'route', label: 'Route' },
  { id: 'waypoints', label: 'Waypoints' },
];

export default function RightPanel() {
  const tab = useStore((s) => s.rightTab);
  const setTab = useStore((s) => s.setRightTab);
  const toggle = useStore((s) => s.togglePanel);
  return (
    <aside className="flex h-full w-[340px] max-w-[90vw] flex-col bg-panel">
      <div className="m-3 mb-1 flex items-center gap-1 rounded-full bg-void/60 p-1">
        <button onClick={() => toggle('rightOpen')} className="px-2 text-faint hover:text-ink" aria-label="Collapse panel"><IChevronR /></button>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex-1 rounded-full py-1.5 text-xs font-medium transition-colors ${tab === t.id ? 'bg-card text-ink shadow-soft' : 'text-faint hover:text-dim'}`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {tab === 'inspect' && <InspectTab />}
        {tab === 'route' && <RouteTab />}
        {tab === 'waypoints' && <WaypointsTab />}
      </div>
    </aside>
  );
}
