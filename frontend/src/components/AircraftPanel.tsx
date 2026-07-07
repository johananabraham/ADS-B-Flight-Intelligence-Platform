import { useAircraft } from '@/hooks';
import type { Aircraft } from '@/types';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

interface AircraftPanelProps {
  selectedAircraft: string | null;
  onSelectAircraft: (icao: string | null) => void;
}

function AircraftRow({
  aircraft,
  isSelected,
  onClick,
}: {
  aircraft: Aircraft;
  isSelected: boolean;
  onClick: () => void;
}) {
  const isEmergency = ['7500', '7600', '7700'].includes(aircraft.squawk ?? '');

  const getAltitudeColor = (alt: number | null) => {
    if (!alt) return 'text-slate-500';
    if (alt > 35000) return 'text-cyan-400';
    if (alt > 20000) return 'text-sky-400';
    if (alt > 10000) return 'text-emerald-400';
    return 'text-amber-400';
  };

  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left px-3 py-2.5 transition-all',
        'border-l-2',
        isSelected
          ? 'bg-accent-primary/10 border-accent-primary'
          : isEmergency
            ? 'border-status-critical bg-status-critical/5 hover:bg-status-critical/10'
            : 'border-transparent hover:bg-surface-3/50'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono font-semibold text-sm truncate">
              {aircraft.callsign || aircraft.icao_hex}
            </span>
            {aircraft.callsign && (
              <span className="text-2xs text-slate-500 font-mono">
                {aircraft.icao_hex}
              </span>
            )}
          </div>
        </div>

        {aircraft.squawk && (
          <span
            className={clsx(
              'text-2xs font-mono px-1.5 py-0.5 rounded',
              isEmergency
                ? 'bg-status-critical text-white'
                : 'bg-surface-3 text-slate-400'
            )}
          >
            {aircraft.squawk}
          </span>
        )}
      </div>

      <div className="mt-1.5 grid grid-cols-4 gap-x-2 text-2xs">
        <div>
          <span className="text-slate-500 block">ALT</span>
          <span className={clsx('font-mono', getAltitudeColor(aircraft.altitude))}>
            {aircraft.altitude ? `${(aircraft.altitude / 1000).toFixed(1)}k` : '—'}
          </span>
        </div>
        <div>
          <span className="text-slate-500 block">SPD</span>
          <span className="font-mono text-slate-300">
            {aircraft.ground_speed?.toFixed(0) ?? '—'}
          </span>
        </div>
        <div>
          <span className="text-slate-500 block">HDG</span>
          <span className="font-mono text-slate-300">
            {aircraft.track ? `${aircraft.track.toFixed(0)}°` : '—'}
          </span>
        </div>
        <div>
          <span className="text-slate-500 block">V/S</span>
          <span className={clsx(
            'font-mono',
            aircraft.vertical_rate && aircraft.vertical_rate > 500 ? 'text-emerald-400' :
            aircraft.vertical_rate && aircraft.vertical_rate < -500 ? 'text-amber-400' :
            'text-slate-300'
          )}>
            {aircraft.vertical_rate ? (aircraft.vertical_rate > 0 ? '+' : '') + aircraft.vertical_rate : '—'}
          </span>
        </div>
      </div>
    </button>
  );
}

export function AircraftPanel({
  selectedAircraft,
  onSelectAircraft,
}: AircraftPanelProps) {
  const { data: aircraft = [], isLoading } = useAircraft();

  // Sort: emergencies first, then by altitude descending
  const sortedAircraft = [...aircraft].sort((a, b) => {
    const aEmergency = ['7500', '7600', '7700'].includes(a.squawk ?? '');
    const bEmergency = ['7500', '7600', '7700'].includes(b.squawk ?? '');
    if (aEmergency && !bEmergency) return -1;
    if (!aEmergency && bEmergency) return 1;
    return (b.altitude ?? 0) - (a.altitude ?? 0);
  });

  return (
    <div className="panel rounded-lg h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2.5 border-b border-surface-3 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-accent-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
            <span className="text-xs font-semibold uppercase tracking-wider">Aircraft</span>
          </div>
          <span className="text-xs font-mono text-accent-primary">
            {aircraft.length}
          </span>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-slate-500 text-sm">
            Scanning...
          </div>
        ) : aircraft.length === 0 ? (
          <div className="p-4 text-center">
            <p className="text-slate-500 text-sm">No aircraft detected</p>
            <p className="text-slate-600 text-xs mt-1">
              Ensure dump1090 is running
            </p>
          </div>
        ) : (
          <div className="divide-y divide-surface-3/50">
            {sortedAircraft.map((a) => (
              <AircraftRow
                key={a.icao_hex}
                aircraft={a}
                isSelected={a.icao_hex === selectedAircraft}
                onClick={() =>
                  onSelectAircraft(
                    a.icao_hex === selectedAircraft ? null : a.icao_hex
                  )
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
