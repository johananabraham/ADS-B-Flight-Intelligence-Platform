import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { FlightMap, AircraftList, AnomalyPanel, StatsBar } from '@/components';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000,
      retry: 1,
    },
  },
});

type SidebarTab = 'aircraft' | 'alerts';

function AppContent() {
  const [selectedAircraft, setSelectedAircraft] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<SidebarTab>('aircraft');

  return (
    <div className="h-screen flex flex-col bg-radar-dark text-white">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-700 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
              <svg
                className="w-5 h-5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-bold">ADS-B Flight Intelligence</h1>
              <p className="text-xs text-gray-400">
                Real-time aircraft tracking & anomaly detection
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Stats Bar */}
      <StatsBar />

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Map */}
        <div className="flex-1 relative">
          <FlightMap
            selectedAircraft={selectedAircraft}
            onSelectAircraft={setSelectedAircraft}
          />
        </div>

        {/* Sidebar */}
        <div className="w-80 bg-gray-900 border-l border-gray-700 flex flex-col">
          {/* Tabs */}
          <div className="flex border-b border-gray-700">
            <button
              onClick={() => setActiveTab('aircraft')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'aircraft'
                  ? 'text-white border-b-2 border-blue-500 bg-gray-800'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Aircraft
            </button>
            <button
              onClick={() => setActiveTab('alerts')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'alerts'
                  ? 'text-white border-b-2 border-red-500 bg-gray-800'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Alerts
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-hidden">
            {activeTab === 'aircraft' ? (
              <AircraftList
                selectedAircraft={selectedAircraft}
                onSelectAircraft={setSelectedAircraft}
              />
            ) : (
              <AnomalyPanel />
            )}
          </div>
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
