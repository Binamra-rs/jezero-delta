import type { SVGProps } from 'react';

type P = SVGProps<SVGSVGElement>;
const base = (p: P) => ({ width: 16, height: 16, viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', strokeWidth: 1.4, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true, ...p });

export const ICrosshair = (p: P) => (<svg {...base(p)}><circle cx="8" cy="8" r="4.5" /><path d="M8 1v3M8 12v3M1 8h3M12 8h3" /></svg>);
export const IStart = (p: P) => (<svg {...base(p)}><circle cx="8" cy="8" r="5.5" /><path d="M6 10.5 8 5l2 5.5M6.7 8.8h2.6" /></svg>);
export const IEnd = (p: P) => (<svg {...base(p)}><circle cx="8" cy="8" r="5.5" /><path d="M6.5 5h2a1.4 1.4 0 0 1 0 2.8h-2V5Zm0 2.8h2.4a1.5 1.5 0 0 1 0 3H6.5V7.8Z" /></svg>);
export const IWaypoint = (p: P) => (<svg {...base(p)}><path d="M8 1.5 13 8l-5 6.5L3 8l5-6.5Z" /><circle cx="8" cy="8" r="1.4" /></svg>);
export const ILayers = (p: P) => (<svg {...base(p)}><path d="m8 2 6 3.2-6 3.2-6-3.2L8 2Z" /><path d="m2 8.2 6 3.2 6-3.2M2 11.2l6 3.2 6-3.2" /></svg>);
export const IRoute = (p: P) => (<svg {...base(p)}><circle cx="3.5" cy="12.5" r="1.8" /><circle cx="12.5" cy="3.5" r="1.8" /><path d="M5 11.5c3-1 1.5-4 4-5.5s2.2-1 2.2-1" /></svg>);
export const IInfo = (p: P) => (<svg {...base(p)}><circle cx="8" cy="8" r="6" /><path d="M8 7.2v4M8 4.8v.2" /></svg>);
export const IEye = (p: P) => (<svg {...base(p)}><path d="M1.5 8S4 3.5 8 3.5 14.5 8 14.5 8 12 12.5 8 12.5 1.5 8 1.5 8Z" /><circle cx="8" cy="8" r="2" /></svg>);
export const IEyeOff = (p: P) => (<svg {...base(p)}><path d="M2 2l12 12M6.6 4c.5-.3 1-.5 1.4-.5 4 0 6.5 4.5 6.5 4.5s-.6 1.1-1.7 2.3M4.2 5.3C2.6 6.5 1.5 8 1.5 8S4 12.5 8 12.5c1 0 1.9-.3 2.7-.7" /></svg>);
export const IUp = (p: P) => (<svg {...base(p)}><path d="m4 10 4-4 4 4" /></svg>);
export const IDown = (p: P) => (<svg {...base(p)}><path d="m4 6 4 4 4-4" /></svg>);
export const IClose = (p: P) => (<svg {...base(p)}><path d="m4 4 8 8M12 4l-8 8" /></svg>);
export const IChevronL = (p: P) => (<svg {...base(p)}><path d="m10 3-5 5 5 5" /></svg>);
export const IChevronR = (p: P) => (<svg {...base(p)}><path d="m6 3 5 5-5 5" /></svg>);
export const ISearch = (p: P) => (<svg {...base(p)}><circle cx="7" cy="7" r="4.5" /><path d="m10.5 10.5 3.5 3.5" /></svg>);
export const IUser = (p: P) => (<svg {...base(p)}><circle cx="8" cy="5.5" r="2.8" /><path d="M2.5 14c.8-2.8 3-4 5.5-4s4.7 1.2 5.5 4" /></svg>);
export const IEdit = (p: P) => (<svg {...base(p)}><path d="M10.5 2.5 13.5 5.5 6 13H3v-3l7.5-7.5Z" /></svg>);
export const ITrash = (p: P) => (<svg {...base(p)}><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 9h5.8l.6-9" /></svg>);
export const ITarget = (p: P) => (<svg {...base(p)}><circle cx="8" cy="8" r="5.5" /><circle cx="8" cy="8" r="2" /></svg>);
export const IWarn = (p: P) => (<svg {...base(p)}><path d="M8 2 14.5 13.5h-13L8 2Z" /><path d="M8 6.5v3.2M8 11.6v.2" /></svg>);

/* ---- survival hub & gallery ---- */
export const IWind = (p: P) => (<svg {...base(p)}><path d="M2 6h8a2 2 0 1 0-2-2M2 9.5h11a2 2 0 1 1-2 2M2 13h5" /></svg>);
export const ICloud = (p: P) => (<svg {...base(p)}><path d="M4.5 12.5h7a3 3 0 0 0 .3-6A4 4 0 0 0 4.2 7 2.8 2.8 0 0 0 4.5 12.5Z" /><path d="M3 14.5h4" /></svg>);
export const IPin = (p: P) => (<svg {...base(p)}><path d="M8 14.5s4.5-4.2 4.5-7.8a4.5 4.5 0 0 0-9 0C3.5 10.3 8 14.5 8 14.5Z" /><circle cx="8" cy="6.7" r="1.7" /></svg>);
export const IShieldAlert = (p: P) => (<svg {...base(p)}><path d="M8 1.8 13 3.7v4c0 3.3-2.2 5.6-5 6.5-2.8-.9-5-3.2-5-6.5v-4L8 1.8Z" /><path d="M8 5.3v3.2M8 10.6v.2" /></svg>);
export const IHeartPulse = (p: P) => (<svg {...base(p)}><path d="M8 13.5S2 10 2 6a3 3 0 0 1 6-.8A3 3 0 0 1 14 6c0 4-6 7.5-6 7.5Z" /><path d="M3.5 8h2l1-1.6 1.6 3 1-1.4h3.4" /></svg>);
export const IAntenna = (p: P) => (<svg {...base(p)}><circle cx="8" cy="6.5" r="1.3" /><path d="M8 7.8V14M5.5 14h5M4.6 3.2a4.8 4.8 0 0 0 0 6.6M11.4 3.2a4.8 4.8 0 0 1 0 6.6M2.8 1.6a7 7 0 0 0 0 9.8M13.2 1.6a7 7 0 0 1 0 9.8" /></svg>);
export const IShieldPlus = (p: P) => (<svg {...base(p)}><path d="M8 1.8 13 3.7v4c0 3.3-2.2 5.6-5 6.5-2.8-.9-5-3.2-5-6.5v-4L8 1.8Z" /><path d="M8 5.5v4M6 7.5h4" /></svg>);
export const IImage = (p: P) => (<svg {...base(p)}><rect x="2" y="3" width="12" height="10" rx="2" /><circle cx="5.8" cy="6.5" r="1.2" /><path d="m3 12 3.5-3.2 2.3 2 2-1.6L13 11.4" /></svg>);
export const IMap = (p: P) => (<svg {...base(p)}><path d="M6 3 2 4.5v8.5L6 11.5l4 1.5 4-1.5V3l-4 1.5L6 3ZM6 3v8.5M10 4.5V13" /></svg>);
export const IExternal = (p: P) => (<svg {...base(p)}><path d="M9 2.5h4.5V7M13.5 2.5 7.5 8.5M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3" /></svg>);
export const IRefresh = (p: P) => (<svg {...base(p)}><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5v3h-3" /></svg>);
export const IKey = (p: P) => (<svg {...base(p)}><circle cx="5" cy="10.5" r="2.8" /><path d="m7 8.5 6-6M11 4.5l1.5 1.5M9.5 6l1.2 1.2" /></svg>);
export const ICopy = (p: P) => (<svg {...base(p)}><rect x="5" y="5" width="8.5" height="8.5" rx="1.5" /><path d="M3.5 10.5h-.5a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h6.5a1 1 0 0 1 1 1v.5" /></svg>);
export const IDownload = (p: P) => (<svg {...base(p)}><path d="M8 2v8M4.8 7 8 10.2 11.2 7M2.5 13.5h11" /></svg>);
