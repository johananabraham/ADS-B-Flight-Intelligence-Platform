import type { Filters } from '@/App';

interface FilterPanelProps {
  filters: Filters;
  onFiltersChange: (filters: Filters) => void;
  onClose: () => void;
  onReset: () => void;
}

export function FilterPanel({ filters, onFiltersChange, onClose, onReset }: FilterPanelProps) {
  const updateFilter = <K extends keyof Filters>(key: K, value: Filters[K]) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  return (
    <div className="panel w-96 p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-cyan-400 tracking-wider uppercase flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          FILTERS
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={onReset}
            className="text-2xs text-slate-400 hover:text-white px-2 py-1 rounded hover:bg-surface-2 transition-colors"
          >
            RESET
          </button>
          <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div className="space-y-4">
        {/* Callsign/ICAO Search */}
        <div>
          <label className="block text-2xs text-slate-400 uppercase tracking-wider mb-1">
            Callsign / ICAO Search
          </label>
          <input
            type="text"
            value={filters.callsignSearch}
            onChange={(e) => updateFilter('callsignSearch', e.target.value)}
            placeholder="e.g., UAL, AAL, A1B2C3"
            className="w-full bg-surface-1 border border-surface-3 rounded px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500/50"
          />
        </div>

        {/* Altitude Range */}
        <div>
          <label className="block text-2xs text-slate-400 uppercase tracking-wider mb-2">
            Altitude Range (ft)
          </label>
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <input
                type="number"
                value={filters.minAltitude}
                onChange={(e) => updateFilter('minAltitude', parseInt(e.target.value) || 0)}
                min={0}
                max={filters.maxAltitude}
                step={1000}
                className="w-full bg-surface-1 border border-surface-3 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500"
              />
              <span className="text-2xs text-slate-500">MIN</span>
            </div>
            <span className="text-slate-500">—</span>
            <div className="flex-1">
              <input
                type="number"
                value={filters.maxAltitude}
                onChange={(e) => updateFilter('maxAltitude', parseInt(e.target.value) || 50000)}
                min={filters.minAltitude}
                max={60000}
                step={1000}
                className="w-full bg-surface-1 border border-surface-3 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-cyan-500"
              />
              <span className="text-2xs text-slate-500">MAX</span>
            </div>
          </div>
          {/* Altitude slider visualization */}
          <div className="mt-2 h-2 bg-surface-2 rounded-full overflow-hidden relative">
            <div
              className="absolute h-full bg-gradient-to-r from-cyan-500/50 to-cyan-400"
              style={{
                left: `${(filters.minAltitude / 60000) * 100}%`,
                right: `${100 - (filters.maxAltitude / 60000) * 100}%`,
              }}
            />
          </div>
          <div className="flex justify-between text-2xs text-slate-500 mt-1">
            <span>0 ft</span>
            <span>60,000 ft</span>
          </div>
        </div>

        {/* Quick altitude presets */}
        <div className="flex gap-2">
          <button
            onClick={() => { updateFilter('minAltitude', 0); updateFilter('maxAltitude', 10000); }}
            className="flex-1 px-2 py-1 text-2xs bg-surface-2 hover:bg-surface-3 rounded transition-colors"
          >
            LOW (&lt;10k)
          </button>
          <button
            onClick={() => { updateFilter('minAltitude', 10000); updateFilter('maxAltitude', 30000); }}
            className="flex-1 px-2 py-1 text-2xs bg-surface-2 hover:bg-surface-3 rounded transition-colors"
          >
            MED (10-30k)
          </button>
          <button
            onClick={() => { updateFilter('minAltitude', 30000); updateFilter('maxAltitude', 50000); }}
            className="flex-1 px-2 py-1 text-2xs bg-surface-2 hover:bg-surface-3 rounded transition-colors"
          >
            HIGH (&gt;30k)
          </button>
          <button
            onClick={() => { updateFilter('minAltitude', 0); updateFilter('maxAltitude', 50000); }}
            className="flex-1 px-2 py-1 text-2xs bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 rounded transition-colors"
          >
            ALL
          </button>
        </div>

        {/* Toggle filters */}
        <div className="border-t border-surface-3 pt-4 space-y-3">
          <label className="flex items-center justify-between cursor-pointer group">
            <span className="text-sm text-slate-300 group-hover:text-white transition-colors">
              Show Military Aircraft
            </span>
            <div
              onClick={() => updateFilter('showMilitary', !filters.showMilitary)}
              className={`w-10 h-5 rounded-full transition-colors relative ${
                filters.showMilitary ? 'bg-cyan-500' : 'bg-surface-3'
              }`}
            >
              <div
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  filters.showMilitary ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </div>
          </label>

          <label className="flex items-center justify-between cursor-pointer group">
            <span className="text-sm text-slate-300 group-hover:text-white transition-colors flex items-center gap-2">
              Show Emergency Squawks
              <span className="text-2xs text-red-400">(7500/7600/7700)</span>
            </span>
            <div
              onClick={() => updateFilter('showEmergency', !filters.showEmergency)}
              className={`w-10 h-5 rounded-full transition-colors relative ${
                filters.showEmergency ? 'bg-cyan-500' : 'bg-surface-3'
              }`}
            >
              <div
                className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                  filters.showEmergency ? 'translate-x-5' : 'translate-x-0.5'
                }`}
              />
            </div>
          </label>
        </div>
      </div>
    </div>
  );
}
