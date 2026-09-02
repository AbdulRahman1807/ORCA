# ORCA — Multilingual and Alerting Specification

**Document:** 13 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** Design defined — IMPLEMENTATION REQUIRED · Language quality **EVALUATION REQUIRED**

---

# PART A — MULTILINGUAL

## A1. Why This Matters Here

The primary stakeholder — a coastal fisher — is far more likely to ask in Malayalam,
Tamil, Telugu, Odia, Marathi, Bengali, Gujarati, Kannada or Hindi than in English. A
marine advisory system that only speaks English is not usable by the people whose safety
depends on it. The SIH problem statement calls this out explicitly.

**The engineering risk is equally explicit:** a mistranslated wave height or a softened
safety verdict is a safety failure. ORCA's language architecture is designed so that
translation **cannot** alter numbers, units or verdicts.

---

## A2. Language Detection

```
input text
   │
   ├─ 1. Script detection (Unicode block)  → Malayalam, Devanagari, Tamil, Telugu,
   │                                         Bengali, Gujarati, Odia, Kannada, Latin
   ├─ 2. If Latin script → language identification (romanised Indic vs English)
   ├─ 3. Session preference (explicit setting always wins)
   └─ 4. Fallback: session default, else English
```

| Rule | Detail |
|---|---|
| Script detection is deterministic | Unicode block frequency; no model call |
| Romanised Indic ("naale kadalil pokamo?") | Handled by a lightweight language-ID step; if confidence is low, ORCA answers in the session language and offers a language switch |
| Explicit user setting | Always overrides detection |
| Detection is recorded | `runs.language` + a `detected_language` event; a wrong detection is user-correctable in one tap |
| Mixed-language input | The dominant script governs; code-mixed English technical terms are expected and handled by the lexicon |

---

## A3. Response-Language Preservation

> **The response is in the language of the user's input, unless the session explicitly
> overrides it.**

| Situation | Behaviour |
|---|---|
| Query in Malayalam | Answer in Malayalam |
| Query in English within a Malayalam session | Answer in English (input wins for that turn); the session language is unchanged |
| User switches language mid-conversation | Honoured immediately; prior turns are not retranslated |
| Language unsupported for generation | Answer in the nearest supported language with an explicit notice, never silently in English |

---

## A4. Pivot Architecture

```
   user query (any language)
        │  detect
        ▼
   ┌──────────────────────────────────────────────────────────┐
   │  INTERNAL REPRESENTATION — canonical English + typed data │
   │  intent · location · time · evidence · assessments        │
   │  numbers · units · coordinates · dataset ids              │
   └──────────────────────────────────────────────────────────┘
        │  generate in target language, FROM the evidence set
        ▼
   localised answer (numbers, units, coordinates unchanged)
```

**Why a pivot, not end-to-end multilingual reasoning:**

1. **Numeric safety.** Reasoning happens once, on typed data. The target-language step
   renders an already-fixed evidence set; it cannot change 2.4 m into 1.4 m because the
   number is injected as a formatted token, not re-derived.
2. **Testability.** One reasoning path is tested thoroughly; the language layer is tested
   separately for fidelity.
3. **Consistency.** Verdicts and severity labels come from a fixed localised vocabulary,
   not free translation, so `MARGINAL` renders identically every time.
4. **Cost and latency.** Retrieval and assessment are language-independent and cacheable.

**Generation, not translation.** The preferred path generates the answer directly in the
target language from the evidence set (with the localised term lexicon in context), rather
than translating an English draft. Post-hoc translation of a generated English answer is
the fallback path when direct generation quality is insufficient for a language.

---

## A5. What Is Never Translated

| Never translated | Reason |
|---|---|
| Numbers and units (2.4 m, 11.3 m s⁻¹, 28.6 °C) | Rendered with locale digit conventions only if the user's locale requires it; the value never changes |
| Coordinates | Positional data |
| Dataset identifiers, product references, bulletin numbers | Machine identifiers |
| **Verbatim official bulletin text** | Quoted as issued, in its issued language. A clearly labelled translation may be shown *beneath* it, never in place of it |
| Source names (INCOIS, IMD, CMEMS) | Proper nouns; may carry a transliteration in parentheses |
| Canonical error codes (in analyst views) | Machine vocabulary |

---

## A6. Terminology Handling

A curated lexicon per language fixes the rendering of domain terms:

```yaml
# i18n/terms/ml.yaml   (Malayalam)
significant_wave_height: {term: "…", short: "…", notes: "Hs; keep the numeric value in metres"}
potential_fishing_zone:  {term: "…", policy: "reserved for the official INCOIS product"}
chlorophyll_a:           {term: "…"}
verdict.MARGINAL:        {term: "…"}
severity.WARNING:        {term: "…"}
disclaimer.not_official_advisory: {text: "…"}
```

| Rule | Detail |
|---|---|
| Reserved terms | "PFZ" / "Potential Fishing Zone" translate only to the officially-used regional term for that product. ORCA's own indicator uses a distinct term in every language and is never rendered with the PFZ term (`12_RISK_AND_RECOMMENDATION_SPEC.md` §5.2) |
| Verdicts and severities | Fixed lexicon entries, never free-generated |
| Disclaimers | Fixed, reviewed strings per language — not model output |
| Review | Each lexicon requires review by a speaker familiar with local marine vocabulary before that language is enabled. Coastal usage differs from formal register, and the fisher-facing register is the target |
| Fallback | A missing lexicon entry falls back to English with the term in parentheses, and logs a gap |

---

## A7. Audio / TTS Strategy

**Status: FUTURE.** Specified as an interface so it can be added without redesign; not
promised in the MVP.

| Component | Design |
|---|---|
| TTS | `synthesize_speech(text, language, voice)` behind a provider abstraction |
| Content | The **narrative and verdict only**. Evidence tables and dataset identifiers are not read aloud |
| Safety framing | Spoken output always leads with the verdict and the limiting factor, then the disclaimer |
| ASR (voice input) | `transcribe(audio, language_hint)`; the transcript is shown for confirmation before a run is submitted, because a misheard place name changes the answer |
| Offline | Not addressed; low-connectivity use is handled by cached answers, not on-device speech |

No quality claim is made for any Indic TTS/ASR path until it is evaluated.

---

## A8. Multilingual Evaluation

**No translation-quality claim is made in this documentation set.** The harness below must
be run and its results recorded before any such claim.

| Test | Method | Pass criterion |
|---|---|---|
| Numeric fidelity | Extract all numbers+units from the localised answer and diff against the evidence set | **100 %** exact match — hard gate |
| Verdict fidelity | Map the localised verdict term back via the lexicon | 100 % — hard gate |
| Disclaimer presence | String match against the reviewed disclaimer | 100 % — hard gate |
| Terminology consistency | Reserved terms used per policy | 100 % — hard gate |
| Round-trip semantics | Native-speaker review of a fixed set of ≥ 30 answers per language | Rated adequate or better |
| Detection accuracy | Labelled set incl. romanised input | Measured, target set after baseline |
| Safety-critical phrasing | Reviewer checks that "do not go" is unambiguous in the local register | Binary pass |

The four hard gates are **automated and blocking**: a localised answer failing any of them
is not delivered; ORCA falls back to a deterministic template in that language, or to
English with an explicit notice.

| Language | MVP status |
|---|---|
| English | Supported |
| Malayalam **or** Hindi (demo region) | MVP target — lexicon + hard gates + native review |
| Tamil, Telugu, Marathi, Odia, Bengali, Gujarati, Kannada | PROPOSED — enabled per language only after lexicon review and gate pass |

---

## A9. Multilingual Failure Behaviour

| Failure | Behaviour |
|---|---|
| Detection uncertain | Answer in the session language; offer a one-tap switch |
| Generation model unavailable for the language | Deterministic template answer assembled from lexicon entries and evidence |
| Hard gate failure | Regenerate once; then template; never deliver a failed localisation |
| Lexicon entry missing | English term in parentheses; gap logged |
| Script rendering unsupported on the client | Font fallback stack; if unavailable, transliteration with a notice |

---

# PART B — ALERTING

## B1. Architecture Principle

An alert is **a scheduled ORCA run over a stored geofence**, not a separate pipeline. It
uses the same capability tools, canonical schema, assessment logic, conflict handling,
provenance and review gate. This guarantees an alert can never make a claim that an
interactive answer could not.

```
 subscription (geofence + domains + min_severity + channels + language + quiet hours)
        │
        ▼  scheduler (per-domain cadence)
 ┌─────────────────────────────────────────────────────────────┐
 │  ORCA run scoped to the geofence                            │
 │  tools → canonical data → geo alignment → assessments       │
 └───────────────────────────┬─────────────────────────────────┘
                             ▼
                    trigger evaluation
                             ▼
                    severity classification
                             ▼
                    deduplication (fingerprint + cooldown)
                             ▼
                    review gate (severity ≥ threshold)
                             ▼
                    rate limiting + quiet hours
                             ▼
                    channel abstraction → in-app · push · SMS · email
                             ▼
                    delivery record + acknowledgement
```

---

## B2. Trigger Types

| Trigger | Condition | Severity source |
|---|---|---|
| **Official warning intersects geofence** | An active `MarineWarning` polygon (or named area) intersects | The warning's own class → quoted and attributed |
| **Cyclone cone intersects geofence** | Published forecast cone intersects within the horizon | `WARNING`/`CRITICAL` |
| **Safety threshold breach** | SAFETY verdict transitions to `UNFAVOURABLE`/`UNSAFE` inside the fence | Derived, ORCA-labelled |
| **Lightning proximity** | Lightning alert/strikes within the fence + buffer | Derived |
| **Fishing opportunity** (opt-in) | FISHING_SUITABILITY becomes `FAVOURABLE` with adequate confidence | `INFO`/`ADVISORY` |
| **Regulatory** | Geofence intersects a restricted area under a new boundary version | `ADVISORY` |
| **Data-availability** (operators/analysts only) | A P0 source has been unavailable beyond a threshold | `INFO` |

**Never triggered from a single missing input.** A trigger requires the domain's required
evidence; an alert that says "unsafe" without wave data is not sent — the subscriber
instead receives, at most, a data-availability notice if they have opted in.

---

## B3. Severity

| Severity | Meaning | Typical trigger |
|---|---|---|
| `INFO` | Situational, no action | Opportunity, data notice |
| `ADVISORY` | Awareness | Conditions approaching thresholds |
| `WATCH` | Conditions may deteriorate | Forecast breach at longer lead |
| `WARNING` | Action recommended | Safety threshold breach, or an official warning intersecting |
| `CRITICAL` | Immediate | Cyclone cone intersection, or an official warning of the highest class |

Severity derived from an **official warning** inherits the issuing authority's class and
is presented as quoted official content. Severity derived from ORCA's own thresholds is
labelled ORCA-derived, and the threshold set and its validation status are named.

---

## B4. Deduplication

```
fingerprint = sha256(subscription_id · trigger_type · domain · severity ·
                     governing_evidence_key · validity_window_bucket)
```

| Rule | Detail |
|---|---|
| Identical fingerprint within the cooldown | Suppressed; the existing alert's `last_seen` is updated |
| Cooldown | Per severity: `INFO` 24 h · `ADVISORY` 12 h · `WATCH` 6 h · `WARNING` 3 h · `CRITICAL` 1 h (initial engineering parameters) |
| Escalation always delivers | A severity increase bypasses the cooldown |
| De-escalation | An "all clear" is sent once, only if a `WARNING`/`CRITICAL` was previously delivered |
| Warning updates | A re-issued official bulletin with a new identifier is a new alert; an unchanged bulletin is not re-sent |
| Storage | `UNIQUE (subscription_id, dedupe_fingerprint, valid_from)` (`09_DATABASE_SPEC.md` §5) |

---

## B5. Geofencing

Evaluation rules are specified in `11_GEOSPATIAL_REASONING_SPEC.md` §12. Alert-specific
rules:

| Rule | Detail |
|---|---|
| Aggregation | Safety triggers use the **worst** value inside the fence; opportunity triggers use `area_fraction_above_threshold` |
| Partial overlap | Triggers, and the alert states the overlap fraction |
| Ambiguous warning areas | An unresolved area (`AMBIGUOUS_AREA`) triggers subscriptions in the named region with the area description quoted; no polygon is fabricated |
| Size limits | Max geofence area and max 20 subscriptions per user (initial parameters) to bound evaluation cost |
| Position-based fences (P1) | Requires user-supplied position; subject to the location-privacy rules in `14` |

---

## B6. Rate Limiting and Quiet Hours

| Control | Default (initial engineering parameters) |
|---|---|
| Max alerts per subscription per day | 6 |
| Max alerts per user per day (all subscriptions) | 12 |
| Quiet hours | User-configured, e.g. 22:00–05:00 IST |
| Quiet-hours override | `CRITICAL` only — a cyclone alert is delivered at 03:00 |
| Burst protection | If > N subscriptions would fire on the same governing evidence, the batch is grouped into one operator review before fan-out |
| Channel backoff | Delivery failures retry with backoff; permanent failure is recorded and surfaced in-app |

---

## B7. Channel Abstraction

```python
class AlertChannel(Protocol):
    name: str
    def deliver(self, alert: Alert, recipient: Recipient) -> DeliveryResult: ...
    def supports(self, severity: str, language: str) -> bool: ...
```

| Channel | MVP | Notes |
|---|---|---|
| `in_app` | ✅ | Alert inbox; always the system of record |
| `web_push` | Should-have | Browser push |
| `sms` | Deferred | Provider-dependent; regulatory and cost considerations; message is truncated to the verdict + limiting factor + validity + "open ORCA for details" |
| `email` | Deferred | Full content with evidence links |
| `voice` | FUTURE | Depends on the TTS path |

**Rule.** Every channel delivers the same verdict and the same disclaimer. A truncated SMS
must never drop the disclaimer or imply official status; the truncation policy keeps
verdict + limiting factor + validity + non-official label and drops detail, in that order.

Delivery outcomes are recorded per alert (`alerts.delivery_status`), so "sent" is a fact,
not an assumption.

---

## B8. Human Review of Alerts

Alerts use the same review gate as interactive runs, with a stricter policy:

| Situation | Disposition |
|---|---|
| Alert derived from a quoted official warning | `AUTO_RELEASE` — ORCA is relaying an authority, not judging |
| ORCA-derived `WARNING` or `CRITICAL` | `REVIEW_REQUIRED` before broadcast |
| Fan-out above the configured size | `REVIEW_REQUIRED` regardless of severity |
| `INFO`/`ADVISORY` | `AUTO_RELEASE` |
| Review times out | **Not sent.** An un-reviewed derived warning is never dispatched; the failure is recorded and escalated to operators |

---

## B9. Alert Content Rules

Every alert contains:

1. **Verdict and limiting factor** — first line.
2. **Validity window** in local time.
3. **Attribution** — quoted official text (verbatim, attributed) *or* an explicit
   ORCA-derived label with the threshold set named.
4. **Evidence link** back to the run.
5. **Disclaimer** — reviewed string, not model output.
6. **Language** — the subscription's language, subject to the same hard gates as
   interactive answers (§A8).

```
⚠ WARNING · Kochi grounds · 03 Sep 05:30–09:30 IST

Sea state is expected to be unsafe for small craft.
Limiting factor: significant wave height up to 3.1 m.

Based on: CMEMS wave forecast (retrieved 02 Sep 16:34 IST) and NOAA wave forecast.
The two forecasts disagree (2.4 m vs 3.1 m); the more adverse value was used.
Threshold set: small_craft_v0.1 (not yet scientifically validated).

This is an ORCA assessment, not an official advisory.
Follow IMD and INCOIS bulletins.                              [open in ORCA]
```

---

## B10. Alert Failure Behaviour

| Failure | Behaviour |
|---|---|
| Source unavailable during evaluation | No alert is generated from missing data. If a previously delivered `WARNING` can no longer be confirmed, subscribers receive a "conditions could not be re-checked" notice (once), not an all-clear |
| Assessment `INSUFFICIENT_EVIDENCE` | No alert |
| Review timeout | Not sent; operators notified |
| Channel failure | Retry with backoff; the in-app record always exists |
| Scheduler outage | Missed windows are recorded; on recovery, only still-valid conditions alert (no replay of expired windows) |
| Duplicate suppression bug suspected | Fingerprints are logged so suppression is auditable |

**The alerting system fails silent-negative, never silent-positive.** It will miss rather
than fabricate — and every miss caused by a source failure is visible in the run record
and the source-health endpoint.

---

## B11. Accessibility

| Requirement | Implementation |
|---|---|
| Never colour alone | Every severity carries an icon and a text label in all channels |
| Screen readers | Alert cards are ARIA live regions with severity announced first |
| Plain language | Fisher-facing alerts avoid technical register; the technical detail sits behind "details" |
| Contrast | WCAG 2.1 AA for all severity styling |
| Text scaling | Alert cards remain legible at 200 % scaling |
| Reduced motion | No animated severity indicators when `prefers-reduced-motion` is set |
| Low-literacy support | Icon + colour + short sentence structure; audio is FUTURE |
