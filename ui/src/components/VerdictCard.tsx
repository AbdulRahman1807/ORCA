import type { ORCAAssessment, ORCADriver } from '../types/api';

const VERDICT_COLOUR: Record<string, string> = {
  FAVOURABLE: 'var(--favourable)', PERMITTED: 'var(--favourable)',
  MARGINAL: 'var(--marginal)', RESTRICTED: 'var(--marginal)',
  UNFAVOURABLE: 'var(--unfavourable)',
  UNSAFE: 'var(--unsafe)', PROHIBITED: 'var(--unsafe)',
  INSUFFICIENT_EVIDENCE: 'var(--unknown)', UNKNOWN: 'var(--unknown)'
};
const BAND_COLOUR: Record<string, string> = {
  favourable: '#34d399', marginal: '#fbbf24',
  unfavourable: '#fb923c', unsafe: '#f43f5e'
};
const BAND_ORDER = ['favourable', 'marginal', 'unfavourable', 'unsafe'];

const titleCase = (s: string) =>
  s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

/* A boolean means CONTAINMENT in the regulatory domain and PRESENCE elsewhere.
 * "EEZ absent" reads as "there is no EEZ" rather than "you are outside it",
 * which is a different and false claim (F-59). */
function booleanWord(value: boolean, domain: string) {
  return domain === 'REGULATORY'
    ? (value ? 'inside' : 'outside')
    : (value ? 'present' : 'absent');
}

/* The API returns a driver's BAND, not the band edges, so the pin is placed
 * inside its band rather than at an absolute position. Inventing an axis would
 * be inventing a fact. */
function ThresholdGauge({ driver, domain }: { driver: ORCADriver; domain: string }) {
  const limiting = driver.contribution === 'limiting';
  const label = (
    <span className={`glabel${limiting ? ' limiting' : ''}`}>
      {limiting ? '▸ ' : ''}
      {titleCase(driver.factor)}
    </span>
  );

  if (typeof driver.value !== 'number') {
    const shown = typeof driver.value === 'boolean'
      ? booleanWord(driver.value, domain)
      : (driver.value ?? '—');
    return (
      <div className="grow">
        {label}
        <span className="gval">{String(shown)}</span>
      </div>
    );
  }

  const idx = BAND_ORDER.indexOf(driver.band ?? '');
  const pin = idx < 0 ? 50 : ((idx + 0.5) / BAND_ORDER.length) * 100;
  return (
    <div className="gauge">
      <div className="grow">
        {label}
        <span className="gval">
          {driver.value}
          {driver.unit ? ` ${driver.unit}` : ''}
        </span>
      </div>
      <div className="gbar">
        {BAND_ORDER.map((b) => (
          <div key={b} className="gseg"
               style={{ flex: 1, background: BAND_COLOUR[b], opacity: 0.55 }} />
        ))}
        <div className="gpin" style={{ left: `${pin}%` }} />
      </div>
    </div>
  );
}

export function VerdictCard({ assessment }: { assessment: ORCAAssessment }) {
  const colour = VERDICT_COLOUR[assessment.verdict] || 'var(--unknown)';
  const gaps = (assessment.not_evaluated || []).map((n) => titleCase(n.factor));
  const capped = (assessment.verdict_capped_by || []).length > 0;

  return (
    <div className="verdict-card" style={{ ['--c' as string]: colour }}>
      <div className="vtop">
        <span className="vdom">{titleCase(assessment.domain)}</span>
        <span className="vverdict">{titleCase(assessment.verdict)}</span>
        <span className="vconf">{assessment.confidence}</span>
      </div>

      {assessment.drivers?.map((d, i) => (
        <ThresholdGauge key={i} driver={d} domain={assessment.domain} />
      ))}

      {capped && (
        <div className="ceiling">
          Ceiling, not a measurement — {assessment.verdict_capped_by.join(', ')}{' '}
          could not be checked.
        </div>
      )}

      {assessment.rationale && <div className="rationale">{assessment.rationale}</div>}

      {gaps.length > 0 && (
        <div className="gaps">
          <b>Not checked:</b> {gaps.slice(0, 6).join(', ')}
          {gaps.length > 6 ? ' …' : ''}
        </div>
      )}
    </div>
  );
}
