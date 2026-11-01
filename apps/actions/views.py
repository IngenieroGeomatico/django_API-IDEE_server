"""Fachada heredada de ``/api/actions/*`` (JSON y JSONP validado)."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from apps.core.http import JSON_MEDIA
from apps.core.params import Parametros

from . import service
from .responses import asset_response, legacy_response


def index(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.action_index(),
        cache_control=service.catalog_cache_control(),
    )


def controls(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.controls(),
        cache_control=service.catalog_cache_control(),
    )


def services(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.services(),
        cache_control=service.catalog_cache_control(),
    )


def projection(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.projection(),
        cache_control=service.catalog_cache_control(),
    )


def plugins(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.plugins(),
        cache_control=service.catalog_cache_control(),
        last_modified=service.plugins_last_modified(),
    )


def plugins_external(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.external_plugins(),
        cache_control=service.catalog_cache_control(),
    )


def plugins_external_reload(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.reload_plugins(),
        cache_control="no-store",
    )


def version(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.version(),
        cache_control=service.catalog_cache_control(),
    )


def versions(request: HttpRequest) -> HttpResponse:
    return legacy_response(
        request,
        service.versions(),
        cache_control=service.catalog_cache_control(),
    )


def resources_svg(request: HttpRequest) -> HttpResponse:
    name = Parametros.desde_request(request).texto("name")
    return legacy_response(
        request,
        service.resources("svg", name=name, nest=True),
        cache_control=service.resources_cache_control(),
        last_modified=service.resources_last_modified("svg"),
    )


def resources_geodata(request: HttpRequest) -> HttpResponse:
    name = Parametros.desde_request(request).texto("name")
    return legacy_response(
        request,
        service.resources("geodata", name=name, nest=True),
        cache_control=service.resources_cache_control(),
        last_modified=service.resources_last_modified("geodata"),
    )


def resources_plugins(request: HttpRequest) -> HttpResponse:
    params = Parametros.desde_request(request)
    name = params.texto("name")
    version = params.texto("version")
    asset_type = params.texto("type")

    if name and version and asset_type:
        asset = service.plugin_asset(name, version, asset_type)
        return asset_response(request, asset, cache_control=service.asset_cache_control())

    return legacy_response(
        request,
        service.resources_plugins(name=name, version=version),
        cache_control=service.catalog_cache_control(),
        last_modified=service.plugins_last_modified(),
        content_type=JSON_MEDIA,
        params=params,
    )


__all__ = [
    "controls",
    "index",
    "plugins",
    "plugins_external",
    "plugins_external_reload",
    "projection",
    "resources_geodata",
    "resources_plugins",
    "resources_svg",
    "services",
    "version",
    "versions",
]
