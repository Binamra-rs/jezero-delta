import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import type { CameraGroup, RawImage, RawImagePage, RawImageQuery } from '../lib/types';
import { useStore } from '../store/useStore';
import { Modal } from './Dialogs';
import { IChevronL, IChevronR, IExternal, IImage, IRefresh } from './icons';
import { Button, Card, Notice, Row, Spinner } from './ui';

const PER_PAGE = 24;
const linkBtn = 'inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso.endsWith('Z') || /[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().replace('T', ' ').slice(0, 16) + ' UTC';
}

function Lightbox({ img, onClose }: { img: RawImage; onClose: () => void }) {
  const [loaded, setLoaded] = useState(false);
  return (
    <Modal title={img.title || img.id} onClose={onClose} wide>
      <div className="grid gap-5 md:grid-cols-[1fr_280px]">
        <div className="relative flex min-h-[240px] items-center justify-center overflow-hidden rounded-xl bg-void">
          {!loaded && <div className="absolute"><Spinner /></div>}
          <img src={img.large} alt={img.title} onLoad={() => setLoaded(true)}
            className={`max-h-[70vh] w-full object-contain transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`} />
        </div>
        <div className="space-y-4">
          <div>
            <Row k="Sol" v={img.sol ?? '—'} />
            <Row k="Camera" v={img.camera_label} sub={img.instrument} />
            {img.filter_name && img.filter_name !== 'UNK' && <Row k="Filter" v={img.filter_name} />}
            <Row k="Taken (UTC)" v={fmtDate(img.date_taken_utc)} />
            <Row k="Local Mars time" v={img.date_taken_mars ?? '—'} />
          </div>
          <div className="flex flex-wrap gap-2">
            {img.full_res && <a className={linkBtn + ' bg-signal/15 text-signal hover:bg-signal/25'} href={img.full_res} target="_blank" rel="noreferrer"><IExternal /> Full resolution</a>}
            {img.link && <a className={linkBtn + ' bg-rim text-ink hover:bg-rim2'} href={img.link} target="_blank" rel="noreferrer"><IExternal /> NASA page</a>}
          </div>
          <p className="text-[11px] leading-relaxed text-faint">
            Image credit: {img.credit}. Raw, unprocessed engineering image released by NASA/JPL; colour, exposure and
            geometry are not calibrated. Image ID <span className="break-all font-mono">{img.id}</span>.
          </p>
        </div>
      </div>
    </Modal>
  );
}

export default function RawImages() {
  const presets = useStore((s) => s.config?.raw_images?.sol_presets ?? []);
  const [cameras, setCameras] = useState<CameraGroup[]>([]);
  const [q, setQ] = useState<RawImageQuery>({ page: 0, per_page: PER_PAGE, order: 'desc', camera: null, sol_min: null, sol_max: null });
  const [solMin, setSolMin] = useState('');
  const [solMax, setSolMax] = useState('');
  const [data, setData] = useState<RawImagePage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<RawImage | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    api.rawCameras().then((r) => setCameras(r.cameras)).catch(() => setCameras([]));
  }, []);

  const load = useCallback((query: RawImageQuery) => {
    abort.current?.abort();
    abort.current = new AbortController();
    setLoading(true);
    setError(null);
    api.rawImages(query, abort.current.signal)
      .then((d) => { setData(d); setLoading(false); })
      .catch((e: Error) => { if (e.name !== 'AbortError') { setError(e.message); setLoading(false); } });
  }, []);

  useEffect(() => { load(q); }, [q, load]);

  const applySols = (min: string, max: string) => {
    const a = min.trim() === '' ? null : Number(min);
    const b = max.trim() === '' ? null : Number(max);
    if ((a !== null && (!Number.isInteger(a) || a < 0)) || (b !== null && (!Number.isInteger(b) || b < 0))) {
      setError('Sols must be whole numbers ≥ 0.');
      return;
    }
    if (a !== null && b !== null && a > b) {
      setError('“From sol” must not be greater than “to sol”.');
      return;
    }
    setQ({ ...q, page: 0, sol_min: a, sol_max: b });
  };

  const totalPages = data?.total ? Math.max(1, Math.ceil(data.total / PER_PAGE)) : null;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-7xl space-y-5 p-5 md:p-8">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2.5">
              <IImage className="text-sky" width={20} height={20} />
              <h1 className="text-lg font-medium text-ink">Perseverance images</h1>
            </div>
          </div>
        </header>

        <Card className="flex flex-wrap items-end gap-3 p-4">
          <label className="flex flex-col gap-1">
            <span className="text-2xs text-faint">Camera</span>
            <select className="jz-select min-w-[190px]" value={q.camera ?? ''} onChange={(e) => setQ({ ...q, page: 0, camera: e.target.value || null })}>
              <option value="">All cameras</option>
              {cameras.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-2xs text-faint">From sol</span>
            <input className="jz-input w-24" inputMode="numeric" value={solMin} onChange={(e) => setSolMin(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && applySols(solMin, solMax)} placeholder="any" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-2xs text-faint">To sol</span>
            <input className="jz-input w-24" inputMode="numeric" value={solMax} onChange={(e) => setSolMax(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && applySols(solMin, solMax)} placeholder="any" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-2xs text-faint">Order</span>
            <select className="jz-select" value={q.order} onChange={(e) => setQ({ ...q, page: 0, order: e.target.value as 'asc' | 'desc' })}>
              <option value="desc">Newest</option>
              <option value="asc">Oldest</option>
            </select>
          </label>
          <Button variant="primary" onClick={() => applySols(solMin, solMax)}>Apply</Button>
          <Button variant="ghost" onClick={() => { setSolMin(''); setSolMax(''); setQ({ page: 0, per_page: PER_PAGE, order: 'desc', camera: null, sol_min: null, sol_max: null }); }}>Reset</Button>
          {presets.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 md:ml-auto">
              {presets.map((p) => (
                <button key={p.label} title={p.source ?? ''} onClick={() => { setSolMin(String(p.sol_min)); setSolMax(String(p.sol_max)); setQ({ ...q, page: 0, sol_min: p.sol_min, sol_max: p.sol_max }); }}
                  className="rounded-full bg-rim px-3 py-1 text-xs text-dim hover:text-ink">
                  {p.label} · sols {p.sol_min}–{p.sol_max}
                </button>
              ))}
            </div>
          )}
        </Card>

        {error && (
          <Notice tone="error">
            <div className="flex items-center justify-between gap-3">
              <span>{error}</span>
              <Button variant="ghost" onClick={() => load(q)}><IRefresh /> Retry</Button>
            </div>
          </Notice>
        )}

        <div className="flex items-center justify-between text-xs text-dim">
          <span>
            {loading ? 'Loading…' : data ? `${data.total !== null ? data.total.toLocaleString() + ' images' : `${data.images.length} images`}${data.cached ? ' · cached' : ''}` : ''}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" disabled={q.page === 0 || loading} onClick={() => setQ({ ...q, page: q.page - 1 })} aria-label="Previous page"><IChevronL /></Button>
            <span className="tabular-nums">Page {q.page + 1}{totalPages ? ` of ${totalPages.toLocaleString()}` : ''}</span>
            <Button variant="ghost" disabled={loading || !data || data.images.length === 0 || (totalPages !== null && q.page + 1 >= totalPages)} onClick={() => setQ({ ...q, page: q.page + 1 })} aria-label="Next page"><IChevronR /></Button>
          </div>
        </div>

        <div className={`grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 ${loading ? 'opacity-60' : ''} transition-opacity`}>
          {(data?.images ?? []).map((img) => (
            <button key={img.id} onClick={() => setOpen(img)} className="animate-fadein group overflow-hidden rounded-xl bg-card text-left shadow-soft transition-transform hover:-translate-y-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-signal/50">
              <div className="aspect-square overflow-hidden bg-void">
                <img src={img.thumb} alt={img.title} loading="lazy" className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
              </div>
              <div className="px-2.5 py-2">
                <div className="truncate text-xs font-medium text-ink">Sol {img.sol ?? '—'} · {img.camera_label}</div>
                <div className="truncate text-[10px] text-faint">{fmtDate(img.date_taken_utc)}</div>
              </div>
            </button>
          ))}
        </div>
        {!loading && data && data.images.length === 0 && <Notice>No images match these filters.</Notice>}

        <p className="pb-4 text-[11px] text-faint">
          Raw images: <a className="hover:text-dim" href="https://mars.nasa.gov/mars2020/multimedia/raw-images/" target="_blank" rel="noreferrer">NASA/JPL-Caltech</a>
        </p>
      </div>
      {open && <Lightbox img={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
