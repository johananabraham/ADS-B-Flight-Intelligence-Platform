import { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useAircraft, useFlightTrail } from '@/hooks';
import type { Aircraft } from '@/types';

// Aircraft icon SVG - clean, minimal design
const createAircraftIcon = (track: number | null, isSelected: boolean, isEmergency: boolean) => {
  const rotation = track ?? 0;

  // Color based on state
  let color = '#00d4ff'; // default cyan
  if (isEmergency) {
    color = '#ef4444'; // red for emergency
  } else if (isSelected) {
    color = '#10b981'; // green for selected
  }

  const size = isSelected ? 28 : 22;
  const shadowBlur = isSelected ? 8 : 4;

  return L.divIcon({
    className: `aircraft-marker ${isEmergency ? 'emergency' : ''}`,
    html: `
      <svg width="${size}" height="${size}" viewBox="0 0 24 24" style="transform: rotate(${rotation}deg); filter: drop-shadow(0 0 ${shadowBlur}px ${color});">
        <path
          d="M12 2 L14 8 L20 10 L14 12 L14 18 L12 16 L10 18 L10 12 L4 10 L10 8 Z"
          fill="${color}"
          stroke="rgba(255,255,255,0.3)"
          stroke-width="0.5"
        />
      </svg>
    `,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
};

interface AircraftMarkerProps {
  aircraft: Aircraft;
  isSelected: boolean;
  onSelect: (icao: string) => void;
}

function AircraftMarker({ aircraft, isSelected, onSelect }: AircraftMarkerProps) {
  if (aircraft.latitude === null || aircraft.longitude === null) {
    return null;
  }

  const isEmergency = ['7500', '7600', '7700'].includes(aircraft.squawk ?? '');

  return (
    <Marker
      position={[aircraft.latitude, aircraft.longitude]}
      icon={createAircraftIcon(aircraft.track, isSelected, isEmergency)}
      eventHandlers={{
        click: () => onSelect(aircraft.icao_hex),
      }}
    >
      <Popup>
        <div className="min-w-[180px]">
          <div className="flex items-center justify-between border-b border-surface-3 pb-2 mb-2">
            <span className="font-mono font-bold text-accent-primary">
              {aircraft.callsign || aircraft.icao_hex}
            </span>
            {aircraft.squawk && (
              <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                isEmergency ? 'bg-status-critical text-white' : 'bg-surface-3 text-slate-400'
              }`}>
                {aircraft.squawk}
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div>
              <span className="text-slate-500">ICAO</span>
              <span className="ml-2 font-mono">{aircraft.icao_hex}</span>
            </div>
            <div>
              <span className="text-slate-500">ALT</span>
              <span className="ml-2 font-mono text-cyan-400">
                {aircraft.altitude?.toLocaleString() ?? '—'} ft
              </span>
            </div>
            <div>
              <span className="text-slate-500">SPD</span>
              <span className="ml-2 font-mono">{aircraft.ground_speed ?? '—'} kts</span>
            </div>
            <div>
              <span className="text-slate-500">HDG</span>
              <span className="ml-2 font-mono">{aircraft.track?.toFixed(0) ?? '—'}°</span>
            </div>
            <div>
              <span className="text-slate-500">V/S</span>
              <span className="ml-2 font-mono">
                {aircraft.vertical_rate ? `${aircraft.vertical_rate > 0 ? '+' : ''}${aircraft.vertical_rate}` : '—'} fpm
              </span>
            </div>
            <div>
              <span className="text-slate-500">MSGS</span>
              <span className="ml-2 font-mono">{aircraft.messages_received}</span>
            </div>
          </div>
        </div>
      </Popup>
    </Marker>
  );
}

interface FlightTrailLineProps {
  icao: string;
}

function FlightTrailLine({ icao }: FlightTrailLineProps) {
  const { data: trail } = useFlightTrail(icao);

  if (!trail || trail.positions.length < 2) {
    return null;
  }

  // Create segments with fading opacity (radar persistence effect)
  const positions = trail.positions;
  const segments: JSX.Element[] = [];

  for (let i = 1; i < positions.length; i++) {
    const opacity = 0.2 + (i / positions.length) * 0.6; // Fade from 0.2 to 0.8

    segments.push(
      <Polyline
        key={i}
        positions={[
          [positions[i - 1].latitude, positions[i - 1].longitude],
          [positions[i].latitude, positions[i].longitude],
        ]}
        pathOptions={{
          color: '#00d4ff',
          weight: 2,
          opacity: opacity,
        }}
      />
    );
  }

  return <>{segments}</>;
}

// Component to set initial map bounds
function MapController({ aircraft }: { aircraft: Aircraft[] }) {
  const map = useMap();

  useEffect(() => {
    // Only adjust on first load with data
    const validAircraft = aircraft.filter(
      (a) => a.latitude !== null && a.longitude !== null
    );

    if (validAircraft.length > 0 && map.getZoom() === 8) {
      const bounds = L.latLngBounds(
        validAircraft.map((a) => [a.latitude!, a.longitude!])
      );
      map.fitBounds(bounds, { padding: [80, 80], maxZoom: 9 });
    }
  }, [aircraft.length > 0]);

  return null;
}

interface FlightMapProps {
  selectedAircraft: string | null;
  onSelectAircraft: (icao: string | null) => void;
}

export function FlightMap({ selectedAircraft, onSelectAircraft }: FlightMapProps) {
  const { data: aircraft = [] } = useAircraft();

  // Center on Columbus, Ohio (where the SDR is)
  const defaultCenter: [number, number] = [39.9612, -82.9988];

  return (
    <MapContainer
      center={defaultCenter}
      zoom={8}
      className="h-full w-full"
      zoomControl={false}
    >
      {/* Dark map tiles */}
      <TileLayer
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />

      <MapController aircraft={aircraft} />

      {/* Flight trail for selected aircraft */}
      {selectedAircraft && <FlightTrailLine icao={selectedAircraft} />}

      {/* Aircraft markers */}
      {aircraft.map((a) => (
        <AircraftMarker
          key={a.icao_hex}
          aircraft={a}
          isSelected={a.icao_hex === selectedAircraft}
          onSelect={onSelectAircraft}
        />
      ))}
    </MapContainer>
  );
}
