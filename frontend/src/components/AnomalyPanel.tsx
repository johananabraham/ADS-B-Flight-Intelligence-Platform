import { useCriticalAnomalies } from '@/hooks';
import type { Anomaly, AnomalySeverity } from '@/types';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

const severityColors: Record<AnomalySeverity, string> = {
  CRITICAL: 'bg-red-500 text-white',
  HIGH: 'bg-orange-500 text-white',
  MEDIUM: 'bg-yellow-500 text-black',
  LOW: 'bg-green-500 text-white',
};

const anomalyTypeLabels: Record<string, string> = {
  RAPID_DESCENT: 'Rapid Descent',
  RAPID_CLIMB: 'Rapid Climb',
  SPEED_ANOMALY: 'Speed Anomaly',
  SQUAWK_7500: 'HIJACK',
  SQUAWK_7600: 'Radio Failure',
  SQUAWK_7700: 'EMERGENCY',
  GHOST_FLIGHT: 'Signal Lost',
  RESTRICTED_AIRSPACE: 'Restricted Zone',
  ALTITUDE_DEVIATION: 'Altitude Deviation',
};

function AnomalyCard({ anomaly }: { anomaly: Anomaly }) {
  const isSquawkEmergency = anomaly.anomaly_type.startsWith('SQUAWK_');

  return (
    <div
      className={clsx(
        'p-3 border-b border-gray-700',
        anomaly.severity === 'CRITICAL' && 'bg-red-900/20',
        anomaly.severity === 'HIGH' && 'bg-orange-900/20'
      )}
    >
      <div className="flex justify-between items-start mb-2">
        <span
          className={clsx(
            'text-xs px-2 py-1 rounded font-semibold',
            severityColors[anomaly.severity]
          )}
        >
          {anomaly.severity}
        </span>
        <span className="text-xs text-gray-500">
          {formatDistanceToNow(new Date(anomaly.detected_at))} ago
        </span>
      </div>

      <p
        className={clsx(
          'font-bold',
          isSquawkEmergency ? 'text-red-400' : 'text-white'
        )}
      >
        {anomalyTypeLabels[anomaly.anomaly_type] || anomaly.anomaly_type}
      </p>

      <p className="text-sm text-gray-300 mt-1">
        <span className="font-mono">
          {anomaly.callsign || anomaly.icao_hex}
        </span>
      </p>

      {anomaly.description && (
        <p className="text-xs text-gray-400 mt-1">{anomaly.description}</p>
      )}

      {anomaly.altitude && (
        <p className="text-xs text-gray-500 mt-1">
          at {anomaly.altitude.toLocaleString()} ft
        </p>
      )}
    </div>
  );
}

export function AnomalyPanel() {
  const { data: anomalies = [], isLoading } = useCriticalAnomalies(24);

  if (isLoading) {
    return (
      <div className="p-4 text-gray-400 text-center">
        Loading anomalies...
      </div>
    );
  }

  if (anomalies.length === 0) {
    return (
      <div className="p-4 text-gray-400 text-center">
        <p className="text-green-400">No active alerts</p>
        <p className="text-xs mt-2">
          Critical and high-severity anomalies will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-y-auto h-full">
      <div className="p-2 bg-red-900/30 border-b border-red-500">
        <p className="text-red-400 text-sm font-semibold">
          {anomalies.length} Active Alert{anomalies.length !== 1 ? 's' : ''}
        </p>
      </div>
      {anomalies.map((a) => (
        <AnomalyCard key={a.id} anomaly={a} />
      ))}
    </div>
  );
}
