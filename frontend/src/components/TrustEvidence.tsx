import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';

import type { PersistedTrustAssessment, TrustState } from '@/types';
import { createTrustAction, fetchTrustEvents } from '@/utils/api';

interface TrustEvidenceProps {
  result?: PersistedTrustAssessment;
  expanded: boolean;
  loading: boolean;
  error: boolean;
  onToggle: () => void;
}

const STATE_STYLES: Record<TrustState, string> = {
  TRUSTED: 'border-status-nominal/40 bg-status-nominal/10 text-status-nominal',
  QUESTIONABLE: 'border-status-warning/40 bg-status-warning/10 text-status-warning',
  LOW_CONFIDENCE: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  INSUFFICIENT_DATA: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
};

export function TrustEvidence({
  result,
  expanded,
  loading,
  error,
  onToggle,
}: TrustEvidenceProps) {
  const assessment = result?.assessment;
  const [historyState, setHistoryState] = useState<TrustState | 'ALL'>('ALL');
  const [annotation, setAnnotation] = useState('');
  const [actionStatus, setActionStatus] = useState<string | null>(null);
  const [actionSaving, setActionSaving] = useState(false);
  const {
    data: events = [],
    isLoading: historyLoading,
    isError: historyError,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: ['trustEvents', assessment?.icao_hex, historyState],
    queryFn: () => fetchTrustEvents(
      assessment!.icao_hex,
      historyState === 'ALL' ? undefined : historyState
    ),
    enabled: expanded && !!assessment,
  });

  async function submitAction(actionType: 'ACKNOWLEDGE' | 'ANNOTATE') {
    if (!result) return;
    setActionSaving(true);
    setActionStatus('Saving…');
    try {
      await createTrustAction(result.assessment_id, {
        action_id: crypto.randomUUID(),
        action_type: actionType,
        actor: 'local-demo-operator',
        ...(actionType === 'ANNOTATE' ? { note: annotation } : {}),
      });
      setActionStatus(actionType === 'ANNOTATE' ? 'Annotation saved.' : 'Event acknowledged.');
      setAnnotation('');
      await refetchEvents();
    } catch {
      setActionStatus('Action could not be saved.');
    } finally {
      setActionSaving(false);
    }
  }
  return (
    <section className="border-b border-surface-3" aria-labelledby="trust-heading">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls="trust-evidence-content"
        className="flex min-h-11 w-full items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-surface-2"
      >
        <span id="trust-heading" className="text-xs uppercase tracking-wider text-slate-400">
          Explainable trust state
        </span>
        <span className="flex items-center gap-2">
          {assessment && (
            <span className={clsx('rounded border px-2 py-1 text-xs font-semibold', STATE_STYLES[assessment.state])}>
              {assessment.state.replace('_', ' ')}
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
        <div id="trust-evidence-content" className="space-y-3 px-4 pb-4 text-xs leading-relaxed">
          {loading && <p className="text-slate-400">Combining independent evidence states…</p>}
          {error && (
            <p role="alert" className="rounded border border-slate-500/30 bg-slate-500/10 p-3 text-slate-300">
              Trust evidence could not be loaded. No fallback score was guessed.
            </p>
          )}
          {assessment && (
            <>
              <div className={clsx('rounded border p-3', STATE_STYLES[assessment.state])}>
                {assessment.reasons.map(reason => <p key={reason}>{reason}</p>)}
              </div>
              <ol className="space-y-2" aria-label="Trust evidence components">
                {assessment.components.map(component => (
                  <li key={component.component} className="rounded border border-surface-3 bg-surface-2 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <span className="font-semibold text-slate-200">
                        {component.component.replace(/_/g, ' ')}
                      </span>
                      <span className="font-mono text-2xs text-slate-400">
                        {component.state.replace(/_/g, ' ')}
                      </span>
                    </div>
                    {component.reasons.map(reason => (
                      <p key={reason} className="mt-2 text-slate-400">{reason}</p>
                    ))}
                    <p className="mt-2 font-mono text-2xs text-slate-500">
                      {formatAge(component.age_seconds)}
                      {component.policy_version && ` · policy ${component.policy_version}`}
                    </p>
                    {component.evidence_ids.length > 0 && (
                      <details className="mt-2 border-t border-surface-3 pt-1">
                        <summary className="flex min-h-11 cursor-pointer items-center text-accent-primary">
                          Evidence identifiers
                        </summary>
                        {component.evidence_ids.map(identifier => (
                          <p key={identifier} className="break-all pb-2 font-mono text-2xs text-slate-500">
                            {identifier}
                          </p>
                        ))}
                      </details>
                    )}
                  </li>
                ))}
              </ol>
              <p className="border-l-2 border-accent-primary/40 pl-3 text-slate-400">
                No numeric score is shown because the combined policy has not been calibrated against field data.
              </p>
              {result && (
                <div className="space-y-3 rounded border border-surface-3 bg-surface-2 p-3">
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      disabled={actionSaving}
                      onClick={() => submitAction('ACKNOWLEDGE')}
                      className="min-h-11 rounded bg-accent-primary/20 px-3 font-semibold text-accent-primary disabled:opacity-40"
                    >
                      Acknowledge
                    </button>
                    <a
                      href={`/api/v1/trust-events/${result.assessment_id}/export`}
                      download
                      className="flex min-h-11 items-center rounded bg-surface-3 px-3 font-semibold text-slate-200"
                    >
                      Export JSON
                    </a>
                  </div>
                  <label className="block text-slate-300">
                    Review note
                    <textarea
                      value={annotation}
                      onChange={event => setAnnotation(event.target.value)}
                      maxLength={2000}
                      rows={3}
                      className="mt-1 w-full rounded border border-surface-3 bg-surface-1 p-2 text-slate-100"
                    />
                  </label>
                  <button
                    type="button"
                    disabled={!annotation.trim() || actionSaving}
                    onClick={() => submitAction('ANNOTATE')}
                    className="min-h-11 rounded bg-surface-3 px-3 font-semibold text-slate-200 disabled:opacity-40"
                  >
                    Save annotation
                  </button>
                  <p className="text-slate-500">
                    Operator identity is self-asserted in this local workflow until authentication is added.
                  </p>
                  {actionStatus && <p aria-live="polite" className="text-slate-300">{actionStatus}</p>}
                </div>
              )}
              <div className="space-y-2">
                <label className="flex items-center justify-between gap-3 text-slate-300">
                  Event history
                  <select
                    value={historyState}
                    onChange={event => setHistoryState(event.target.value as TrustState | 'ALL')}
                    className="min-h-11 rounded border border-surface-3 bg-surface-2 px-2 text-slate-100"
                  >
                    <option value="ALL">All states</option>
                    {Object.keys(STATE_STYLES).map(state => <option key={state}>{state}</option>)}
                  </select>
                </label>
                {historyLoading && <p className="text-slate-400">Loading event history…</p>}
                {historyError && <p role="alert" className="text-status-warning">Event history could not be loaded.</p>}
                {!historyLoading && !historyError && events.length === 0 && (
                  <p className="text-slate-500">No persisted events match this filter.</p>
                )}
                {events.map(event => (
                  <div key={event.assessment_id} className="rounded border border-surface-3 bg-surface-2 p-3">
                    <div className="flex justify-between gap-3">
                      <span className="font-semibold text-slate-200">{event.state.replace('_', ' ')}</span>
                      <time className="text-slate-500">{new Date(event.evaluated_at).toLocaleTimeString()}</time>
                    </div>
                    <p className="mt-1 break-all font-mono text-2xs text-slate-500">{event.assessment_id}</p>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}

function formatAge(ageSeconds: number | null): string {
  return ageSeconds === null ? 'No timestamp' : `Evidence age ${Math.round(ageSeconds)}s`;
}
