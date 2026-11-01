"""Lógica de las acciones y recursos, compartida por la fachada y la API canónica."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from django.conf import settings

from apps.catalog import loaders
from apps.catalog.external import get_external_plugins, reload_external_plugins
from apps.core.http import etag_for
from apps.core.problems import NotFound, UpstreamError, invalid_parameter

LEGACY_ACTIONS: tuple[str, ...] = (
    "/controls",
    "/services",
    "/version",
    "/projection",
    "/plugins",
    "/plugins/external",
    "/plugins/external/reload",
    "/resourcesPlugins",
    "/versions",
    "/resources/svg",
    "/resources/geodata",
    "/../../doc",
    "/../../doc/ol",
    "/../../doc/cesium",
)

CANONICAL_ACTIONS: tuple[tuple[str, str], ...] = (
    ("actions/controls", "controls"),
    ("actions/services", "services"),
    ("actions/projection", "projection"),
    ("actions/plugins", "plugins"),
    ("actions/plugins/external", "plugins-external"),
    ("actions/plugins/external/reload", "plugins-external-reload"),
    ("actions/version", "version"),
    ("actions/versions", "versions"),
    ("actions/resourcesPlugins", "resources-plugins"),
    ("resources/svg", "resources-svg"),
    ("resources/geodata", "resources-geodata"),
)

PLUGIN_TYPES = frozenset({"api-idee", "css", "js"})
DEFAULT_ASSET_TIMEOUT = 5.0
DEFAULT_ASSET_MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Asset:
    content: bytes
    media_type: str
    etag: str


def _config() -> dict[str, Any]:
    return dict(getattr(settings, "API_IDEE", None) or {})


def _cache_seconds(key: str, default: int) -> int:
    try:
        return int(_config().get(key, default))
    except (TypeError, ValueError):
        return default


def _public_url() -> str:
    value = str(_config().get("PUBLIC_URL") or "http://localhost:8000/")
    return value if value.endswith("/") else value + "/"


# ---------------------------------------------------------------------------
# Acciones simples
# ---------------------------------------------------------------------------
def action_index() -> list[str]:
    return list(LEGACY_ACTIONS)


def canonical_index() -> dict[str, Any]:
    base = _public_url().rstrip("/")
    links = [
        {
            "href": f"{base}/api/v1/{path}",
            "rel": rel,
            "type": "application/json",
        }
        for path, rel in CANONICAL_ACTIONS
    ]
    return {
        "title": "Acciones y recursos de API-IDEE",
        "links": links,
    }


def controls() -> list[str]:
    return list(loaders.load_controls())


def services() -> list[str]:
    return list(loaders.load_services())


def projection() -> dict[str, str]:
    return {"code": loaders.load_projection()}


def version() -> dict[str, str]:
    return loaders.load_version()


def versions() -> dict[str, dict[str, dict[str, str]]]:
    return loaders.versions_payload()


def plugins() -> list[str]:
    return list(loaders.plugin_names())


def external_plugins() -> list[str]:
    return list(get_external_plugins().names)


def reload_plugins() -> dict[str, Any]:
    state = reload_external_plugins()
    return {
        "success": True,
        "message": "Lista de plugins externos recargada correctamente",
        "count": len(state.names),
    }


def resources(kind: str, *, name: str | None = None, nest: bool = False) -> dict[str, Any]:
    return loaders.resources_payload(kind, name=name, nest_resources=nest)


# ---------------------------------------------------------------------------
# Catálogo de plugins y sus ficheros
# ---------------------------------------------------------------------------
def _plugin_catalog() -> list[dict[str, Any]]:
    external = [
        loaders.resolve_tree(plugin)
        for plugin in get_external_plugins().resources
        if isinstance(plugin, dict) and isinstance(plugin.get("versions"), list)
    ]
    internal = list(loaders.load_internal_plugins())

    merged: dict[str, dict[str, Any]] = {}
    for plugin in external:
        name = str(plugin.get("name", ""))
        if name:
            merged[name] = plugin
    # Los plugins internos tienen prioridad sobre los remotos con el mismo nombre.
    for plugin in internal:
        name = str(plugin.get("name", ""))
        if name:
            merged[name] = plugin

    return sorted(merged.values(), key=lambda item: str(item.get("name", "")))


def resources_plugins(
    *, name: str | None = None, version: str | None = None
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for plugin in _plugin_catalog():
        plugin_name = str(plugin.get("name", ""))
        if name is not None and plugin_name != name:
            continue

        resources = [
            resource
            for resource in plugin.get("versions", [])
            if version is None or str(resource.get("api-idee", "")) == version
        ]
        if version is not None and not resources:
            continue

        results.append(
            {
                "name": plugin_name,
                "obsolete": str(plugin.get("obsolete", "false")),
                "resources": resources,
            }
        )
        if name is not None:
            break
    return results


def _find_plugin_resource(name: str, version: str) -> dict[str, Any]:
    for plugin in _plugin_catalog():
        if str(plugin.get("name", "")) != name:
            continue
        for resource in plugin.get("versions", []):
            if str(resource.get("api-idee", "")) == version:
                return dict(resource)
        break
    raise NotFound(f"No existe el recurso del plugin «{name}» para la versión «{version}».")


def _local_static_path(url: str):
    parsed = urlparse(url)
    if parsed.scheme in {"http", "https"}:
        public = _public_url()
        if not url.startswith(public):
            return None
        path = "/" + url[len(public) :].lstrip("/")
    elif url.startswith("/"):
        path = url
    else:
        return None

    static_root = (settings.BASE_DIR / "static").resolve()
    candidate = (static_root / path.lstrip("/")).resolve()
    if not candidate.is_relative_to(static_root):
        return None
    return candidate if candidate.is_file() else None


def _fetch_asset(url: str, expected_type: str) -> Asset:
    config = _config()
    timeout = float(config.get("PLUGIN_ASSET_TIMEOUT", DEFAULT_ASSET_TIMEOUT))
    max_bytes = int(config.get("PLUGIN_ASSET_MAX_BYTES", DEFAULT_ASSET_MAX_BYTES))

    from apps.catalog.external import is_allowed_url

    if not is_allowed_url(url):
        raise NotFound("El recurso del plugin no está disponible en este despliegue.")

    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise UpstreamError(f"No se pudo descargar el recurso del plugin: {exc}") from exc

    if len(response.content) > max_bytes:
        raise UpstreamError("El recurso del plugin supera el tamaño máximo permitido.")

    media_type = response.headers.get("Content-Type", "").split(";")[0].strip()
    if not media_type or media_type == "application/octet-stream":
        media_type = "text/css" if expected_type == "css" else "application/javascript"
    return Asset(response.content, media_type, etag_for(response.content))


def plugin_asset(name: str, version: str, asset_type: str) -> Asset:
    """Devuelve el fichero JS/CSS (o la versión) asociado a un plugin."""
    if asset_type not in PLUGIN_TYPES:
        raise invalid_parameter(
            "type",
            "tipo no admitido; use uno de: api-idee, css, js",
            asset_type,
        )

    resource = _find_plugin_resource(name, version)
    value = resource.get(asset_type)
    if not value:
        raise NotFound(f"El plugin «{name}» no publica un recurso de tipo «{asset_type}».")

    url = str(value)
    if asset_type == "api-idee":
        payload = url.encode("utf-8")
        return Asset(payload, "text/html; charset=utf-8", etag_for(payload))

    local = _local_static_path(url)
    if local is not None:
        payload = local.read_bytes()
        media_type = "text/css" if asset_type == "css" else "application/javascript"
        return Asset(payload, media_type, etag_for(payload))

    return _fetch_asset(url, asset_type)


# ---------------------------------------------------------------------------
# Fechas de modificación y cabeceras de caché
# ---------------------------------------------------------------------------
def resources_last_modified(kind: str) -> datetime:
    return loaders.data_file_mtime(f"resources_{kind}.json")


def plugins_last_modified() -> datetime:
    return loaders.data_file_mtime("plugins.json")


def catalog_cache_control() -> str:
    return f"public, max-age={_cache_seconds('CATALOG_MAX_AGE', 300)}"


def resources_cache_control() -> str:
    return f"public, max-age={_cache_seconds('RESOURCE_MAX_AGE', 86400)}"


def asset_cache_control() -> str:
    return f"public, max-age={_cache_seconds('PLUGIN_ASSET_MAX_AGE', 3600)}"


def body_etag(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


__all__ = [
    "Asset",
    "action_index",
    "asset_cache_control",
    "canonical_index",
    "catalog_cache_control",
    "controls",
    "external_plugins",
    "plugin_asset",
    "plugins",
    "plugins_last_modified",
    "projection",
    "reload_plugins",
    "resources",
    "resources_cache_control",
    "resources_last_modified",
    "resources_plugins",
    "services",
    "version",
    "versions",
]
