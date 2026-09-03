export interface ORCAField {
  field: string;
  label: string;
  kind: "scalar" | "vector";
  unit: string | null;
  lats: number[];
  lons: number[];
  values?: (number | null)[][];
  u?: (number | null)[][];
  v?: (number | null)[][];
  speed?: (number | null)[][];
  range: { min: number; max: number };
  cells: { total: number; valid: number; coverage: number };
  valid_time: string;
  source: string;
  source_id: string;
  dataset: string;
  advisory_only: boolean;
}

export interface ORCADriver {
  factor: string;
  value: number | boolean | null;
  unit: string | null;
  band: string | null;
  contribution: 'limiting' | 'supporting' | 'context';
}

export interface ORCAAssessment {
  domain: string;
  verdict: string;
  confidence: string;
  rationale: string;
  // A driver's value may be a number, or a BOOLEAN for containment
  // (regulatory) and presence (warnings, advisories).
  drivers: ORCADriver[];
  not_evaluated: { factor: string; reason: string; detail: string | null }[];
  missing_required: string[];
  verdict_capped_by: string[];
  limiting_factor: string | null;
}

export interface ORCAEvidence {
  evidence_id: string;
  domain: string;
  statement: string;
  parameter: string;
  value: any;
  unit: string | null;
  value_kind: string;
  provenance_id: string;
  weight: string;
}

export interface ORCAMapLayer {
  id: string;
  type: string;
  name: string;
  data: any; // GeoJSON Feature
}

export interface ORCAResponse {
  thread_id?: string;
  language?: string;
  intent?: string;
  resolved_location?: { lat: number; lon: number; label: string; dest_lat?: number; dest_lon?: number };
  resolved_time_window?: { start_time: string; end_time: string };
  // The API returns WHICH detail is missing ('location', 'time_window',
  // 'destination', 'intent') or null -- not a boolean.
  clarification_needed?: string | null;
  plan?: any;
  assessments?: ORCAAssessment[];
  evidence?: ORCAEvidence[];
  alerts?: ORCAAlert[];
  map_layers?: ORCAMapLayer[];
  claims?: any[];
  not_evaluated?: any[];
  disposition?: string;
  recommendation?: { category: string; headline: string; is_official_advisory: boolean };
  trace?: ORCATraceEvent[];
}

export interface ORCAAlert {
  kind: 'approaching' | 'leaving' | 'inside';
  boundary_type: string;
  severity: 'info' | 'caution' | 'warning';
  distance_km: number | null;
  inside: boolean;
  name: string | null;
  dataset_version: string | null;
  advisory_only: boolean;
}

export interface ORCATraceEvent {
  node: string;
  status: string;
  duration_ms?: number;
  summary?: string;
  tool?: string;
  source?: string;
  codes?: string[];
  fallback_used?: boolean;
}

export interface ORCASource {
  tool: string;
  description: string;
  yields: string[];
  domains: string[];
  available: boolean;
  unavailable_reason: string | null;
}

export interface ORCASourceHealth { sources: ORCASource[] }

export interface ORCABoundaries {
  type: 'FeatureCollection';
  features: any[];
  dataset_version?: string;
  snapshot_version?: string;
}

export interface ORCAProvenance {
  provenance_id: string;
  parameter: string;
  unit: string | null;
  value_kind: string;
  source: string;
  source_id: string;
  organisation?: string | null;
  dataset?: string | null;
  access_method?: string | null;
  retrieved_at?: string | null;
  licence_reference?: string | null;
  derivation?: {
    method: string; method_version: string;
    inputs: string[]; params: Record<string, unknown>;
  } | null;
}
