"""Renderizado de las plantillas de visualizador (T-11 y T-15)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any
from urllib.parse import parse_qsl, urlencode

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.core.params import Parametros
from apps.core.validators import parse_enum

from .builder import (
    ViewConfig,
    legacy_map_payload,
    viewer_payload,
)
from .layers import parse_legacy_layers
from .validate import PluginConfig, plugin_assets

DEFAULT_IMPLEMENTATION = "ol"
IMPLEMENTATIONS = ("ol", "cesium")
DEFAULT_PLUGIN_NAMES: tuple[str, ...] = ("mousesrs", "sharemap")

DEFAULT_LAYERS = (
    "WMS*Límite administrativo*https://www.ign.es/wms-inspire/unidades-administrativas?"
    "*AU.AdministrativeBoundary*true*false**true*true*true*1.3.0",
    "WMS*Unidad administrativa*https://www.ign.es/wms-inspire/unidades-administrativas?"
    "*AU.AdministrativeUnit*true*false**true*true*true*1.3.0",
    "WMTS*https://www.ign.es/wmts/ign-base?*IGNBaseTodo*GoogleMapsCompatible*IGNBaseTodo"
    "*true*image/jpeg",
)

DEFAULT_CONTROLS = (
    "panzoom",
    "scale*true",
    "scaleline",
    "rotate",
    "location",
    "backgroundlayers",
    "getfeatureinfo",
)

DEFAULT_PLUGIN_PARAMS: dict[str, dict[str, Any]] = {
    "toc": {"collapsible": True, "collapsed": True},
    "mousesrs": {"srs": "EPSG:4326", "label": "WGS84", "precision": 6},
    "sharemap": {"position": "BR"},
}


def implementation_from(params: Parametros) -> str:
    return (
        parse_enum(
            params.texto("impl") or DEFAULT_IMPLEMENTATION,
            IMPLEMENTATIONS,
            name="implementation",
        )
        or DEFAULT_IMPLEMENTATION
    )


def default_visualizador_payload() -> tuple[dict[str, Any], list[PluginConfig]]:
    layers = parse_legacy_layers(",".join(DEFAULT_LAYERS))
    view = ViewConfig(crs="EPSG:3857", center=[-467062.8225, 4683459.6216], zoom=5)
    from .validate import normalize_controls, normalize_plugins

    controls = normalize_controls(list(DEFAULT_CONTROLS))
    plugins = normalize_plugins(
        [
            {"type": name, "params": DEFAULT_PLUGIN_PARAMS.get(name, {})}
            for name in DEFAULT_PLUGIN_NAMES
        ]
    )
    payload = viewer_payload(
        container="mapjs",
        view=view,
        layers=layers,
        controls=controls,
        plugins=plugins,
        implementation="ol",
    )
    return payload, plugins


def render_viewer(request: HttpRequest) -> HttpResponse:
    params = Parametros.desde_request(request)
    implementation = implementation_from(params)
    _payload, plugins = legacy_map_payload(params)
    names = [plugin.type for plugin in plugins]
    css, js = plugin_assets(names, implementation=implementation)
    return render(
        request,
        "viewer.html",
        {
            "implementation": implementation,
            "plugin_css": css,
            "plugin_js": js,
            "js_query": _js_query(request),
        },
    )


def render_visualizador(
    request: HttpRequest,
    *,
    payload: dict[str, Any],
    plugin_names: Iterable[str] | None = None,
    status: int = 200,
) -> HttpResponse:
    names: Sequence[str] = list(plugin_names or DEFAULT_PLUGIN_NAMES)
    css, js = plugin_assets(names, implementation="ol")
    return render(
        request,
        "visualizador.html",
        {
            "config": payload,
            "plugin_css": css,
            "plugin_js": js,
            "status": status,
        },
        status=status,
    )


def _js_query(request: HttpRequest) -> str:
    pairs = [
        (key, value)
        for key, value in parse_qsl(request.META.get("QUERY_STRING", ""), keep_blank_values=True)
        if key.casefold() not in {"implementation", "impl"}
    ]
    if not any(key.casefold() == "container" for key, _ in pairs):
        pairs.insert(0, ("container", "map"))
    return urlencode(pairs, doseq=True)


__all__ = [
    "DEFAULT_IMPLEMENTATION",
    "DEFAULT_LAYERS",
    "DEFAULT_PLUGIN_NAMES",
    "IMPLEMENTATIONS",
    "default_visualizador_payload",
    "implementation_from",
    "render_viewer",
    "render_visualizador",
]
