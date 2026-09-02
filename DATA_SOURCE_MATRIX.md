# ORCA --- Data Source Matrix

**Project:** ORCA --- Marine EcOsystem Reasoning with Collaborative
Agents\
**SIH Problem:** SIH26176\
**Version:** 0.1\
**Date:** September 2026\
**Status:** Working baseline

## 1. Purpose

This document defines the external data/resources ORCA may use for
marine retrieval, analysis, reasoning and visualization.

A source being a government portal does not imply that its underlying
data is programmatically accessible. Every source therefore has both an
access classification and a verification status.

## 2. Classification

  -----------------------------------------------------------------------
  Class                               Meaning
  ----------------------------------- -----------------------------------
  A                                   Direct programmatic access
                                      identified; endpoint testing
                                      required

  B                                   Programmatic access requires
                                      registration/authentication or
                                      conditions

  C                                   Download/file access; unsuitable as
                                      a live API

  D                                   Human-facing portal; no reliable
                                      programmatic interface identified

  E                                   Access unclear; requires
                                      verification

  F                                   Not realistically useful as an ORCA
                                      dependency
  -----------------------------------------------------------------------

  -----------------------------------------------------------------------
  Status                              Meaning
  ----------------------------------- -----------------------------------
  🟢                                  Access mechanism sufficiently
                                      established; proceed to integration
                                      test

  🟡                                  Capability identified;
                                      endpoint/dataset testing remains

  🔴                                  Do not make a core runtime
                                      dependency
  -----------------------------------------------------------------------

## 3. Tier 1 --- Core Indian Government Sources

### IMD --- India Meteorological Department

  Field      Value
  ---------- ---------------------------------------------------------
  Role       Weather, marine weather and severe-weather intelligence
  Access     REST API
  Auth       Registration/access conditions require testing
  Format     JSON
  Class      B
  Status     🟡
  Priority   P0

Relevant capabilities: fishermen warnings, coastal/sea bulletins, port
warnings, cyclone tracks, cyclone wind polygons, cyclone cone,
lightning, current weather and multi-day warnings.

**ORCA uses:** marine safety, fishing safety, cyclone intelligence,
lightning alerts, weather-aware route planning.

**Required verification:** authentication, response schemas, timestamps,
geographic fields, rate limits, failure behavior and current-data
retrieval.

### INCOIS --- ERDDAP

  Field      Value
  ---------- -----------------------------------------------------------
  Role       Oceanographic data access
  Access     ERDDAP REST/tableDAP/griddap interfaces
  Auth       Public datasets identified; verify per dataset
  Formats    CSV, JSON, GeoJSON, NetCDF and related scientific formats
  Class      A
  Status     🟡
  Priority   P0

Candidate data: SST, chlorophyll/ocean colour, Argo, buoys, tide gauges,
current observations and other catalogue datasets.

**ORCA uses:** ocean-state analysis, spatial/temporal retrieval,
historical comparison, in-situ validation and evidence.

**Required verification:** exact dataset IDs, accessibility,
Indian-coast subsetting, time constraints, formats, variables, units and
coordinate conventions.

### INCOIS --- GeoServer / WMS

  Field      Value
  ---------- ---------------------------------
  Role       Geospatial ocean/fishing layers
  Access     OGC WMS; WFS must be tested
  Auth       Not confirmed
  Class      A/E
  Status     🟡
  Priority   P0

Candidate layers: PFZ, SST, chlorophyll and other exposed geospatial
layers.

**Critical question:** can ORCA obtain actual PFZ geometries/attributes,
rather than only rendered WMS imagery?

**Required verification:** GetCapabilities, layer enumeration, GetMap,
GetFeatureInfo, WFS availability, attributes and temporal behavior.

### INCOIS --- Ocean State Forecast / LAS

  Field      Value
  ---------- ------------------------------------------------------------
  Role       Ocean forecast
  Access     LAS/OPeNDAP or underlying machine-readable model interface
  Auth       Unclear
  Class      B/E
  Status     🟡
  Priority   P0

Candidate data: significant wave height, wave period, swell, wind,
currents and forecast time.

**Rule:** do not depend on a human-facing OSF/SARAT portal or image
scraping. Identify the underlying machine-readable data.

### MOSDAC / ISRO

  Field      Value
  ---------- --------------------------------------------
  Role       ISRO satellite ocean products
  Access     Data-download tooling / file or FTP access
  Auth       MOSDAC account for authenticated downloads
  Formats    HDF5, NetCDF and product-specific formats
  Class      B/C
  Status     🟡
  Priority   P1

Candidate products: OceanSat ocean colour, satellite SST and satellite
wind/scatterometer products.

**ORCA uses:** independent satellite evidence, SST/chlorophyll analysis
and cross-source validation.

**Implementation rule:** initially treat MOSDAC as an EO enhancement,
not a hard live-demo dependency. Pre-stage representative data if
acquisition latency makes live retrieval unsuitable.

## 4. Tier 2 --- Supporting Indian Sources

  ----------------------------------------------------------------------------------------------
  Source         Capability            Access                Class       Status      Priority
  -------------- --------------------- --------------------- ----------- ----------- -----------
  Bhuvan/NRSC    Basemaps/thematic     WMS/WMTS/API          A/B         🟡          P1
                 geospatial layers                                                   

  data.gov.in    Fisheries             REST API              B           🟡          P1
                 statistics/context                                                  

  NCSCM          Coastal/ecological    Portal/publications   D           🔴          P2
                 reference                                                           

  National       Nautical              Download/PDF/paid     C/F         🔴          P2
  Hydrographic   charts/notices        products                                      
  Office                                                                             

  NFDB           Fisheries             Website               F           🔴          ---
                 policy/publications                                                 
  ----------------------------------------------------------------------------------------------

Bhuvan should not be treated as the primary ocean-data backend unless a
specific marine layer is verified.

## 5. External Fallback / Supplementary Sources

  -----------------------------------------------------------------------
  Capability              Candidate               Role
  ----------------------- ----------------------- -----------------------
  Ocean forecast          CMEMS                   Fallback/support

  Weather/ocean model     NOAA                    Fallback/support

  EEZ/boundaries          MarineRegions or        Geofencing
                          equivalent              
                          authoritative GIS       

  Protected areas         UNEP-WCMC / Protected   Ecological/geofencing
                          Planet                  support

  Vessel activity         Global Fishing Watch    Future capability
  -----------------------------------------------------------------------

External sources should be explicitly identified as external in ORCA
provenance.

## 6. Capability Matrix

  -------------------------------------------------------------------------------------
  ORCA           Required data        Primary         Fallback/support   Priority
  capability                                                             
  -------------- -------------------- --------------- ------------------ --------------
  Fishing        PFZ, SST, Chl-a,     INCOIS + IMD    CMEMS/NOAA         P0
  suitability    weather, waves                                          

  Marine safety  Wind, waves, swell,  IMD + INCOIS    CMEMS/NOAA         P0
                 warnings                                                

  Cyclone        Track, cone, wind,   IMD             ---                P0
  intelligence   warnings                                                

  Lightning risk Lightning/warnings   IMD             ---                P0

  PFZ analysis   PFZ + SST + Chl-a    INCOIS          ---                P0

  Ocean          SST, currents,       INCOIS          CMEMS              P0
  conditions     waves, observations                                     

  Geospatial     Coordinates,         Bhuvan +        External GIS       P0
  reasoning      boundaries, map      boundary source                    
                 layers                                                  

  Route safety   Weather + ocean +    IMD + INCOIS    CMEMS/NOAA         P1
                 boundaries                                              

  Historical     Fisheries/ocean      data.gov.in +   External           P1
  analysis       history              datasets                           

  Ecological     SST/Chl + ecological INCOIS + NCSCM  External           P1/P2
  risk           layers                                                  

  Subsurface     T/S/BGC profiles     INCOIS ERDDAP   Global Argo        P2
  analysis                                                               
  -------------------------------------------------------------------------------------

## 7. Data Architecture Principle

ORCA should not expose individual government APIs directly to the
Planner or agents.

Use:

``` text
Source
  ↓
Source Adapter
  ↓
Normalized Data Object
  ↓
Capability Tool
  ↓
Agent
```

For example:

``` text
                    ORCA
                      |
              Capability Layer
                      |
       +--------------+--------------+
       |              |              |
   Weather        Ocean Data     Geospatial
       |              |              |
      IMD       INCOIS ERDDAP    INCOIS GeoServer
                    / LAS             Bhuvan
                       |
                    MOSDAC
                       |
               External fallbacks
```

This isolates authentication, parsing, retries, caching, source-specific
schemas and endpoint changes inside adapters.

## 8. Provenance Requirement

Every data value entering reasoning should retain, where available:

``` json
{
  "parameter": "sea_surface_temperature",
  "value": 28.4,
  "unit": "degC",
  "location": {},
  "valid_time": "",
  "source": "INCOIS",
  "dataset": "",
  "retrieved_at": "",
  "spatial_resolution": "",
  "temporal_resolution": "",
  "quality": "",
  "provenance": {}
}
```

The full canonical schema will be defined separately.

## 9. Failure/Fallback Principle

ORCA must distinguish:

-   source unavailable
-   dataset unavailable
-   stale data
-   no observations
-   conflicting sources
-   low-quality data
-   insufficient spatial coverage
-   insufficient temporal coverage

A fallback must never silently replace the primary source.

Example:

``` text
INCOIS unavailable
      ↓
CMEMS fallback
      ↓
Response metadata:
"Ocean-current data sourced from CMEMS
because INCOIS data was unavailable."
```

## 10. P0 Verification Checklist

### INCOIS ERDDAP

-   Retrieve catalogue
-   Identify exact SST, Chl-a, waves, currents and Argo datasets
-   Check public accessibility
-   Query Indian-coast bounding box
-   Test temporal subsetting
-   Test JSON/CSV/NetCDF
-   Record variables, units and coordinates

### INCOIS GeoServer

-   GetCapabilities
-   Enumerate layers
-   Test PFZ/SST/Chl GetMap
-   Test GetFeatureInfo
-   Test WFS
-   Determine whether PFZ geometries/attributes are retrievable

### IMD API

-   Test fishermen warning
-   Test coastal/sea bulletin
-   Test cyclone track
-   Test cyclone wind
-   Test cyclone cone
-   Test lightning
-   Establish authentication
-   Record response schemas and failure behavior

### INCOIS OSF/LAS

-   Identify machine-readable datasets
-   Test wave height
-   Test wave period/swell
-   Test wind
-   Test currents
-   Test forecast timestamps

### MOSDAC

-   Create/verify account
-   Test programmatic authentication
-   Identify exact datasets
-   Download representative OceanSat data
-   Test parsing
-   Record acquisition latency and file sizes

## 11. Known Unverified Areas

Do not state that an Indian government service does not exist merely
because it was not found.

Use:

> "No publicly documented/programmatically accessible source was
> identified during this audit."

This applies particularly to: - tidal prediction - public government
AIS/vessel tracking - operational HAB feeds - machine-readable
ecological sensitivity layers - some INCOIS forecast interfaces - PFZ
vector geometry access

## 12. Decision

### Core runtime candidates --- P0

1.  INCOIS ERDDAP
2.  INCOIS GeoServer
3.  IMD API
4.  INCOIS OSF/LAS

### Supporting integration --- P1

5.  MOSDAC
6.  Bhuvan/NRSC
7.  data.gov.in

### External fallback/support

8.  CMEMS
9.  NOAA
10. authoritative GIS boundary datasets

### Not runtime dependencies at present

NCSCM, NHO, NFDB and human-facing portals without machine-readable
access.

## 13. Next Artifact

After P0 endpoint testing, create:

**`04_ORCA_TOOL_CONTRACTS.md`**

It should define agent-callable capabilities such as:

``` text
get_weather()
get_marine_warnings()
get_cyclone_track()
get_lightning()
get_pfZ()
get_sst()
get_chlorophyll()
get_wave_conditions()
get_currents()
get_ocean_observations()
get_maritime_boundaries()
```

Each contract should specify input, source selection, request,
normalization, output schema, provenance, quality/confidence, error
handling and fallback.
