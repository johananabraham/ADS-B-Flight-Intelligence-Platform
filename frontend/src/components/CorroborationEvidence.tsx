import clsx from 'clsx';

import type { CorroborationEvidence as Evidence, CorroborationState } from '@/types';

interface CorroborationEvidenceProps {
  evidence?: Evidence;
  expanded: boolean;
  loading: boolean;
  error: boolean;
  onToggle: () => void;
}

const STATE_STYLES: Record<CorroborationState, string> = {
  CORROBORATED: 'border-status-nominal/40 bg-status-nominal/10 text-status-nominal',
  LOCAL_ONLY: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  EXTERNAL_ONLY: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  CONFLICTING: 'border-status-warning/40 bg-status-warning/10 text-status-warning',
  STALE: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
  UNAVAILABLE: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
};

export function CorroborationEvidence({
  evidence,
  expanded,
  loading,
  error,
  onToggle,
}: CorroborationEvidenceProps) {
  return (
    <section className="border-b border-surface-3" aria-labelledby="corroboration-heading">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls="corroboration-content"
        className="flex min-h-11 w-full cursor-pointer items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent-primary"
      >
        <span id="corroboration-heading" className="text-xs uppercase tracking-wider text-slate-400">
          Cross-source check
        </span>
        <span className="flex items-center gap-2">
          {evidence && (
            <span className={clsx('rounded border px-2 py-1 text-xs font-semibold', STATE_STYLES[evidence.state])}>
              {evidence.state.replace('_', ' ')}
            </span>
          )}
          <svg
            aria-hidden="true"
            className={clsx('h-4 w-4 text-slate-400 transition-transform', expanded && 'rotate-90')}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m9 18 6-6-6-6" />
          </svg>
        </span>
      </button>

      {expanded && (
        <div id="corroboration-content" className="space-y-3 px-4 pb-4 text-xs leading-relaxed">
          {loading && <p className="text-slate-400">Checking the external observation source…</p>}
          {error && (
            <p role="alert" className="rounded border border-slate-500/30 bg-slate-500/10 p-3 text-slate-300">
              Cross-source evidence could not be loaded. This does not make the local track suspicious.
            </p>
          )}
          {evidence && (
            <>
              <p className={clsx('rounded border p-3', STATE_STYLES[evidence.state])}>
                {evidence.explanation}
              </p>
              <div className="grid grid-cols-3 gap-2">
                <Measurement label="Time delta" value={format(evidence.time_delta_seconds, 's')} />
                <Measurement label="Position delta" value={format(evidence.position_distance_nm, 'nm')} />
                <Measurement label="Altitude delta" value={format(evidence.altitude_difference_ft, 'ft')} />
              </div>
              <p className="border-l-2 border-accent-primary/40 pl-3 text-slate-400">
                This is cross-source corroboration, not aircraft authentication or full sensor fusion.
              </p>
              <p className="font-mono text-2xs text-slate-500">
                Policy {evidence.policy_version} · checked {new Date(evidence.evaluated_at).toLocaleTimeString()}
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}

function Measurement({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded bg-surface-2 p-2">
      <div className="text-2xs uppercase text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-slate-200">{value}</div>
    </div>
  );
}

function format(value: number | null, unit: string): string {
  return value === null ? '—' : `${value.toFixed(1)} ${unit}`;
}
