/**
 * Project CRS registration and exact Mars coordinate conversion.
 *
 * The proj4 string comes from the API (/api/v1/config), which reads it from
 * config/project.yaml — the frontend never hard-codes CRS parameters.
 * OpenLayers uses the registered projection for rendering; the explicit
 * equations below (identical to backend/jezero/crs.py) are used for the
 * coordinate read-outs so they match the backend to floating-point precision.
 */
import proj4 from 'proj4';
import { register } from 'ol/proj/proj4';
import { get as getProjection } from 'ol/proj';
import type Projection from 'ol/proj/Projection';
import type { CrsInfo } from './types';

export function registerProjectCrs(crs: CrsInfo, extent: [number, number, number, number]): Projection {
  const def = crs.proj4.replace(/\s*\+type=crs/, '');
  proj4.defs(crs.id, def);
  register(proj4);
  const proj = getProjection(crs.id);
  if (!proj) throw new Error(`Projection ${crs.id} failed to register`);
  proj.setExtent(extent);
  // OpenLayers would otherwise derive point resolution via EPSG:4326 using
  // the EARTH radius. Use the exact Mars equirectangular scale instead:
  // ground metres per map metre along a parallel = cos(lat) / cos(lat_ts).
  const R = radiusFromProj4(def);
  const cosTs = Math.cos(crs.standard_parallel_deg * DEG);
  proj.setGetPointResolution((resolution: number, point: number[]) => {
    const lat = crs.latitude_of_origin_deg + point[1] / R / DEG;
    return (resolution * Math.cos(lat * DEG)) / cosTs;
  });
  return proj;
}

function radiusFromProj4(p4: string): number {
  const m = /\+R=([0-9.]+)/.exec(p4);
  if (!m) throw new Error('Project CRS must be a Mars sphere (+R=)');
  return parseFloat(m[1]);
}

const DEG = Math.PI / 180;

export interface Converter {
  toGeographic(x: number, y: number): { lon_e: number; lat: number };
  toProjected(lonE: number, lat: number): { x: number; y: number };
}

export function makeConverter(crs: CrsInfo): Converter {
  const R = radiusFromProj4(crs.proj4);
  const lon0 = crs.central_meridian_deg_e;
  const lat0 = crs.latitude_of_origin_deg;
  const k = R * Math.cos(crs.standard_parallel_deg * DEG);
  return {
    toGeographic(x, y) {
      const lat = lat0 + y / R / DEG;
      let lon = (lon0 + x / k / DEG) % 360;
      if (lon < 0) lon += 360;
      return { lon_e: lon, lat };
    },
    toProjected(lonE, lat) {
      const dlon = ((((lonE - lon0 + 180) % 360) + 360) % 360) - 180;
      return { x: k * dlon * DEG, y: R * (lat - lat0) * DEG };
    },
  };
}
