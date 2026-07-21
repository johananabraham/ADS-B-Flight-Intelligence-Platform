import { useCallback, useEffect, useState } from 'react';
import clsx from 'clsx';

type PlaybackState = 'PLAYING' | 'PAUSED' | 'COMPLETED';
type ReplayAction = 'pause' | 'resume' | 'restart' | 'seek' | 'speed';

interface ReplayStatus {
  recording_id: string;
  title: string;
  state: PlaybackState;
  speed: number;
  position_ms: number;
  duration_ms: number;
  event_index: number;
  event_count: number;
  loop: boolean;
}

const SPEEDS = [0.5, 1, 2, 10];

function formatTime(milliseconds: number): string {
  const totalSeconds = Math.max(0, milliseconds) / 1000;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = (totalSeconds % 60).toFixed(1).padStart(4, '0');
  return `${minutes}:${seconds}`;
}

export function ReplayControls() {
  const [status, setStatus] = useState<ReplayStatus | null>(null);
  const [seekSeconds, setSeekSeconds] = useState(0);
  const [editingSeek, setEditingSeek] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/v1/replay/status');
      if (!response.ok) throw new Error('Recorded replay controls are unavailable');
      const nextStatus: ReplayStatus = await response.json();
      setStatus(nextStatus);
      if (!editingSeek) setSeekSeconds(nextStatus.position_ms / 1000);
      setError(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Replay status failed');
    }
  }, [editingSeek]);

  useEffect(() => {
    void loadStatus();
    const timer = window.setInterval(() => void loadStatus(), 1000);
    return () => window.clearInterval(timer);
  }, [loadStatus]);

  const sendCommand = async (action: ReplayAction, value?: number) => {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch('/api/v1/replay/commands', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, value }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'Replay command failed');
      setStatus(body);
      setSeekSeconds(body.position_ms / 1000);
      setEditingSeek(false);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Replay command failed');
    } finally {
      setBusy(false);
    }
  };

  const state = status?.state ?? 'PAUSED';
  const durationSeconds = (status?.duration_ms ?? 0) / 1000;

  return (
    <section
      aria-label="Recorded replay timeline"
      className="panel w-[min(720px,calc(100vw-2rem))] px-4 py-3 shadow-xl"
    >
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={clsx(
              'h-2 w-2 rounded-full',
              state === 'PLAYING' ? 'bg-status-nominal pulse-live' : 'bg-status-caution'
            )} />
            <span className="text-xs font-semibold tracking-wider text-slate-200">RECORDED REPLAY</span>
            <span className="text-2xs font-mono text-slate-400">{state}</span>
          </div>
          <p className="truncate text-2xs text-slate-500" title={status?.title}>
            {status?.title ?? 'Connecting to replay controller…'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={busy || !status || state === 'COMPLETED'}
            onClick={() => void sendCommand(state === 'PLAYING' ? 'pause' : 'resume')}
            className="min-h-11 min-w-20 rounded bg-accent-primary/20 px-3 text-xs font-semibold text-accent-primary transition-colors hover:bg-accent-primary/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-primary disabled:cursor-not-allowed disabled:opacity-40"
          >
            {state === 'PLAYING' ? 'PAUSE' : 'RESUME'}
          </button>
          <button
            type="button"
            disabled={busy || !status}
            onClick={() => void sendCommand('restart')}
            className="min-h-11 rounded bg-surface-3 px-3 text-xs font-semibold text-slate-300 transition-colors hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-primary disabled:cursor-not-allowed disabled:opacity-40"
          >
            RESTART
          </button>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <span className="w-12 text-right font-mono text-2xs text-slate-300">
          {formatTime(seekSeconds * 1000)}
        </span>
        <label className="sr-only" htmlFor="replay-position">Replay position</label>
        <input
          id="replay-position"
          type="range"
          min={0}
          max={Math.max(durationSeconds, 0.1)}
          step={0.1}
          value={Math.min(seekSeconds, Math.max(durationSeconds, 0.1))}
          disabled={busy || !status}
          onChange={(event) => {
            setEditingSeek(true);
            setSeekSeconds(Number(event.target.value));
          }}
          className="h-11 min-w-0 flex-1 cursor-pointer accent-cyan-400 disabled:cursor-not-allowed disabled:opacity-40"
        />
        <span className="w-12 font-mono text-2xs text-slate-500">
          {formatTime(status?.duration_ms ?? 0)}
        </span>
        <button
          type="button"
          disabled={busy || !status || !editingSeek}
          onClick={() => void sendCommand('seek', seekSeconds)}
          className="min-h-11 rounded border border-surface-3 px-3 text-2xs font-semibold text-slate-300 hover:border-accent-primary/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-primary disabled:cursor-not-allowed disabled:opacity-40"
        >
          SEEK
        </button>
      </div>

      <div className="mt-2 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2" aria-label="Playback speed">
          <span className="text-2xs uppercase tracking-wider text-slate-500">Speed</span>
          {SPEEDS.map((speed) => (
            <button
              key={speed}
              type="button"
              disabled={busy || !status}
              aria-pressed={status?.speed === speed}
              onClick={() => void sendCommand('speed', speed)}
              className={clsx(
                'min-h-11 min-w-11 rounded px-2 font-mono text-2xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-primary disabled:cursor-not-allowed disabled:opacity-40',
                status?.speed === speed
                  ? 'bg-accent-primary/20 text-accent-primary'
                  : 'bg-surface-3 text-slate-400 hover:text-slate-200'
              )}
            >
              {speed}×
            </button>
          ))}
        </div>
        <span className="font-mono text-2xs text-slate-500">
          {status ? `${status.event_index}/${status.event_count} EVENTS` : 'NO STATUS'}
        </span>
      </div>

      {error && (
        <div role="alert" className="mt-2 rounded border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}. Retry after confirming recorded replay mode is running.
        </div>
      )}
      <span className="sr-only" aria-live="polite">{busy ? 'Applying replay command' : ''}</span>
    </section>
  );
}
