import { useEffect } from 'react';
import MapView from './map/MapView';
import TopBar from './components/TopBar';
import LayerPanel from './components/LayerPanel';
import RightPanel from './components/RightPanel';
import BottomBar from './components/BottomBar';
import RawImages from './components/RawImages';
import SurvivalHub from './components/SurvivalHub';
import { Toast, WaypointDialog } from './components/Dialogs';
import { IChevronL, IChevronR } from './components/icons';
import { Spinner } from './components/ui';
import { useStore } from './store/useStore';

function useKeyboardShortcuts() {
  const setMode = useStore((s) => s.setMode);
  const view = useStore((s) => s.view);
  useEffect(() => {
    if (view !== 'map') return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (k === 'escape' || k === 'i') setMode('inspect');
      else if (k === 'a') setMode('start');
      else if (k === 'b') setMode('end');
      else if (k === 'w') setMode('waypoint');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setMode, view]);
}

export default function App() {
  const config = useStore((s) => s.config);
  const configError = useStore((s) => s.configError);
  const loadConfig = useStore((s) => s.loadConfig);
  const loadWaypoints = useStore((s) => s.loadWaypoints);
  const view = useStore((s) => s.view);
  const leftOpen = useStore((s) => s.leftOpen);
  const rightOpen = useStore((s) => s.rightOpen);
  const toggle = useStore((s) => s.togglePanel);
  useKeyboardShortcuts();

  useEffect(() => {
    void loadConfig();
    void loadWaypoints();
  }, [loadConfig, loadWaypoints]);

  if (configError) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="max-w-md rounded-2xl bg-panel p-6 shadow-soft">
          <div className="mb-2 text-sm font-semibold text-alert">Can’t load the Jezero datasets</div>
          <p className="text-sm text-dim">{configError}</p>
          <button onClick={() => void loadConfig()} className="mt-4 rounded-lg bg-card px-3 py-1.5 text-xs text-ink hover:bg-rim">Retry</button>
        </div>
      </div>
    );
  }
  if (!config) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <Spinner />
        <div className="text-xs text-faint">Loading Jezero datasets…</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <div className="relative min-h-0 flex-1">
        {/* Map view stays mounted (hidden) so tiles, view and state survive switching tabs */}
        <div className={`absolute inset-0 flex ${view === 'map' ? '' : 'invisible pointer-events-none'}`} aria-hidden={view !== 'map'}>
          {leftOpen && (
            <div className="absolute inset-y-0 left-0 z-30 md:static">
              <LayerPanel />
            </div>
          )}
          <main className="flex min-w-0 flex-1 flex-col">
            <div className="relative min-h-0 flex-1">
              <MapView config={config} />
              {!leftOpen && (
                <button onClick={() => toggle('leftOpen')} className="absolute left-0 top-24 z-20 rounded-r-xl bg-card px-1.5 py-3 text-dim shadow-soft hover:text-ink" aria-label="Open layer panel"><IChevronR /></button>
              )}
              {!rightOpen && (
                <button onClick={() => toggle('rightOpen')} className="absolute right-0 top-24 z-20 rounded-l-xl bg-card px-1.5 py-3 text-dim shadow-soft hover:text-ink" aria-label="Open information panel"><IChevronL /></button>
              )}
            </div>
            <BottomBar />
          </main>
          {rightOpen && (
            <div className="absolute inset-y-0 right-0 z-30 lg:static">
              <RightPanel />
            </div>
          )}
        </div>
        {view === 'images' && <div className="absolute inset-0 bg-void"><RawImages /></div>}
        {view === 'hub' && <div className="absolute inset-0 bg-void"><SurvivalHub /></div>}
      </div>
      <WaypointDialog />
      <Toast />
    </div>
  );
}
