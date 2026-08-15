import { useEffect, useMemo, useState } from 'react';
import fixture from './fixtures/static-evidence-v1.json';

type Evidence = {kind: string; severity: string; summary: string; measured: number; threshold: number; unit: string};
type Frame = {elapsed_seconds: number; state: string; evidence: Evidence[]};
type Scenario = {id: string; title: string; family: string; summary: string; frames: Frame[]};

const scenarios = fixture.scenarios as Scenario[];
const repository = 'https://github.com/johananabraham/ADS-B-Flight-Intelligence-Platform';

export default function StaticEvidenceApp() {
  const [scenarioId, setScenarioId] = useState(scenarios[0].id);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const scenario = useMemo(() => scenarios.find((item) => item.id === scenarioId) ?? scenarios[0], [scenarioId]);
  const frame = scenario.frames[frameIndex] ?? scenario.frames[0];

  useEffect(() => {
    setFrameIndex(0);
    setPlaying(false);
  }, [scenarioId]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setFrameIndex((current) => {
        if (current >= scenario.frames.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 1000 / speed);
    return () => window.clearInterval(timer);
  }, [playing, scenario.frames.length, speed]);

  return (
    <div className="min-h-dvh bg-surface-0 text-slate-200">
      <a href="#recorded-evidence" className="sr-only fixed left-3 top-3 z-50 rounded bg-cyan-400 px-4 py-3 font-semibold text-slate-950 focus:not-sr-only">Skip to recorded evidence</a>
      <div className="sticky top-0 z-10 bg-amber-400 px-4 py-2 text-center text-xs font-bold tracking-[0.16em] text-slate-950">
        RECORDED RESEARCH DEMO — NOT LIVE TRAFFIC
      </div>
      <main id="recorded-evidence" className="mx-auto max-w-6xl px-4 py-10 md:px-8" tabIndex={-1}>
        <header className="mb-10 border-b border-slate-800 pb-8">
          <p className="font-data text-xs tracking-[0.18em] text-cyan-400">ADS-B FEEDER INTEGRITY · STATIC EVIDENCE V1</p>
          <h1 className="mt-3 max-w-4xl text-4xl font-bold tracking-tight text-white md:text-6xl">Evidence for untrusted telemetry, with the limits left visible.</h1>
          <p className="mt-4 max-w-3xl text-lg text-slate-400">Browser-local playback of checked-in synthetic fixtures and research status. No backend, receiver, authentication, mutation, WebSocket, database, or external data request is used.</p>
        </header>

        <section className="grid gap-4 md:grid-cols-2" aria-label="Research status">
          <article className="panel p-5"><p className="font-data text-xs text-cyan-400">BENIGN FIELD BENCHMARK</p><h2 className="mt-2 text-xl font-semibold">{fixture.benchmark.status}</h2><p className="mt-2 text-sm text-slate-400">{fixture.benchmark.detail}</p><div className="mt-4 grid grid-cols-2 gap-3 font-data text-sm"><span>Abrupt recall<br/><strong className="text-white">{fixture.benchmark.synthetic_abrupt_targeted_recall * 100}% / 20</strong></span><span>Gradual recall<br/><strong className="text-white">{fixture.benchmark.synthetic_gradual_targeted_recall * 100}% / 20</strong></span></div></article>
          <article className="panel p-5"><p className="font-data text-xs text-cyan-400">PUBLIC CANDIDATE</p><h2 className="mt-2 text-xl font-semibold">{fixture.public_candidate.outcome}</h2><p className="mt-2 text-sm text-slate-400">{fixture.public_candidate.detail}</p><p className="mt-4 border-l-2 border-amber-400 pl-3 text-xs text-amber-200">{fixture.public_candidate.claim_boundary}</p></article>
        </section>

        <section className="panel mt-6 p-5">
          <div className="flex flex-col justify-between gap-4 border-b border-slate-800 pb-5 md:flex-row md:items-end">
            <div><p className="font-data text-xs text-cyan-400">DETERMINISTIC PLAYBACK</p><h2 className="mt-1 text-2xl font-semibold">{scenario.title}</h2><p className="mt-2 max-w-2xl text-sm text-slate-400">{scenario.summary}</p></div>
            <label className="text-sm text-slate-400">Scenario<select className="ml-3 min-h-11 rounded border border-slate-700 bg-slate-900 px-3 py-2 text-white" value={scenarioId} onChange={(event) => setScenarioId(event.target.value)}>{scenarios.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
          </div>
          <div className="grid gap-5 py-6 md:grid-cols-[1fr_2fr]">
            <div><p className="font-data text-xs text-slate-500">T+{frame.elapsed_seconds.toFixed(1)}s · POLICY {fixture.policy_version}</p><p className={`mt-3 inline-block border px-3 py-1 font-data text-sm ${frame.state === 'QUESTIONABLE' ? 'border-amber-400 text-amber-300' : 'border-emerald-500 text-emerald-300'}`}>{frame.state}</p><p className="mt-5 text-sm text-slate-400">Frame {frameIndex + 1} of {scenario.frames.length} · {scenario.family}</p></div>
            <div>{frame.evidence.length === 0 ? <p className="rounded border border-slate-800 bg-slate-950 p-5 text-slate-400">No active integrity evidence in this frame. NOMINAL does not mean verified or trusted.</p> : frame.evidence.map((item) => <article key={item.kind} className="rounded border border-amber-500/50 bg-amber-500/5 p-5"><p className="font-data text-xs text-amber-300">{item.kind} · {item.severity}</p><p className="mt-2 text-white">{item.summary}</p><p className="mt-3 font-data text-sm text-slate-400">Measured {item.measured} {item.unit} · threshold {item.threshold} {item.unit}</p></article>)}</div>
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-slate-800 pt-5"><button className="min-h-11 rounded bg-cyan-500 px-4 py-2 font-semibold text-slate-950 transition-colors hover:bg-cyan-300 motion-reduce:transition-none" onClick={() => setPlaying((value) => !value)}>{playing ? 'Pause' : 'Play'}</button><button className="min-h-11 rounded border border-slate-700 px-4 py-2 transition-colors hover:border-slate-500 motion-reduce:transition-none" onClick={() => {setFrameIndex(0); setPlaying(false);}}>Reset</button><label className="text-sm text-slate-400">Speed<select className="ml-2 min-h-11 rounded border border-slate-700 bg-slate-900 px-2 py-2" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option></select></label><input aria-label="Playback frame" className="h-11 min-w-48 flex-1 cursor-pointer accent-cyan-400" type="range" min="0" max={scenario.frames.length - 1} value={frameIndex} onChange={(event) => {setFrameIndex(Number(event.target.value)); setPlaying(false);}} /></div>
        </section>

        <nav className="mt-8 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4" aria-label="Project evidence links">
          <a className="panel flex min-h-11 items-center p-4 text-cyan-300 transition-colors hover:border-cyan-500 motion-reduce:transition-none" href={`${repository}/blob/main/docs/FEEDER_SIDECAR.md`}>Local Docker guide</a>
          <a className="panel flex min-h-11 items-center p-4 text-cyan-300 transition-colors hover:border-cyan-500 motion-reduce:transition-none" href={`${repository}/blob/main/docs/BENIGN_FIELD_EVALUATION.md`}>Benchmark method</a>
          <a className="panel flex min-h-11 items-center p-4 text-cyan-300 transition-colors hover:border-cyan-500 motion-reduce:transition-none" href={`${repository}/blob/main/docs/PUBLIC_ANOMALY_REPLAY.md`}>Public replay method</a>
          <a className="panel flex min-h-11 items-center p-4 text-cyan-300 transition-colors hover:border-cyan-500 motion-reduce:transition-none" href={repository}>Source code</a>
        </nav>
      </main>
      <footer className="border-t border-slate-800 px-4 py-6 text-center text-xs tracking-[0.12em] text-slate-500">RECORDED RESEARCH DEMO — NOT LIVE TRAFFIC</footer>
    </div>
  );
}
