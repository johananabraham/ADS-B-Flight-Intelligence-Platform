import { useState, useEffect, useCallback, useMemo } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FlightMap } from '@/components/FlightMap';
import { AircraftPanel } from '@/components/AircraftPanel';
import { AircraftDetail } from '@/components/AircraftDetail';
import { AlertsPanel } from '@/components/AlertsPanel';
import { StatusBar } from '@/components/StatusBar';
import { FilterPanel } from '@/components/FilterPanel';
import { StatsPanel } from '@/components/StatsPanel';
import { GeofencePanel } from '@/components/GeofencePanel';
import { SafetyPanel } from '@/components/SafetyPanel';
import { ReplayControls } from '@/components/ReplayControls';
import { StationFleetPanel } from '@/components/StationFleetPanel';
import { LoginForm } from '@/components/LoginForm';
import type { Geofence } from '@/components/GeofencePanel';
import { useWebSocket } from '@/hooks';
import type { Aircraft } from '@/types';
import { AuthProvider, useAuth } from '@/context/AuthContext';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000,
      retry: 1,
    },
  },
});

export interface Filters {
  minAltitude: number;
  maxAltitude: number;
  callsignSearch: string;
  showMilitary: boolean;
  showEmergency: boolean;
}

const defaultFilters: Filters = {
  minAltitude: 0,
  maxAltitude: 50000,
  callsignSearch: '',
  showMilitary: true,
  showEmergency: true,
};

// Military callsign prefixes
const MILITARY_PREFIXES = ['RCH', 'REACH', 'EVAC', 'NAVY', 'ARMY', 'USAF', 'MC', 'PAT', 'TOPCAT', 'GOLD', 'SENTRY', 'AWAC'];
const EMERGENCY_SQUAWKS = ['7500', '7600', '7700'];
const SOURCE_MODE = import.meta.env.VITE_DATA_SOURCE_MODE;
const IS_RECORDED_REPLAY = SOURCE_MODE === 'RECORDED REPLAY';

function AppContent() {
  const { isAuthenticated, isLoading: authLoading, user, logout } = useAuth();
  const [selectedAircraft, setSelectedAircraft] = useState<string | null>(null);
  const [showAlerts, setShowAlerts] = useState(false);
  const [showOverlays, setShowOverlays] = useState(true);
  const [showFilters, setShowFilters] = useState(false);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [showGeofences, setShowGeofences] = useState(false);
  const [showSafety, setShowSafety] = useState(false);
  const [showStations, setShowStations] = useState(false);
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [geofences, setGeofences] = useState<Geofence[]>([]);

  // Use WebSocket for real-time updates
  const { aircraft: rawAircraft, stats, connected, lastUpdate } = useWebSocket();

  // Apply filters to aircraft
  const aircraft = useMemo(() => {
    return rawAircraft.filter((a: Aircraft) => {
      // Altitude filter
      const alt = a.altitude ?? 0;
      if (alt < filters.minAltitude || alt > filters.maxAltitude) return false;

      // Callsign search
      if (filters.callsignSearch) {
        const search = filters.callsignSearch.toUpperCase();
        const callsign = (a.callsign || '').toUpperCase();
        const icao = a.icao_hex.toUpperCase();
        if (!callsign.includes(search) && !icao.includes(search)) return false;
      }

      // Military filter
      if (!filters.showMilitary) {
        const callsign = (a.callsign || '').toUpperCase();
        if (MILITARY_PREFIXES.some(prefix => callsign.startsWith(prefix))) return false;
      }

      // Emergency filter
      if (!filters.showEmergency) {
        if (a.squawk && EMERGENCY_SQUAWKS.includes(a.squawk)) return false;
      }

      return true;
    });
  }, [rawAircraft, filters]);
  const selectedAircraftData = aircraft.find(a => a.icao_hex === selectedAircraft);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      if (e.target instanceof HTMLInputElement) return;

      if (e.key === 'Escape') {
        setSelectedAircraft(null);
        setShowAlerts(false);
        setShowFilters(false);
        setShowStats(false);
        setShowGeofences(false);
        setShowSafety(false);
        setShowStations(false);
      }
      if (e.key === 'a' && !e.metaKey && !e.ctrlKey) {
        setShowAlerts(prev => !prev);
      }
      if (e.key === 'o' && !e.metaKey && !e.ctrlKey) {
        setShowOverlays(prev => !prev);
      }
      if (e.key === 'f' && !e.metaKey && !e.ctrlKey) {
        setShowFilters(prev => !prev);
      }
      if (e.key === 'h' && !e.metaKey && !e.ctrlKey) {
        setShowHeatmap(prev => !prev);
      }
      if (e.key === 's' && !e.metaKey && !e.ctrlKey) {
        setShowStats(prev => !prev);
      }
      if (e.key === 'g' && !e.metaKey && !e.ctrlKey) {
        setShowGeofences(prev => !prev);
      }
      if (e.key === 'r' && !e.metaKey && !e.ctrlKey) {
        setShowSafety(prev => !prev);
      }
      if (e.key === 'n' && !e.metaKey && !e.ctrlKey) {
        setShowStations(prev => !prev);
      }
      if (e.key === 'l' && !e.metaKey && !e.ctrlKey && user) {
        if (confirm('Are you sure you want to logout?')) {
          logout();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [user, logout]);

  const handleSelectAircraft = useCallback((icao: string | null) => {
    setSelectedAircraft(icao);
  }, []);

  return (
    <div className="h-screen w-screen overflow-hidden bg-surface-0 text-slate-200">
      {/* Scan line effect */}
      <div className="scan-line" />

      {/* Full-screen map */}
      <div className="absolute inset-0">
        <FlightMap
          aircraft={aircraft}
          selectedAircraft={selectedAircraft}
          onSelectAircraft={handleSelectAircraft}
          showOverlays={showOverlays}
          showHeatmap={showHeatmap}
          geofences={geofences}
        />
        {/* Grid overlay */}
        <div className="map-grid-overlay" />
      </div>

      {/* Status bar - top */}
      <div className="absolute top-0 left-0 right-0 z-[1000]">
        <StatusBar
          onToggleAlerts={() => setShowAlerts(!showAlerts)}
          alertsOpen={showAlerts}
          showOverlays={showOverlays}
          onToggleOverlays={() => setShowOverlays(!showOverlays)}
          showFilters={showFilters}
          onToggleFilters={() => setShowFilters(!showFilters)}
          stationsOpen={showStations}
          onToggleStations={() => setShowStations(!showStations)}
          connected={connected}
          stats={stats}
          lastUpdate={lastUpdate}
          aircraftCount={aircraft.length}
          totalAircraftCount={rawAircraft.length}
          sourceMode={SOURCE_MODE}
          aircraft={aircraft}
        />
      </div>

      {/* Aircraft panel - left */}
      <div className="absolute top-16 left-4 bottom-4 w-72 z-[1000]">
        <AircraftPanel
          aircraft={aircraft}
          selectedAircraft={selectedAircraft}
          onSelectAircraft={handleSelectAircraft}
        />
      </div>

      {/* Aircraft detail - center bottom (when selected) */}
      {selectedAircraftData && (
        <div className={`absolute left-80 right-80 z-[1000] mx-auto max-w-xl overflow-y-auto ${IS_RECORDED_REPLAY ? 'bottom-44 max-h-[calc(100vh-13rem)]' : 'bottom-4 max-h-[calc(100vh-6rem)]'}`}>
          <AircraftDetail
            aircraft={selectedAircraftData}
            onClose={() => setSelectedAircraft(null)}
          />
        </div>
      )}

      {/* Alerts panel - right (conditional) */}
      {showAlerts && !showStations && (
        <div className="absolute top-16 right-4 bottom-4 w-80 z-[1000]">
          <AlertsPanel onClose={() => setShowAlerts(false)} />
        </div>
      )}

      {/* Filter panel - top center (conditional) */}
      {showFilters && (
        <div className="absolute top-16 left-1/2 -translate-x-1/2 z-[1001]">
          <FilterPanel
            filters={filters}
            onFiltersChange={setFilters}
            onClose={() => setShowFilters(false)}
            onReset={() => setFilters(defaultFilters)}
          />
        </div>
      )}

      {/* Stats panel - right side (conditional) */}
      {showStats && !showAlerts && !showGeofences && !showStations && (
        <div className="absolute top-16 right-4 z-[1000]">
          <StatsPanel
            aircraft={aircraft}
            stats={stats}
            onClose={() => setShowStats(false)}
          />
        </div>
      )}

      {/* Geofence panel - right side (conditional) */}
      {showGeofences && !showAlerts && !showSafety && !showStations && (
        <div className="absolute top-16 right-4 z-[1000]">
          <GeofencePanel
            geofences={geofences}
            aircraft={aircraft}
            onAddGeofence={(fence) => setGeofences(prev => [...prev, fence])}
            onRemoveGeofence={(id) => setGeofences(prev => prev.filter(f => f.id !== id))}
            onToggleGeofence={(id) => setGeofences(prev => prev.map(f => f.id === id ? { ...f, active: !f.active } : f))}
            onClose={() => setShowGeofences(false)}
          />
        </div>
      )}

      {/* Safety Research panel - positioned by component */}
      {showSafety && !showStations && <SafetyPanel onClose={() => setShowSafety(false)} />}

      {showStations && (
        <div className="absolute bottom-4 right-4 top-16 z-[1001] w-[26rem] max-w-[calc(100vw-2rem)]">
          <StationFleetPanel onClose={() => setShowStations(false)} />
        </div>
      )}

      {IS_RECORDED_REPLAY && (
        <div className="absolute bottom-4 left-1/2 z-[1000] -translate-x-1/2">
          <ReplayControls />
        </div>
      )}

      {/* User info and logout */}
      {user && (
        <div className="absolute top-4 right-4 z-[1002] flex items-center gap-2 px-3 py-1.5 rounded bg-gray-800 text-sm text-slate-300">
          <span className="font-medium">{user.username}</span>
          <span className="text-slate-500">•</span>
          <span className="text-xs text-slate-400 uppercase">{user.role}</span>
          <button
            onClick={() => {
              if (confirm('Are you sure you want to logout?')) {
                logout();
              }
            }}
            className="ml-2 text-xs text-red-400 hover:text-red-300"
            title="Press L to logout"
          >
            Logout
          </button>
        </div>
      )}

      {/* Connection status indicator */}
      <div className={`absolute top-16 right-4 z-[999] flex items-center gap-2 px-2 py-1 rounded text-2xs ${
        connected ? 'text-green-400' : 'text-red-400'
      }`}>
        <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`} />
        {connected ? 'LIVE' : 'DISCONNECTED'}
      </div>

      {/* Keyboard shortcuts hint */}
      <div className="absolute bottom-4 right-4 z-[1000] text-2xs text-slate-600">
        <span className="opacity-50">A</span>lerts · <span className="opacity-50">S</span>tats · <span className="opacity-50">G</span>eofence · <span className="opacity-50">R</span>esearch · <span className="opacity-50">N</span>odes · <span className="opacity-50">F</span>ilter · <span className="opacity-50">H</span>eatmap · <span className="opacity-50">O</span>verlays · <span className="opacity-50">L</span>ogout · <span className="opacity-50">ESC</span>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </QueryClientProvider>
  );
}
