import { describe, expect, it } from 'vitest';
import { makeConverter } from './crs';
import { parseCoordinateQuery } from './format';
import type { CrsInfo } from './types';

const crs = {
  id: 'JEZERO_DELTA_EQC', version: 1,
  proj4: '+proj=eqc +lat_ts=18.45 +lat_0=0.0 +lon_0=77.4 +x_0=0.0 +y_0=0.0 +R=3396190.0 +units=m +no_defs +type=crs',
  central_meridian_deg_e: 77.4, standard_parallel_deg: 18.45, latitude_of_origin_deg: 0,
} as unknown as CrsInfo;

describe('Mars equirectangular converter (must match backend/jezero/crs.py)', () => {
  const c = makeConverter(crs);
  it('matches backend reference values', () => {
    // values produced by backend/jezero/crs.py
    const a = c.toProjected(77.45, 18.44);
    expect(a.x).toBeCloseTo(2811.3994803494493, 6);
    expect(a.y).toBeCloseTo(1093025.4223297667, 6);
    const b = c.toProjected(77.3, 18.56);
    expect(b.x).toBeCloseTo(-5622.798960698899, 6);
    expect(b.y).toBeCloseTo(1100138.3860325634, 6);
  });
  it('round-trips', () => {
    const p = c.toProjected(77.4321, 18.4765);
    const g = c.toGeographic(p.x, p.y);
    expect(g.lon_e).toBeCloseTo(77.4321, 10);
    expect(g.lat).toBeCloseTo(18.4765, 10);
  });
});

describe('coordinate search parsing', () => {
  it('parses lat, lon', () => expect(parseCoordinateQuery('18.44, 77.45')).toEqual({ kind: 'geo', lat: 18.44, lon: 77.45 }));
  it('parses hemispheres', () => expect(parseCoordinateQuery('77.45E 18.44N')).toEqual({ kind: 'geo', lat: 18.44, lon: 77.45 }));
  it('parses x/y', () => expect(parseCoordinateQuery('x=100 y=-50')).toEqual({ kind: 'xy', x: 100, y: -50 }));
  it('rejects junk', () => expect(parseCoordinateQuery('jezero')).toBeNull());
});
