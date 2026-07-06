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

export interface Stats {
  active_aircraft: number;
  total_positions_today: number;
  anomalies_today: number;
  critical_anomalies: number;
  last_updated: string;
}
