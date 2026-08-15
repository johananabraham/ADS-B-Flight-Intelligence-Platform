import { useState, useCallback } from 'react';
import { useCriticalAnomalies } from '@/hooks';
import type { Anomaly, AnomalySeverity } from '@/types';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

interface HistoricalMatch {
  ntsb_id: string;
  excerpt: string;
  event_date: string;
  aircraft: string;
  fatal_injuries: number;
}

interface AlertsPanelProps {
  onClose: () => void;
}

const severityConfig: Record<AnomalySeverity, { color: string; bg: string }> = {
  CRITICAL: { color: 'text-status-critical', bg: 'bg-status-critical/20' },
  HIGH: { color: 'text-status-warning', bg: 'bg-status-warning/20' },
  MEDIUM: { color: 'text-status-caution', bg: 'bg-status-caution/20' },
  LOW: { color: 'text-status-nominal', bg: 'bg-status-nominal/20' },
};

const anomalyLabels: Record<string, string> = {
  RAPID_DESCENT: 'RAPID DESCENT',
  RAPID_CLIMB: 'RAPID CLIMB',
  SPEED_ANOMALY: 'SPEED ANOMALY',
  SQUAWK_7500: 'SQUAWK 7500 — HIJACK',
  SQUAWK_7600: 'SQUAWK 7600 — RADIO FAIL',
  SQUAWK_7700: 'SQUAWK 7700 — EMERGENCY',
  TRACK_LOSS: 'TRACK LOSS',
  GHOST_FLIGHT: 'TRACK LOSS (LEGACY)',
  RESTRICTED_AIRSPACE: 'RESTRICTED ZONE',
  ALTITUDE_DEVIATION: 'ALT DEVIATION',
  KINEMATIC_PLAUSIBILITY: 'KINEMATIC INCONSISTENCY',
};

function AlertCard({ anomaly }: { anomaly: Anomaly }) {
  const config = severityConfig[anomaly.severity];
  const isSquawk = anomaly.anomaly_type.startsWith('SQUAWK_');
  const [expanded, setExpanded] = useState(false);
  const [historicalMatches, setHistoricalMatches] = useState<HistoricalMatch[] | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchHistorical = useCallback(async () => {
    if (historicalMatches !== null) return;
    setLoading(true);

    // Map anomaly type to search query
    const queryMap: Record<string, string> = {
      RAPID_DESCENT: 'rapid descent loss of control',
      RAPID_CLIMB: 'unusual climb rate stall',
      SPEED_ANOMALY: 'airspeed anomaly stall',
      SQUAWK_7500: 'hijacking security incident',
      SQUAWK_7600: 'radio communication failure',
      SQUAWK_7700: 'emergency declaration mayday',
      TRACK_LOSS: 'lost contact radar signal lost',
      GHOST_FLIGHT: 'lost contact radar signal lost',
      RESTRICTED_AIRSPACE: 'airspace violation restricted area',
      ALTITUDE_DEVIATION: 'altitude deviation TCAS',
    };

    const query = queryMap[anomaly.anomaly_type] || anomaly.anomaly_type;

    try {
      const res = await fetch('/api/v1/safety/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: `Find incidents similar to: ${query}` }),
      });
      const data = await res.json();

      // Extract incidents from tool calls if available
      const toolResult = data.tool_calls?.find((tc: { name: string }) => tc.name === 'search_incident_narratives');
      if (toolResult?.result?.results) {
        setHistoricalMatches(toolResult.result.results.slice(0, 3));
      } else {
        setHistoricalMatches([]);
      }
    } catch {
      setHistoricalMatches([]);
    } finally {
      setLoading(false);
    }
  }, [anomaly.anomaly_type, historicalMatches]);

  const handleExpand = () => {
    setExpanded(!expanded);
    if (!expanded) fetchHistorical();
  };

  return (
    <div className={clsx('p-3 border-l-2', config.bg, config.color.replace('text-', 'border-'))}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={clsx('text-2xs font-semibold px-1.5 py-0.5 rounded', config.bg, config.color)}>
              {anomaly.severity}
            </span>
            <span className="text-2xs text-slate-500">
              {formatDistanceToNow(new Date(anomaly.detected_at))} ago
            </span>
            <span className="rounded border border-slate-700 px-1.5 py-0.5 text-2xs text-slate-400">
              {anomaly.category === 'INTEGRITY_EVIDENCE' ? 'INTEGRITY' : 'OPERATIONAL'}
            </span>
          </div>

          <p className={clsx('text-sm font-semibold mt-1.5', isSquawk && 'text-status-critical')}>
            {anomalyLabels[anomaly.anomaly_type] || anomaly.anomaly_type}
          </p>

          <p className="text-xs text-slate-400 mt-1 font-mono">
            {anomaly.callsign || anomaly.icao_hex}
          </p>

          {anomaly.description && (
            <p className="text-xs text-slate-500 mt-1 line-clamp-2">
              {anomaly.description}
            </p>
          )}

          {anomaly.altitude && (
            <p className="text-2xs text-slate-600 mt-1 font-mono">
              FL{Math.round(anomaly.altitude / 100)}
            </p>
          )}

          {/* Historical matches toggle */}
          <button
            onClick={handleExpand}
            className="mt-2 text-2xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
          >
            <span>{expanded ? '▼' : '▶'}</span>
            <span>Similar Historical Incidents</span>
          </button>

          {expanded && (
            <div className="mt-2 pl-2 border-l border-surface-3 space-y-2">
              {loading && <p className="text-2xs text-slate-500">Searching NTSB database...</p>}
              {historicalMatches && historicalMatches.length === 0 && (
                <p className="text-2xs text-slate-500">No similar incidents found</p>
              )}
              {historicalMatches && historicalMatches.map((match, i) => (
                <div key={i} className="text-2xs">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-cyan-400">{match.ntsb_id}</span>
                    {match.fatal_injuries > 0 && (
                      <span className="text-red-400">({match.fatal_injuries} fatal)</span>
                    )}
                  </div>
                  <p className="text-slate-500 line-clamp-2 mt-0.5">{match.excerpt}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function AlertsPanel({ onClose }: AlertsPanelProps) {
  const { data: anomalies = [], isLoading } = useCriticalAnomalies(24);

  return (
    <div className="panel rounded-lg h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-surface-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-status-critical" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span className="text-xs font-semibold uppercase tracking-wider">Alerts</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-500 hover:text-slate-300 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-slate-500 text-sm">
            Loading alerts...
          </div>
        ) : anomalies.length === 0 ? (
          <div className="p-4 text-center">
            <div className="w-8 h-8 rounded-full bg-status-nominal/20 text-status-nominal mx-auto flex items-center justify-center">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-status-nominal text-sm font-medium mt-2">All Clear</p>
            <p className="text-slate-600 text-xs mt-1">
              No active alerts in the last 24 hours
            </p>
          </div>
        ) : (
          <div className="divide-y divide-surface-3/50">
            {anomalies.map((a) => (
              <AlertCard key={a.id} anomaly={a} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
