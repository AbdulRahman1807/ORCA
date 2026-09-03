import type { ORCASource } from '../types/api';

/* A capability with no source is DECLARED, never hidden. Every answer names
 * what it could not check, and so does this panel. */
export function SourceHealth({ sources }: { sources: ORCASource[] }) {
  if (!sources.length) return <div className="empty">Loading…</div>;
  return (
    <>
      {sources.map((s) => (
        <div key={s.tool} className="source-row">
          <span className={`dot${s.available ? '' : ' off'}`} />
          <div>
            <div className="mono-sm">{s.tool}</div>
            <div className="source-desc">
              {s.available ? s.description : (s.unavailable_reason || 'not bound')}
            </div>
          </div>
        </div>
      ))}
      <div className="disclaimer">
        A capability with no source is declared, never hidden. Every answer names
        what it could not check.
      </div>
    </>
  );
}
