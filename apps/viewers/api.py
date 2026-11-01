"""API canónica de visualizadores: ``/api/v1/viewers`` (plan §3.10)."""

from __future__ import annotations

import uuid
from typing import Any

from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from pydantic import Field

from apps.core.http import json_response, link_header
from apps.core.limits import load_limits
from apps.core.params import Parametros
from apps.core.problems import NotFound, invalid_parameter
from apps.core.validators import parse_enum

from .builder import ViewConfig, validate_container, viewer_payload
from .layers import SUPPORTED_TYPES, LayerConfig
from .models import Viewer
from .render import render_visualizador
from .validate import ControlConfig, PluginConfig, normalize_controls, normalize_plugins

router = Router(tags=["viewers"], by_alias=True)

F_PARAM = {
    "name": "f",
    "in": "query",
    "required": False,
    "description": "Formato de respuesta.",
    "schema": {"type": "string", "enum": ["json", "html"]},
}


class ViewerIn(Schema):
    """Cuerpo de ``POST /api/v1/viewers``."""

    container: str = "map"
    view: ViewConfig = Field(default_factory=ViewConfig)
    layers: list[LayerConfig] = Field(default_factory=list)
    controls: list[str | ControlConfig] = Field(default_factory=list)
    plugins: list[str | PluginConfig] = Field(default_factory=list)
    configuration: dict[str, Any] | None = None


class ViewerLink(Schema):
    href: str
    rel: str
    type: str


class ViewerResource(Schema):
    id: str
    created_at: str = Field(alias="createdAt")
    links: list[ViewerLink]
    container: str
    view: dict[str, Any]
    layers: list[dict[str, Any]]
    controls: list[dict[str, Any]]
    plugins: list[dict[str, Any]]
    configuration: dict[str, Any] | None = None


def _format(value: str) -> str:
    chosen = parse_enum(value or "json", ("json", "html"), name="f")
    return chosen or "json"


def _normalize(
    payload: ViewerIn,
) -> tuple[dict[str, Any], ViewConfig, list[LayerConfig], list[ControlConfig], list[PluginConfig]]:
    container = validate_container(payload.container)
    limits = load_limits()
    if len(payload.layers) > limits.max_layers:
        raise invalid_parameter(
            "layers",
            f"no se admiten más de {limits.max_layers} capas",
            len(payload.layers),
        )

    unsupported = sorted(
        {layer.type.value for layer in payload.layers if layer.type not in SUPPORTED_TYPES}
    )
    if unsupported:
        raise invalid_parameter(
            "layers",
            "tipos no admitidos en la API canónica: " + ", ".join(unsupported),
            unsupported,
        )
    if not payload.layers:
        raise invalid_parameter("layers", "el visualizador debe incluir al menos una capa")

    controls = normalize_controls(payload.controls)
    plugins = normalize_plugins(payload.plugins)
    if payload.configuration is not None and not isinstance(payload.configuration, dict):
        raise invalid_parameter("configuration", "debe ser un objeto JSON")

    stored: dict[str, Any] = {
        "container": container,
        "view": payload.view.dump(),
        "layers": [layer.dump() for layer in payload.layers],
        "controls": [control.dump() for control in controls],
        "plugins": [plugin.dump() for plugin in plugins],
    }
    if payload.configuration is not None:
        stored["configuration"] = payload.configuration
    return stored, payload.view, payload.layers, controls, plugins


def _stored_models(
    config: dict[str, Any],
) -> tuple[ViewConfig, list[LayerConfig], list[ControlConfig], list[PluginConfig]]:
    view = ViewConfig.model_validate(config.get("view") or {})
    layers = [LayerConfig.model_validate(item) for item in config.get("layers") or []]
    controls = [ControlConfig.model_validate(item) for item in config.get("controls") or []]
    plugins = [PluginConfig.model_validate(item) for item in config.get("plugins") or []]
    return view, layers, controls, plugins


def _payload(config: dict[str, Any]) -> dict[str, Any]:
    view, layers, controls, plugins = _stored_models(config)
    payload = viewer_payload(
        container=str(config.get("container") or "map"),
        view=view,
        layers=layers,
        controls=controls,
        plugins=plugins,
    )
    if config.get("configuration"):
        payload["configuration"] = config["configuration"]
    return payload


def _resource(viewer: Viewer) -> dict[str, Any]:
    config = dict(viewer.config)
    base = f"/api/v1/viewers/{viewer.id}"
    return {
        "id": str(viewer.id),
        "createdAt": viewer.created_at.isoformat(),
        "links": [
            {"href": base, "rel": "self", "type": "application/json"},
            {"href": base, "rel": "alternate", "type": "text/html"},
        ],
        **config,
    }


def _response(
    request: HttpRequest,
    viewer: Viewer,
    *,
    status: int,
    chosen: str,
) -> HttpResponse:
    location = f"/api/v1/viewers/{viewer.id}"
    if chosen == "html":
        config = dict(viewer.config)
        _view, _layers, _controls, plugins = _stored_models(config)
        response = render_visualizador(
            request,
            payload=_payload(config),
            plugin_names=[plugin.type for plugin in plugins],
            status=status,
        )
    else:
        response = json_response(_resource(viewer), status=status)
    response["Location"] = location
    response["Link"] = link_header(
        [
            {"href": location, "rel": "self", "type": "application/json"},
            {"href": location, "rel": "alternate", "type": "text/html"},
        ]
    )
    return response


@router.post(
    "/viewers",
    response={201: ViewerResource},
    summary="Crea un visualizador",
    openapi_extra={"parameters": [F_PARAM]},
)
def create_viewer(request: HttpRequest, payload: ViewerIn) -> HttpResponse:
    chosen = _format(Parametros.desde_request(request).texto("f") or "json")
    stored, *_ = _normalize(payload)
    viewer = Viewer.objects.create(config=stored)
    return _response(request, viewer, status=201, chosen=chosen)


@router.get(
    "/viewers/{viewer_id}",
    response=ViewerResource,
    summary="Recupera un visualizador",
    openapi_extra={"parameters": [F_PARAM]},
)
def get_viewer(request: HttpRequest, viewer_id: str) -> HttpResponse:
    chosen = _format(Parametros.desde_request(request).texto("f") or "json")
    try:
        identifier = uuid.UUID(viewer_id)
    except (ValueError, AttributeError) as exc:
        raise NotFound("El visualizador solicitado no existe.") from exc

    viewer = Viewer.objects.filter(pk=identifier).first()
    if viewer is None:
        raise NotFound("El visualizador solicitado no existe.")
    return _response(request, viewer, status=200, chosen=chosen)


__all__ = ["ViewerIn", "ViewerResource", "create_viewer", "get_viewer", "router"]
