import { VerdictCard } from './VerdictCard';
import type { ORCAResponse } from '../types/api';

const titleCase = (s: string) =>
  s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const ASK_HINT: Record<string, string> = {
  location: 'e.g. "near Kochi" or "9.93N 76.26E"',
  time_window: 'e.g. "tomorrow morning" or "tonight"',
  destination: 'e.g. "to Chennai"',
  intent: 'e.g. "is it safe?" or "how is the fishing?"'
};

export const askHintFor = (what?: string | null) =>
  (what && ASK_HINT[what]) || 'Ask a follow-up…';

interface Props {
  data: ORCAResponse;
  onEvidenceClick: (provenanceId: string) => void;
}

export function Answer({ data, onEvidenceClick }: Props) {
  const rec = data.recommendation;

  /* ORCA is ASKING, not answering. The question is the whole content: it gets
   * its own card, and the caller closes the trace panel so nothing sits on top
   * of it. A question the user cannot see is not a question (F-57). */
  if (data.clarification_needed) {
    return (
      <div className="clarify">
        <div className="qmark">?</div>
        <div>
          <div className="headline">{rec?.headline || 'I need one more detail.'}</div>
          <div className="sub">waiting on {data.clarification_needed}</div>
        </div>
      </div>
    );
  }

  const L = data.resolved_location;
  const where = L
    ? `${L.label || ''} ${L.lat?.toFixed(2)}N ${L.lon?.toFixed(2)}E`.trim()
    : '';

  return (
    <>
      <div className="headline">{rec?.headline}</div>
      <div className="sub">
        {[data.intent, where, data.disposition?.toLowerCase()]
          .filter(Boolean).join(' · ')}
      </div>

      {(data.alerts || []).map((a, i) => (
        <div key={i} className={`alert${a.severity === 'warning' ? ' warning' : ''}`}>
          <i>{a.kind === 'inside' ? '◉' : '◈'}</i>
          <div>
            <b>{titleCase(a.kind)} {titleCase(a.boundary_type)}</b>
            {a.name ? ` — ${a.name}` : ''}
            {a.distance_km != null && (
              <div className="mono-xs">
                {a.distance_km} km · {a.dataset_version} · advisory only
              </div>
            )}
          </div>
        </div>
      ))}

      {(data.assessments || []).length > 0 && (
        <>
          <div className="sec">Independent assessments</div>
          <div className="verdicts">
            {data.assessments!.map((a, i) => <VerdictCard key={i} assessment={a} />)}
          </div>
        </>
      )}

      {(data.evidence || []).length > 0 && (
        <>
          <div className="sec">Evidence ({data.evidence!.length})</div>
          {data.evidence!.slice(0, 12).map((e) => (
            <div key={e.evidence_id} className="ev">
              {e.statement || e.parameter}
              <br />
              <span className="p" title="Show the provenance chain"
                    onClick={() => onEvidenceClick(e.provenance_id)}>
                {e.provenance_id}
              </span>
            </div>
          ))}
        </>
      )}

      <div className="disclaimer">
        ORCA is not an official advisory service. It cites INCOIS and IMD;
        it does not replace them.
      </div>
    </>
  );
}
