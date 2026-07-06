import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useAircraft, useFlightTrail } from '@/hooks';
import type { Aircraft } from '@/types';

// Custom aircraft icon
const createAircraftIcon = (track: number | null, isSelected: boolean) => {
  const rotation = track ?? 0;
  const color = isSelected ? '#22c55e' : '#3b82f6';

  return L.divIcon({
    className: 'aircraft-icon',
    html: `
      <svg width="24" height="24" viewBox="0 0 24 24" style="transform: rotate(${rotation}deg)">
        <path
          d="M12 2L4 12h3v8h10v-8h3L12 2z"
          fill="${color}"
          stroke="#fff"
          stroke-width="1"
        />
      </svg>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
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

  return (
    <Marker
      position={[aircraft.latitude, aircraft.longitude]}
      icon={createAircraftIcon(aircraft.track, isSelected)}
      eventHandlers={{
        click: () => onSelect(aircraft.icao_hex),
      }}
    >
      <Popup>
        <div className="text-sm">
          <p className="font-bold">{aircraft.callsign || aircraft.icao_hex}</p>
          <p>ICAO: {aircraft.icao_hex}</p>
          <p>Altitude: {aircraft.altitude?.toLocaleString() ?? 'N/A'} ft</p>
          <p>Speed: {aircraft.ground_speed ?? 'N/A'} kts</p>
          <p>Squawk: {aircraft.squawk ?? 'N/A'}</p>
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

  const positions: [number, number][] = trail.positions.map((p) => [
    p.latitude,
    p.longitude,
  ]);

  return (
    <Polyline
      positions={positions}
      pathOptions={{
        color: '#22c55e',
        weight: 2,
        opacity: 0.7,
        dashArray: '5, 5',
      }}
    />
  );
}

// Component to fit map to aircraft bounds
function MapBoundsUpdater({ aircraft }: { aircraft: Aircraft[] }) {
  const map = useMap();

  useEffect(() => {
    if (aircraft.length === 0) return;

    const validAircraft = aircraft.filter(
      (a) => a.latitude !== null && a.longitude !== null
    );

    if (validAircraft.length === 0) return;

    const bounds = L.latLngBounds(
      validAircraft.map((a) => [a.latitude!, a.longitude!])
    );

    // Only fit bounds on initial load
    if (map.getZoom() === undefined) {
      map.fitBounds(bounds, { padding: [50, 50] });
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

  // Default center on Columbus, Ohio
  const defaultCenter: [number, number] = [39.9612, -82.9988];

  return (
    <MapContainer
      center={defaultCenter}
      zoom={8}
      className="h-full w-full"
      style={{ background: '#0a1628' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://carto.com/">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />

      <MapBoundsUpdater aircraft={aircraft} />

      {aircraft.map((a) => (
        <AircraftMarker
          key={a.icao_hex}
          aircraft={a}
          isSelected={a.icao_hex === selectedAircraft}
          onSelect={onSelectAircraft}
        />
      ))}

      {selectedAircraft && <FlightTrailLine icao={selectedAircraft} />}
    </MapContainer>
  );
}
