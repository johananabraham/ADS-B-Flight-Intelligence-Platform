import { useStats } from '@/hooks';
import { formatDistanceToNow } from 'date-fns';

export function StatsBar() {
  const { data: stats, isLoading } = useStats();

  if (isLoading || !stats) {
    return (
      <div className="bg-gray-900 border-b border-gray-700 px-4 py-2">
        <p className="text-gray-400 text-sm">Loading stats...</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border-b border-gray-700 px-4 py-2 flex items-center justify-between">
      <div className="flex items-center space-x-6">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm text-gray-300">
            <span className="font-bold text-white">
              {stats.active_aircraft}
            </span>{' '}
            aircraft
          </span>
        </div>

        <div className="text-sm text-gray-400">
          <span className="font-mono text-blue-400">
            {stats.total_positions_today.toLocaleString()}
          </span>{' '}
          positions today
        </div>

        <div className="text-sm text-gray-400">
          <span className="font-mono text-yellow-400">
            {stats.anomalies_today}
          </span>{' '}
          anomalies
        </div>

        {stats.critical_anomalies > 0 && (
          <div className="text-sm">
            <span className="font-mono text-red-500 font-bold animate-pulse">
              {stats.critical_anomalies} CRITICAL
            </span>
          </div>
        )}
      </div>

      <div className="text-xs text-gray-500">
        Updated {formatDistanceToNow(new Date(stats.last_updated))} ago
      </div>
    </div>
  );
}
