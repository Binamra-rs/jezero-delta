import { useMemo, useState } from 'react';
import { makeConverter } from '../lib/crs';
import { parseCoordinateQuery } from '../lib/format';
import { useStore, type ClickMode, type View } from '../store/useStore';
import { ICrosshair, IEnd, IImage, ILayers, IMap, ISearch, IShieldPlus, IStart, IWaypoint } from './icons';

const TOOLS: { mode: ClickMode; label: string; icon: JSX.Element; key: string }[] = [
  { mode: 'inspect', label: 'Inspect', icon: <ICrosshair />, key: 'I' },
  { mode: 'start', label: 'Start A', icon: <IStart />, key: 'A' },
  { mode: 'end', label: 'Dest. B', icon: <IEnd />, key: 'B' },
  { mode: 'waypoint', label: 'Waypoint', icon: <IWaypoint />, key: 'W' },
];

const VIEWS: { id: View; label: string; icon: JSX.Element }[] = [
  { id: 'map', label: 'Map', icon: <IMap /> },
  { id: 'images', label: 'Images', icon: <IImage /> },
  { id: 'hub', label: 'Hub', icon: <IShieldPlus /> },
];

function Search() {
  const config = useStore((s) => s.config);
  const waypoints = useStore((s) => s.waypoints);
  const flyTo = useStore((s) => s.requestFlyTo);
  const select = useStore((s) => s.selectWaypoint);
  const inspect = useStore((s) => s.runInspect);
  const notify = useStore((s) => s.notify);
  const [q, setQ] = useState('');
  const conv = useMemo(() => (config ? makeConverter(config.crs) : null), [config]);
  const matches = q.length >= 2 ? waypoints.filter((w) => w.name.toLowerCase().includes(q.toLowerCase())).slice(0, 6) : [];

  const submit = () => {
    if (!config || !conv) return;
    const parsed = parseCoordinateQuery(q);
    if (parsed) {
      const p = parsed.kind === 'xy' ? { x: parsed.x, y: parsed.y } : conv.toProjected(parsed.lon, parsed.lat);
      const [minx, miny, maxx, maxy] = config.boundary;
      if (p.x < minx || p.x > maxx || p.y < miny || p.y > maxy) {
        notify('Those coordinates are outside the Jezero project area.', 'error');
        return;
      }
      flyTo(p);
      void inspect(p);
      setQ('');
      return;
    }
    if (matches[0]) {
      select(matches[0].id, true);
      setQ('');
      return;
    }
    notify('Try "18.44, 77.45" or a waypoint name.', 'error');
  };

  return (
    <div className="relative hidden w-[220px] lg:block">
      <ISearch className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        placeholder="Search"
        className="jz-input w-full rounded-full !py-2 !pl-9"
        aria-label="Search coordinates or waypoints"
      />
      {matches.length > 0 && (
        <div className="absolute left-0 right-0 top-full z-50 mt-2 overflow-hidden rounded-xl bg-card shadow-soft">
          {matches.map((w) => (
            <button key={w.id} onClick={() => { select(w.id, true); setQ(''); }} className="block w-full px-3 py-2 text-left text-xs text-ink hover:bg-rim">
              {w.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function TopBar() {
  const config = useStore((s) => s.config);
  const view = useStore((s) => s.view);
  const setView = useStore((s) => s.setView);
  const mode = useStore((s) => s.mode);
  const setMode = useStore((s) => s.setMode);
  const toggle = useStore((s) => s.togglePanel);
  return (
    <header className="flex h-14 items-center gap-3 bg-hull px-4">
      {view === 'map' && (
        <button onClick={() => toggle('leftOpen')} className="rounded-lg p-1.5 text-dim hover:bg-card hover:text-ink" aria-label="Toggle layer panel"><ILayers /></button>
      )}
      <span className="pr-1 text-[15px] font-medium text-ink">Jezero</span>

      <nav className="flex items-center gap-1 rounded-full bg-panel p-1" aria-label="Views">
        {VIEWS.map((v) => (
          <button
            key={v.id}
            onClick={() => setView(v.id)}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${view === v.id ? 'bg-card text-ink shadow-soft' : 'text-faint hover:text-dim'}`}
            aria-pressed={view === v.id}
          >
            {v.icon}
            <span className="hidden md:inline">{v.label}</span>
          </button>
        ))}
      </nav>

      {view === 'map' && (
        <nav className="flex items-center gap-0.5 rounded-full bg-panel p-1" aria-label="Map tools">
          {TOOLS.map((t) => (
            <button
              key={t.mode}
              onClick={() => setMode(t.mode)}
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs transition-colors ${mode === t.mode ? 'bg-card text-ink shadow-soft' : 'text-faint hover:text-dim'}`}
              aria-pressed={mode === t.mode}
              title={`${t.label} (${t.key})`}
            >
              {t.icon}
              <span className="hidden 2xl:inline">{t.label}</span>
            </button>
          ))}
        </nav>
      )}
      <div className="flex-1" />
      {config && view === 'map' && <Search />}
    </header>
  );
}
