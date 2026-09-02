"""Minimal Zarr v2 reader over HTTP.

CMEMS publishes its analysis/forecast products as ARCO (Zarr) stores. This
reader fetches only the chunks a query actually needs, which keeps a point
query to a couple of HTTP requests instead of a bulk download.

Deliberately narrow: it reads the v2 layout CMEMS publishes and nothing else.
The alternative (xarray + zarr + fsspec + aiohttp) brings an async stack and
much looser control over error mapping, which matters because every failure
here has to become a canonical ORCA code.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from numcodecs import get_codec

log = logging.getLogger("orca.adapters.cmems")

_EPOCH_RE = "since"


class ZarrError(Exception):
    def __init__(self, kind: str, detail: str = "", status: int | None = None):
        super().__init__(f"{kind}: {detail}")
        self.kind = kind          # not_found | forbidden | unavailable | decode
        self.detail = detail
        self.status = status


@dataclass(slots=True)
class ArrayMeta:
    name: str
    shape: tuple[int, ...]
    chunks: tuple[int, ...]
    dtype: np.dtype
    fill_value: Any
    compressor: dict | None
    filters: list[dict] | None
    order: str
    dims: tuple[str, ...]
    attrs: dict

    @property
    def scale_factor(self) -> float:
        return float(self.attrs.get("scale_factor", 1.0))

    @property
    def add_offset(self) -> float:
        return float(self.attrs.get("add_offset", 0.0))

    @property
    def units(self) -> str | None:
        return self.attrs.get("units")


class ZarrStore:
    """A single Zarr v2 store addressed by base URL."""

    def __init__(self, base_url: str, http):
        self.base_url = base_url.rstrip("/")
        self._http = http
        self._meta: dict[str, Any] | None = None
        self._coords: dict[str, np.ndarray] = {}
        self._chunk_cache: dict[tuple[str, tuple[int, ...]], np.ndarray | None] = {}

    # -- metadata --------------------------------------------------------------

    def _consolidated(self) -> dict[str, Any]:
        if self._meta is None:
            r = self._http.get_bytes(f"{self.base_url}/.zmetadata")
            self._meta = json.loads(r)["metadata"]
        return self._meta

    def array(self, name: str) -> ArrayMeta:
        m = self._consolidated()
        try:
            za = m[f"{name}/.zarray"]
        except KeyError:
            raise ZarrError("not_found", f"array {name!r} is not in this store")
        attrs = m.get(f"{name}/.zattrs", {})
        return ArrayMeta(
            name=name,
            shape=tuple(za["shape"]),
            chunks=tuple(za["chunks"]),
            dtype=np.dtype(za["dtype"]),
            fill_value=za.get("fill_value"),
            compressor=za.get("compressor"),
            filters=za.get("filters"),
            order=za.get("order", "C"),
            dims=tuple(attrs.get("_ARRAY_DIMENSIONS", ())),
            attrs=attrs,
        )

    def variables(self) -> list[str]:
        m = self._consolidated()
        return sorted({k.split("/")[0] for k in m if k.endswith("/.zarray")})

    # -- data ------------------------------------------------------------------

    def _decode_chunk(self, meta: ArrayMeta, raw: bytes) -> np.ndarray:
        buf: Any = raw
        if meta.compressor:
            buf = get_codec(meta.compressor).decode(buf)
        for f in reversed(meta.filters or []):
            buf = get_codec(f).decode(buf)
        arr = np.frombuffer(buf, dtype=meta.dtype)
        expected = int(np.prod(meta.chunks))
        if arr.size != expected:
            raise ZarrError("decode",
                            f"{meta.name}: chunk has {arr.size} values, expected {expected}")
        return arr.reshape(meta.chunks, order=meta.order)

    def _chunk(self, meta: ArrayMeta, index: tuple[int, ...]) -> np.ndarray | None:
        """Fetch one chunk. Returns None if the store omits it (all-fill)."""
        ck = (meta.name, index)
        if ck in self._chunk_cache:
            return self._chunk_cache[ck]
        out = self._fetch_chunk(meta, index)
        self._chunk_cache[ck] = out
        return out

    def _fetch_chunk(self, meta: ArrayMeta, index: tuple[int, ...]) -> np.ndarray | None:
        key = ".".join(str(i) for i in index)
        try:
            raw = self._http.get_bytes(f"{self.base_url}/{meta.name}/{key}")
        except ZarrError as exc:
            # Zarr omits chunks that are entirely fill, so a 404 means "no data
            # here" and reads as absent.
            #
            # A 403 is NOT treated as absent. On the CMEMS buckets a denied
            # request and a nonexistent key return an identical AccessDenied
            # body, so the two are indistinguishable -- and we have observed the
            # same chunk return 200 earlier in a session and 403 later, which
            # points to throttling of unauthenticated egress rather than
            # absence. Reading a denial as "no data" would silently drop real
            # observations and could present a masked sea as a calm one.
            if exc.kind == "not_found":
                return None
            raise
        return self._decode_chunk(meta, raw)

    def read_coord(self, name: str) -> np.ndarray:
        """Read a full 1-D coordinate array (they are small and reused)."""
        if name in self._coords:
            return self._coords[name]
        meta = self.array(name)
        if len(meta.shape) != 1:
            raise ZarrError("decode", f"{name} is not 1-D")
        n, cs = meta.shape[0], meta.chunks[0]
        out = np.empty(n, dtype=meta.dtype)
        for ci in range((n + cs - 1) // cs):
            chunk = self._chunk(meta, (ci,))
            lo, hi = ci * cs, min((ci + 1) * cs, n)
            out[lo:hi] = (np.full(hi - lo, meta.fill_value, dtype=meta.dtype)
                          if chunk is None else chunk[: hi - lo])
        self._coords[name] = out
        return out

    def read_point(self, var: str, index: dict[str, int]) -> float | None:
        """Read a single value, fetching only the chunk that contains it."""
        meta = self.array(var)
        if not meta.dims:
            raise ZarrError("decode", f"{var}: no _ARRAY_DIMENSIONS attribute")
        idx = tuple(index[d] for d in meta.dims)
        for i, (v, n) in enumerate(zip(idx, meta.shape)):
            if not 0 <= v < n:
                raise ZarrError("not_found",
                                f"{var}: index {v} out of range on {meta.dims[i]}")
        cidx = tuple(v // c for v, c in zip(idx, meta.chunks))
        inner = tuple(v % c for v, c in zip(idx, meta.chunks))
        chunk = self._chunk(meta, cidx)
        if chunk is None:
            return None
        raw = chunk[inner]
        if meta.fill_value is not None and raw == meta.fill_value:
            return None
        return float(raw) * meta.scale_factor + meta.add_offset


    def read_window(self, var: str, index: dict[str, int],
                    window: dict[str, int]) -> tuple[np.ndarray, dict[str, slice]]:
        """Read a rectangular window around a point, as a masked float array.

        Used to find the nearest valid cell when the exact cell is masked --
        coastal cells are routinely land-masked in wave models. Fill values
        become NaN; scale/offset are applied.
        """
        meta = self.array(var)
        slices: dict[str, slice] = {}
        for d in meta.dims:
            n = meta.shape[meta.dims.index(d)]
            half = window.get(d, 0)
            centre = index[d]
            slices[d] = slice(max(0, centre - half), min(n, centre + half + 1))

        shape = tuple(slices[d].stop - slices[d].start for d in meta.dims)
        out = np.full(shape, np.nan, dtype="f8")
        ranges = [range(slices[d].start, slices[d].stop) for d in meta.dims]

        # Group the requested cells by the chunk that holds them.
        needed: dict[tuple[int, ...], list[tuple[tuple[int, ...], tuple[int, ...]]]] = {}
        import itertools
        for idx in itertools.product(*ranges):
            cidx = tuple(v // c for v, c in zip(idx, meta.chunks))
            inner = tuple(v % c for v, c in zip(idx, meta.chunks))
            local = tuple(v - slices[d].start for v, d in zip(idx, meta.dims))
            needed.setdefault(cidx, []).append((inner, local))

        for cidx, cells in needed.items():
            chunk = self._chunk(meta, cidx)
            if chunk is None:
                continue
            for inner, local in cells:
                raw = chunk[inner]
                if meta.fill_value is not None and raw == meta.fill_value:
                    continue
                out[local] = float(raw) * meta.scale_factor + meta.add_offset
        return out, slices


# -- coordinate helpers --------------------------------------------------------

def nearest_index(coord: np.ndarray, value: float) -> tuple[int, float]:
    """Index of the nearest coordinate value, and the residual."""
    i = int(np.abs(coord - value).argmin())
    return i, float(coord[i] - value)


def decode_time(values: np.ndarray, units: str) -> list[datetime]:
    """Decode CF time values, e.g. 'hours since 1950-01-01'."""
    unit, _, epoch = units.partition(f" {_EPOCH_RE} ")
    base = datetime.fromisoformat(epoch.strip().replace("Z", "+00:00"))
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    per = {"days": 86400.0, "hours": 3600.0, "minutes": 60.0, "seconds": 1.0}
    step = per.get(unit.strip().lower())
    if step is None:
        raise ZarrError("decode", f"unsupported time unit {unit!r}")
    return [base + timedelta(seconds=float(v) * step) for v in values]
