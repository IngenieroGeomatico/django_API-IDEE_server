"""Respuestas JSON/JSONP y de fichero para acciones y recursos."""

from __future__ import annotations

import json
from datetime import datetime

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from apps.core.http import (
    JSON_MEDIA,
    common_headers,
    conditional_response,
    etag_for,
    jsonp_response,
    negotiate,
)
from apps.core.params import Parametros

from .service import Asset


def _conditional_json(
    request: HttpRequest,
    payload,
    *,
    cache_control: str,
    last_modified: datetime | None,
    content_type: str = JSON_MEDIA,
) -> HttpResponse:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    response = HttpResponse(body, content_type=content_type)
    conditional_response(request, response, etag=etag_for(body), last_modified=last_modified)
    if response.status_code == 304:
        response.content = b""
    return response


def legacy_response(
    request: HttpRequest,
    payload,
    *,
    cache_control: str,
    last_modified: datetime | None = None,
    content_type: str = "application/javascript; charset=utf-8",
    params: Parametros | None = None,
) -> HttpResponse:
    """Respuesta de la fachada heredada: JSON o JSONP validado.

    El servidor original declaraba ``@Produces("application/javascript")`` para
    todas las acciones, incluso cuando no había ``callback``. Se conserva ese
    comportamiento salvo en ``resourcesPlugins``, que ya devolvía JSON.
    """
    params = params or Parametros.desde_request(request)
    config = getattr(settings, "API_IDEE", None) or {}
    if config.get("JSONP_ENABLED", True):
        callback = params.callback()
        if callback:
            response = jsonp_response(payload, callback)
            common_headers(
                response,
                request=request,
                params=params,
                vary=("Accept-Encoding",),
            )
            return response

    response = _conditional_json(
        request,
        payload,
        cache_control=cache_control,
        last_modified=last_modified,
        content_type=content_type,
    )
    return common_headers(response, request=request, params=params, cache_control=cache_control)


def canonical_response(
    request: HttpRequest,
    payload,
    *,
    cache_control: str,
    last_modified: datetime | None = None,
    allowed: tuple[str, ...] = ("f",),
    params: Parametros | None = None,
) -> HttpResponse:
    """Respuesta de ``/api/v1``: solo JSON, sin JSONP y con parámetros estrictos."""
    params = params or Parametros.desde_request(request)
    params.rechazar_desconocidos(allowed)
    negotiate(request, params, supported=("json",))

    response = _conditional_json(
        request,
        payload,
        cache_control=cache_control,
        last_modified=last_modified,
    )
    return common_headers(response, request=request, params=params, cache_control=cache_control)


def asset_response(
    request: HttpRequest,
    asset: Asset,
    *,
    cache_control: str,
) -> HttpResponse:
    response = HttpResponse(asset.content, content_type=asset.media_type)
    response["ETag"] = asset.etag
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = cache_control
    conditional_response(request, response, etag=asset.etag)
    if response.status_code == 304:
        response.content = b""
    request_id = getattr(request, "request_id", None)
    if request_id:
        response["X-Request-Id"] = request_id
    return response


__all__ = ["asset_response", "canonical_response", "legacy_response"]
