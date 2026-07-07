import { Circle, CircleMarker, Tooltip } from 'react-leaflet';
import { memo } from 'react';

// Receiver location (Columbus, Ohio)
const RECEIVER_LOCATION: [number, number] = [39.9612, -82.9988];

// Range rings in nautical miles
const RANGE_RINGS = [50, 100, 150, 200];

// Major airports near Columbus
const AIRPORTS = [
  { code: 'CMH', name: 'John Glenn Columbus Intl', lat: 39.9980, lon: -82.8919 },
  { code: 'DAY', name: 'Dayton International', lat: 39.9024, lon: -84.2194 },
  { code: 'CVG', name: 'Cincinnati/N. Kentucky Intl', lat: 39.0488, lon: -84.6678 },
  { code: 'CLE', name: 'Cleveland Hopkins Intl', lat: 41.4117, lon: -81.8498 },
  { code: 'PIT', name: 'Pittsburgh International', lat: 40.4915, lon: -80.2329 },
  { code: 'IND', name: 'Indianapolis International', lat: 39.7173, lon: -86.2944 },
  { code: 'LCK', name: 'Rickenbacker Intl', lat: 39.8138, lon: -82.9278 },
];

// Restricted airspace zones (example)
const RESTRICTED_ZONES = [
  { name: 'R-5501A', lat: 40.05, lon: -82.88, radius: 5 }, // Example
];

export const RangeRings = memo(function RangeRings() {
  return (
    <>
      {RANGE_RINGS.map((range) => (
        <Circle
          key={range}
          center={RECEIVER_LOCATION}
          radius={range * 1852} // Convert NM to meters
          pathOptions={{
            color: '#1e3a5f',
            weight: 1,
            fill: false,
            dashArray: '4, 8',
            opacity: 0.5,
          }}
        >
          <Tooltip
            permanent
            direction="right"
            className="range-tooltip"
            offset={[10, 0]}
          >
            <span className="text-2xs font-mono text-slate-500">{range}nm</span>
          </Tooltip>
        </Circle>
      ))}
      {/* Receiver location marker */}
      <CircleMarker
        center={RECEIVER_LOCATION}
        radius={6}
        pathOptions={{
          color: '#10b981',
          fillColor: '#10b981',
          fillOpacity: 1,
          weight: 2,
        }}
      >
        <Tooltip direction="top" offset={[0, -8]}>
          <span className="text-xs font-medium">SDR Receiver</span>
        </Tooltip>
      </CircleMarker>
    </>
  );
});

export const AirportMarkers = memo(function AirportMarkers() {
  return (
    <>
      {AIRPORTS.map((airport) => (
        <CircleMarker
          key={airport.code}
          center={[airport.lat, airport.lon]}
          radius={4}
          pathOptions={{
            color: '#6366f1',
            fillColor: '#6366f1',
            fillOpacity: 0.8,
            weight: 1,
          }}
        >
          <Tooltip direction="top" offset={[0, -6]}>
            <div className="text-xs">
              <div className="font-bold text-indigo-400">{airport.code}</div>
              <div className="text-slate-400 text-2xs">{airport.name}</div>
            </div>
          </Tooltip>
        </CircleMarker>
      ))}
    </>
  );
});

export const RestrictedZones = memo(function RestrictedZones() {
  return (
    <>
      {RESTRICTED_ZONES.map((zone) => (
        <Circle
          key={zone.name}
          center={[zone.lat, zone.lon]}
          radius={zone.radius * 1852}
          pathOptions={{
            color: '#ef4444',
            fillColor: '#ef4444',
            fillOpacity: 0.1,
            weight: 1,
            dashArray: '4, 4',
          }}
        >
          <Tooltip>
            <span className="text-xs font-mono text-red-400">{zone.name}</span>
          </Tooltip>
        </Circle>
      ))}
    </>
  );
});
