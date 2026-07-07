import { useState, useMemo } from 'react';
import type { Aircraft } from '@/types';

export interface Geofence {
  id: string;
  name: string;
  type: 'circle' | 'polygon';
  center?: { lat: number; lng: number };
  radius?: number; // in nautical miles
  vertices?: { lat: number; lng: number }[];
  color: string;
  active: boolean;
}

interface GeofencePanelProps {
  geofences: Geofence[];
  aircraft: Aircraft[];
  onAddGeofence: (geofence: Geofence) => void;
  onRemoveGeofence: (id: string) => void;
  onToggleGeofence: (id: string) => void;
  onClose: () => void;
}

// Convert degrees to radians
const toRad = (deg: number) => deg * (Math.PI / 180);

// Haversine distance in nautical miles
function haversineDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 3440.065; // Earth's radius in nautical miles
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

// Check if point is inside polygon using ray casting
function isPointInPolygon(lat: number, lng: number, vertices: { lat: number; lng: number }[]): boolean {
  let inside = false;
  for (let i = 0, j = vertices.length - 1; i < vertices.length; j = i++) {
    const xi = vertices[i].lat, yi = vertices[i].lng;
    const xj = vertices[j].lat, yj = vertices[j].lng;

    if ((yi > lng) !== (yj > lng) && lat < ((xj - xi) * (lng - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

export function GeofencePanel({
  geofences,
  aircraft,
  onAddGeofence,
  onRemoveGeofence,
  onToggleGeofence,
  onClose,
}: GeofencePanelProps) {
  const [newFenceName, setNewFenceName] = useState('');
  const [newFenceLat, setNewFenceLat] = useState('');
  const [newFenceLng, setNewFenceLng] = useState('');
  const [newFenceRadius, setNewFenceRadius] = useState('25');

  // Count aircraft in each geofence
  const geofenceViolations = useMemo(() => {
    const violations: Record<string, Aircraft[]> = {};

    geofences.forEach(fence => {
      if (!fence.active) return;
      violations[fence.id] = [];

      aircraft.forEach(a => {
        if (a.latitude === null || a.longitude === null) return;

        if (fence.type === 'circle' && fence.center && fence.radius) {
          const dist = haversineDistance(fence.center.lat, fence.center.lng, a.latitude, a.longitude);
          if (dist <= fence.radius) {
            violations[fence.id].push(a);
          }
        } else if (fence.type === 'polygon' && fence.vertices) {
          if (isPointInPolygon(a.latitude, a.longitude, fence.vertices)) {
            violations[fence.id].push(a);
          }
        }
      });
    });

    return violations;
  }, [geofences, aircraft]);

  const totalViolations = Object.values(geofenceViolations).reduce((sum, arr) => sum + arr.length, 0);

  const handleAddGeofence = () => {
    if (!newFenceName || !newFenceLat || !newFenceLng || !newFenceRadius) return;

    const newFence: Geofence = {
      id: `fence-${Date.now()}`,
      name: newFenceName,
      type: 'circle',
      center: { lat: parseFloat(newFenceLat), lng: parseFloat(newFenceLng) },
      radius: parseFloat(newFenceRadius),
      color: GEOFENCE_COLORS[geofences.length % GEOFENCE_COLORS.length],
      active: true,
    };

    onAddGeofence(newFence);
    setNewFenceName('');
    setNewFenceLat('');
    setNewFenceLng('');
    setNewFenceRadius('25');
  };

  return (
    <div className="panel w-80 max-h-[80vh] overflow-y-auto">
      <div className="p-3 border-b border-surface-3 flex items-center justify-between sticky top-0 bg-surface-1">
        <h3 className="text-sm font-semibold text-cyan-400 tracking-wider uppercase flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
          </svg>
          GEOFENCES
        </h3>
        <div className="flex items-center gap-2">
          {totalViolations > 0 && (
            <span className="px-1.5 py-0.5 bg-red-500/20 text-red-400 text-2xs font-mono rounded">
              {totalViolations} IN ZONE
            </span>
          )}
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div className="p-3 space-y-4">
        {/* Existing Geofences */}
        {geofences.length > 0 ? (
          <div className="space-y-2">
            {geofences.map(fence => {
              const violations = geofenceViolations[fence.id] || [];
              return (
                <div
                  key={fence.id}
                  className={`p-2 rounded border ${
                    violations.length > 0 && fence.active
                      ? 'border-red-500/50 bg-red-500/10'
                      : 'border-surface-3 bg-surface-2/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: fence.color }}
                      />
                      <span className="text-sm font-medium">{fence.name}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => onToggleGeofence(fence.id)}
                        className={`p-1 rounded transition-colors ${
                          fence.active
                            ? 'text-green-400 hover:text-green-300'
                            : 'text-slate-500 hover:text-slate-400'
                        }`}
                        title={fence.active ? 'Deactivate' : 'Activate'}
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          {fence.active ? (
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          ) : (
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          )}
                        </svg>
                      </button>
                      <button
                        onClick={() => onRemoveGeofence(fence.id)}
                        className="p-1 rounded text-slate-500 hover:text-red-400 transition-colors"
                        title="Remove"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  <div className="mt-1 text-2xs text-slate-400">
                    {fence.type === 'circle' && fence.center && (
                      <span>{fence.center.lat.toFixed(3)}, {fence.center.lng.toFixed(3)} • {fence.radius}nm</span>
                    )}
                  </div>
                  {violations.length > 0 && fence.active && (
                    <div className="mt-2 pt-2 border-t border-red-500/30">
                      <span className="text-2xs text-red-400 font-semibold">
                        {violations.length} aircraft in zone:
                      </span>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {violations.slice(0, 5).map(v => (
                          <span key={v.icao_hex} className="text-2xs bg-red-500/20 text-red-300 px-1 py-0.5 rounded font-mono">
                            {v.callsign || v.icao_hex}
                          </span>
                        ))}
                        {violations.length > 5 && (
                          <span className="text-2xs text-red-400">+{violations.length - 5} more</span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="text-center text-slate-500 text-sm py-4">
            No geofences defined
          </div>
        )}

        {/* Add New Geofence */}
        <div className="border-t border-surface-3 pt-4">
          <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-3">Add Circular Geofence</h4>
          <div className="space-y-2">
            <input
              type="text"
              placeholder="Zone name (e.g., Restricted Area)"
              value={newFenceName}
              onChange={(e) => setNewFenceName(e.target.value)}
              className="w-full bg-surface-2 border border-surface-3 rounded px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                placeholder="Center Lat"
                value={newFenceLat}
                onChange={(e) => setNewFenceLat(e.target.value)}
                step="0.001"
                className="bg-surface-2 border border-surface-3 rounded px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
              />
              <input
                type="number"
                placeholder="Center Lng"
                value={newFenceLng}
                onChange={(e) => setNewFenceLng(e.target.value)}
                step="0.001"
                className="bg-surface-2 border border-surface-3 rounded px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div className="flex gap-2">
              <input
                type="number"
                placeholder="Radius (nm)"
                value={newFenceRadius}
                onChange={(e) => setNewFenceRadius(e.target.value)}
                min="1"
                max="500"
                className="flex-1 bg-surface-2 border border-surface-3 rounded px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
              />
              <button
                onClick={handleAddGeofence}
                disabled={!newFenceName || !newFenceLat || !newFenceLng}
                className="px-4 py-2 bg-cyan-500 hover:bg-cyan-400 disabled:bg-surface-3 disabled:text-slate-500 rounded text-sm font-medium transition-colors"
              >
                ADD
              </button>
            </div>
          </div>
        </div>

        {/* Preset Zones */}
        <div className="border-t border-surface-3 pt-4">
          <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-2">Quick Add Presets</h4>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => onAddGeofence({
                id: `fence-${Date.now()}`,
                name: 'DC SFRA',
                type: 'circle',
                center: { lat: 38.8977, lng: -77.0365 },
                radius: 30,
                color: GEOFENCE_COLORS[geofences.length % GEOFENCE_COLORS.length],
                active: true,
              })}
              className="px-2 py-1.5 bg-surface-2 hover:bg-surface-3 rounded text-2xs transition-colors"
            >
              DC SFRA (30nm)
            </button>
            <button
              onClick={() => onAddGeofence({
                id: `fence-${Date.now()}`,
                name: 'Area 51',
                type: 'circle',
                center: { lat: 37.2350, lng: -115.8111 },
                radius: 25,
                color: GEOFENCE_COLORS[geofences.length % GEOFENCE_COLORS.length],
                active: true,
              })}
              className="px-2 py-1.5 bg-surface-2 hover:bg-surface-3 rounded text-2xs transition-colors"
            >
              Area 51 (25nm)
            </button>
            <button
              onClick={() => onAddGeofence({
                id: `fence-${Date.now()}`,
                name: 'Camp David',
                type: 'circle',
                center: { lat: 39.6481, lng: -77.4650 },
                radius: 3,
                color: GEOFENCE_COLORS[geofences.length % GEOFENCE_COLORS.length],
                active: true,
              })}
              className="px-2 py-1.5 bg-surface-2 hover:bg-surface-3 rounded text-2xs transition-colors"
            >
              Camp David (3nm)
            </button>
            <button
              onClick={() => onAddGeofence({
                id: `fence-${Date.now()}`,
                name: 'Custom Zone',
                type: 'circle',
                center: { lat: 39.9612, lng: -82.9988 },
                radius: 50,
                color: GEOFENCE_COLORS[geofences.length % GEOFENCE_COLORS.length],
                active: true,
              })}
              className="px-2 py-1.5 bg-surface-2 hover:bg-surface-3 rounded text-2xs transition-colors"
            >
              Local (50nm)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const GEOFENCE_COLORS = [
  '#ef4444', // red
  '#f59e0b', // amber
  '#8b5cf6', // purple
  '#06b6d4', // cyan
  '#10b981', // emerald
  '#ec4899', // pink
];

export { haversineDistance, isPointInPolygon };
