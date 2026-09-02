# ORCA — Frontend Design Specification

**Document:** 02 of 30 · **Version:** 1.0 · **Date:** 2026-09-02
**Status:** PROPOSED — IMPLEMENTATION REQUIRED

---

## 1. Design Premise

ORCA's frontend is an **operational conversational marine intelligence interface**, not a
generic chatbot and not a static dashboard.

Three properties distinguish it:

1. **Conversation and map are one workspace.** Every answer mutates map state; every map
   interaction can seed the next question. Neither is decorative.
2. **Evidence is a first-class surface.** Any statement can be expanded into the sources,
   datasets, times and derivations behind it. The evidence panel is not a debug view.
3. **Uncertainty and failure are rendered, never hidden.** Missing sources, stale data,
   conflicts and low confidence appear in the UI with the same visual weight as results.

No visual branding is specified beyond what is functionally required. Colour is used for
**semantics** (severity, freshness, verdict), not decoration.

---

## 2. Information Architecture

```
ORCA
├── Session / Conversation
│   ├── Turn (user query)
│   └── Turn (ORCA answer)
│       ├── Answer narrative (language-localised)
│       ├── Assessment cards  ×4 domains
│       ├── Evidence references (inline citation chips)
│       ├── Reasoning summary (concise, non-CoT)
│       └── Run status strip (tools used / failed / fallback)
├── Map workspace
│   ├── Basemap
│   ├── Query-scoped layers (PFZ, SST, Chl, waves, currents, wind)
│   ├── Context layers (EEZ, MPA, restricted, geofences)
│   ├── Warning overlays (cyclone track/cone, warning areas)
│   ├── Route corridor (P1)
│   └── Temporal control (validity time scrubber)
├── Evidence panel
│   ├── Claim → evidence tree
│   ├── Provenance record viewer
│   ├── Derivation viewer (inputs + method + version)
│   └── Conflict viewer
├── Alerts
│   ├── Alert inbox
│   ├── Subscriptions + geofence editor
│   └── Alert detail (triggering evidence)
├── Review queue  (role: reviewer/officer)
│   ├── Pending items
│   └── Approve / edit / reject with rationale
└── Settings
    ├── Language
    ├── Role / view profile
    ├── Units
    └── Data-freshness tolerance
```

---

## 3. Desktop Layout

Three-pane workspace, 1440 px reference width.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ TOP BAR  ORCA │ session ▾ │ language ▾ │ role ▾ │ alerts ● 2 │ status: LIVE  │
├──────────────┬───────────────────────────────────────┬───────────────────────┤
│              │                                       │                       │
│ CONVERSATION │              MAP                      │  EVIDENCE             │
│  (380–460px) │            (fluid)                    │  (360–420px,          │
│              │                                       │   collapsible)        │
│ ┌──────────┐ │  ┌─────────────────────────────────┐  │ ┌───────────────────┐ │
│ │ user     │ │  │                                 │  │ │ Claim             │ │
│ │ turn     │ │  │   basemap + layers              │  │ │  └ Evidence #1    │ │
│ └──────────┘ │  │                                 │  │ │     source/dataset│ │
│ ┌──────────┐ │  │   ┌───────────────┐             │  │ │     valid_time    │ │
│ │ SAFETY   │ │  │   │ layer control │             │  │ │     retrieved_at  │ │
│ │ card     │ │  │   └───────────────┘             │  │ │     quality       │ │
│ ├──────────┤ │  │                                 │  │ │  └ Evidence #2    │ │
│ │ FISHING  │ │  │   [legend]        [scale bar]   │  │ └───────────────────┘ │
│ │ card     │ │  └─────────────────────────────────┘  │ ┌───────────────────┐ │
│ ├──────────┤ │  ┌─────────────────────────────────┐  │ │ CONFLICT (1)      │ │
│ │ REGULAT. │ │  │ ◀ time scrubber ▶  03 Sep 06:00 │  │ │ Hs: 2.4 vs 3.1 m  │ │
│ │ card     │ │  └─────────────────────────────────┘  │ └───────────────────┘ │
│ └──────────┘ │                                       │                       │
│ [ input… ]   │                                       │                       │
└──────────────┴───────────────────────────────────────┴───────────────────────┘
│ RUN STRIP  plan ✓ · retrieve 7/9 · 1 fallback · 1 auth-required · 6.4 s      │
└──────────────────────────────────────────────────────────────────────────────┘
```

Behaviour:

- The evidence panel opens contextually when a citation chip is clicked, and can be
  pinned open.
- The map is never blank while an answer is present: at minimum it shows the resolved
  query location and its analysis extent.
- The run strip is always visible during and after execution.

---

## 4. Mobile Layout

Primary target: field use by fishers on low-cost Android devices, intermittent
connectivity, bright sunlight, one-handed use.

```
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│ ORCA        ⚠2  ☰     │   │  ← Map                │   │  ← Evidence           │
├───────────────────────┤   ├───────────────────────┤   ├───────────────────────┤
│ ┌───────────────────┐ │   │                       │   │ Claim: "Hs 2.4 m"     │
│ │ SAFETY  ⚠ MARGINAL│ │   │      map fills        │   │ ─────────────────     │
│ │ waves 2.4 m …     │ │   │      viewport         │   │ CMEMS · dataset id    │
│ └───────────────────┘ │   │                       │   │ valid 03 Sep 06:00Z   │
│ ┌───────────────────┐ │   │  ┌─────────────────┐  │   │ retrieved 05:12Z      │
│ │ FISHING ✓ GOOD    │ │   │  │ layers  ▾       │  │   │ forecast · 1/12°      │
│ └───────────────────┘ │   │  └─────────────────┘  │   │ quality: nominal      │
│                       │   │                       │   │                       │
│ Answer text…          │   │  [legend]             │   │ [open source page]    │
│ [why?] [evidence]     │   │  ◀ time ▶             │   │                       │
├───────────────────────┤   ├───────────────────────┤   ├───────────────────────┤
│ 💬 Ask…          🎙   │   │ [back to answer]      │   │ [back to answer]      │
└───────────────────────┘   └───────────────────────┘   └───────────────────────┘
   Conversation-first          Map sheet (swipe up)        Evidence sheet
```

Rules:

- **Verdict first.** Assessment cards appear above prose. A user must get safety status
  in under one second of reading.
- Map and evidence are bottom sheets, not separate pages; state is preserved on dismiss.
- All interactive targets ≥ 44 × 44 px.
- Text remains legible at high ambient brightness (high-contrast palette, no thin
  weights below 14 px).
- Degraded-network mode: last successful answer and its map snapshot remain viewable
  with an explicit "cached, retrieved at …" banner.

---

## 5. Conversation Interface

### 5.1 Turn structure

| Element | Content |
|---|---|
| User turn | Raw text, detected language badge, resolved location/time chips (editable) |
| Resolution chips | `📍 Kochi (9.93 N, 76.26 E)` `🕑 03 Sep 05:30–09:30 IST` — clicking re-opens resolution |
| Progress stream | Live node/tool events while the run executes (see §5.2) |
| Assessment cards | One per applicable domain |
| Narrative | Language-localised prose with inline citation chips |
| Reasoning summary | 1–3 sentences: what was checked and what drove the verdict |
| Run strip | Tools attempted/succeeded/failed, fallbacks, elapsed time |
| Actions | `Why?` · `Show evidence` · `Show on map` · `Ask follow-up` · `Report an issue` |

### 5.2 Streamed progress (WebSocket)

```
● Understanding your question…                       (intent_context)
● Planning: 7 data requests                          (plan)
  ├ ✓ marine warnings          IMD             0.6 s
  ├ ✓ wave conditions          CMEMS           1.9 s
  ├ ✓ sea surface temperature  INCOIS ERDDAP   1.2 s
  ├ ✓ chlorophyll              INCOIS ERDDAP   1.4 s
  ├ ⚠ PFZ                      raster only     2.1 s
  ├ ✗ lightning                AUTH_REQUIRED   0.2 s
  └ ✓ boundaries               MarineRegions   0.4 s
● Aligning data in space and time…                   (geo_reason)
● Assessing safety and fishing suitability…          (assess_*)
● Composing answer…                                  (report)
```

The progress stream shows **tool and node events only**. It never streams model
chain-of-thought.

### 5.3 Multi-turn behaviour

- Location and time context carry forward; the UI shows the inherited context chips on
  the new turn and allows one-tap clearing.
- Follow-ups like "what about Thursday?" mutate only the time context and re-run.
- Disambiguation is a first-class turn type: when the Planner cannot resolve a location
  or time, ORCA asks one specific question with tappable options rather than guessing.

---

## 6. Map Interface

**Library:** MapLibre GL JS (vector basemap + GeoJSON sources + raster tile sources).

| Concern | Specification |
|---|---|
| Projection | Web Mercator display (EPSG:3857); all data delivered in EPSG:4326 |
| Basemap | Neutral, low-saturation; land muted so ocean layers dominate |
| Bathymetry/coastline | Optional context layer |
| Query extent | Analysis bbox drawn as a thin dashed outline, always present |
| Point of interest | Resolved query location as a distinct marker with coordinate readout |
| Interaction | Pan/zoom, click-to-inspect (returns values at point with provenance), draw bbox/polygon to scope a query, long-press to set location |
| Readout | Cursor position lat/lon always visible; scale bar mandatory |
| Legend | Every active data layer contributes a legend entry with units and value range |
| Attribution | Source attribution for each active layer is permanently visible |

### 6.1 Layer inventory

| Layer | Type | Source binding | Default |
|---|---|---|---|
| PFZ advisory | vector (if available) or raster | `get_pfz` | on for fishing intents |
| SST | raster (colour-mapped grid) | `get_sst` | on |
| SST anomaly | raster (diverging scale) | `get_sst` derived | off |
| Chlorophyll-a | raster (log scale) | `get_chlorophyll` | on for fishing intents |
| Significant wave height | raster | `get_wave_conditions` | on for safety intents |
| Surface currents | vector field (arrows/streamlines) | `get_currents` | off |
| Wind | vector field (barbs) | `get_weather` | off |
| Marine warning areas | vector polygons | `get_marine_warnings` | on if any active |
| Cyclone track + cone | vector line + polygon | `get_cyclone_track` | on if any active |
| Lightning | point cluster | `get_lightning` | on if any |
| EEZ / boundaries | vector | `get_maritime_boundaries` | on |
| MPA / restricted | vector | `get_maritime_boundaries` | on |
| Geofences | vector | user subscriptions | off |
| Route corridor (P1) | vector line + buffer | `get_route_advisory` | contextual |

### 6.2 Layer control

```
┌──────────────────────────────────┐
│ LAYERS                      [×]  │
├──────────────────────────────────┤
│ ▣ PFZ advisory        ⓘ RASTER   │   ← representation badge
│    INCOIS · 03 Sep · ●fresh      │   ← source + validity + freshness dot
│    opacity ▓▓▓▓▓▓░░░░  60%       │
├──────────────────────────────────┤
│ ▣ Sea surface temp     ⓘ GRID    │
│    INCOIS ERDDAP · 02 Sep ●aging │
│    opacity ▓▓▓▓▓▓▓▓░░  80%       │
├──────────────────────────────────┤
│ ▢ Chlorophyll-a        ⓘ GRID    │
│    INCOIS ERDDAP · 01 Sep ●stale │
├──────────────────────────────────┤
│ ▣ Wave height          ⓘ GRID    │
│    CMEMS ⇄ fallback    ●fresh    │   ← fallback marker
├──────────────────────────────────┤
│ ✗ Lightning         AUTH_REQUIRED│   ← unavailable layer stays listed
└──────────────────────────────────┘
```

Unavailable layers are **listed and greyed with their reason**, never silently omitted.

---

## 7. Evidence / Provenance Panel

Three levels of depth:

**L1 — Citation chip** (inline in narrative): `[INCOIS ERDDAP · 02 Sep]`. Hover/tap →
minicard with parameter, value, unit, valid time, source.

**L2 — Evidence list** (panel): every evidence item supporting the selected claim.

```
CLAIM  "Significant wave height reaches 2.4 m around 06:00 IST."
├─ EVIDENCE E-114                                    [forecast]
│    parameter          significant_wave_height
│    value / unit       2.4 m
│    location           9.85 N, 76.10 E (nearest grid node)
│    valid_time         2026-09-03T00:30Z
│    source / dataset   CMEMS / <dataset_id>
│    retrieved_at       2026-09-02T11:04Z
│    resolution         1/12° · 3-hourly
│    quality            nominal
│    fallback_used      false
└─ [view raw normalized record]  [view source reference]
```

**L3 — Derivation view** (for `value_kind: derived`): shows the input evidence IDs, the
method identifier and version, and the parameters, so the number can be recomputed.

```
DERIVED  sst_anomaly = +1.2 °C
  method     anomaly_vs_climatology_window  v1.2
  inputs     E-101 (SST field, INCOIS ERDDAP)
             E-102 (10-day mean, computed)
  params     window=10d, mask=cloud_flagged, agg=mean
```

**Conflict view**: when two authoritative sources materially disagree, both are shown
side-by-side with the delta, the tolerance that was exceeded, and the effect on the
assessment. The UI never presents a silently chosen winner.

---

## 8. Recommendation Cards

One card per assessment domain. Cards are independent and may disagree.

```
┌────────────────────────────────────────────────────────────┐
│ ⚠  MARINE SAFETY                       MARGINAL            │
│                                        confidence: medium  │
├────────────────────────────────────────────────────────────┤
│ • Significant wave height 2.4 m at 06:00 IST   [CMEMS]     │
│ • Wind 22 kt from W                            [IMD]       │
│ • No active fishermen's warning                [IMD]       │
│ • Lightning data unavailable (auth required)   ⓘ           │
├────────────────────────────────────────────────────────────┤
│ Basis: threshold set "small_craft_v0.1"  ⓘ not yet         │
│ scientifically validated                                   │
│                             [why?]  [evidence]  [on map]   │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ ✓  FISHING SUITABILITY                 FAVOURABLE          │
│                                        confidence: medium  │
├────────────────────────────────────────────────────────────┤
│ • PFZ advisory intersects query area (raster) [INCOIS]     │
│ • Chlorophyll-a 0.8 mg/m³, above local median [ERDDAP]     │
│ • SST 28.6 °C, anomaly +0.4 °C                [derived]    │
└────────────────────────────────────────────────────────────┘
```

Verdict vocabulary (fixed, from `12_RISK_AND_RECOMMENDATION_SPEC.md`):
`FAVOURABLE · MARGINAL · UNFAVOURABLE · UNSAFE · INSUFFICIENT_EVIDENCE`, plus
regulatory `PERMITTED · RESTRICTED · PROHIBITED · UNKNOWN`.

**Combination rule shown to the user:** the interface never averages cards. When domains
disagree, the narrative leads with the constraint: *"Fishing conditions look good, but
sea state is marginal — the limiting factor is wave height, not fish availability."*

---

## 9. Warning and Alert Presentation

Official warnings are visually distinct from ORCA-derived assessments.

```
╔════════════════════════════════════════════════════════════╗
║ OFFICIAL WARNING — IMD                                     ║
║ Fishermen's warning · issued 02 Sep 08:30 IST              ║
║ valid until 04 Sep 08:30 IST                               ║
║ ──────────────────────────────────────────────────────     ║
║ "<verbatim bulletin text as issued>"                       ║
║                                        [source bulletin ↗] ║
╚════════════════════════════════════════════════════════════╝
        ▲ double border + "OFFICIAL" label = quoted authority

┌────────────────────────────────────────────────────────────┐
│ ORCA ASSESSMENT (derived — not an official advisory)       │
└────────────────────────────────────────────────────────────┘
        ▲ single border + explicit derived label
```

Severity styling: `INFO` neutral · `ADVISORY` blue · `WATCH` amber ·
`WARNING` orange · `CRITICAL` red, each additionally carrying an icon and a text label
(never colour alone — see §15 Accessibility).

---

## 10. Data Freshness Indicators

Freshness is computed per layer/evidence item from `valid_time`, `retrieved_at` and the
product's expected cadence.

| State | Rule (per-parameter policy) | Presentation |
|---|---|---|
| `FRESH` | within expected cadence | ● solid, no annotation |
| `AGING` | 1–2 cadence intervals old | ◐ half, "as of <time>" |
| `STALE` | beyond staleness policy | ◯ hollow + amber "STALE — <age>" |
| `EXPIRED` | past validity, unusable | ✗ + layer excluded from assessment, listed as excluded |

Every timestamp is displayed in **both** IST (primary, user-facing) and UTC (secondary,
in the evidence panel). Relative time ("2 hours ago") is always accompanied by the
absolute time.

---

## 11. Source Indicators

- Every layer, card bullet and evidence item names its source.
- A **fallback badge** `⇄ fallback` appears whenever `fallback_used = true`, with the
  reason on hover ("INCOIS ERDDAP unreachable → CMEMS").
- An **external badge** marks non-Indian-authority sources (CMEMS, NOAA, Argo,
  MarineRegions).
- A **representation badge** marks `RASTER` vs `VECTOR` vs `POINT` vs `BULLETIN`, so a
  raster-derived PFZ statement is never mistaken for polygon geometry.

---

## 12. Uncertainty Presentation

ORCA renders four distinct uncertainty types, never merged:

| Type | Rendering |
|---|---|
| **Value uncertainty** (source-supplied spread/error) | ± band on numbers, shaded band on charts |
| **Spatial uncertainty** (coarse grid, nearest-node distance) | "nearest grid node 6 km away" annotation |
| **Temporal uncertainty** (forecast lead time, staleness) | lead-time chip "+18 h forecast" |
| **Evidence sufficiency** (missing inputs) | explicit list: "Not evaluated: lightning (auth required)" |

Confidence per assessment is a three-level qualitative label (`low`/`medium`/`high`) with
a tooltip listing exactly which factors reduced it. No spurious precision (no "87.3 %
confidence") is displayed anywhere.

---

## 13. Route Visualisation (P1)

```
   Kochi ●───────────────────────────────────● Kavaratti
          ░░░░▓▓▓▓████▓▓▓▓░░░░░░░░░░░░░░░░░░
          └── corridor buffer, coloured by worst-domain verdict per segment

   segment table:
   ┌──────┬───────────┬──────────┬──────────────────────────┐
   │ seg  │ Hs (m)    │ verdict  │ limiting factor          │
   ├──────┼───────────┼──────────┼──────────────────────────┤
   │ 1    │ 1.6       │ FAVOURABLE│ —                       │
   │ 2    │ 2.9       │ MARGINAL │ wave height              │
   │ 3    │ 3.6       │ UNSAFE   │ wave height + swell      │
   └──────┴───────────┴──────────┴──────────────────────────┘
```

Route output always carries the disclaimer that it is advisory context and not a
navigational route; boundary crossings along the corridor are flagged separately.

---

## 14. PFZ Visualisation

Three mutually exclusive presentations, chosen by what the tool actually returned:

| Tool result | Presentation | Label |
|---|---|---|
| Vector geometry available | Polygons with attributes, clickable | `PFZ · VECTOR · INCOIS` |
| `RASTER_ONLY` | Rendered raster overlay, no polygon interaction, no area computation | `PFZ · RASTER (no geometry) · INCOIS` |
| `NO_DATA` / `SOURCE_UNAVAILABLE` | Layer listed as unavailable with reason; fishing card notes the gap | `PFZ · unavailable` |

The UI must make it impossible to mistake case 2 for case 1: point-in-polygon questions
are disabled and the card says "PFZ shown as imagery; exact boundaries not available".

---

## 15. Temporal Controls

- **Validity scrubber** — moves the analysis time within the query window; layers
  re-render at the selected valid time; the assessment cards are recomputed only when the
  user commits (explicit "re-assess at this time" action), so the displayed verdict never
  silently desynchronises from the narrative.
- **Lead-time indicator** — shows forecast lead relative to now.
- **History mode** — for retrospective queries, a date-range control with a play control
  over daily composites.
- **Time zone** — IST primary; UTC shown in evidence.

---

## 16. Multilingual Interaction

- Language selector in the top bar; default = detected input language.
- The answer, assessment verdicts, severity labels and UI chrome are localised; **numbers,
  units, coordinates, dataset identifiers and quoted official bulletin text are not
  translated**. Quoted official text is always shown in its issued language, with an
  optional clearly-labelled translation beneath it.
- Right-to-left is not required for the target languages but the layout uses logical
  properties so it is not precluded.
- Indic script rendering requires a font stack with Noto Sans (Malayalam, Devanagari,
  Tamil, Telugu, Bengali, Gujarati, Odia, Kannada) fallbacks; line-height is increased for
  Indic scripts to avoid clipping.
- Voice input (`🎙`) is present in the mobile layout as a FUTURE capability and is hidden
  unless the feature flag is enabled.

---

## 17. Accessibility

- WCAG 2.1 AA contrast targets for all text and semantic colour.
- **Never colour alone**: every severity/verdict/freshness state carries an icon and a
  text label.
- Full keyboard operability including map pan/zoom, layer toggles and the evidence tree.
- ARIA live region announces run progress and the final verdict.
- The map has a mandatory non-visual equivalent: a structured text summary of what is
  displayed (extent, layers, key values), reachable via "describe this map".
- Respects `prefers-reduced-motion` (no animated streamlines when set).
- Minimum body text 16 px on mobile; user text scaling to 200 % must not break layout.

---

## 18. Role-Specific Views

| Role | Default landing | Emphasis | Extra affordances |
|---|---|---|---|
| `fisher` | Conversation (mobile) | Safety card, PFZ, plain language | Voice (future), simplified units, share to WhatsApp-style export |
| `operator` | Split conversation + map | Waves, wind, warnings, temporal control | Multi-location watchlist |
| `officer` | Warning-first workspace | Cyclone, warnings, exposure, geofences | Review queue, broadcast (gated) |
| `analyst` | Map + evidence | Raw fields, anomalies, conflicts | Dataset inspector, export (GeoJSON/CSV/NetCDF ref) |
| `reviewer` | Review queue | Pending high-impact outputs | Approve/edit/reject |

Role changes the default layout and emphasis only; it never changes the underlying
evidence or hides provenance.

---

## 19. Loading, Error and Empty States

| State | Presentation | Rule |
|---|---|---|
| Run in progress | Streamed node/tool checklist (§5.2), skeletons for cards | Never a bare spinner |
| Partial success | Answer rendered with an explicit "not evaluated" list | Always name what is missing and why |
| Tool failure | Inline chip with canonical code + plain-language gloss ("IMD requires credentials — warnings not checked") | Code is always shown to analyst role |
| All sources failed | No recommendation. Explicit statement of what could not be reached + retry | Never fabricate a verdict |
| No data for the area/time | "No data in this area for this time" + suggested nearest available extent/time | Distinguish `NO_DATA` from `SOURCE_UNAVAILABLE` in the copy |
| No active warning | Positive statement: "No active marine warning found for this area at this time (IMD, checked 11:04 IST)" | `NO_ACTIVE_WARNING` is a result, not an error |
| Conflict | Conflict banner on the affected card + conflict entry in evidence panel | Both values shown |
| Stale data used | Amber banner: "Using data from <time> — older than expected cadence" | Assessment confidence lowered visibly |
| Session offline | Cached-answer banner with retrieval time; input disabled with explanation | Never present cache as live |
| Empty session | Suggested representative queries per role, in the user's language | |

---

## 20. Human-Review Controls (reviewer/officer roles)

```
┌───────────────────────────────────────────────────────────────┐
│ REVIEW QUEUE (3)                                              │
├───────────────────────────────────────────────────────────────┤
│ ⚠ RUN r-8f21 · cyclone exposure · UNSAFE · conf: low          │
│   trigger: unresolved conflict on Hs + safety verdict UNSAFE  │
│   [open]                                                      │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ REVIEW  r-8f21                                                │
│ ┌───────────────────────────────────────────────────────────┐ │
│ │ Proposed answer (read-only)                               │ │
│ │ Assessments · Evidence · Conflicts · Run trace            │ │
│ └───────────────────────────────────────────────────────────┘ │
│ Reviewer action:  ( ) approve  ( ) edit  ( ) reject           │
│ Rationale (required): [__________________________________]    │
│ [submit]   — recorded in audit log and attached to provenance │
└───────────────────────────────────────────────────────────────┘
```

Delivered answers that passed through review carry a visible
`Reviewed by <role> at <time>` marker. Edits are diffed against the proposed answer and
both versions are retained.

---

## 21. Responsive Behaviour

| Breakpoint | Layout |
|---|---|
| ≥ 1280 px | Three panes (conversation / map / evidence) |
| 1024–1279 px | Two panes; evidence becomes an overlay drawer |
| 768–1023 px | Conversation primary; map as a resizable top panel |
| < 768 px | Single column; map and evidence as bottom sheets |

The map never falls below 240 px height when displayed. On mobile, entering map mode
pauses conversation autoscroll.

---

## 22. Component Inventory

| Component | Responsibility | Key props / state |
|---|---|---|
| `AppShell` | Layout, role, language, breakpoint | role, locale, panes |
| `SessionList` | Session switching | sessions[] |
| `ConversationPane` | Turn list, input, autoscroll | turns[], streaming |
| `QueryInput` | Text/voice input, language badge | value, detectedLang |
| `ContextChips` | Resolved location/time, editable | location, timeWindow |
| `RunProgress` | Streamed node/tool events | events[] |
| `AssessmentCard` | One domain verdict + drivers | domain, verdict, confidence, evidenceRefs |
| `AnswerNarrative` | Localised prose + citation chips | markdown, citations[] |
| `CitationChip` | L1 evidence affordance | evidenceId |
| `ReasoningSummary` | Concise non-CoT summary | text |
| `RunStrip` | Tool tally, fallbacks, timing | runStats |
| `MapCanvas` | MapLibre instance, sources/layers | layers[], extent, validTime |
| `LayerControl` | Toggle, opacity, source/freshness badges | layers[] |
| `MapLegend` | Per-layer legend + units | activeLayers[] |
| `TimeScrubber` | Validity time control | window, validTime |
| `FeatureInspector` | Click-to-inspect values + provenance | point, values[] |
| `EvidencePanel` | Claim→evidence tree | claimId |
| `EvidenceRecord` | L2 provenance record | provenance |
| `DerivationView` | L3 method + inputs | derivation |
| `ConflictView` | Side-by-side disagreement | conflict |
| `OfficialWarningCard` | Quoted authority bulletin | warning |
| `AlertInbox` / `AlertDetail` | Alerts + triggering evidence | alerts[] |
| `GeofenceEditor` | Draw/edit subscription geometry | geometry, thresholds |
| `ReviewQueue` / `ReviewDetail` | Human-review workflow | pending[], decision |
| `FreshnessDot` | Freshness state | state, validTime, retrievedAt |
| `SourceBadge` | Source, external, fallback, representation | source, flags |
| `EmptyState` / `ErrorState` | Canonical code → user copy | code, detail |
| `LocaleProvider` | i18n, number/date formatting | locale |

---

## 23. Frontend ↔ Backend Interaction Model

```
POST /v1/sessions                       → session_id
POST /v1/sessions/{id}/queries          → { run_id, status: "accepted" }
WS   /v1/runs/{run_id}/events           → streamed run events
GET  /v1/runs/{run_id}                  → final answer + assessments + evidence refs
GET  /v1/runs/{run_id}/evidence         → evidence records
GET  /v1/runs/{run_id}/layers           → layer descriptors (GeoJSON URLs / tile URLs)
GET  /v1/geo/features/{layer_id}        → GeoJSON
GET  /v1/geo/tiles/{layer_id}/{z}/{x}/{y}.png → raster tiles
POST /v1/runs/{run_id}/review           → reviewer decision
GET  /v1/alerts                         → alert inbox
```

Contract rules:

1. **The frontend never talks to an external source directly.** All map layers are served
   through ORCA endpoints so that provenance, attribution and caching stay under control.
2. **Evidence is referenced, not duplicated.** Answers carry `evidence_ids`; records are
   fetched on demand.
3. **Streaming events are structural** (node started/finished, tool result summaries).
   Model chain-of-thought is never sent to the client.
4. **Every layer descriptor carries provenance** — source, dataset, valid_time,
   retrieved_at, representation, fallback flag — so the layer control can render badges
   without extra calls.
5. **Idempotency**: query submission accepts an `Idempotency-Key` so a retried submit does
   not create a duplicate run.

Full endpoint definitions: `08_API_SPEC.md`.

---

## 24. Frontend Non-Goals

- No client-side scientific computation. The frontend renders values; it does not derive
  them.
- No client-side threshold logic. Verdicts arrive from the backend.
- No offline model inference.
- No marketing-oriented animation or decorative dashboarding.
