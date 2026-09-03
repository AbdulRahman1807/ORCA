import { useEffect, useState } from 'react';
import { fetchProvenance } from '../api/client';
import type { ORCAProvenance } from '../types/api';

const Row = ({ k, v }: { k: string; v: unknown }) =>
  v == null || v === '' ? null : (
    <div className="prov-row">
      <span className="prov-k">{k}</span>
      <span className="prov-v">{String(v)}</span>
    </div>
  );

/* The evidence panel's L2/L3: where a number came from and, when derived, the
 * method and inputs that make it recomputable. */
export function ProvenancePanel({ thread, provenanceId }:
  { thread?: string; provenanceId: string | null }) {
  const [rec, setRec] = useState<ORCAProvenance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!thread || !provenanceId) return;
    setRec(null);
    setError(null);
    fetchProvenance(thread, provenanceId)
      .then((d) => setRec(d.provenance?.[0] ?? null))
      .catch((e) => setError(e.message));
  }, [thread, provenanceId]);

  if (!provenanceId) return <div className="empty">Select an evidence id.</div>;
  if (error) return <div className="empty">Could not load provenance.</div>;
  if (!rec) return <div className="empty"><span className="spin" /></div>;

  const d = rec.derivation;
  return (
    <>
      <div className="sec">Value</div>
      <Row k="parameter" v={rec.parameter} />
      <Row k="unit" v={rec.unit} />
      <Row k="kind" v={rec.value_kind} />

      <div className="sec">Source</div>
      <Row k="source" v={rec.source} />
      <Row k="source id" v={rec.source_id} />
      <Row k="organisation" v={rec.organisation} />
      <Row k="dataset" v={rec.dataset} />
      <Row k="access" v={rec.access_method} />
      <Row k="retrieved" v={String(rec.retrieved_at ?? '').slice(0, 19)} />

      {d && (
        <>
          <div className="sec">Derivation</div>
          <Row k="method" v={`${d.method} v${d.method_version}`} />
          <Row k="inputs" v={(d.inputs || []).join(', ')} />
          <Row k="params" v={JSON.stringify(d.params || {})} />
        </>
      )}

      {rec.licence_reference && (
        <div className="disclaimer">{rec.licence_reference}</div>
      )}
    </>
  );
}
