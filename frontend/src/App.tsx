import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FlightMap } from '@/components/FlightMap';
import { AircraftPanel } from '@/components/AircraftPanel';
import { AlertsPanel } from '@/components/AlertsPanel';
import { StatusBar } from '@/components/StatusBar';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000,
      retry: 1,
    },
  },
});

function AppContent() {
  const [selectedAircraft, setSelectedAircraft] = useState<string | null>(null);
  const [showAlerts, setShowAlerts] = useState(false);

  return (
    <div className="h-screen w-screen overflow-hidden bg-surface-0 text-slate-200">
      {/* Scan line effect */}
      <div className="scan-line" />

      {/* Full-screen map */}
      <div className="absolute inset-0">
        <FlightMap
          selectedAircraft={selectedAircraft}
          onSelectAircraft={setSelectedAircraft}
        />
        {/* Grid overlay */}
        <div className="map-grid-overlay" />
      </div>

      {/* Status bar - top */}
      <div className="absolute top-0 left-0 right-0 z-[1000]">
        <StatusBar onToggleAlerts={() => setShowAlerts(!showAlerts)} alertsOpen={showAlerts} />
      </div>

      {/* Aircraft panel - left */}
      <div className="absolute top-16 left-4 bottom-4 w-80 z-[1000]">
        <AircraftPanel
          selectedAircraft={selectedAircraft}
          onSelectAircraft={setSelectedAircraft}
        />
      </div>

      {/* Alerts panel - right (conditional) */}
      {showAlerts && (
        <div className="absolute top-16 right-4 bottom-4 w-80 z-[1000]">
          <AlertsPanel onClose={() => setShowAlerts(false)} />
        </div>
      )}

      {/* Coordinates display - bottom right */}
      <div className="absolute bottom-4 right-4 z-[1000] panel rounded px-3 py-2">
        <div className="flex items-center gap-4 text-xs">
          <span className="text-slate-500">RECEIVER</span>
          <span className="font-mono text-accent-primary">39.9612°N</span>
          <span className="font-mono text-accent-primary">82.9988°W</span>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
