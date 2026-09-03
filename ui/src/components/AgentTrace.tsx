import type { ORCATraceEvent } from '../types/api';

const NODE_LABEL: Record<string, string> = {
  ingest: 'Ingest', intent_context: 'Resolve intent, place and time',
  plan: 'Plan', tool_exec: 'Retrieve', validate: 'Validate evidence',
  replan: 'Re-plan', geo_reason: 'Align and derive',
  assess_safety: 'Assess safety', assess_fishing_suitability: 'Assess fishing',
  assess_regulatory: 'Assess regulatory', conflict_resolve: 'Resolve conflicts',
  evidence_assemble: 'Assemble evidence', review_gate: 'Review gate',
  human_review: 'Human review', report: 'Compose answer', finalize: 'Finalise',
  clarify: 'Ask for clarification', error_handler: 'Error'
};

/* Every node the graph emitted, including each parallel tool in a fan-out.
 * Showing only the newest per superstep collapsed seven tools to one line and
 * hid the single thing this panel exists to show (F-56). */
export function AgentTrace({ trace, live }: { trace: ORCATraceEvent[]; live: boolean }) {
  if (!trace.length) return <div className="empty">No trace yet.</div>;

  return (
    <div className="trace">
      {trace.map((ev, i) => {
        const bad = ev.status === 'error' || ev.status === 'failed';
        const warn = ev.status === 'degraded' || ev.status === 'partial';
        const isLast = live && i === trace.length - 1;
        const bits: string[] = [];
        if (ev.codes?.length) bits.push(ev.codes.join(', '));
        if (ev.fallback_used) bits.push('served by a fallback');
        if (ev.summary && !ev.tool) bits.push(ev.summary);

        return (
          <div key={i}>
            {i > 0 && <div className="rail" />}
            <div className={`tnode${isLast ? ' live' : ''}`}>
              <span className={`tdot${bad ? ' err' : warn ? ' warn' : ''}`} />
              <span className="tname">{ev.tool || NODE_LABEL[ev.node] || ev.node}</span>
              <span className="tmeta">
                {ev.source ? `${ev.source} · ` : ''}
                {ev.duration_ms ?? 0} ms
              </span>
            </div>
            {bits.length > 0 && <div className="tsum">{bits.join(' — ')}</div>}
          </div>
        );
      })}
    </div>
  );
}
