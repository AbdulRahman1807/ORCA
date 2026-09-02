"""HTTP client for the Copernicus Marine (CMEMS) data store.

Source: S-07 (03_DATA_SOURCE_MATRIX.md).

Access note, verified 2026-09-02: the CMEMS STAC catalogue and the ARCO (Zarr)
object store both answered unauthenticated requests, including real data chunks.
The audit had recorded CMEMS as AUTH REQUIRED; that holds for the subsetting and
download services, but the ARCO store served this project's wave and current
reads without credentials. Credentials remain supported and are used when
configured -- absence of them is not treated as failure.

Terms of use: Copernicus Marine Service terms. Attribution is mandatory and is
carried in provenance.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from ...schemas.errors import ErrorCode
from .store import ZarrError

log = logging.getLogger("orca.adapters.cmems")

STAC_BASE = "https://stac.marine.copernicus.eu/metadata"
SOURCE_NAME = "CMEMS"
SOURCE_ID = "S-07"
ORGANISATION = "Copernicus Marine Service (EU)"
ATTRIBUTION = "E.U. Copernicus Marine Service Information"

#: ZarrError.kind -> canonical ORCA error code
_KIND_TO_CODE = {
    "not_found": ErrorCode.NO_DATA,
    "forbidden": ErrorCode.AUTH_REQUIRED,
    "unavailable": ErrorCode.SOURCE_UNAVAILABLE,
    "decode": ErrorCode.ADAPTER_ERROR,
}


def canonical_code(exc: ZarrError) -> ErrorCode:
    return _KIND_TO_CODE.get(exc.kind, ErrorCode.ADAPTER_ERROR)


class CmemsHttp:
    """Byte-range friendly HTTP client with canonical failure classification."""

    def __init__(self, timeout: float = 60.0, max_retries: int = 2,
                 username: str | None = None, password: str | None = None):
        self.max_retries = max_retries
        auth = None
        user = username or os.getenv("ORCA_CMEMS_USERNAME")
        pwd = password or os.getenv("ORCA_CMEMS_PASSWORD")
        if user and pwd:
            auth = httpx.BasicAuth(user, pwd)
            log.info("cmems: using configured credentials")
        self._client = httpx.Client(
            timeout=timeout, auth=auth, follow_redirects=True,
            headers={"User-Agent": "ORCA/0.1 (SIH26176 prototype; marine data integration)"},
        )
        self.bytes_read = 0
        self.requests = 0

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CmemsHttp":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def get_bytes(self, url: str) -> bytes:
        last: ZarrError | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                r = self._client.get(url)
            except httpx.TimeoutException as exc:
                last = ZarrError("unavailable", f"timeout: {exc}")
            except httpx.TransportError as exc:
                last = ZarrError("unavailable", str(exc))
            else:
                self.requests += 1
                if r.status_code == 200:
                    self.bytes_read += len(r.content)
                    return r.content
                if r.status_code in (401, 403):
                    raise ZarrError("forbidden",
                                    "CMEMS store rejected the request; credentials "
                                    "may be required for this asset", r.status_code)
                if r.status_code == 404:
                    raise ZarrError("not_found", url.rsplit("/", 1)[-1], 404)
                if r.status_code == 429:
                    last = ZarrError("unavailable", "rate limited", 429)
                elif r.status_code >= 500:
                    last = ZarrError("unavailable", f"HTTP {r.status_code}", r.status_code)
                else:
                    raise ZarrError("decode", f"HTTP {r.status_code}", r.status_code)
            if attempt <= self.max_retries:
                time.sleep(min(2 ** attempt * 0.4, 5.0))
                log.warning("cmems retry %d/%d %s", attempt, self.max_retries, url)
        raise last or ZarrError("unavailable", "unreachable")

    def get_json(self, url: str) -> Any:
        import json
        return json.loads(self.get_bytes(url))
