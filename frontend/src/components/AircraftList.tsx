import { useAircraft } from '@/hooks';
import type { Aircraft } from '@/types';
import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';

interface AircraftListProps {
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

  return (
    <div
      onClick={onClick}
      className={clsx(
        'p-3 border-b border-gray-700 cursor-pointer transition-colors',
        isSelected ? 'bg-green-900/30' : 'hover:bg-gray-800',
        isEmergency && 'border-l-4 border-l-red-500'
      )}
    >
      <div className="flex justify-between items-start">
        <div>
          <p className="font-mono font-bold text-white">
            {aircraft.callsign || aircraft.icao_hex}
          </p>
          <p className="text-xs text-gray-400">
            ICAO: {aircraft.icao_hex}
          </p>
        </div>
        {aircraft.squawk && (
          <span
            className={clsx(
              'text-xs px-2 py-1 rounded font-mono',
              isEmergency
                ? 'bg-red-500 text-white'
                : 'bg-gray-700 text-gray-300'
            )}
          >
            {aircraft.squawk}
          </span>
        )}
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-400">
        <div>
          <span className="text-gray-500">ALT:</span>{' '}
          {aircraft.altitude?.toLocaleString() ?? '--'} ft
        </div>
        <div>
          <span className="text-gray-500">SPD:</span>{' '}
          {aircraft.ground_speed ?? '--'} kts
        </div>
        <div>
          <span className="text-gray-500">VS:</span>{' '}
          {aircraft.vertical_rate ?? '--'} ft/m
        </div>
        <div>
          <span className="text-gray-500">TRK:</span>{' '}
          {aircraft.track?.toFixed(0) ?? '--'}°
        </div>
      </div>

      <p className="mt-1 text-xs text-gray-500">
        Updated {formatDistanceToNow(new Date(aircraft.last_seen))} ago
      </p>
    </div>
  );
}

export function AircraftList({
  selectedAircraft,
  onSelectAircraft,
}: AircraftListProps) {
  const { data: aircraft = [], isLoading, error } = useAircraft();

  // Sort by altitude descending
  const sortedAircraft = [...aircraft].sort(
    (a, b) => (b.altitude ?? 0) - (a.altitude ?? 0)
  );

  if (isLoading) {
    return (
      <div className="p-4 text-gray-400 text-center">
        Loading aircraft...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-red-400 text-center">
        Error loading aircraft
      </div>
    );
  }

  if (aircraft.length === 0) {
    return (
      <div className="p-4 text-gray-400 text-center">
        <p>No aircraft detected</p>
        <p className="text-xs mt-2">
          Make sure dump1090 is running and the ingestion service is active.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-y-auto h-full">
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
  );
}
