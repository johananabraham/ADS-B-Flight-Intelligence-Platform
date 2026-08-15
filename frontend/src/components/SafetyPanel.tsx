import { useState, useCallback, useRef } from 'react';

interface SafetyPanelProps {
  onClose: () => void;
}

interface SafetyResult {
  answer: string;
  trace_id: string;
  trace_url?: string;
  citations: SafetyCitation[];
  tool_calls: { name: string; arguments: Record<string, unknown>; duration_ms: number }[];
  iterations: number;
  total_tokens: number;
  error?: string;
}

interface SafetyCitation {
  source_type: 'NTSB_INCIDENT' | 'ECFR_REGULATION';
  label: string;
  document_id?: string;
  source_url?: string;
  effective_date?: string;
  source_sha256?: string;
  span: {
    section?: string;
    char_start?: number;
    char_end?: number;
    text: string;
  };
}

export function SafetyPanel({ onClose }: SafetyPanelProps) {
  const sessionId = useRef(crypto.randomUUID());
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<SafetyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/safety/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, session_id: sessionId.current }),
      });

      if (!response.ok) throw new Error('Query failed');

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [query]);

  return (
    <div className="absolute top-16 right-4 w-[500px] max-h-[70vh] z-[1001] bg-gray-900/95 rounded-lg border border-cyan-500/30 shadow-xl overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-cyan-500/30">
        <h2 className="text-lg font-semibold text-cyan-400">Safety Research</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">&times;</button>
      </div>

      {/* Query Input */}
      <form onSubmit={handleSubmit} className="p-4 border-b border-cyan-500/20">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about NTSB incidents or FAA regulations..."
            className="flex-1 bg-gray-800 border border-cyan-500/30 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-cyan-400"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-600 rounded text-sm font-medium transition-colors"
          >
            {loading ? '...' : 'Ask'}
          </button>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          Examples: "How many Cessna 172 accidents in California?" • "What regulations cover VFR fuel?"
        </p>
      </form>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {error && (
          <div className="p-3 bg-red-900/50 border border-red-500/30 rounded text-red-300 text-sm">
            {error}
          </div>
        )}

        {result && (
          <>
            {/* Answer */}
            <div className="prose prose-invert prose-sm max-w-none">
              <div className="whitespace-pre-wrap text-gray-200 text-sm leading-relaxed">
                {result.answer}
              </div>
            </div>

            {result.citations.length > 0 && (
              <section aria-label="Grounded sources" className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
                  Grounded sources
                </h3>
                {result.citations.map((citation) => (
                  <details
                    key={`${citation.source_type}:${citation.label}`}
                    className="rounded border border-cyan-500/20 bg-gray-800/70 p-2 text-xs"
                  >
                    <summary className="cursor-pointer text-gray-200">
                      {citation.source_url ? (
                        <a
                          href={citation.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="font-mono text-cyan-400 hover:underline"
                          onClick={(event) => event.stopPropagation()}
                        >
                          {citation.label}
                        </a>
                      ) : (
                        <span className="font-mono text-cyan-400">{citation.label}</span>
                      )}
                      {citation.effective_date && (
                        <span className="ml-2 text-gray-500">effective {citation.effective_date}</span>
                      )}
                    </summary>
                    <p className="mt-2 whitespace-pre-wrap text-gray-400">{citation.span.text}</p>
                    <div className="mt-2 space-y-0.5 text-[10px] text-gray-600">
                      {citation.document_id && <div>Document: {citation.document_id}</div>}
                      {citation.span.section && <div>Section: {citation.span.section}</div>}
                      {citation.source_sha256 && (
                        <div className="break-all">SHA-256: {citation.source_sha256}</div>
                      )}
                    </div>
                  </details>
                ))}
              </section>
            )}

            {result.answer && result.citations.length === 0 && (
              <p className="rounded border border-amber-500/20 bg-amber-950/30 p-2 text-xs text-amber-300">
                No retrieved source was matched to a citation in this answer. Treat it as unverified.
              </p>
            )}

            {/* Tool calls (collapsed by default) */}
            {result.tool_calls.length > 0 && (
              <details className="text-xs">
                <summary className="text-gray-500 cursor-pointer hover:text-gray-300">
                  {result.tool_calls.length} tool calls • {result.iterations} iterations • {result.total_tokens} tokens
                </summary>
                <div className="mt-2 space-y-2">
                  {result.tool_calls.map((tc, i) => (
                    <div key={i} className="p-2 bg-gray-800 rounded border border-gray-700">
                      <span className="text-cyan-400">{tc.name}</span>
                      <span className="text-gray-500 ml-2">({tc.duration_ms.toFixed(0)}ms)</span>
                    </div>
                  ))}
                </div>
              </details>
            )}

            <p className="select-all break-all font-mono text-[10px] text-gray-600">
              {result.trace_url ? (
                <a href={result.trace_url} target="_blank" rel="noreferrer" className="hover:text-cyan-500">
                  Trace {result.trace_id}
                </a>
              ) : (
                <>Trace {result.trace_id}</>
              )}
            </p>
          </>
        )}

        {!result && !loading && !error && (
          <div className="text-center text-gray-500 py-8">
            <p className="text-2xl mb-2">🔍</p>
            <p>Query NTSB incident database and FAA regulations using natural language.</p>
          </div>
        )}
      </div>
    </div>
  );
}
