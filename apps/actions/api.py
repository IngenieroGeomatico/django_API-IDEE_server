"""API canónica ``/api/v1/actions`` y ``/api/v1/resources`` (plan §3.11)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema
from pydantic import Field

from apps.core.params import Parametros

from . import service
from .responses import asset_response, canonical_response

router = Router(tags=["actions"], by_alias=True)

F_PARAM = {
    "name": "f",
    "in": "query",
    "required": False,
    "description": "Formato de respuesta. Solo se admite JSON.",
    "schema": {"type": "string", "enum": ["json"]},
}
NAME_PARAM = {
    "name": "name",
    "in": "query",
    "required": False,
    "description": "Nombre del recurso o plugin.",
    "schema": {"type": "string"},
}
VERSION_PARAM = {
    "name": "version",
    "in": "query",
    "required": False,
    "description": "Versión de API-IDEE del plugin.",
    "schema": {"type": "string"},
}
TYPE_PARAM = {
    "name": "type",
    "in": "query",
    "required": False,
    "description": "Tipo de recurso del plugin.",
    "schema": {"type": "string", "enum": ["api-idee", "css", "js"]},
}


class Link(Schema):
    href: str
    rel: str
    type: str


class ActionIndex(Schema):
    title: str
    links: list[Link]


class Projection(Schema):
    code: str


class VersionInfo(Schema):
    date: str
    number: str
    number_ol: str = Field(alias="number-ol")
    number_cesium: str = Field(alias="number-cesium")


class VersionEntry(Schema):
    js: str
    config: str
    css: str


class PluginResource(Schema):
    api_idee: str = Field(alias="api-idee")
    js: str
    css: str


class PluginEntry(Schema):
    name: str
    obsolete: str
    resources: list[PluginResource]


class ReloadResult(Schema):
    success: bool
    message: str
    count: int


class ResourceItem(Schema):
    file: str
    url: str


class ResourceCollection(Schema):
    name: str
    resources: list[ResourceItem]


class ResourcePayload(Schema):
    collections: list[ResourceCollection]


# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------
@router.get(
    "/actions",
    response=ActionIndex,
    summary="Índice de acciones",
    openapi_extra={"parameters": [F_PARAM]},
)
def index(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.canonical_index(),
        cache_control=service.catalog_cache_control(),
    )


@router.get(
    "/actions/controls",
    response=list[str],
    summary="Controles disponibles",
    openapi_extra={"parameters": [F_PARAM]},
)
def controls(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.controls(),
        cache_control=service.catalog_cache_control(),
    )


@router.get(
    "/actions/services",
    response=list[str],
    summary="Tipos de capa disponibles",
    openapi_extra={"parameters": [F_PARAM]},
)
def services(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.services(),
        cache_control=service.catalog_cache_control(),
    )


@router.get(
    "/actions/projection",
    response=Projection,
    summary="Proyección por defecto",
    openapi_extra={"parameters": [F_PARAM]},
)
def projection(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.projection(),
        cache_control=service.catalog_cache_control(),
    )


@router.get(
    "/actions/version",
    response=VersionInfo,
    summary="Versión publicada",
    openapi_extra={"parameters": [F_PARAM]},
)
def version(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.version(),
        cache_control=service.catalog_cache_control(),
    )


@router.get(
    "/actions/versions",
    response=dict[str, dict[str, VersionEntry]],
    summary="Versiones",
    openapi_extra={"parameters": [F_PARAM]},
)
def versions(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.versions(),
        cache_control=service.catalog_cache_control(),
    )


@router.get(
    "/actions/plugins",
    response=list[str],
    summary="Plugins internos",
    openapi_extra={"parameters": [F_PARAM]},
)
def plugins(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.plugins(),
        cache_control=service.catalog_cache_control(),
        last_modified=service.plugins_last_modified(),
    )


@router.get(
    "/actions/plugins/external",
    response=list[str],
    summary="Plugins externos disponibles",
    openapi_extra={"parameters": [F_PARAM]},
)
def plugins_external(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.external_plugins(),
        cache_control=service.catalog_cache_control(),
    )


@router.get(
    "/actions/plugins/external/reload",
    response=ReloadResult,
    summary="Recargar plugins externos",
    openapi_extra={"parameters": [F_PARAM]},
)
def plugins_external_reload(request: HttpRequest) -> HttpResponse:
    return canonical_response(
        request,
        service.reload_plugins(),
        cache_control="no-store",
    )


@router.get(
    "/actions/resourcesPlugins",
    response=list[PluginEntry] | str,
    summary="Recursos de plugins",
    openapi_extra={"parameters": [F_PARAM, NAME_PARAM, VERSION_PARAM, TYPE_PARAM]},
)
def resources_plugins(request: HttpRequest) -> HttpResponse:
    params = Parametros.desde_request(request)
    name = params.texto("name")
    version = params.texto("version")
    asset_type = params.texto("type")

    if name and version and asset_type:
        asset = service.plugin_asset(name, version, asset_type)
        return asset_response(request, asset, cache_control=service.asset_cache_control())

    return canonical_response(
        request,
        service.resources_plugins(name=name, version=version),
        cache_control=service.catalog_cache_control(),
        last_modified=service.plugins_last_modified(),
        allowed=("f", "name", "version", "type"),
        params=params,
    )


@router.get(
    "/resources/svg",
    response=ResourcePayload,
    summary="Colecciones SVG",
    openapi_extra={"parameters": [F_PARAM, NAME_PARAM]},
)
def resources_svg(request: HttpRequest) -> HttpResponse:
    params = Parametros.desde_request(request)
    name = params.texto("name")
    return canonical_response(
        request,
        service.resources("svg", name=name),
        cache_control=service.resources_cache_control(),
        last_modified=service.resources_last_modified("svg"),
        allowed=("f", "name"),
        params=params,
    )


@router.get(
    "/resources/geodata",
    response=ResourcePayload,
    summary="Colecciones de geodatos",
    openapi_extra={"parameters": [F_PARAM, NAME_PARAM]},
)
def resources_geodata(request: HttpRequest) -> HttpResponse:
    params = Parametros.desde_request(request)
    name = params.texto("name")
    return canonical_response(
        request,
        service.resources("geodata", name=name),
        cache_control=service.resources_cache_control(),
        last_modified=service.resources_last_modified("geodata"),
        allowed=("f", "name"),
        params=params,
    )


__all__ = ["router"]
