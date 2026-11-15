import { useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { makeConverter } from '../lib/crs';
import { fmtLat, fmtLon } from '../lib/format';
import { useStore } from '../store/useStore';
import { IClose } from './icons';
import { Button, Notice, Spinner } from './ui';

export function Modal({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && closeRef.current();
    window.addEventListener('keydown', onKey);
    ref.current?.querySelector<HTMLElement>('input,textarea')?.focus();
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-void/70 p-4 backdrop-blur-sm" onMouseDown={onClose}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label={title} onMouseDown={(e) => e.stopPropagation()}
        className={`animate-fadein w-full ${wide ? 'max-w-4xl' : 'max-w-sm'} max-h-[92vh] overflow-y-auto rounded-2xl bg-panel shadow-soft`}>
        <div className="flex items-center justify-between px-5 pb-2 pt-4">
          <div className="text-sm font-semibold text-ink">{title}</div>
          <button onClick={onClose} className="rounded-lg p-1 text-faint hover:bg-card hover:text-ink" aria-label="Close"><IClose /></button>
        </div>
        <div className="px-5 pb-5">{children}</div>
      </div>
    </div>
  );
}

const field = 'jz-input w-full py-2 text-sm';

export function WaypointDialog() {
  const draft = useStore((s) => s.waypointDraft);
  const close = useStore((s) => s.closeWaypointDraft);
  const save = useStore((s) => s.saveWaypoint);
  const config = useStore((s) => s.config);
  const conv = useMemo(() => (config ? makeConverter(config.crs) : null), [config]);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(draft?.editing?.name ?? '');
    setDesc(draft?.editing?.description ?? '');
    setError(null);
  }, [draft]);

  if (!draft || !conv) return null;
  const g = conv.toGeographic(draft.point.x, draft.point.y);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await save(name.trim(), desc);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={draft.editing ? 'Edit waypoint' : 'New waypoint'} onClose={close}>
      <form onSubmit={submit} className="space-y-3">
        <div className="font-mono text-[11px] text-dim">{fmtLat(g.lat)} · {fmtLon(g.lon_e)}</div>
        <input className={field} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
        <textarea className={`${field} min-h-[96px] resize-y`} placeholder="Notes (optional)" value={desc} onChange={(e) => setDesc(e.target.value)} maxLength={4000} />
        {error && <Notice tone="error">{error}</Notice>}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={close}>Cancel</Button>
          <Button type="submit" variant="primary" disabled={busy || !name.trim()}>{busy && <Spinner />} Save</Button>
        </div>
      </form>
    </Modal>
  );
}

export function Toast() {
  const toast = useStore((s) => s.toast);
  if (!toast) return null;
  return (
    <div role="status" className={`animate-fadein fixed bottom-24 left-1/2 z-[90] -translate-x-1/2 rounded-xl px-4 py-2.5 text-xs shadow-soft ${toast.tone === 'error' ? 'bg-card text-alert' : 'bg-card text-ink'}`}>
      {toast.text}
    </div>
  );
}
