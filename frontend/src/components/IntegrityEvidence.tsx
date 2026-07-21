import clsx from 'clsx';

import type { KinematicEvaluation, KinematicRuleResult } from '@/types';

interface IntegrityEvidenceProps {
  evaluation?: KinematicEvaluation;
  expanded: boolean;
  loading: boolean;
  error: boolean;
  onToggle: () => void;
}

const STATUS_STYLES = {
  PASS: 'border-status-nominal/40 bg-status-nominal/10 text-status-nominal',
  FLAGGED: 'border-status-warning/40 bg-status-warning/10 text-status-warning',
  INSUFFICIENT_DATA: 'border-slate-500/40 bg-slate-500/10 text-slate-300',
};

export function IntegrityEvidence({
  evaluation,
  expanded,
  loading,
  error,
  onToggle,
}: IntegrityEvidenceProps) {
  const failedRules = evaluation?.rule_results.filter(rule => rule.status === 'FLAGGED') ?? [];

  return (
    <section className="border-b border-surface-3" aria-labelledby="integrity-heading">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls="integrity-evidence-content"
        className="flex min-h-11 w-full cursor-pointer items-center justify-between gap-3 p-4 text-left transition-colors hover:bg-surface-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent-primary"
      >
        <span id="integrity-heading" className="text-xs uppercase tracking-wider text-slate-400">
          Integrity Evidence
        </span>
        <span className="flex items-center gap-2">
          {evaluation && (
            <span className={clsx('rounded border px-2 py-1 text-xs font-semibold', STATUS_STYLES[evaluation.status])}>
              {evaluation.status.replace('_', ' ')}
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
        <div id="integrity-evidence-content" className="space-y-3 px-4 pb-4 text-xs leading-relaxed">
          {loading && <p className="text-slate-400">Evaluating recent position reports…</p>}
          {error && (
            <p role="alert" className="rounded border border-red-500/30 bg-red-500/10 p-3 text-red-300">
              Integrity evidence could not be loaded. Confirm the API and database migration are running.
            </p>
          )}
          {!loading && !error && !evaluation && (
            <p className="rounded border border-surface-3 bg-surface-2 p-3 text-slate-300">
              No evaluation yet. Two complete position reports from the same source are required.
            </p>
          )}
          {evaluation && (
            <>
              <p className="text-slate-300">
                Policy {evaluation.policy_version} compared two observations over{' '}
                <span className="font-mono text-slate-100">{evaluation.delta_seconds.toFixed(1)} s</span>.
              </p>

              {evaluation.status === 'PASS' && (
                <p className="rounded border border-status-nominal/30 bg-status-nominal/10 p-3 text-slate-200">
                  All {evaluation.rule_results.length} available checks stayed within conservative limits.
                </p>
              )}

              {evaluation.status === 'INSUFFICIENT_DATA' && (
                <p className="rounded border border-slate-500/30 bg-slate-500/10 p-3 text-slate-200">
                  {evaluation.reason || 'The available observations could not be scored safely.'}
                </p>
              )}

              {failedRules.length > 0 && (
                <div className="space-y-2" aria-label="Failed kinematic rules">
                  {failedRules.map(rule => <FailedRule key={rule.rule} rule={rule} />)}
                </div>
              )}

              <p className="border-l-2 border-accent-primary/40 pl-3 text-slate-400">
                These checks measure internal consistency. They do not authenticate the transmitter or prove spoofing.
              </p>
              <p className="font-mono text-2xs text-slate-500">
                Source: {evaluation.source_type} / {evaluation.source_id}
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}

function FailedRule({ rule }: { rule: KinematicRuleResult }) {
  return (
    <div className="rounded border border-status-warning/30 bg-status-warning/10 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-status-warning">
          {rule.rule.replace(/_/g, ' ')}
        </span>
        <span className="font-mono text-slate-100">
          {rule.value.toLocaleString()} {rule.unit}
        </span>
      </div>
      <p className="mt-1 text-slate-300">
        Policy limit: {rule.threshold.toLocaleString()} {rule.unit}
      </p>
    </div>
  );
}
