import { legendGradient, type FieldSpec } from '../lib/fields';
import type { ORCAField } from '../types/api';

interface Props {
  spec: FieldSpec | null;
  field: ORCAField | null;
  error: string | null;
}

/* Always states coverage. A field that is 50% masked must not look like a
 * complete picture, and a field that FAILED is absent, not empty -- an empty
 * map reads as calm water. */
export function Legend({ spec, field, error }: Props) {
  if (!spec) return null;

  if (error) {
    return (
      <div className="legend show">
        <h4>{spec.label}</h4>
        <div className="legend-msg">
          Not available for this area.
          <br />
          <span className="mono-xs">{error.slice(0, 130)}</span>
        </div>
        <div className="cov">
          The layer is absent, not empty — an empty map would read as calm water.
        </div>
      </div>
    );
  }
  if (!field) return null;

  const cov = Math.round((field.cells.coverage || 0) * 100);
  const masked = field.cells.total - field.cells.valid;
  return (
    <div className="legend show">
      <h4>
        {field.label} <span className="dim">{field.unit}</span>
      </h4>
      <div className="ramp" style={{ background: legendGradient(spec) }} />
      <div className="rlab">
        <span>{field.range.min}</span>
        <span>{field.range.max}</span>
      </div>
      <div className="cov">
        <b style={{ color: cov < 90 ? 'var(--marginal)' : 'var(--text-secondary)' }}>
          {cov}% coverage
        </b>{' '}
        — {masked} cells masked, drawn as gaps.
        <br />
        <span className="mono-xs">
          {field.source} · {String(field.valid_time).slice(0, 16).replace('T', ' ')}Z
        </span>
      </div>
    </div>
  );
}
