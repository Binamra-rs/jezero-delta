import { useEffect, useRef, useState } from 'react';
import OlMap from 'ol/Map';
import View from 'ol/View';
import TileLayer from 'ol/layer/Tile';
import XYZ from 'ol/source/XYZ';
import TileGrid from 'ol/tilegrid/TileGrid';
import VectorLayer from 'ol/layer/Vector';
import VectorSource from 'ol/source/Vector';
import Feature from 'ol/Feature';
import OlPoint from 'ol/geom/Point';
import LineString from 'ol/geom/LineString';
import { fromExtent } from 'ol/geom/Polygon';
import GeoJSON from 'ol/format/GeoJSON';
import { Circle as CircleStyle, Fill, RegularShape, Stroke, Style, Text } from 'ol/style';
import ScaleLine from 'ol/control/ScaleLine';
import Zoom from 'ol/control/Zoom';
import { containsCoordinate } from 'ol/extent';
import type Projection from 'ol/proj/Projection';
import type { FeatureLike } from 'ol/Feature';
import 'ol/ol.css';

import { api, tileMaxZoom, tileUrl } from '../lib/api';
import { registerProjectCrs } from '../lib/crs';
import type { AppConfig } from '../lib/types';
import { useStore } from '../store/useStore';

const C = { signal: '#9dc2b4', ochre: '#d9a982', ink: '#e2ded8', void: '#1a1b1e', caution: '#d5bf8c', sky: '#a5b9d4', dim: '#aaa49c' };
const COVERAGE_COLOR: Record<string, string> = {
  hirise_dtm_1: C.signal, hirise_dtm_2: C.sky, themis_ti: C.caution, ctx_dem: C.dim, ctx_ortho: C.dim,
};

const routeStyles = [
  new Style({ stroke: new Stroke({ color: 'rgba(26,27,30,0.7)', width: 7, lineCap: 'round', lineJoin: 'round' }) }),
  new Style({ stroke: new Stroke({ color: C.ochre, width: 3, lineCap: 'round', lineJoin: 'round' }) }),
];

function endpointStyle(label: string, color: string) {
  return new Style({
    image: new CircleStyle({ radius: 10, fill: new Fill({ color: C.void }), stroke: new Stroke({ color, width: 2.5 }) }),
    text: new Text({ text: label, font: '600 11px Inter, sans-serif', fill: new Fill({ color }) }),
  });
}
const startStyle = endpointStyle('A', C.signal);
const endStyle = endpointStyle('B', C.ochre);

const inspectStyle = [
  new Style({ image: new RegularShape({ points: 4, radius: 11, radius2: 0, angle: 0, stroke: new Stroke({ color: C.void, width: 4 }) }) }),
  new Style({ image: new RegularShape({ points: 4, radius: 10, radius2: 0, angle: 0, stroke: new Stroke({ color: C.signal, width: 1.5 }) }) }),
];

function waypointStyle(feature: FeatureLike, resolution: number): Style[] {
  const selected = feature.get('selected') as boolean;
  const shape = new Style({
    image: new RegularShape({
      points: 4, radius: selected ? 9 : 7, angle: 0,
      fill: new Fill({ color: selected ? C.signal : C.ink }), stroke: new Stroke({ color: C.void, width: 2 }),
    }),
  });
  if (resolution > 8 && !selected) return [shape];
  return [shape, new Style({
    text: new Text({
      text: feature.get('name') as string, offsetY: -18, font: '500 11px Inter, sans-serif',
      fill: new Fill({ color: selected ? C.signal : C.ink }), stroke: new Stroke({ color: C.void, width: 3 }),
    }),
  })];
}

function coverageStyle(feature: FeatureLike): Style {
  const color = COVERAGE_COLOR[feature.get('layer') as string] ?? C.ink;
  return new Style({ stroke: new Stroke({ color, width: 1.5, lineDash: [6, 5] }) });
}

const boundaryStyle = new Style({ stroke: new Stroke({ color: 'rgba(217,169,130,0.45)', width: 1.5, lineDash: [2, 6] }) });

interface Handles {
  map: OlMap;
  proj: Projection;
  tiles: Map<string, TileLayer<XYZ>>;
  route: VectorSource;
  points: VectorSource;
  waypoints: VectorSource;
  coverage: Map<string, VectorLayer<VectorSource>>;
}

export default function MapView({ config }: { config: AppConfig }) {
  const el = useRef<HTMLDivElement>(null);
  const h = useRef<Handles | null>(null);
  const [loading, setLoading] = useState(0);
  const [tileErrors, setTileErrors] = useState(0);

  const layers = useStore((s) => s.layers);
  const mode = useStore((s) => s.mode);
  const inspectPoint = useStore((s) => s.inspectPoint);
  const route = useStore((s) => s.route);
  const waypoints = useStore((s) => s.waypoints);
  const selectedWaypoint = useStore((s) => s.selectedWaypoint);
  const flyTo = useStore((s) => s.flyTo);
  const view = useStore((s) => s.view);

  // ------------------------------------------------------------- initialise
  useEffect(() => {
    if (!el.current) return;
    const boundary = config.boundary;
    const proj = registerProjectCrs(config.crs, boundary);
    const tg = config.tilegrid;
    const tiles = new Map<string, TileLayer<XYZ>>();
    config.layers.forEach((l, i) => {
      // Per-layer grid: same origin and resolutions as the project grid, limited to the
      // layer's extent and deepest available zoom (beyond it OpenLayers up-samples).
      const grid = new TileGrid({
        origin: tg.origin, resolutions: tg.resolutions.slice(0, tileMaxZoom(l, config) + 1), tileSize: tg.tile_size, extent: l.bounds,
      });
      const source = new XYZ({
        url: tileUrl(l, config), projection: proj, tileGrid: grid, crossOrigin: 'anonymous',
        transition: 150, interpolate: true,
      });
      source.on('tileloadstart', () => setLoading((n) => n + 1));
      source.on('tileloadend', () => setLoading((n) => Math.max(0, n - 1)));
      source.on('tileloaderror', () => {
        setLoading((n) => Math.max(0, n - 1));
        setTileErrors((n) => n + 1);
      });
      const layer = new TileLayer({ source, visible: l.default_visible, opacity: l.default_opacity, zIndex: i, extent: boundary, preload: 1 });
      layer.set('id', l.id);
      tiles.set(l.id, layer);
    });

    const boundarySrc = new VectorSource({ features: [new Feature(fromExtent(boundary))] });
    const route = new VectorSource();
    const points = new VectorSource();
    const waypointsSrc = new VectorSource();
    const coverage = new Map<string, VectorLayer<VectorSource>>();
    const fmt = new GeoJSON();
    config.layers.filter((l) => l.kind === 'authoritative' && l.coverage_geojson).forEach((l) => {
      const src = new VectorSource();
      const vl = new VectorLayer({ source: src, style: coverageStyle, zIndex: 900, visible: false });
      coverage.set(l.id, vl);
      api.coverage(l).then((fc) => {
        const obj = { ...(fc as Record<string, unknown>) };
        delete obj.crs; // coordinates are already in the project CRS
        src.addFeatures(fmt.readFeatures(obj, { dataProjection: proj, featureProjection: proj }));
      }).catch(() => undefined);
    });

    const map = new OlMap({
      target: el.current,
      layers: [
        ...tiles.values(),
        new VectorLayer({ source: boundarySrc, style: boundaryStyle, zIndex: 890 }),
        ...coverage.values(),
        new VectorLayer({ source: route, style: routeStyles, zIndex: 1000 }),
        new VectorLayer({ source: waypointsSrc, style: waypointStyle, zIndex: 1010, declutter: true }),
        new VectorLayer({ source: points, zIndex: 1020 }),
      ],
      view: new View({
        projection: proj, resolutions: tg.resolutions, constrainResolution: true, extent: boundary,
        showFullExtent: true, smoothExtentConstraint: true,
      }),
      controls: [new Zoom({ className: 'jz-zoom' }), new ScaleLine({ units: 'metric', className: 'jz-scale' })],
    });
    map.getView().fit(boundary, { padding: [24, 24, 24, 24] });

    let raf = 0;
    map.on('pointermove', (e) => {
      if (e.dragging) return;
      cancelAnimationFrame(raf);
      const [x, y] = e.coordinate;
      raf = requestAnimationFrame(() => useStore.getState().setPointer(containsCoordinate(boundary, [x, y]) ? { x, y } : null));
      const hit = map.hasFeatureAtPixel(e.pixel, { layerFilter: (lyr) => lyr.getSource() === waypointsSrc });
      const target = map.getTargetElement();
      if (target) target.style.cursor = hit ? 'pointer' : useStore.getState().mode === 'inspect' ? '' : 'crosshair';
    });

    map.on('singleclick', (e) => {
      const st = useStore.getState();
      const [x, y] = e.coordinate;
      if (!containsCoordinate(boundary, [x, y])) {
        st.notify('That location is outside the Jezero project area.');
        return;
      }
      if (st.mode === 'inspect') {
        const wp = map.forEachFeatureAtPixel(e.pixel, (f) => f, { layerFilter: (lyr) => lyr.getSource() === waypointsSrc });
        if (wp) {
          st.selectWaypoint(wp.get('id') as string);
          st.setRightTab('waypoints');
          return;
        }
        void st.runInspect({ x, y });
      } else if (st.mode === 'start' || st.mode === 'end') {
        st.setRoutePoint(st.mode, { x, y });
      } else if (st.mode === 'waypoint') {
        st.openWaypointDraft({ x, y });
      }
    });

    h.current = { map, proj, tiles, route, points, waypoints: waypointsSrc, coverage };
    return () => {
      map.setTarget(undefined);
      h.current = null;
    };
  }, [config]);

  // ---------------------------------------------------------- layer states
  useEffect(() => {
    const H = h.current;
    if (!H) return;
    for (const [id, st] of Object.entries(layers)) {
      const tl = H.tiles.get(id);
      if (tl) {
        tl.setVisible(st.visible);
        tl.setOpacity(st.opacity);
        tl.setZIndex(st.order);
      }
      H.coverage.get(id)?.setVisible(st.showCoverage);
    }
  }, [layers]);

  // -------------------------------------------- inspect marker + endpoints
  useEffect(() => {
    const H = h.current;
    if (!H) return;
    H.points.clear();
    if (inspectPoint) {
      const f = new Feature(new OlPoint([inspectPoint.x, inspectPoint.y]));
      f.setStyle(inspectStyle);
      H.points.addFeature(f);
    }
    if (route.start) {
      const f = new Feature(new OlPoint([route.start.x, route.start.y]));
      f.setStyle(startStyle);
      H.points.addFeature(f);
    }
    if (route.end) {
      const f = new Feature(new OlPoint([route.end.x, route.end.y]));
      f.setStyle(endStyle);
      H.points.addFeature(f);
    }
  }, [inspectPoint, route.start, route.end]);

  // ----------------------------------------------------------------- route
  useEffect(() => {
    const H = h.current;
    if (!H) return;
    H.route.clear();
    if (route.result) {
      H.route.addFeature(new Feature(new LineString(route.result.geometry.coordinates)));
      const routeExtent = H.route.getExtent();

if (routeExtent) {
  H.map.getView().fit(routeExtent, {
    padding: [80, 80, 80, 80],
    duration: 500,
    maxZoom: H.map.getView().getZoom() ?? undefined,
  });
}
    }
  }, [route.result]);

  // ------------------------------------------------------------- waypoints
  useEffect(() => {
    const H = h.current;
    if (!H) return;
    H.waypoints.clear();
    H.waypoints.addFeatures(waypoints.map((w) => {
      const f = new Feature({ geometry: new OlPoint([w.x, w.y]), name: w.name, id: w.id, selected: w.id === selectedWaypoint });
      f.setId(w.id);
      return f;
    }));
  }, [waypoints, selectedWaypoint]);

  // ------------------------------------------------------------------ flyTo
  useEffect(() => {
    const H = h.current;
    if (!H || !flyTo) return;
    const view = H.map.getView();
    view.animate({ center: [flyTo.point.x, flyTo.point.y], resolution: Math.min(view.getResolution() ?? 8, 8), duration: 600 });
  }, [flyTo]);

  // the map stays mounted while other views are shown; resize when it returns
  useEffect(() => {
    if (view === 'map') requestAnimationFrame(() => h.current?.map.updateSize());
  }, [view]);

  useEffect(() => {
    const target = h.current?.map.getTargetElement();
    if (target) target.style.cursor = mode === 'inspect' ? '' : 'crosshair';
  }, [mode]);

  return (
    <div className="relative h-full w-full">
      <div ref={el} className="absolute inset-0 bg-void" aria-label="Jezero crater map" role="application" />
      <div className={`pointer-events-none absolute inset-x-0 top-0 h-0.5 overflow-hidden transition-opacity duration-300 ${loading > 0 ? 'opacity-100' : 'opacity-0'}`}>
        <div className="h-full w-1/3 animate-[scan_1.6s_ease-in-out_infinite] bg-signal/35" />
      </div>
      {mode !== 'inspect' && (
        <div className="pointer-events-none absolute left-1/2 top-4 -translate-x-1/2 rounded-full bg-card/95 px-4 py-2 text-xs text-ink shadow-soft backdrop-blur">
          {mode === 'start' && <>Click the map to place <span className="text-signal">start A</span></>}
          {mode === 'end' && <>Click the map to place <span className="text-ochre">destination B</span></>}
          {mode === 'waypoint' && <>Click the map to place a <span className="text-signal">waypoint</span></>}
          <span className="ml-2 text-faint">Esc to cancel</span>
        </div>
      )}
      {tileErrors > 0 && (
        <div className="absolute bottom-4 right-4 rounded-full bg-card/95 px-3 py-1 text-2xs text-alert shadow-soft">
          {tileErrors} tile{tileErrors === 1 ? '' : 's'} failed to load
        </div>
      )}
    </div>
  );
}
