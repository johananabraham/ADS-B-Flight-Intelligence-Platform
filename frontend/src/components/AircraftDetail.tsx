import { useState, useEffect } from 'react';
import {
  useFlightTrail,
  useKinematicEvaluations,
  useWindowKinematicEvaluations,
} from '@/hooks';
import type { Aircraft } from '@/types';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';
import { IntegrityEvidence } from './IntegrityEvidence';

interface SafetyContext {
  aircraft: string;
  incidents: {
    total_count: number;
    fatal_count: number;
    by_phase: { phase: string; count: number }[];
    recent_examples: { ntsb_id: string; excerpt: string; event_date: string }[];
  };
  risk_factors: { factor: string; count: number }[];
  error?: string;
}

interface FlightRoute {
  callsign: string | null;
  origin: string | null;
  destination: string | null;
  route?: string[];
  operator?: string;
  flight_number?: string;
  error?: string;
}

interface AircraftDetailProps {
  aircraft: Aircraft;
  onClose: () => void;
}

export function AircraftDetail({ aircraft, onClose }: AircraftDetailProps) {
  const { data: trail } = useFlightTrail(aircraft.icao_hex, 60);
  const isEmergency = ['7500', '7600', '7700'].includes(aircraft.squawk ?? '');
  const [safetyContext, setSafetyContext] = useState<SafetyContext | null>(null);
  const [safetyLoading, setSafetyLoading] = useState(false);
  const [showSafety, setShowSafety] = useState(false);
  const [flightRoute, setFlightRoute] = useState<FlightRoute | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [showIntegrity, setShowIntegrity] = useState(false);
  const {
    data: kinematicEvaluations = [],
    isLoading: integrityLoading,
    isError: integrityError,
  } = useKinematicEvaluations(aircraft.icao_hex);
  const latestEvaluation = kinematicEvaluations[0];
  const {
    data: windowEvaluations = [],
    isLoading: windowLoading,
    isError: windowError,
  } = useWindowKinematicEvaluations(aircraft.icao_hex);
  const latestWindowEvaluation = windowEvaluations[0];

  // Fetch flight route on mount
  useEffect(() => {
    if (!aircraft.callsign) {
      setFlightRoute(null);
      return;
    }

    setRouteLoading(true);
    fetch(`/api/v1/aircraft/${aircraft.icao_hex}/route`)
      .then(res => res.json())
      .then(data => setFlightRoute(data))
      .catch(() => setFlightRoute(null))
      .finally(() => setRouteLoading(false));
  }, [aircraft.icao_hex, aircraft.callsign]);

  // Fetch safety context when expanded
  useEffect(() => {
    if (!showSafety || safetyContext) return;

    // Extract aircraft make from callsign patterns (rough heuristic)
    // In real implementation, you'd have aircraft type from database
    const callsign = aircraft.callsign || '';
    let make = 'Unknown';

    // Common airline prefixes to aircraft types
    if (callsign.startsWith('DAL') || callsign.startsWith('AAL') || callsign.startsWith('UAL')) {
      make = 'Boeing'; // Major carriers fly mostly Boeing/Airbus
    } else if (callsign.startsWith('N') && callsign.length <= 6) {
      make = 'Cessna'; // Many GA aircraft
    }

    setSafetyLoading(true);
    fetch(`/api/v1/safety/aircraft/${encodeURIComponent(make)}/context`)
      .then(res => res.json())
      .then(data => setSafetyContext(data))
      .catch(() => setSafetyContext({ aircraft: make, incidents: { total_count: 0, fatal_count: 0, by_phase: [], recent_examples: [] }, risk_factors: [], error: 'Failed to load' }))
      .finally(() => setSafetyLoading(false));
  }, [showSafety, safetyContext, aircraft.callsign]);

  // Calculate flight stats from trail
  const stats = trail?.positions ? {
    maxAlt: Math.max(...trail.positions.map(p => p.altitude ?? 0)),
    minAlt: Math.min(...trail.positions.filter(p => p.altitude).map(p => p.altitude!)),
    avgSpeed: trail.positions.reduce((acc, p) => acc + (p.ground_speed ?? 0), 0) / trail.positions.length,
    distance: calculateDistance(trail.positions),
    duration: trail.positions.length > 1
      ? (new Date(trail.positions[trail.positions.length - 1].timestamp).getTime() -
         new Date(trail.positions[0].timestamp).getTime()) / 1000 / 60
      : 0,
  } : null;

  return (
    <div className="panel rounded-lg overflow-hidden">
      {/* Header */}
      <div className={clsx(
        'px-4 py-3 border-b',
        isEmergency ? 'bg-status-critical/20 border-status-critical/50' : 'border-surface-3'
      )}>
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold font-mono text-accent-primary">
                {aircraft.callsign || aircraft.icao_hex}
              </span>
              {isEmergency && (
                <span className="px-2 py-0.5 bg-status-critical text-white text-xs font-bold rounded animate-pulse">
                  {aircraft.squawk === '7500' ? 'HIJACK' :
                   aircraft.squawk === '7600' ? 'RADIO FAIL' : 'EMERGENCY'}
                </span>
              )}
            </div>
            {aircraft.callsign && (
              <span className="text-xs text-slate-500 font-mono">{aircraft.icao_hex}</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-500 hover:text-slate-300 hover:bg-surface-3 rounded transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Route Information */}
      {(flightRoute || routeLoading) && (
        <div className="p-4 border-b border-surface-3 bg-surface-1">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Flight Info</div>
          {routeLoading ? (
            <div className="text-xs text-slate-500">Loading flight info...</div>
          ) : (
            <>
              {/* Operator */}
              {flightRoute?.operator && (
                <div className="mb-3 text-center">
                  <div className="text-2xs text-slate-500 uppercase">Operator</div>
                  <div className="text-lg text-amber-400">{flightRoute.operator}</div>
                </div>
              )}
              {/* Route if available */}
              {(flightRoute?.origin || flightRoute?.destination) && (
                <div className="flex items-center justify-between gap-4">
                  <div className="text-center flex-1">
                    <div className="text-2xs text-slate-500 uppercase">Origin</div>
                    <div className="font-mono text-lg text-emerald-400">
                      {flightRoute.origin || '—'}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-slate-500">
                    <div className="w-8 h-px bg-slate-600" />
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                    </svg>
                    <div className="w-8 h-px bg-slate-600" />
                  </div>
                  <div className="text-center flex-1">
                    <div className="text-2xs text-slate-500 uppercase">Destination</div>
                    <div className="font-mono text-lg text-cyan-400">
                      {flightRoute.destination || '—'}
                    </div>
                  </div>
                </div>
              )}
              {/* Note about route availability */}
              {!flightRoute?.origin && !flightRoute?.destination && flightRoute?.operator && (
                <div className="text-2xs text-slate-600 text-center mt-2">
                  Route data not available from public APIs
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Current State */}
      <div className="p-4 border-b border-surface-3">
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Current State</div>
        <div className="grid grid-cols-3 gap-4">
          <DataBlock
            label="Altitude"
            value={aircraft.altitude ? `${aircraft.altitude.toLocaleString()}` : '—'}
            unit="ft"
            color="text-cyan-400"
          />
          <DataBlock
            label="Speed"
            value={aircraft.ground_speed?.toFixed(0) ?? '—'}
            unit="kts"
          />
          <DataBlock
            label="Heading"
            value={aircraft.track?.toFixed(0) ?? '—'}
            unit="°"
          />
          <DataBlock
            label="Vertical"
            value={aircraft.vertical_rate ? `${aircraft.vertical_rate > 0 ? '+' : ''}${aircraft.vertical_rate}` : '—'}
            unit="fpm"
            color={aircraft.vertical_rate && aircraft.vertical_rate > 500 ? 'text-emerald-400' :
                   aircraft.vertical_rate && aircraft.vertical_rate < -500 ? 'text-amber-400' : undefined}
          />
          <DataBlock
            label="Squawk"
            value={aircraft.squawk || '—'}
            color={isEmergency ? 'text-status-critical' : undefined}
          />
          <DataBlock
            label="Messages"
            value={aircraft.messages_received.toLocaleString()}
          />
        </div>
      </div>

      {/* Position */}
      <div className="p-4 border-b border-surface-3">
        <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Position</div>
        <div className="grid grid-cols-2 gap-4">
          <DataBlock
            label="Latitude"
            value={aircraft.latitude?.toFixed(4) ?? '—'}
            unit="°N"
          />
          <DataBlock
            label="Longitude"
            value={aircraft.longitude?.toFixed(4) ?? '—'}
            unit="°W"
          />
        </div>
      </div>

      {/* Flight Stats */}
      {stats && stats.duration > 0 && (
        <div className="p-4 border-b border-surface-3">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Flight Statistics (Last Hour)</div>
          <div className="grid grid-cols-3 gap-4">
            <DataBlock
              label="Max Alt"
              value={stats.maxAlt.toLocaleString()}
              unit="ft"
            />
            <DataBlock
              label="Avg Speed"
              value={stats.avgSpeed.toFixed(0)}
              unit="kts"
            />
            <DataBlock
              label="Track Time"
              value={stats.duration.toFixed(0)}
              unit="min"
            />
          </div>
        </div>
      )}

      {/* Altitude Profile */}
      {trail && trail.positions.length > 5 && (
        <div className="p-4 border-b border-surface-3">
          <div className="text-xs text-slate-500 uppercase tracking-wider mb-3">Altitude Profile</div>
          <AltitudeChart positions={trail.positions} />
        </div>
      )}

      <IntegrityEvidence
        evaluation={latestEvaluation}
        windowEvaluation={latestWindowEvaluation}
        expanded={showIntegrity}
        loading={integrityLoading || windowLoading}
        error={integrityError || windowError}
        onToggle={() => setShowIntegrity(value => !value)}
      />

      {/* Safety Context (collapsible) */}
      <div className="border-b border-surface-3">
        <button
          onClick={() => setShowSafety(!showSafety)}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-surface-2 transition-colors"
        >
          <span className="text-xs text-slate-500 uppercase tracking-wider">Safety Research</span>
          <span className="text-slate-500">{showSafety ? '▼' : '▶'}</span>
        </button>
        {showSafety && (
          <div className="px-4 pb-4">
            {safetyLoading && <div className="text-xs text-slate-500">Loading safety data...</div>}
            {safetyContext && !safetyContext.error && (
              <div className="space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2 bg-surface-2 rounded">
                    <div className="text-slate-500">Total Incidents</div>
                    <div className="text-lg font-mono text-amber-400">{safetyContext.incidents.total_count}</div>
                  </div>
                  <div className="p-2 bg-surface-2 rounded">
                    <div className="text-slate-500">Fatal</div>
                    <div className="text-lg font-mono text-red-400">{safetyContext.incidents.fatal_count}</div>
                  </div>
                </div>
                {safetyContext.incidents.by_phase.length > 0 && (
                  <div>
                    <div className="text-slate-500 mb-1">Top Incident Phases</div>
                    {safetyContext.incidents.by_phase.slice(0, 3).map((p, i) => (
                      <div key={i} className="flex justify-between text-slate-400">
                        <span>{p.phase}</span>
                        <span>{p.count}</span>
                      </div>
                    ))}
                  </div>
                )}
                {safetyContext.risk_factors.length > 0 && (
                  <div className="p-2 bg-amber-900/20 border border-amber-500/30 rounded text-amber-300">
                    {safetyContext.risk_factors[0].factor}
                  </div>
                )}
              </div>
            )}
            {safetyContext?.error && (
              <div className="text-xs text-red-400">{safetyContext.error}</div>
            )}
          </div>
        )}
      </div>

      {/* Timing */}
      <div className="p-4 text-xs text-slate-500">
        <div className="flex justify-between">
          <span>First seen</span>
          <span className="text-slate-400">{formatDistanceToNow(new Date(aircraft.first_seen))} ago</span>
        </div>
        <div className="flex justify-between mt-1">
          <span>Last update</span>
          <span className="text-slate-400">{formatDistanceToNow(new Date(aircraft.last_seen))} ago</span>
        </div>
      </div>
    </div>
  );
}

function DataBlock({ label, value, unit, color }: {
  label: string;
  value: string;
  unit?: string;
  color?: string;
}) {
  return (
    <div>
      <div className="text-2xs text-slate-500 uppercase">{label}</div>
      <div className={clsx('font-mono text-lg', color || 'text-slate-200')}>
        {value}
        {unit && <span className="text-xs text-slate-500 ml-1">{unit}</span>}
      </div>
    </div>
  );
}

function AltitudeChart({ positions }: { positions: Array<{ altitude: number | null; timestamp: string }> }) {
  const validPositions = positions.filter(p => p.altitude !== null);
  if (validPositions.length < 2) return null;

  const maxAlt = Math.max(...validPositions.map(p => p.altitude!));
  const minAlt = Math.min(...validPositions.map(p => p.altitude!));
  const range = maxAlt - minAlt || 1;

  const width = 100;
  const height = 40;

  const points = validPositions.map((p, i) => {
    const x = (i / (validPositions.length - 1)) * width;
    const y = height - ((p.altitude! - minAlt) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-12">
      <defs>
        <linearGradient id="altGradient" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#00d4ff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon
        points={`0,${height} ${points} ${width},${height}`}
        fill="url(#altGradient)"
      />
      <polyline
        points={points}
        fill="none"
        stroke="#00d4ff"
        strokeWidth="1"
      />
    </svg>
  );
}

function calculateDistance(positions: Array<{ latitude: number; longitude: number }>): number {
  let distance = 0;
  for (let i = 1; i < positions.length; i++) {
    distance += haversine(
      positions[i - 1].latitude, positions[i - 1].longitude,
      positions[i].latitude, positions[i].longitude
    );
  }
  return distance;
}

function haversine(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 3440.065; // Earth radius in nautical miles
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}
