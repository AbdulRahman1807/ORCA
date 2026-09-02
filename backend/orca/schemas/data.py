"""Canonical data objects returned by capability tools."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .core import Provenance, SpatialRef, TemporalRef, QualityMetadata, Uncertainty
from .enums import Representation, ValueKind


class Observation(BaseModel):
    """A measured value at a point (and optionally a depth)."""
    type: Literal["Observation"] = "Observation"
    parameter: str
    value: float | None
    unit: str | None = None
    value_kind: ValueKind = ValueKind.OBSERVED
    spatial: SpatialRef
    temporal: TemporalRef
    quality: QualityMetadata = Field(default_factory=QualityMetadata)
    uncertainty: Uncertainty | None = None
    platform: dict[str, Any] | None = None
    provenance_id: str


class Forecast(Observation):
    type: Literal["Forecast"] = "Forecast"          # type: ignore[assignment]
    value_kind: ValueKind = ValueKind.FORECAST


class DerivedResult(BaseModel):
    type: Literal["DerivedResult"] = "DerivedResult"
    parameter: str
    value: float | bool | None
    unit: str | None = None
    value_kind: ValueKind = ValueKind.DERIVED
    spatial: SpatialRef | None = None
    temporal: TemporalRef | None = None
    quality: QualityMetadata = Field(default_factory=QualityMetadata)
    detail: dict[str, Any] = Field(default_factory=dict)
    provenance_id: str


class OceanField(BaseModel):
    """A gridded field. The array itself lives in object storage, never in JSON."""
    type: Literal["OceanField"] = "OceanField"
    parameter: str
    unit: str | None = None
    value_kind: ValueKind = ValueKind.OBSERVED
    spatial: SpatialRef
    temporal: TemporalRef
    values_ref: str | None = None
    values_inline: list[list[float | None]] | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    quality: QualityMetadata = Field(default_factory=QualityMetadata)
    provenance_id: str


class RasterRef(BaseModel):
    """Rendered imagery. Displayable and citable -- never spatially testable."""
    type: Literal["RasterRef"] = "RasterRef"
    parameter: str
    representation: Representation = Representation.RASTER
    value_kind: ValueKind = ValueKind.OBSERVED
    raster_uri: str
    legend_uri: str | None = None
    source_request: dict[str, Any] = Field(default_factory=dict)
    spatial: SpatialRef
    temporal: TemporalRef
    numeric_values_available: bool = False
    geometry_available: bool = False
    provenance_id: str


class VectorFeature(BaseModel):
    type: Literal["VectorFeature"] = "VectorFeature"
    feature_id: str
    parameter: str
    boundary_type: str | None = None
    name: str | None = None
    jurisdiction: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    geometry_ref: str | None = None
    geometry_inline: dict[str, Any] | None = None
    spatial: SpatialRef
    temporal: TemporalRef | None = None
    dataset_version: str | None = None
    advisory_only: bool = True
    value_kind: ValueKind = ValueKind.OBSERVED
    provenance_id: str


class MarineWarning(BaseModel):
    """Official bulletins are a distinct type because they are quoted, not computed."""
    type: Literal["MarineWarning"] = "MarineWarning"
    warning_id: str
    warning_type: str
    severity: str
    issuing_office: str
    issued_at: Any
    valid_from: Any = None
    valid_to: Any = None
    affected_area: SpatialRef | None = None
    area_description: str | None = None
    area_resolved: bool = False
    text_verbatim: str = ""
    language: str = "en"
    bulletin_reference: str | None = None
    value_kind: ValueKind = ValueKind.OBSERVED
    is_official: bool = True
    provenance_id: str


DataObject = (
    Observation | Forecast | DerivedResult | OceanField
    | RasterRef | VectorFeature | MarineWarning
)


class Conflict(BaseModel):
    conflict_id: str
    parameter: str
    candidates: list[dict[str, Any]]
    delta: dict[str, float]
    tolerance: dict[str, Any]
    material: bool
    safety_relevant: bool
    policy: str | None = None
    used_provenance_id: str | None = None
    rationale: str | None = None
