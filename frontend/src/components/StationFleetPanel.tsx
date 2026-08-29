import { formatDistanceToNow } from 'date-fns';
import clsx from 'clsx';
import { useStations } from '@/hooks';
import type { Station, StationHealthState } from '@/types';

interface StationFleetPanelProps {
  onClose: () => void;
}

const STATE_STYLES: Record<StationHealthState, string> = {
  HEALTHY: 'border-status-nominal/40 bg-status-nominal/10 text-status-nominal',
  DEGRADED: 'border-status-caution/40 bg-status-caution/10 text-status-caution',
  STALE: 'border-status-warning/40 bg-status-warning/10 text-status-warning',
  OFFLINE: 'border-status-critical/40 bg-status-critical/10 text-status-critical',
  NO_DATA: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
};

const STATES: StationHealthState[] = [
  'HEALTHY',
  'DEGRADED',
  'STALE',
  'OFFLINE',
  'NO_DATA',
];

export function StationFleetPanel({ onClose }: StationFleetPanelProps) {
  const { data: stations = [], isLoading, isError, refetch } = useStations();
  const counts = Object.fromEntries(
    STATES.map((state) => [
      state,
      stations.filter((station) => station.health.state === state).length,
    ])
  ) as Record<StationHealthState, number>;

  return (
    <section
      aria-labelledby="station-fleet-heading"
      className="panel flex h-full w-full flex-col overflow-hidden rounded"
    >
      <header className="flex items-center justify-between border-b border-surface-3 px-4 py-3">
        <div>
          <p className="text-2xs font-semibold uppercase tracking-[0.2em] text-accent-primary">
            Edge network
          </p>
          <h2 id="station-fleet-heading" className="text-base font-semibold text-slate-100">
            Station health
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close station health panel"
          className="flex h-11 w-11 items-center justify-center rounded text-slate-400 transition-colors hover:bg-surface-3 hover:text-slate-100"
        >
          <svg aria-hidden="true" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeWidth="1.5" d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </header>

      <div className="grid grid-cols-5 gap-1 border-b border-surface-3 p-3" aria-label="Station state counts">
        {STATES.map((state) => (
          <div key={state} className="rounded bg-surface-2 px-1 py-2 text-center">
            <div className={clsx('font-mono text-sm font-semibold', stateText(state))}>
              {counts[state]}
            </div>
            <div className="mt-1 truncate text-[9px] font-semibold tracking-wide text-slate-500">
              {state.replace('_', ' ')}
            </div>
          </div>
        ))}
      </div>

      <p className="border-b border-surface-3 bg-accent-primary/5 px-4 py-2 text-xs leading-5 text-slate-400">
        Device heartbeats are correlated with privacy-safe receiver pipeline health. This is operational evidence, not proof of RF authenticity.
      </p>

      <div className="flex-1 space-y-3 overflow-y-auto p-3" aria-live="polite">
        {isLoading && <LoadingState />}
        {isError && (
          <div role="alert" className="rounded border border-status-critical/30 bg-status-critical/10 p-4">
            <p className="text-sm font-medium text-status-critical">Station health could not be loaded.</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">Check the backend connection, then retry.</p>
            <button
              type="button"
              onClick={() => refetch()}
              className="mt-3 min-h-11 rounded bg-surface-3 px-4 text-xs font-semibold text-slate-200 transition-colors hover:bg-slate-700"
            >
              Retry
            </button>
          </div>
        )}
        {!isLoading && !isError && stations.length === 0 && (
          <div className="rounded border border-surface-3 bg-surface-2 p-5 text-center">
            <StationIcon />
            <p className="mt-3 text-sm font-medium text-slate-200">No station telemetry yet</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              Start the ESP32 firmware or hardware-free station simulator to populate this view.
            </p>
          </div>
        )}
        {stations.map((station) => (
          <StationCard key={station.node_id} station={station} />
        ))}
      </div>
    </section>
  );
}

function StationCard({ station }: { station: Station }) {
  const age = station.health.telemetry_age_seconds;
  return (
    <article className="rounded border border-surface-3 bg-surface-2/95 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate font-mono text-sm font-semibold text-slate-100">{station.node_id}</h3>
          <p className="mt-1 text-xs text-slate-400">
            Received {formatDistanceToNow(new Date(station.last_received_at))} ago
          </p>
        </div>
        <span className={clsx('shrink-0 rounded border px-2 py-1 text-2xs font-semibold', STATE_STYLES[station.health.state])}>
          {station.health.state.replace('_', ' ')}
        </span>
      </div>

      <p className="mt-3 border-l-2 border-surface-3 pl-3 text-xs leading-5 text-slate-300">
        {station.health.reasons[0]}
      </p>

      <dl className="mt-3 grid grid-cols-3 gap-2">
        <Metric label="RSSI" value={station.rssi_dbm == null ? '—' : `${station.rssi_dbm} dBm`} />
        <Metric label="Heap" value={formatBytes(station.free_heap_bytes)} />
        <Metric label="Queue" value={station.offline_queue_depth ?? '—'} />
        <Metric label="Uptime" value={formatDuration(station.uptime_seconds)} />
        <Metric label="Reconnects" value={station.reconnect_count ?? '—'} />
        <Metric label="Age" value={age == null ? '—' : `${Math.max(0, Math.round(age))}s`} />
        <Metric label="Receiver" value={station.receiver_connection ?? 'NO DATA'} />
        <Metric
          label="RF age"
          value={station.receiver_last_message_age_seconds == null ? '—' : `${Math.round(station.receiver_last_message_age_seconds)}s`}
        />
        <Metric
          label="RX queue"
          value={station.receiver_queue_depth == null ? '—' : `${station.receiver_queue_depth}/${station.receiver_queue_capacity}`}
        />
      </dl>

      <details className="mt-3 border-t border-surface-3 pt-2 text-xs">
        <summary className="min-h-11 cursor-pointer select-none py-3 font-medium text-accent-primary transition-colors hover:text-cyan-200">
          Evidence and policy
        </summary>
        <div className="space-y-2 pb-2 leading-5 text-slate-400">
          {station.health.reasons.slice(1).map((reason) => <p key={reason}>{reason}</p>)}
          <p>Policy v{station.health.policy_version} · firmware {station.firmware_version ?? 'unknown'}</p>
          <p className="break-all font-mono text-2xs text-slate-500">
            Telemetry: {station.health.telemetry_message_id ?? 'none'}
          </p>
          <p className="break-all font-mono text-2xs text-slate-500">
            Presence: {station.health.presence_message_id ?? 'none'}
          </p>
          <p className="break-all font-mono text-2xs text-slate-500">
            Pipeline: {station.health.pipeline_message_id ?? 'none'} · policy {station.receiver_policy_version ?? 'none'}
          </p>
        </div>
      </details>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded bg-surface-1 px-2 py-2">
      <dt className="text-[9px] font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-1 truncate font-mono text-xs text-slate-200">{value}</dd>
    </div>
  );
}

function LoadingState() {
  return (
    <div aria-label="Loading station health" className="space-y-3">
      {[0, 1, 2].map((item) => (
        <div key={item} className="h-32 animate-pulse rounded border border-surface-3 bg-surface-2" />
      ))}
    </div>
  );
}

function StationIcon() {
  return (
    <svg aria-hidden="true" className="mx-auto h-8 w-8 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 18v3m-4 0h8M8.5 15.5a5 5 0 017 0M5.5 12.5a9 9 0 0113 0M12 9h.01" />
    </svg>
  );
}

function stateText(state: StationHealthState): string {
  if (state === 'HEALTHY') return 'text-status-nominal';
  if (state === 'DEGRADED') return 'text-status-caution';
  if (state === 'STALE') return 'text-status-warning';
  if (state === 'OFFLINE') return 'text-status-critical';
  return 'text-slate-300';
}

function formatBytes(value: number | null): string {
  return value == null ? '—' : `${Math.round(value / 1024)} KiB`;
}

function formatDuration(value: number | null): string {
  if (value == null) return '—';
  if (value < 3600) return `${Math.floor(value / 60)}m`;
  return `${Math.floor(value / 3600)}h`;
}
