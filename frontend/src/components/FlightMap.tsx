import { useMemo, memo, useEffect, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, useMap, Circle } from 'react-leaflet';
import L from 'leaflet';
import { useFlightTrail } from '@/hooks';
import type { Aircraft } from '@/types';
import type { Geofence } from './GeofencePanel';
import { RangeRings, AirportMarkers } from './MapOverlays';

// Cache icons to prevent recreation
const iconCache = new Map<string, L.DivIcon>();

function getAircraftIcon(track: number | null, isSelected: boolean, isEmergency: boolean): L.DivIcon {
  const rotation = Math.round((track ?? 0) / 5) * 5;
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

  const handleClick = useCallback((e: L.LeafletMouseEvent) => {
    L.DomEvent.stopPropagation(e.originalEvent);
    onSelect(aircraft.icao_hex);
  }, [aircraft.icao_hex, onSelect]);

  return (
    <Marker
      position={[aircraft.latitude, aircraft.longitude]}
      icon={icon}
      eventHandlers={{ click: handleClick }}
    />
  );
}, (prev, next) => {
  // Custom comparison for memo
  return (
    prev.aircraft.icao_hex === next.aircraft.icao_hex &&
    prev.aircraft.latitude === next.aircraft.latitude &&
    prev.aircraft.longitude === next.aircraft.longitude &&
    prev.aircraft.track === next.aircraft.track &&
    prev.aircraft.squawk === next.aircraft.squawk &&
    prev.isSelected === next.isSelected
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

function MapClickHandler({ onClick }: { onClick: () => void }) {
  const map = useMap();

  useEffect(() => {
    const handler = () => onClick();
    map.on('click', handler);
    return () => {
      map.off('click', handler);
    };
  }, [map, onClick]);

  return null;
}

interface FlightMapProps {
  aircraft: Aircraft[];
  selectedAircraft: string | null;
  onSelectAircraft: (icao: string | null) => void;
  showOverlays?: boolean;
  showHeatmap?: boolean;
  geofences?: Geofence[];
}

// Nautical miles to meters conversion
const NM_TO_METERS = 1852;

// Geofence layer component
const GeofenceLayer = memo(function GeofenceLayer({ geofences }: { geofences: Geofence[] }) {
  return (
    <>
      {geofences.filter(f => f.active && f.type === 'circle' && f.center && f.radius).map(fence => (
        <Circle
          key={fence.id}
          center={[fence.center!.lat, fence.center!.lng]}
          radius={fence.radius! * NM_TO_METERS}
          pathOptions={{
            color: fence.color,
            fillColor: fence.color,
            fillOpacity: 0.1,
            weight: 2,
            dashArray: '5, 10',
          }}
        />
      ))}
    </>
  );
});

// Simple heatmap visualization using circles
const HeatmapLayer = memo(function HeatmapLayer({ aircraft }: { aircraft: Aircraft[] }) {
  // Create density grid
  const heatmapData = useMemo(() => {
    const grid = new Map<string, { lat: number; lng: number; count: number }>();
    const gridSize = 0.1; // ~10km grid cells

    aircraft.forEach(a => {
      if (a.latitude === null || a.longitude === null) return;
      const gridLat = Math.floor(a.latitude / gridSize) * gridSize;
      const gridLng = Math.floor(a.longitude / gridSize) * gridSize;
      const key = `${gridLat},${gridLng}`;

      if (grid.has(key)) {
        grid.get(key)!.count++;
      } else {
        grid.set(key, { lat: gridLat + gridSize / 2, lng: gridLng + gridSize / 2, count: 1 });
      }
    });

    return Array.from(grid.values());
  }, [aircraft]);

  return (
    <>
      {heatmapData.map(cell => (
        <Circle
          key={`${cell.lat},${cell.lng}`}
          center={[cell.lat, cell.lng]}
          radius={cell.count * 2000}
          pathOptions={{
            color: 'transparent',
            fillColor: cell.count > 3 ? '#ef4444' : cell.count > 1 ? '#f59e0b' : '#22c55e',
            fillOpacity: 0.3,
          }}
        />
      ))}
    </>
  );
});

export function FlightMap({ aircraft, selectedAircraft, onSelectAircraft, showOverlays = true, showHeatmap = false, geofences = [] }: FlightMapProps) {

  const defaultCenter: [number, number] = [39.9612, -82.9988];

  const handleMapClick = useCallback(() => {
    onSelectAircraft(null);
  }, [onSelectAircraft]);

  return (
    <MapContainer
      center={defaultCenter}
      zoom={8}
      className="h-full w-full"
      zoomControl={false}
    >
      {/* Dark theme map with visible features */}
      <TileLayer
        attribution='&copy; Stadia Maps'
        url="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png"
      />

      <MapClickHandler onClick={handleMapClick} />

      {/* Heatmap layer */}
      {showHeatmap && <HeatmapLayer aircraft={aircraft} />}

      {/* Geofence layer */}
      {geofences.length > 0 && <GeofenceLayer geofences={geofences} />}

      {/* Map overlays */}
      {showOverlays && (
        <>
          <RangeRings />
          <AirportMarkers />
        </>
      )}

      {/* Flight trail for selected aircraft */}
      {selectedAircraft && <FlightTrail icao={selectedAircraft} />}

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
