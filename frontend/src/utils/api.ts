import axios from 'axios';
import type {
  Aircraft,
  Anomaly,
  FlightTrail,
  KinematicEvaluation,
  Stats,
  WindowKinematicEvaluation,
} from '@/types';

const api = axios.create({
  baseURL: '/api/v1',
});

export async function fetchAircraft(): Promise<Aircraft[]> {
  const { data } = await api.get<Aircraft[]>('/aircraft/');
  return data;
}

export async function fetchAircraftByIcao(icao: string): Promise<Aircraft> {
  const { data } = await api.get<Aircraft>(`/aircraft/${icao}`);
  return data;
}

export async function fetchFlightTrail(
  icao: string,
  minutes: number = 30
): Promise<FlightTrail> {
  const { data } = await api.get<FlightTrail>(`/aircraft/${icao}/trail`, {
    params: { minutes },
  });
  return data;
}

export async function fetchStats(): Promise<Stats> {
  const { data } = await api.get<Stats>('/aircraft/stats/overview');
  return data;
}

export async function fetchAnomalies(hours: number = 24): Promise<Anomaly[]> {
  const { data } = await api.get<Anomaly[]>('/anomalies/', {
    params: { hours },
  });
  return data;
}

export async function fetchCriticalAnomalies(
  hours: number = 24
): Promise<Anomaly[]> {
  const { data } = await api.get<Anomaly[]>('/anomalies/critical', {
    params: { hours },
  });
  return data;
}

export async function acknowledgeAnomaly(
  id: number,
  acknowledged: number
): Promise<Anomaly> {
  const { data } = await api.patch<Anomaly>(`/anomalies/${id}/acknowledge`, {
    acknowledged,
  });
  return data;
}

export async function fetchKinematicEvaluations(
  icao: string,
  limit: number = 5
): Promise<KinematicEvaluation[]> {
  const { data } = await api.get<KinematicEvaluation[]>('/kinematics/evaluations', {
    params: { icao_hex: icao, limit },
  });
  return data;
}

export async function fetchWindowKinematicEvaluations(
  icao: string,
  limit: number = 5
): Promise<WindowKinematicEvaluation[]> {
  const { data } = await api.get<WindowKinematicEvaluation[]>(
    '/kinematics/window-evaluations',
    { params: { icao_hex: icao, limit } }
  );
  return data;
}

export default api;
