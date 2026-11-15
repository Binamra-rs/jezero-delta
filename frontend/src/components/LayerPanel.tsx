import { useState } from 'react';
import type { LayerInfo } from '../lib/types';
import { fmtRes } from '../lib/format';
import { useStore } from '../store/useStore';
import { IChevronL, IDown, IEye, IEyeOff, IInfo, IUp } from './icons';
import { Label } from './ui';

const GROUP_TITLES: Record<string, string> = {
  imagery: 'Imagery', elevation: 'Elevation', thermophysical: 'Thermal', derived: 'Terrain',
};

export function LegendBar({ layer }: { layer: LayerInfo }) {
  const { stops, range } = layer.legend;
  const grad = `linear-gradient(90deg, ${stops.map((s) => `${s.color} ${s.position * 100}%`).join(', ')})`;
  const fmt = (v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(1));
  return (
    <div>
      <div className="h-1.5 rounded-sm" style={{ background: grad }} />
      {range && (
        <div className="mt-0.5 flex justify-between font-mono text-[10px] text-faint tabular-nums">
          <span>{fmt(range[0])}</span>
          <span>{layer.unit}</span>
          <span>{fmt(range[1])}</span>
        </div>
      )}
    </div>
  );
}

function LayerRow({ layer }: { layer: LayerInfo }) {
  const st = useStore((s) => s.layers[layer.id]);
  const setLayer = useStore((s) => s.setLayer);
  const moveLayer = useStore((s) => s.moveLayer);
  const [open, setOpen] = useState(false);
  if (!st) return null;
  const cov = layer.coverage?.boundary_fraction;
  return (
    <div className={`group mx-2 my-1 rounded-xl px-3 py-2 transition-colors hover:bg-card ${st.visible ? 'bg-card/60' : 'opacity-75'}`}>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setLayer(layer.id, { visible: !st.visible })}
          className={`rounded p-0.5 ${st.visible ? 'text-ink' : 'text-faint hover:text-dim'}`}
          aria-pressed={st.visible}
          aria-label={`${st.visible ? 'Hide' : 'Show'} ${layer.title}`}
        >
          {st.visible ? <IEye /> : <IEyeOff />}
        </button>
        <div className="min-w-0 flex-1">
          <div className={`truncate text-[13px] ${st.visible ? 'text-ink' : 'text-dim'}`}>{layer.title}</div>
        </div>
        <div className="flex flex-col opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <button className="text-faint hover:text-ink" onClick={() => moveLayer(layer.id, 1)} aria-label="Move layer up"><IUp width={12} height={12} /></button>
          <button className="text-faint hover:text-ink" onClick={() => moveLayer(layer.id, -1)} aria-label="Move layer down"><IDown width={12} height={12} /></button>
        </div>
        <button className={`p-0.5 ${open ? 'text-signal' : 'text-faint hover:text-ink'}`} onClick={() => setOpen(!open)} aria-label="Layer details" aria-expanded={open}>
          <IInfo />
        </button>
      </div>
      {st.visible && (
        <div className="mt-2 space-y-2 pl-7">
          {layer.style !== 'gray' && <LegendBar layer={layer} />}
          <input
            type="range" min={0} max={1} step={0.05} value={st.opacity}
            onChange={(e) => setLayer(layer.id, { opacity: Number(e.target.value) })}
            className="jz-range w-full" aria-label={`${layer.title} opacity`} title={`Opacity ${Math.round(st.opacity * 100)}%`}
          />
        </div>
      )}
      {open && (
        <div className="mt-2 space-y-1 rounded-lg bg-void/40 p-2.5 text-[11px] leading-relaxed text-dim">
          <div>
            {layer.kind === 'derived' ? `${layer.derivative} from ${layer.source_title}` : layer.source ?? layer.source_title}
            {' · '}{fmtRes(layer.resolution_m)}
            {cov !== undefined && cov < 0.99 && ` · ${(cov * 100).toFixed(0)}% of area`}
          </div>
          {layer.doi && <a className="text-signal hover:underline" href={`https://doi.org/${layer.doi}`} target="_blank" rel="noreferrer">doi:{layer.doi}</a>}
          {layer.coverage_geojson && (
            <label className="flex items-center gap-2 pt-1">
              <input type="checkbox" checked={st.showCoverage} onChange={(e) => setLayer(layer.id, { showCoverage: e.target.checked })} className="accent-signal" />
              <span>Show outline</span>
            </label>
          )}
        </div>
      )}
    </div>
  );
}

export default function LayerPanel() {
  const config = useStore((s) => s.config);
  const layers = useStore((s) => s.layers);
  const toggle = useStore((s) => s.togglePanel);
  const [byGroup, setByGroup] = useState(true);
  if (!config) return null;
  const ordered = [...config.layers].sort((a, b) => (layers[b.id]?.order ?? 0) - (layers[a.id]?.order ?? 0));
  const groups = Array.from(new Set(config.layers.map((l) => l.group ?? 'other')));
  return (
    <aside className="flex h-full w-[300px] max-w-[85vw] flex-col bg-panel">
      <div className="flex items-center justify-between px-4 py-3">
        <Label>Layers</Label>
        <div className="flex items-center gap-2">
          <button onClick={() => setByGroup(!byGroup)} className="text-[10px] text-faint hover:text-ink">{byGroup ? 'Order' : 'Groups'}</button>
          <button onClick={() => toggle('leftOpen')} className="text-faint hover:text-ink" aria-label="Collapse layer panel"><IChevronL /></button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {byGroup
          ? groups.map((g) => (
              <section key={g}>
                <Label className="px-4 pb-1 pt-3">{GROUP_TITLES[g] ?? g}</Label>
                {config.layers.filter((l) => (l.group ?? 'other') === g).map((l) => <LayerRow key={l.id} layer={l} />)}
              </section>
            ))
          : ordered.map((l) => <LayerRow key={l.id} layer={l} />)}
      </div>
    </aside>
  );
}
