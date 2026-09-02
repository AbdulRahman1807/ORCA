"""HTTP client for INCOIS ERDDAP.

This module is the ONLY place that knows ERDDAP URLs and query syntax.
Nothing above the adapter layer may import it.

Source: S-01..S-04 (03_DATA_SOURCE_MATRIX.md). Audit status: VERIFIED.
Terms of use: INCOIS ERDDAP terms -- see source portal. No authentication was
observed for the P0 datasets; that is not a guarantee and may change.
"""
from __future__ import annotations

import logging
import pathlib
import re
import time
from dataclasses import dataclass
from typing import Any

import certifi
import httpx

from ...schemas.errors import ErrorCode

log = logging.getLogger("orca.adapters.incois_erddap")

#: INCOIS ERDDAP serves ONLY its leaf certificate -- the GlobalSign intermediate
#: ("GlobalSign RSA OV SSL CA 2018") is absent from the TLS chain. Verified
#: 2026-09-02 via `openssl s_client -showcerts` (chain length 1).
#:
#: macOS/Windows succeed anyway because the OS verifier fetches the issuer via
#: the certificate's AIA extension; `certifi` (roots only) does not, and a plain
#: Linux container would therefore FAIL to reach a source that works on a laptop.
#:
#: We handle this in two portable ways and NEVER by disabling verification:
#:   1. the OS trust store via `truststore` (AIA-capable on macOS/Windows), then
#:   2. a bundle of certifi roots + the missing intermediate (portable to Linux).
_TLS_DIR = pathlib.Path(__file__).resolve().parents[4] / "config" / "tls"
_INTERMEDIATE_PEM = _TLS_DIR / "globalsign_rsa_ov_ssl_ca_2018.pem"
_BUNDLE_PEM = _TLS_DIR / "incois_bundle.pem"


def _ensure_bundle() -> pathlib.Path | None:
    """Build `certifi roots + missing intermediate` on demand.

    The bundle is generated, never committed: vendoring a copy of certifi's root
    store would go stale silently. Only the 1.5 kB intermediate is tracked.
    """
    if not _INTERMEDIATE_PEM.is_file():
        return None
    roots = pathlib.Path(certifi.where())
    if (_BUNDLE_PEM.is_file()
            and _BUNDLE_PEM.stat().st_mtime >= max(roots.stat().st_mtime,
                                                   _INTERMEDIATE_PEM.stat().st_mtime)):
        return _BUNDLE_PEM
    try:
        _BUNDLE_PEM.write_text(
            roots.read_text() + "\n" + _INTERMEDIATE_PEM.read_text()
        )
    except OSError:
        return None
    return _BUNDLE_PEM


def _build_ssl_context() -> Any:
    """Return an httpx `verify` value. Verification is never disabled."""
    try:
        import ssl

        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:  # pragma: no cover - truststore unavailable
        log.info("truststore unavailable; falling back to bundled intermediate")
    bundle = _ensure_bundle()
    if bundle is not None:
        return str(bundle)
    log.warning(
        "no intermediate at %s; using certifi roots only -- INCOIS ERDDAP may fail "
        "TLS verification because it omits its intermediate certificate",
        _INTERMEDIATE_PEM,
    )
    return certifi.where()

DEFAULT_BASE_URL = "https://erddap.incois.gov.in/erddap"
SOURCE_NAME = "INCOIS ERDDAP"
ORGANISATION = "INCOIS (MoES)"


class ErddapError(Exception):
    """Adapter-level failure carrying a canonical code.

    Provider exceptions never cross the adapter boundary; they become this.
    """

    def __init__(self, code: ErrorCode, detail: str = "", status: int | None = None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(slots=True)
class ErddapResponse:
    payload: dict[str, Any]
    url: str
    elapsed_ms: int
    bytes: int


#: ERDDAP selector syntax uses characters the servlet container rejects when
#: sent raw (observed: Tomcat returns an HTML 400 before ERDDAP ever parses the
#: query). We percent-encode exactly those, and nothing else -- a generic query
#: encoder would also encode `,` `:` `(` `)` `&` `=` and break the selector.
_MUST_ENCODE = {
    "[": "%5B", "]": "%5D", '"': "%22", " ": "%20",
    "<": "%3C", ">": "%3E", "|": "%7C", "{": "%7B", "}": "%7D",
    "\\": "%5C", "^": "%5E", "`": "%60",
}


def encode_query(query: str) -> str:
    for raw, enc in _MUST_ENCODE.items():
        query = query.replace(raw, enc)
    return query


_UNKNOWN_DATASET = re.compile(r"Currently unknown datasetID", re.I)
_NO_MATCHING = re.compile(r"Your query produced no matching results", re.I)


class ErddapClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: float = 45.0,
                 max_retries: int = 2):
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self._client = httpx.Client(
            timeout=timeout,
            verify=_build_ssl_context(),
            headers={"User-Agent": "ORCA/0.1 (SIH26176 prototype; marine data integration)"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "ErddapClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- request ---------------------------------------------------------------

    def get_json(self, path: str, query: str = "") -> ErddapResponse:
        """GET an ERDDAP .json endpoint, mapping every failure to a canonical code.

        `query` is passed through verbatim: ERDDAP's selector syntax uses
        characters that must NOT be percent-encoded by a query-param encoder.
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{encode_query(query)}"

        last: ErddapError | None = None
        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                r = self._client.get(url)
            except httpx.TimeoutException as exc:
                last = ErddapError(ErrorCode.TIMEOUT, str(exc))
            except httpx.TransportError as exc:
                # DNS failure, connection refused, TLS failure.
                # NOTE: a DNS failure on OUR network is a local condition. We
                # report SOURCE_UNAVAILABLE, which never asserts the endpoint
                # itself is broken (03_DATA_SOURCE_MATRIX.md rule 3).
                last = ErddapError(ErrorCode.SOURCE_UNAVAILABLE, str(exc))
            else:
                elapsed = int((time.perf_counter() - started) * 1000)
                err = self._classify(r)
                if err is None:
                    return ErddapResponse(r.json(), url, elapsed, len(r.content))
                if err.code not in (ErrorCode.SOURCE_UNAVAILABLE, ErrorCode.TIMEOUT,
                                    ErrorCode.RATE_LIMITED):
                    raise err          # not retryable -- fail immediately
                last = err

            if attempt <= self.max_retries:
                time.sleep(min(2 ** attempt * 0.4, 5.0))
                log.warning("erddap retry %d/%d url=%s code=%s",
                            attempt, self.max_retries, url, last.code)
        raise last or ErddapError(ErrorCode.ADAPTER_ERROR, "unreachable")

    @staticmethod
    def _classify(r: httpx.Response) -> ErddapError | None:
        body = r.text[:600]
        if r.status_code == 200:
            if body.lstrip().startswith("Error"):
                # ERDDAP occasionally returns errors with a 200 status.
                return ErddapClient._from_body(body, r.status_code)
            return None
        if r.status_code in (401, 403):
            return ErddapError(ErrorCode.AUTH_REQUIRED,
                               "ERDDAP returned an authentication challenge",
                               r.status_code)
        if r.status_code == 429:
            return ErddapError(ErrorCode.RATE_LIMITED, body, r.status_code)
        if r.status_code == 404:
            return ErddapClient._from_body(body, r.status_code)
        if r.status_code >= 500:
            return ErddapError(ErrorCode.SOURCE_UNAVAILABLE, body, r.status_code)
        return ErddapClient._from_body(body, r.status_code)

    @staticmethod
    def _from_body(body: str, status: int | None) -> ErddapError:
        if body.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
            return ErddapError(
                ErrorCode.ADAPTER_ERROR,
                f"servlet container rejected the request (HTTP {status}) before ERDDAP "
                f"parsed it -- this indicates a malformed/unencoded selector",
                status,
            )
        if _UNKNOWN_DATASET.search(body):
            # Observed live on 2026-09-02: NOAA_AVHRR_datasets vanished from the
            # catalogue mid-session. A dataset that disappears is DATASET_UNAVAILABLE
            # -- it is never silently substituted with another dataset.
            return ErddapError(ErrorCode.DATASET_UNAVAILABLE,
                               "dataset is not currently loaded by the ERDDAP server",
                               status)
        if _NO_MATCHING.search(body):
            return ErddapError(ErrorCode.NO_DATA,
                               "query was valid but matched no data", status)
        return ErddapError(ErrorCode.ADAPTER_ERROR, body.strip()[:300], status)
