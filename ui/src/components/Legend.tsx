import { legendGradient, type FieldSpec } from '../lib/fields';
import type { ORCAField } from '../types/api';

export interface CorridorInfo { unit: string | null; min: number; max: number }

interface Props {
  spec: FieldSpec | null;
  field: ORCAField | null;
  error: string | null;
  corridor?: CorridorInfo | null;
}

/* Always states coverage. A field that is 50% masked must not look like a
 * complete picture, and a field that FAILED is absent, not empty -- an empty
 * map reads as calm water. */
export function Legend({ spec, field, error, corridor }: Props) {
  const corridorBox = corridor ? (
    <div className="legend show corridor-legend">
      <h4>Route corridor <span className="dim">{corridor.unit}</span></h4>
      <div className="ramp"
           style={{ background: 'linear-gradient(90deg,#34d399,#a3e635,#fbbf24,#f43f5e)' }} />
      <div className="rlab">
        <span>0</span><span>1.5</span><span>2.5</span><span>3.5+</span>
      </div>
      <div className="cov">
        Wave height along the path — {corridor.min.toFixed(2)}–{corridor.max.toFixed(2)}{' '}
        {corridor.unit}. Grey segments had no wave value at that point and are
        left untinted rather than given a neighbour's.
      </div>
    </div>
  ) : null;

  if (!spec) return corridorBox;

  if (error) {
    return (
      <>
        {corridorBox}
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
      </>
    );
  }
  if (!field) return corridorBox;

  const cov = Math.round((field.cells.coverage || 0) * 100);
  const masked = field.cells.total - field.cells.valid;
  return (
    <>
      {corridorBox}
      <div className="legend show">
        <h4>
          {field.label} <span className="dim">{field.unit}</span>
        </h4>
        <div className="ramp" style={{ background: legendGradient(spec) }} />
        <div className="rlab">
          <span>{field.range.min}</span>
          <span>{field.range.max}</span>
        </div>
        {spec.name === 'chlorophyll' && (
          <div className="cov median-note">
            <span className="median-key" /> the local median — fishing judges the
            RATIO to it, not the absolute value, so the ring is the comparison
            the verdict actually made.
          </div>
        )}
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
    </>
  );
}
