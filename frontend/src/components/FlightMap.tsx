import { useMemo, memo, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import { useAircraft, useFlightTrail } from '@/hooks';
import type { Aircraft } from '@/types';

// Cache icons to prevent recreation
const iconCache = new Map<string, L.DivIcon>();

function getAircraftIcon(track: number | null, isSelected: boolean, isEmergency: boolean): L.DivIcon {
  const rotation = Math.round((track ?? 0) / 5) * 5; // Round to nearest 5 degrees
  const key = `${rotation}-${isSelected}-${isEmergency}`;

  if (iconCache.has(key)) {
    return iconCache.get(key)!;
  }

  let color = '#00d4ff';
  if (isEmergency) color = '#ef4444';
  else if (isSelected) color = '#10b981';

  const size = isSelected ? 28 : 22;

  const icon = L.divIcon({
    className: 'aircraft-marker',
    html: `<svg width="${size}" height="${size}" viewBox="0 0 24 24" style="transform:rotate(${rotation}deg)">
      <path d="M12 2 L14 8 L20 10 L14 12 L14 18 L12 16 L10 18 L10 12 L4 10 L10 8 Z" fill="${color}" stroke="#fff" stroke-width="0.5"/>
    </svg>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });

  iconCache.set(key, icon);
  return icon;
}

interface AircraftMarkerProps {
  aircraft: Aircraft;
  isSelected: boolean;
  onSelect: (icao: string) => void;
}

const AircraftMarker = memo(function AircraftMarker({ aircraft, isSelected, onSelect }: AircraftMarkerProps) {
  if (aircraft.latitude === null || aircraft.longitude === null) {
    return null;
  }

  const isEmergency = ['7500', '7600', '7700'].includes(aircraft.squawk ?? '');
  const icon = getAircraftIcon(aircraft.track, isSelected, isEmergency);

  return (
    <Marker
      position={[aircraft.latitude, aircraft.longitude]}
      icon={icon}
      eventHandlers={{
        click: (e) => {
          L.DomEvent.stopPropagation(e.originalEvent);
          onSelect(aircraft.icao_hex);
        },
      }}
    />
  );
});

const FlightTrail = memo(function FlightTrail({ icao }: { icao: string }) {
  const { data: trail } = useFlightTrail(icao, 30);

  const positions = useMemo(() => {
    if (!trail || trail.positions.length < 2) return null;
    return trail.positions.map(p => [p.latitude, p.longitude] as [number, number]);
  }, [trail]);

  if (!positions) return null;

  return (
    <Polyline
      positions={positions}
      pathOptions={{
        color: '#00d4ff',
        weight: 2,
        opacity: 0.6,
      }}
    />
  );
});

function MapBounds({ aircraft }: { aircraft: Aircraft[] }) {
  const map = useMap();

  const validAircraft = aircraft.filter(a => a.latitude !== null && a.longitude !== null);

  if (validAircraft.length > 0) {
    const bounds = L.latLngBounds(validAircraft.map(a => [a.latitude!, a.longitude!]));
    const currentBounds = map.getBounds();

    // Only fit bounds if aircraft are outside current view
    if (!currentBounds.contains(bounds)) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 10, animate: false });
    }
  }

  return null;
}

interface FlightMapProps {
  selectedAircraft: string | null;
  onSelectAircraft: (icao: string | null) => void;
}

export function FlightMap({ selectedAircraft, onSelectAircraft }: FlightMapProps) {
  const { data: aircraft = [] } = useAircraft();

  const defaultCenter: [number, number] = [39.9612, -82.9988];

  const handleMapClick = () => {
    onSelectAircraft(null);
  };

  return (
    <MapContainer
      center={defaultCenter}
      zoom={8}
      className="h-full w-full"
      zoomControl={false}
    >
      <TileLayer
        attribution='&copy; CARTO'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />

      <MapClickHandler onClick={handleMapClick} />

      {selectedAircraft && <FlightTrail icao={selectedAircraft} />}

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

function MapClickHandler({ onClick }: { onClick: () => void }) {
  const map = useMap();

  useEffect(() => {
    map.on('click', onClick);
    return () => {
      map.off('click', onClick);
    };
  }, [map, onClick]);

  return null;
}
