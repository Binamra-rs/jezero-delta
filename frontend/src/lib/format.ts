export const fmtLat = (lat: number) => `${Math.abs(lat).toFixed(5)}° ${lat >= 0 ? 'N' : 'S'}`;
export const fmtLon = (lonE: number) => `${lonE.toFixed(5)}° E`;
export const fmtXY = (v: number) => `${v.toLocaleString('en-US', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} m`;

export function fmtDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(2)} km` : `${m.toFixed(0)} m`;
}

export function fmtValue(v: number | null | undefined, unit: string, digits = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return 'No Data';
  const n = Math.abs(v) >= 1000 ? v.toLocaleString('en-US', { maximumFractionDigits: 1 }) : v.toFixed(digits);
  return unit ? `${n} ${unit}` : n;
}

export function fmtRes(m: number): string {
  return m < 10 ? `${m.toFixed(2)} m/px` : `${m.toFixed(0)} m/px`;
}

/** Parse "18.44, 77.45" (lat, lon) or "77.45E 18.44N" or "x=1234 y=5678". */
export function parseCoordinateQuery(q: string): { kind: 'geo'; lat: number; lon: number } | { kind: 'xy'; x: number; y: number } | null {
  const s = q.trim();
  const xy = /^x\s*=?\s*(-?[\d.]+)[,\s]+y\s*=?\s*(-?[\d.]+)$/i.exec(s);
  if (xy) return { kind: 'xy', x: parseFloat(xy[1]), y: parseFloat(xy[2]) };
  const tagged = /^(-?[\d.]+)\s*°?\s*([NSEW])[,\s]+(-?[\d.]+)\s*°?\s*([NSEW])$/i.exec(s);
  if (tagged) {
    const a = { v: parseFloat(tagged[1]), h: tagged[2].toUpperCase() };
    const b = { v: parseFloat(tagged[3]), h: tagged[4].toUpperCase() };
    const latPart = 'NS'.includes(a.h) ? a : b;
    const lonPart = latPart === a ? b : a;
    if (!'NS'.includes(latPart.h) || !'EW'.includes(lonPart.h)) return null;
    const lat = latPart.h === 'S' ? -latPart.v : latPart.v;
    const lon = lonPart.h === 'W' ? 360 - lonPart.v : lonPart.v;
    return { kind: 'geo', lat, lon };
  }
  const plain = /^(-?[\d.]+)[,\s]+(-?[\d.]+)$/.exec(s);
  if (plain) return { kind: 'geo', lat: parseFloat(plain[1]), lon: parseFloat(plain[2]) };
  return null;
}
