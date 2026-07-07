import { useStats, useCriticalAnomalies } from '@/hooks';
import { formatDistanceToNow } from 'date-fns';

interface StatusBarProps {
  onToggleAlerts: () => void;
  alertsOpen: boolean;
}

export function StatusBar({ onToggleAlerts, alertsOpen }: StatusBarProps) {
  const { data: stats } = useStats();
  const { data: anomalies = [] } = useCriticalAnomalies(24);

  const hasAlerts = anomalies.length > 0;

  return (
    <div className="panel border-t-0 border-x-0 rounded-none">
      <div className="flex items-center justify-between px-4 py-2">
        {/* Left: System ID */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-status-nominal pulse-live" />
            <span className="text-sm font-semibold tracking-wide">ADS-B INTEL</span>
            <span className="text-2xs text-slate-500 font-mono">v1.0</span>
          </div>

          <div className="h-4 w-px bg-surface-3" />

          {/* Live stats */}
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-xs uppercase tracking-wider">Tracking</span>
              <span className="font-mono text-accent-primary font-semibold">
                {stats?.active_aircraft ?? '—'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-xs uppercase tracking-wider">Positions</span>
              <span className="font-mono text-slate-300">
                {stats?.total_positions_today?.toLocaleString() ?? '—'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-xs uppercase tracking-wider">Anomalies</span>
              <span className={`font-mono ${stats?.anomalies_today ? 'text-status-caution' : 'text-slate-300'}`}>
                {stats?.anomalies_today ?? '0'}
              </span>
            </div>
          </div>
        </div>

        {/* Right: Time and alerts toggle */}
        <div className="flex items-center gap-4">
          {stats?.last_updated && (
            <span className="text-xs text-slate-500">
              Updated {formatDistanceToNow(new Date(stats.last_updated))} ago
            </span>
          )}

          <button
            onClick={onToggleAlerts}
            className={`
              flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium
              transition-colors
              ${alertsOpen
                ? 'bg-accent-primary/20 text-accent-primary'
                : hasAlerts
                  ? 'bg-status-critical/20 text-status-critical'
                  : 'bg-surface-3 text-slate-400 hover:text-slate-200'
              }
            `}
          >
            {hasAlerts && (
              <span className="w-2 h-2 rounded-full bg-status-critical pulse-live" />
            )}
            <span>ALERTS</span>
            {hasAlerts && (
              <span className="font-mono">{anomalies.length}</span>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
