from __future__ import annotations

import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.core.http import json_response, jsonp_response
from apps.core.limits import load_limits
from apps.core.params import Parametros
from apps.core.problems import (
    MethodNotAllowed,
    PayloadTooLarge,
    invalid_parameter,
)

from . import client
from .validators import validate_proxy_url

logger = logging.getLogger("apps.proxy")

JSONP_ENABLED_KEY = "JSONP_ENABLED"


def _json_enabled(settings) -> bool:
    config = getattr(settings, "API_IDEE", None) or {}
    return bool(config.get(JSONP_ENABLED_KEY, True))


def _target_from_request(request: HttpRequest) -> tuple[str, str, dict[str, Any] | None, Any]:
    """Devuelve (url, method, headers, body)."""
    # POST JSON
    if request.method == "POST":
        content_type = (request.content_type or "").split(";")[0].strip().lower()
        is_json = content_type in {"application/json", "application/problem+json"}
        if is_json or content_type.endswith("+json"):
            limits = load_limits()
            if len(request.body) > limits.max_body_bytes:
                raise PayloadTooLarge("El cuerpo supera el límite.")
            try:
                payload = json.loads(request.body or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise invalid_parameter("body", "el JSON no es válido") from exc
            if not isinstance(payload, dict):
                raise invalid_parameter("body", "se esperaba un objeto JSON")
            url = payload.get("url") or request.headers.get("X-Target-URL")
            method = str(payload.get("method") or "GET").upper()
            headers = payload.get("headers")
            body = payload.get("body")
            if not url:
                raise invalid_parameter("url", "la URL es obligatoria")
            return str(url), method, headers if isinstance(headers, dict) else None, body
        # form / raw
        url = request.POST.get("url") or request.headers.get("X-Target-URL")
        if not url:
            raise invalid_parameter("url", "la URL es obligatoria")
        return str(url), "POST", None, request.body

    # GET
    params = Parametros.desde_request(request)
    url = params.texto("url")
    if not url:
        # legacy alias target-url
        url = request.headers.get("X-Target-URL")
    if not url:
        raise invalid_parameter("url", "la URL es obligatoria")
    method = params.texto("method") or "GET"
    return str(url), method.upper(), None, None


def _stream_response(request, url, method, headers, body, *, image: bool = False):
    validate_proxy_url(url)
    status, resp_headers, iterator = client.fetch_stream(url, method, headers=headers, content=body)
    content_type = resp_headers.get("Content-Type", "application/octet-stream")
    if image and not content_type.lower().startswith("image/"):
        # consume to close
        for _ in iterator:
            pass
        raise invalid_parameter("url", "el recurso no es una imagen")
    response = StreamingHttpResponse(iterator, status=status, content_type=content_type)
    response["X-Upstream-Status"] = str(status)
    for key, value in resp_headers.items():
        if key.lower() not in {"content-type"}:
            response[key] = value
    response["Access-Control-Expose-Headers"] = "X-Upstream-Status"
    return response


@require_GET
def proxy_image(request: HttpRequest) -> HttpResponse:
    params = Parametros.desde_request(request)
    url = params.texto("url")
    if not url:
        url = request.headers.get("X-Target-URL")
    if not url:
        raise invalid_parameter("url", "la URL es obligatoria")
    validate_proxy_url(url)
    # size check via fetch_bytes
    try:
        status, headers, data = client.fetch_bytes(url, "GET")
    except Exception as exc:
        raise invalid_parameter("url", "no se pudo obtener la imagen") from exc
    content_type = headers.get("Content-Type", "")
    if not content_type.lower().startswith("image/"):
        raise invalid_parameter("url", "el recurso no es una imagen")
    limits = load_limits()
    from django.conf import settings as _s

    config = getattr(_s, "API_IDEE", {}) or {}
    max_image = int(config.get("PROXY_MAX_BYTES", limits.proxy_max_bytes))
    if len(data) > max_image:
        raise invalid_parameter("url", "la imagen supera el tamaño máximo")
    response = HttpResponse(data, content_type=content_type, status=status)
    response["X-Upstream-Status"] = str(status)
    return response


def proxy_legacy(request: HttpRequest) -> HttpResponse:
    # GET /api/proxy
    if request.method != "GET":
        raise MethodNotAllowed("Solo se admite GET.", headers={"Allow": "GET"})
    params = Parametros.desde_request(request)
    url, method, headers, body = _target_from_request(request)
    validate_proxy_url(url)
    status, resp_headers, data = client.fetch_bytes(url, method, headers=headers, content=body)
    from django.conf import settings as dj_settings

    payload = {
        "status": status,
        "headers": resp_headers,
        "body": data.decode("utf-8", errors="replace"),
    }
    callback = params.callback() if hasattr(params, "callback") else params.texto("callback")
    # validate callback
    if callback:
        from apps.core.validators import validate_callback

        callback = validate_callback(callback)
    if callback and _json_enabled(dj_settings):
        return jsonp_response(payload, callback)
    return json_response(payload)


@csrf_exempt
@require_POST
def proxy_post(request: HttpRequest) -> HttpResponse:
    url, method, headers, body = _target_from_request(request)
    validate_proxy_url(url)
    status, resp_headers, iterator = client.fetch_stream(url, method, headers=headers, content=body)
    content_type = resp_headers.get("Content-Type", "application/octet-stream")
    response = StreamingHttpResponse(iterator, status=status, content_type=content_type)
    response["X-Upstream-Status"] = str(status)
    for key, value in resp_headers.items():
        if key.lower() not in {"content-type"}:
            response[key] = value
    return response


def proxy_canonical(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        url, method, headers, body = _target_from_request(request)
        return _stream_response(request, url, method, headers, body)
    if request.method == "POST":
        url, method, headers, body = _target_from_request(request)
        # If body is str, encode
        if isinstance(body, str):
            body = body.encode("utf-8")
        return _stream_response(request, url, method, headers, body)
    raise MethodNotAllowed("Solo se admiten GET y POST.", headers={"Allow": "GET, POST"})
