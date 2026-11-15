export interface CrsInfo {
  id: string;
  version: number;
  proj4: string;
  geographic_proj4: string;
  central_meridian_deg_e: number;
  standard_parallel_deg: number;
  latitude_of_origin_deg: number;
  reference_surface: string;
  projection: string;
  latitude_type: string;
  longitude_direction: string;
  longitude_domain: string;
}

export interface TileGridInfo {
  origin: [number, number];
  extent: [number, number, number, number];
  tile_size: number;
  resolutions: number[];
  matrix_sizes: [number, number][];
}

export interface LegendInfo {
  ramp: string;
  stops: { position: number; color: string }[];
  range: [number, number] | null;
}

export interface LayerInfo {
  id: string;
  title: string;
  group: string | null;
  style: string;
  unit: string;
  kind: 'authoritative' | 'derived';
  derivative?: string | null;
  source_dataset: string;
  source_title: string;
  source?: string | null;
  doi?: string | null;
  product_id?: string | null;
  native_ground_pixel_m?: [number, number] | null;
  resolution_m: number;
  resampling?: string | null;
  bounds: [number, number, number, number];
  range: [number, number] | null;
  default_visible: boolean;
  default_opacity: number;
  coverage?: { area_km2: number; boundary_fraction: number } | null;
  coverage_geojson?: string | null;
  /** static exports only: deepest pre-rendered zoom level */
  static_max_zoom?: number;
  legend: LegendInfo;
}

export interface CostProfile {
  name: string;
  label: string;
  description: string;
  max_slope_deg: number;
  max_edge_grade_deg: number;
  alpha: number;
  slope_exponent: number;
  beta: number;
  roughness_ref_m: number;
  max_roughness_m: number | null;
  gamma_up: number;
  gamma_down: number;
}

export interface AppConfig {
  project: { id: string; title: string };
  crs: CrsInfo;
  boundary: [number, number, number, number];
  tilegrid: TileGridInfo;
  catalog_version: string;
  layers: LayerInfo[];
  routing: { default_profile: string; profiles: Record<string, CostProfile>; terrain_sources: string[] };
  raw_images?: { sol_presets: SolPreset[] };
  /** present in static exports (backend/scripts/export_static.py) */
  static?: { tile_template: string; format: string; generated_from_catalog: string };
}

export interface SolPreset {
  label: string;
  sol_min: number;
  sol_max: number;
  source?: string;
}

export interface Location {
  x: number;
  y: number;
  lon_e: number;
  lat: number;
  crs_id: string;
  crs_version: number;
  inside_boundary: boolean;
}

export interface Sample {
  layer: string;
  title: string;
  unit: string;
  kind: string;
  source_dataset: string;
  source_title: string | null;
  resolution_m: number;
  sampling: string;
  in_coverage: boolean;
  value: number | null;
  status: 'ok' | 'no_data' | 'outside_extent';
}

export interface InspectResult {
  location: Location;
  summary: {
    elevation: Sample | null;
    slope: Sample | null;
    thermal_inertia: Sample | null;
    roughness: Sample | null;
  };
  layers: Record<string, Sample>;
}

export interface RouteStats {
  distance_m: number;
  surface_distance_m: number;
  ascent_m: number;
  descent_m: number;
  mean_slope_deg: number;
  max_slope_deg: number;
  max_edge_grade_deg: number;
  start_elevation_m: number;
  end_elevation_m: number;
  cost: number;
  n_cells: number;
}

export interface RouteResult {
  label: string;
  geometry: { type: 'LineString'; coordinates: [number, number][]; crs: string };
  geographic: [number, number][];
  stats: RouteStats;
  terrain: { source: string; layer: string; title: string; resolution_m: number; auto_selected: boolean };
  profile: CostProfile;
  search: { expansions: number; algorithm: string };
  limitations: string;
  start: Location;
  end: Location;
}

export interface Waypoint {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  x: number;
  y: number;
  lon_e: number;
  lat: number;
  crs_id: string;
  crs_version: number;
  created_at: string;
  updated_at: string;
}

export interface MapPoint {
  x: number;
  y: number;
}

export interface RawImage {
  id: string;
  sol: number | null;
  instrument: string;
  camera_group: string | null;
  camera_label: string;
  filter_name?: string | null;
  title: string;
  caption: string;
  credit: string;
  date_taken_utc: string | null;
  date_taken_mars: string | null;
  date_received: string | null;
  site: number | null;
  drive: number | null;
  sample_type: string | null;
  mast_az_deg: number | null;
  mast_el_deg: number | null;
  dimension: string | null;
  thumb: string;
  medium: string;
  large: string;
  full_res: string | null;
  link: string | null;
}

export interface RawImagePage {
  page: number;
  per_page: number;
  total: number | null;
  images: RawImage[];
  source: string;
  source_url: string;
  fetched_at: string;
  cached: boolean;
}

export interface CameraGroup {
  id: string;
  label: string;
  instruments: string[];
}

export interface RawImageQuery {
  page: number;
  per_page: number;
  sol_min?: number | null;
  sol_max?: number | null;
  camera?: string | null;
  order: 'asc' | 'desc';
}
