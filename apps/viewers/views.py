"""Vistas heredadas del builder y de los visualizadores (T-11, T-15 y T-16)."""

from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from apps.core.http import common_headers, set_deprecation
from apps.core.limits import load_limits
from apps.core.params import Parametros
from apps.core.problems import (
    MethodNotAllowed,
    PayloadTooLarge,
    UnsupportedMediaType,
    invalid_parameter,
)

from .builder import JS_MEDIA, build_legacy_js, build_post_js, legacy_map_payload
from .render import default_visualizador_payload, render_viewer, render_visualizador

logger = logging.getLogger("apps.viewers")


def index(request: HttpRequest) -> HttpResponse:
    """Página equivalente a ``index.jsp``: monta el builder sobre ``/api/js``."""
    _require_get(request)
    return render_viewer(request)


def visualizador(request: HttpRequest) -> HttpResponse:
    """Visualizador de ejemplo equivalente a ``visor.jsp``."""
    _require_get(request)
    params = Parametros.desde_request(request)
    if any(
        params.tiene(name)
        for name in ("layers", "controls", "plugins", "center", "zoom", "bbox", "crs")
    ):
        map_payload, plugins = legacy_map_payload(params)
        map_payload["container"] = "mapjs"
        payload = {
            "map": map_payload,
            "plugins": [
                {"class": plugin.class_name, "args": plugin.invocation_args()} for plugin in plugins
            ],
        }
        names = [plugin.type for plugin in plugins] or None
        return render_visualizador(request, payload=payload, plugin_names=names)

    payload, plugins = default_visualizador_payload()
    return render_visualizador(
        request,
        payload=payload,
        plugin_names=[plugin.type for plugin in plugins],
    )


def api_js(request: HttpRequest) -> HttpResponse:
    """``GET/POST /api/js``: JavaScript generado de forma segura."""
    if request.method == "GET":
        code = build_legacy_js(Parametros.desde_request(request))
    elif request.method == "POST":
        code = build_post_js(_json_body(request))
    else:
        raise MethodNotAllowed(
            "Solo se admiten GET y POST.",
            headers={"Allow": "GET, POST"},
        )

    response = HttpResponse(code, content_type=JS_MEDIA)
    response["Cache-Control"] = "no-store"
    common_headers(response, request=request, cache_control=None)
    api_config = getattr(settings, "API_IDEE", None) or {}
    set_deprecation(
        response,
        sunset=api_config.get("LEGACY_SUNSET"),
        detail="El builder /api/js se mantiene por compatibilidad",
    )
    return response


def _require_get(request: HttpRequest) -> None:
    if request.method != "GET":
        raise MethodNotAllowed(
            "Solo se admite GET.",
            headers={"Allow": "GET"},
        )


def _json_body(request: HttpRequest) -> dict[str, Any]:
    content_type = (request.content_type or "").split(";")[0].strip().lower()
    if content_type != "application/json" and not content_type.endswith("+json"):
        raise UnsupportedMediaType(
            "El cuerpo debe enviarse con Content-Type: application/json.",
            headers={"Accept": "application/json"},
        )
    limits = load_limits()
    if len(request.body) > limits.max_body_bytes:
        raise PayloadTooLarge(
            f"El cuerpo supera el límite de {limits.max_body_bytes} bytes.",
        )
    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise invalid_parameter("body", "el JSON no es válido") from exc
    if not isinstance(payload, dict):
        raise invalid_parameter("body", "se esperaba un objeto JSON")
    return payload


__all__ = ["api_js", "index", "visualizador"]
