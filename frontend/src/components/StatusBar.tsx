import { useState } from 'react';
import { useCriticalAnomalies } from '@/hooks';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';
import type { Aircraft, Stats } from '@/types';
import { exportToCSV, exportToJSON } from '@/utils/export';

interface StatusBarProps {
  onToggleAlerts: () => void;
  alertsOpen: boolean;
  showOverlays: boolean;
  onToggleOverlays: () => void;
  showFilters: boolean;
  onToggleFilters: () => void;
  connected: boolean;
  stats: Stats | null;
  lastUpdate: Date | null;
  aircraftCount: number;
  totalAircraftCount: number;
  aircraft?: Aircraft[];
}

export function StatusBar({
  onToggleAlerts,
  alertsOpen,
  showOverlays,
  onToggleOverlays,
  showFilters,
  onToggleFilters,
  connected,
  stats,
  lastUpdate,
  aircraftCount,
  totalAircraftCount,
  aircraft = [],
}: StatusBarProps) {
  const [showExport, setShowExport] = useState(false);
  const { data: anomalies = [] } = useCriticalAnomalies(24);

  const hasAlerts = anomalies.length > 0;
  const isFiltered = aircraftCount !== totalAircraftCount;

  const handleExportCSV = () => {
    exportToCSV(aircraft);
    setShowExport(false);
  };

  const handleExportJSON = () => {
    exportToJSON(aircraft);
    setShowExport(false);
  };

  return (
    <div className="panel border-t-0 border-x-0 rounded-none">
      <div className="flex items-center justify-between px-4 py-2">
        {/* Left: System ID */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className={clsx(
              'w-2 h-2 rounded-full',
              connected ? 'bg-status-nominal pulse-live' : 'bg-status-critical'
            )} />
            <span className="text-sm font-semibold tracking-wide">ADS-B INTEL</span>
            <span className="text-2xs text-slate-500 font-mono">v1.0</span>
          </div>

          <div className="h-4 w-px bg-surface-3" />

          {/* Live stats */}
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-slate-500 text-xs uppercase tracking-wider">Tracking</span>
              <span className="font-mono font-semibold text-accent-primary">
                {aircraftCount}
                {isFiltered && (
                  <span className="text-slate-500 font-normal">/{totalAircraftCount}</span>
                )}
              </span>
            </div>
            <Stat label="Positions" value={stats?.total_positions_today?.toLocaleString()} />
            <Stat
              label="Anomalies"
              value={stats?.anomalies_today}
              color={stats?.anomalies_today ? 'text-status-caution' : undefined}
            />
          </div>
        </div>

        {/* Right: Controls */}
        <div className="flex items-center gap-3">
          {lastUpdate && (
            <span className="text-xs text-slate-500">
              {formatDistanceToNow(lastUpdate)} ago
            </span>
          )}

          <div className="h-4 w-px bg-surface-3" />

          {/* Filters toggle */}
          <button
            onClick={onToggleFilters}
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium transition-colors',
              showFilters
                ? 'bg-accent-primary/20 text-accent-primary'
                : isFiltered
                  ? 'bg-yellow-500/20 text-yellow-400'
                  : 'bg-surface-3 text-slate-400 hover:text-slate-200'
            )}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            <span>FILTER</span>
            {isFiltered && <span className="font-mono text-2xs">ON</span>}
          </button>

          {/* Overlays toggle */}
          <button
            onClick={onToggleOverlays}
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium transition-colors',
              showOverlays
                ? 'bg-accent-primary/20 text-accent-primary'
                : 'bg-surface-3 text-slate-400 hover:text-slate-200'
            )}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <circle cx="12" cy="12" r="10" strokeWidth="1.5" />
              <circle cx="12" cy="12" r="6" strokeWidth="1.5" />
              <circle cx="12" cy="12" r="2" strokeWidth="1.5" />
            </svg>
            <span>OVERLAYS</span>
          </button>

          {/* Export dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowExport(!showExport)}
              className={clsx(
                'flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium transition-colors',
                showExport
                  ? 'bg-accent-primary/20 text-accent-primary'
                  : 'bg-surface-3 text-slate-400 hover:text-slate-200'
              )}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span>EXPORT</span>
            </button>
            {showExport && (
              <div className="absolute right-0 top-full mt-1 bg-surface-1 border border-surface-3 rounded shadow-lg z-50 min-w-32">
                <button
                  onClick={handleExportCSV}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-surface-2 transition-colors flex items-center gap-2"
                >
                  <span className="font-mono text-2xs text-slate-500">CSV</span>
                  <span>Spreadsheet</span>
                </button>
                <button
                  onClick={handleExportJSON}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-surface-2 transition-colors flex items-center gap-2"
                >
                  <span className="font-mono text-2xs text-slate-500">JSON</span>
                  <span>Raw Data</span>
                </button>
              </div>
            )}
          </div>

          {/* Alerts toggle */}
          <button
            onClick={onToggleAlerts}
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded text-xs font-medium transition-colors',
              alertsOpen
                ? 'bg-accent-primary/20 text-accent-primary'
                : hasAlerts
                  ? 'bg-status-critical/20 text-status-critical'
                  : 'bg-surface-3 text-slate-400 hover:text-slate-200'
            )}
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

function Stat({ label, value, highlight, color }: {
  label: string;
  value?: string | number | null;
  highlight?: boolean;
  color?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-500 text-xs uppercase tracking-wider">{label}</span>
      <span className={clsx(
        'font-mono font-semibold',
        color || (highlight ? 'text-accent-primary' : 'text-slate-300')
      )}>
        {value ?? '—'}
      </span>
    </div>
  );
}
