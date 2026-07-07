import { useFlightTrail } from '@/hooks';
import type { Aircraft } from '@/types';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

interface AircraftDetailProps {
  aircraft: Aircraft;
  onClose: () => void;
}

export function AircraftDetail({ aircraft, onClose }: AircraftDetailProps) {
  const { data: trail } = useFlightTrail(aircraft.icao_hex, 60);
  const isEmergency = ['7500', '7600', '7700'].includes(aircraft.squawk ?? '');

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
