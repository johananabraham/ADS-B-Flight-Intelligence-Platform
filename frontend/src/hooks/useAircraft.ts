import { useQuery } from '@tanstack/react-query';
import {
  fetchAircraft,
  fetchFlightTrail,
  fetchStats,
  fetchAnomalies,
  fetchCriticalAnomalies,
  fetchKinematicEvaluations,
  fetchWindowKinematicEvaluations,
} from '@/utils/api';

export function useAircraft() {
  return useQuery({
    queryKey: ['aircraft'],
    queryFn: fetchAircraft,
    refetchInterval: 2000, // Refresh every 2 seconds
  });
}

export function useFlightTrail(icao: string | null, minutes: number = 30) {
  return useQuery({
    queryKey: ['trail', icao, minutes],
    queryFn: () => fetchFlightTrail(icao!, minutes),
    enabled: !!icao,
    refetchInterval: 5000,
  });
}

export function useStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    refetchInterval: 5000,
  });
}

export function useAnomalies(hours: number = 24) {
  return useQuery({
    queryKey: ['anomalies', hours],
    queryFn: () => fetchAnomalies(hours),
    refetchInterval: 10000,
  });
}

export function useCriticalAnomalies(hours: number = 24) {
  return useQuery({
    queryKey: ['criticalAnomalies', hours],
    queryFn: () => fetchCriticalAnomalies(hours),
    refetchInterval: 5000,
  });
}

export function useKinematicEvaluations(icao: string | null) {
  return useQuery({
    queryKey: ['kinematicEvaluations', icao],
    queryFn: () => fetchKinematicEvaluations(icao!),
    enabled: !!icao,
    refetchInterval: 5000,
  });
}

export function useWindowKinematicEvaluations(icao: string | null) {
  return useQuery({
    queryKey: ['windowKinematicEvaluations', icao],
    queryFn: () => fetchWindowKinematicEvaluations(icao!),
    enabled: !!icao,
    refetchInterval: 5000,
  });
}
