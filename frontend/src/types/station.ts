export type StationHealthState =
  | 'HEALTHY'
  | 'DEGRADED'
  | 'STALE'
  | 'OFFLINE'
  | 'NO_DATA';

export interface StationHealth {
  state: StationHealthState;
  policy_version: string;
  node_id: string | null;
  evaluated_at: string;
  telemetry_age_seconds: number | null;
  reasons: string[];
  telemetry_message_id: string | null;
  presence_message_id: string | null;
}

export interface Station {
  node_id: string;
  firmware_version: string | null;
  last_received_at: string;
  last_observed_at: string | null;
  presence_status: string | null;
  uptime_seconds: number | null;
  reconnect_count: number | null;
  rssi_dbm: number | null;
  free_heap_bytes: number | null;
  offline_queue_depth: number | null;
  watchdog_reset_count: number | null;
  temperature_c: number | null;
  supply_voltage_v: number | null;
  health: StationHealth;
}
