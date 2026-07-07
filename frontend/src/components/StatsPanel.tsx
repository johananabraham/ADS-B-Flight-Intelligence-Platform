import { useState, useEffect, useMemo } from 'react';
import type { Aircraft, Stats } from '@/types';

interface StatsPanelProps {
  aircraft: Aircraft[];
  stats: Stats | null;
  onClose: () => void;
}

interface TimeSeriesPoint {
  time: string;
  count: number;
}

export function StatsPanel({ aircraft, stats, onClose }: StatsPanelProps) {
  const [activityHistory, setActivityHistory] = useState<TimeSeriesPoint[]>([]);

  // Track activity over time
  useEffect(() => {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });

    setActivityHistory(prev => {
      const newHistory = [...prev, { time: timeStr, count: aircraft.length }];
      // Keep last 60 data points (1 hour of minute data)
      return newHistory.slice(-60);
    });
  }, [aircraft.length]);

  // Aircraft statistics
  const aircraftStats = useMemo(() => {
    const withPosition = aircraft.filter(a => a.latitude && a.longitude).length;
    const withAltitude = aircraft.filter(a => a.altitude !== null).length;
    const withSquawk = aircraft.filter(a => a.squawk).length;
    const emergencies = aircraft.filter(a => ['7500', '7600', '7700'].includes(a.squawk ?? '')).length;

    // Altitude distribution
    const altBuckets = {
      ground: 0,    // 0-1000
      low: 0,       // 1000-10000
      medium: 0,    // 10000-30000
      high: 0,      // 30000-45000
      veryHigh: 0,  // 45000+
    };

    aircraft.forEach(a => {
      const alt = a.altitude ?? 0;
      if (alt < 1000) altBuckets.ground++;
      else if (alt < 10000) altBuckets.low++;
      else if (alt < 30000) altBuckets.medium++;
      else if (alt < 45000) altBuckets.high++;
      else altBuckets.veryHigh++;
    });

    // Speed distribution
    const avgSpeed = aircraft.reduce((sum, a) => sum + (a.ground_speed ?? 0), 0) / aircraft.length || 0;
    const maxSpeed = Math.max(...aircraft.map(a => a.ground_speed ?? 0), 0);
    const avgAltitude = aircraft.reduce((sum, a) => sum + (a.altitude ?? 0), 0) / aircraft.length || 0;
    const maxAltitude = Math.max(...aircraft.map(a => a.altitude ?? 0), 0);

    // Vertical rate analysis
    const climbing = aircraft.filter(a => (a.vertical_rate ?? 0) > 500).length;
    const descending = aircraft.filter(a => (a.vertical_rate ?? 0) < -500).length;
    const level = aircraft.length - climbing - descending;

    return {
      withPosition,
      withAltitude,
      withSquawk,
      emergencies,
      altBuckets,
      avgSpeed,
      maxSpeed,
      avgAltitude,
      maxAltitude,
      climbing,
      descending,
      level,
    };
  }, [aircraft]);

  // Simple sparkline component
  const Sparkline = ({ data, max }: { data: number[]; max: number }) => {
    if (data.length < 2) return null;
    const height = 30;
    const width = 200;
    const points = data.map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - (v / max) * height;
      return `${x},${y}`;
    }).join(' ');

    return (
      <svg width={width} height={height} className="mt-1">
        <polyline
          points={points}
          fill="none"
          stroke="#00d4ff"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  };

  // Bar chart component
  const BarChart = ({ data }: { data: { label: string; value: number; color: string }[] }) => {
    const maxVal = Math.max(...data.map(d => d.value), 1);
    return (
      <div className="space-y-1.5">
        {data.map(d => (
          <div key={d.label} className="flex items-center gap-2">
            <span className="text-2xs text-slate-400 w-12">{d.label}</span>
            <div className="flex-1 h-3 bg-surface-2 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{
                  width: `${(d.value / maxVal) * 100}%`,
                  backgroundColor: d.color,
                }}
              />
            </div>
            <span className="text-2xs font-mono text-slate-300 w-8 text-right">{d.value}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="panel w-80 max-h-[80vh] overflow-y-auto">
      <div className="p-3 border-b border-surface-3 flex items-center justify-between sticky top-0 bg-surface-1">
        <h3 className="text-sm font-semibold text-cyan-400 tracking-wider uppercase flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          STATISTICS
        </h3>
        <button onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="p-3 space-y-4">
        {/* Activity Timeline */}
        <div>
          <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-2">Activity Timeline</h4>
          <div className="bg-surface-2/50 rounded p-2">
            <Sparkline
              data={activityHistory.map(p => p.count)}
              max={Math.max(...activityHistory.map(p => p.count), 10)}
            />
            <div className="flex justify-between text-2xs text-slate-500 mt-1">
              <span>{activityHistory[0]?.time || '--:--'}</span>
              <span>{activityHistory[activityHistory.length - 1]?.time || '--:--'}</span>
            </div>
          </div>
        </div>

        {/* Quick Stats Grid */}
        <div className="grid grid-cols-2 gap-2">
          <StatBox label="Total Aircraft" value={aircraft.length} icon="aircraft" />
          <StatBox label="With Position" value={aircraftStats.withPosition} icon="position" />
          <StatBox label="Avg Speed" value={`${aircraftStats.avgSpeed.toFixed(0)} kts`} icon="speed" />
          <StatBox label="Avg Altitude" value={`${(aircraftStats.avgAltitude / 1000).toFixed(1)}k ft`} icon="altitude" />
        </div>

        {/* Altitude Distribution */}
        <div>
          <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-2">Altitude Distribution</h4>
          <BarChart data={[
            { label: 'Ground', value: aircraftStats.altBuckets.ground, color: '#ef4444' },
            { label: 'Low', value: aircraftStats.altBuckets.low, color: '#f59e0b' },
            { label: 'Medium', value: aircraftStats.altBuckets.medium, color: '#22c55e' },
            { label: 'High', value: aircraftStats.altBuckets.high, color: '#3b82f6' },
            { label: 'FL450+', value: aircraftStats.altBuckets.veryHigh, color: '#8b5cf6' },
          ]} />
        </div>

        {/* Flight Phase */}
        <div>
          <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-2">Flight Phase</h4>
          <div className="flex gap-2">
            <div className="flex-1 bg-surface-2/50 rounded p-2 text-center">
              <div className="text-emerald-400 font-mono font-bold text-lg">{aircraftStats.climbing}</div>
              <div className="text-2xs text-slate-500">CLIMBING</div>
            </div>
            <div className="flex-1 bg-surface-2/50 rounded p-2 text-center">
              <div className="text-slate-300 font-mono font-bold text-lg">{aircraftStats.level}</div>
              <div className="text-2xs text-slate-500">LEVEL</div>
            </div>
            <div className="flex-1 bg-surface-2/50 rounded p-2 text-center">
              <div className="text-amber-400 font-mono font-bold text-lg">{aircraftStats.descending}</div>
              <div className="text-2xs text-slate-500">DESCENDING</div>
            </div>
          </div>
        </div>

        {/* System Stats */}
        {stats && (
          <div>
            <h4 className="text-xs text-slate-400 uppercase tracking-wider mb-2">System Stats (Today)</h4>
            <div className="bg-surface-2/50 rounded p-2 space-y-1.5">
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Positions Recorded</span>
                <span className="font-mono text-slate-300">{stats.total_positions_today.toLocaleString()}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Anomalies Detected</span>
                <span className={`font-mono ${stats.anomalies_today > 0 ? 'text-amber-400' : 'text-slate-300'}`}>
                  {stats.anomalies_today}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-slate-400">Critical Alerts</span>
                <span className={`font-mono ${stats.critical_anomalies > 0 ? 'text-red-400' : 'text-slate-300'}`}>
                  {stats.critical_anomalies}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Emergencies */}
        {aircraftStats.emergencies > 0 && (
          <div className="bg-red-500/10 border border-red-500/30 rounded p-2">
            <div className="flex items-center gap-2 text-red-400">
              <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
              <span className="text-xs font-semibold uppercase">{aircraftStats.emergencies} Emergency Squawk{aircraftStats.emergencies > 1 ? 's' : ''}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function StatBox({ label, value, icon }: { label: string; value: string | number; icon: string }) {
  const icons: Record<string, JSX.Element> = {
    aircraft: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
      </svg>
    ),
    position: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
    speed: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    altitude: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 11l5-5m0 0l5 5m-5-5v12" />
      </svg>
    ),
  };

  return (
    <div className="bg-surface-2/50 rounded p-2">
      <div className="flex items-center gap-1.5 text-slate-400 mb-1">
        {icons[icon]}
        <span className="text-2xs uppercase">{label}</span>
      </div>
      <div className="font-mono font-semibold text-lg text-white">{value}</div>
    </div>
  );
}
