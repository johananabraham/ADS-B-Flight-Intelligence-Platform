export interface Aircraft {
  id: number;
  icao_hex: string;
  callsign: string | null;
  latitude: number | null;
  longitude: number | null;
  altitude: number | null;
  ground_speed: number | null;
  track: number | null;
  vertical_rate: number | null;
  squawk: string | null;
  last_seen: string;
  first_seen: string;
  messages_received: number;
}

export interface AircraftPosition {
  icao_hex: string;
  latitude: number;
  longitude: number;
  altitude: number | null;
  ground_speed: number | null;
  track: number | null;
  timestamp: string;
}

export interface FlightTrail {
  icao_hex: string;
  callsign: string | null;
  positions: AircraftPosition[];
}

export type AnomalyType =
  | 'RAPID_DESCENT'
  | 'RAPID_CLIMB'
  | 'SPEED_ANOMALY'
  | 'SQUAWK_7500'
  | 'SQUAWK_7600'
  | 'SQUAWK_7700'
  | 'GHOST_FLIGHT'
  | 'RESTRICTED_AIRSPACE'
  | 'ALTITUDE_DEVIATION';

export type AnomalySeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface Anomaly {
  id: number;
  icao_hex: string;
  callsign: string | null;
  anomaly_type: AnomalyType;
  severity: AnomalySeverity;
  latitude: number | null;
  longitude: number | null;
  altitude: number | null;
  description: string | null;
  details: Record<string, unknown> | null;
  detected_at: string;
  resolved_at: string | null;
  acknowledged: number;
}

export type KinematicEvaluationStatus = 'PASS' | 'FLAGGED' | 'INSUFFICIENT_DATA';

export interface KinematicRuleResult {
  rule: string;
  status: KinematicEvaluationStatus;
  value: number;
  threshold: number;
  unit: string;
  explanation: string;
  observation_ids: string[];
}

export interface KinematicEvaluation {
  evaluation_id: string;
  policy_version: string;
  previous_observation_id: string;
  current_observation_id: string;
  source_type: string;
  source_id: string;
  icao_hex: string;
  evaluated_at: string;
  status: KinematicEvaluationStatus;
  reason: string | null;
  delta_seconds: number;
  measurements: Record<string, number>;
  rule_results: KinematicRuleResult[];
}

export interface WindowKinematicEvaluation {
  evaluation_id: string;
  policy_version: string;
  first_observation_id: string;
  current_observation_id: string;
  observation_ids: string[];
  source_type: string;
  source_id: string;
  icao_hex: string;
  evaluated_at: string;
  status: KinematicEvaluationStatus;
  reason: string | null;
  duration_seconds: number;
  measurements: Record<string, number>;
  rule_results: KinematicRuleResult[];
}

export interface Stats {
  active_aircraft: number;
  total_positions_today: number;
  anomalies_today: number;
  critical_anomalies: number;
  last_updated: string;
}
