"""Negociación de formato, cabeceras HTTP y respuestas JSON/JSONP (plan §4.10)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.http import http_date

from .params import Parametros
from .problems import NotAcceptable, invalid_parameter
from .validators import validate_callback

PROBLEM_JSON = "application/problem+json"
JSON_MEDIA = "application/json"


@dataclass(frozen=True, slots=True)
class Representation:
    key: str
    media_type: str
    extension: str


REPRESENTATIONS: dict[str, Representation] = {
    "json": Representation("json", JSON_MEDIA, ".json"),
    "html": Representation("html", "text/html", ".html"),
    "geojson": Representation("geojson", "application/geo+json", ".geojson"),
    "gml": Representation("gml", "application/gml+xml", ".gml"),
    "kml": Representation("kml", "application/vnd.google-earth.kml+xml", ".kml"),
    "mvt": Representation("mvt", "application/vnd.mapbox-vector-tile", ".pbf"),
    "csv": Representation("csv", "text/csv", ".csv"),
}

DEFAULT_SUPPORTED: tuple[str, ...] = ("json", "html", "geojson")


# ---------------------------------------------------------------------------
# Negociación f / Accept
# ---------------------------------------------------------------------------
def _parse_accept(value: str) -> list[tuple[str, str, float]]:
    ranges: list[tuple[str, str, float]] = []
    for part in value.split(","):
        segments = [segment.strip() for segment in part.split(";") if segment.strip()]
        if not segments:
            continue
        media = segments[0].lower()
        if "/" not in media:
            continue
        type_, subtype = media.split("/", 1)
        quality = 1.0
        for segment in segments[1:]:
            if segment.lower().startswith("q="):
                try:
                    quality = float(segment[2:])
                except ValueError:
                    quality = 1.0
        ranges.append((type_, subtype, max(0.0, min(1.0, quality))))
    return ranges


def _match_score(media_type: str, accept_type: str, accept_subtype: str) -> int:
    type_, subtype = media_type.lower().split("/", 1)
    if accept_type == type_ and accept_subtype == subtype:
        return 3
    if accept_type == type_ and accept_subtype == "*":
        return 2
    if accept_type == "*" and accept_subtype == "*":
        return 1
    return 0


def best_media_type(value: str, media_types: Sequence[str]) -> str | None:
    """Devuelve el media type soportado que mejor encaja con ``Accept``."""
    ranges = _parse_accept(value)
    if not ranges:
        return media_types[0] if media_types else None

    best_choice: tuple[tuple[float, float, int], str] | None = None
    for index, media_type in enumerate(media_types):
        candidate: tuple[float, float, int] | None = None
        for accept_type, accept_subtype, quality in ranges:
            if quality <= 0:
                continue
            score = _match_score(media_type, accept_type, accept_subtype)
            if not score:
                continue
            rank = (float(score), quality, -index)
            if candidate is None or rank > candidate:
                candidate = rank
        if candidate is not None and (best_choice is None or candidate > best_choice[0]):
            best_choice = (candidate, media_type)
    return best_choice[1] if best_choice else None


def negotiate(
    request: HttpRequest,
    params: Parametros | None = None,
    *,
    supported: Sequence[str] = DEFAULT_SUPPORTED,
) -> Representation:
    """Resuelve la representación de respuesta a partir de ``f`` o ``Accept``."""
    keys = [key for key in supported if key in REPRESENTATIONS]
    if not keys:
        raise ValueError("No hay representaciones soportadas válidas")

    if params is not None:
        requested = params.texto("f")
        if requested is not None:
            key = requested.strip().lower()
            if key not in REPRESENTATIONS or key not in keys:
                raise invalid_parameter(
                    "f",
                    "formato no soportado; use uno de: " + ", ".join(keys),
                    requested,
                )
            return REPRESENTATIONS[key]

    accept = request.headers.get("Accept", "") or "*/*"
    media_type = best_media_type(accept, [REPRESENTATIONS[key].media_type for key in keys])
    if media_type is None:
        raise NotAcceptable(
            "Ninguno de los formatos solicitados está disponible.",
            headers={"Accept": ", ".join(REPRESENTATIONS[key].media_type for key in keys)},
        )
    for key in keys:
        if REPRESENTATIONS[key].media_type == media_type:
            return REPRESENTATIONS[key]
    raise NotAcceptable("Formato no disponible.")  # pragma: no cover


# ---------------------------------------------------------------------------
# Cabeceras y caché
# ---------------------------------------------------------------------------
def add_vary(response: HttpResponse, *values: str) -> HttpResponse:
    existing = response.get("Vary", "")
    current = [item.strip() for item in existing.split(",") if item.strip()]
    lowered = {item.lower() for item in current}
    for value in values:
        if value.lower() not in lowered:
            current.append(value)
            lowered.add(value.lower())
    if current:
        response["Vary"] = ", ".join(current)
    return response


def etag_for(payload: str | bytes) -> str:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    digest = hashlib.sha256(data).hexdigest()
    return f'"sha256-{digest[:32]}"'


def _etag_matches(header: str, etag: str) -> bool:
    if header.strip() == "*":
        return True
    for candidate in header.split(","):
        candidate = candidate.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:].strip()
        if candidate == etag:
            return True
    return False


def is_not_modified(
    request: HttpRequest,
    *,
    etag: str | None = None,
    last_modified: datetime | None = None,
) -> bool:
    if etag is not None:
        inm = request.headers.get("If-None-Match")
        if inm:
            return _etag_matches(inm, etag)
    if last_modified is not None:
        ims = request.headers.get("If-Modified-Since")
        if ims:
            try:
                since = parsedate_to_datetime(ims)
            except (TypeError, ValueError):
                return False
            if since.tzinfo is None:
                return False
            return last_modified.replace(microsecond=0) <= since.replace(microsecond=0)
    return False


def conditional_response(
    request: HttpRequest,
    response: HttpResponse,
    *,
    etag: str | None = None,
    last_modified: datetime | None = None,
) -> HttpResponse:
    if etag is not None:
        response["ETag"] = etag
    if last_modified is not None:
        response["Last-Modified"] = http_date(last_modified.timestamp())
    if is_not_modified(request, etag=etag, last_modified=last_modified):
        response.status_code = HTTPStatus.NOT_MODIFIED
        response.content = b""
    return response


def common_headers(
    response: HttpResponse,
    *,
    request: HttpRequest | None = None,
    params: Parametros | None = None,
    crs_uri: str | None = None,
    cache_control: str | None = None,
    vary: Sequence[str] = ("Accept", "Accept-Encoding"),
) -> HttpResponse:
    add_vary(response, *vary)
    response["X-Content-Type-Options"] = "nosniff"
    if crs_uri:
        response["Content-Crs"] = f"<{crs_uri}>"
    if cache_control:
        response["Cache-Control"] = cache_control
    if params is not None and params.deprecations:
        names = ", ".join(sorted({given for given, _ in params.deprecations}))
        set_deprecation(response, detail=f"Parámetros obsoletos: {names}")
    if request is not None:
        request_id = getattr(request, "request_id", None)
        if request_id:
            response["X-Request-Id"] = request_id
    return response


def set_deprecation(
    response: HttpResponse,
    *,
    sunset: str | None = None,
    detail: str | None = None,
) -> HttpResponse:
    response["Deprecation"] = "true"
    if sunset:
        response["Sunset"] = sunset
    if detail:
        response["Warning"] = f'299 - "{detail}"'
    return response


# ---------------------------------------------------------------------------
# Respuestas
# ---------------------------------------------------------------------------
def json_response(
    payload: Any,
    *,
    status: int = 200,
    headers: Mapping[str, str] | None = None,
) -> HttpResponse:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    response = HttpResponse(body, status=status, content_type=JSON_MEDIA)
    for key, value in (headers or {}).items():
        response[key] = value
    return response


def jsonp_response(
    payload: Any,
    callback: str,
    *,
    status: int = 200,
    sunset: str | None = None,
) -> HttpResponse:
    """JSONP heredado: callback validado, sin caché y con ``nosniff``."""
    cb = validate_callback(callback)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    body = body.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    response = HttpResponse(
        f"{cb}({body});",
        status=status,
        content_type="application/javascript; charset=utf-8",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    config = getattr(settings, "API_IDEE", None) or {}
    set_deprecation(response, sunset=sunset or config.get("JSONP_SUNSET"), detail="JSONP obsoleto")
    return response


def content_disposition(filename: str, *, inline: bool = False) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "download"
    disposition = "inline" if inline else "attachment"
    return f'{disposition}; filename="{safe}"'


def link_header(links: Iterable[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for link in links:
        segment = f"<{link['href']}>"
        for key in ("rel", "type", "title"):
            if link.get(key):
                segment += f'; {key}="{link[key]}"'
        parts.append(segment)
    return ", ".join(parts)


__all__ = [
    "DEFAULT_SUPPORTED",
    "JSON_MEDIA",
    "PROBLEM_JSON",
    "REPRESENTATIONS",
    "Representation",
    "add_vary",
    "best_media_type",
    "common_headers",
    "conditional_response",
    "content_disposition",
    "etag_for",
    "is_not_modified",
    "json_response",
    "jsonp_response",
    "link_header",
    "negotiate",
    "set_deprecation",
]
