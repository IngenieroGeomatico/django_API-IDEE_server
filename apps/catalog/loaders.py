"""Carga del catálogo versionado de acciones y recursos (plan §3.11)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings

DATA_DIR = Path(__file__).resolve().parent / "data"

PUBLIC_PLACEHOLDER = "${api-idee.url}"
STATIC_PLACEHOLDER = "${api-idee.static_resources.url}"

DEFAULT_STATIC_RESOURCES_URL = "https://componentes.idee.es/estaticos"


class CatalogNotFound(LookupError):
    """El recurso solicitado no existe en el catálogo."""


@lru_cache(maxsize=32)
def _read_json(filename: str) -> Any:
    path = DATA_DIR / filename
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def clear_catalog_cache() -> None:
    """Vacía la caché de lectura (útil en tests y tras un despliegue)."""
    _read_json.cache_clear()


def _config() -> dict[str, Any]:
    return dict(getattr(settings, "API_IDEE", None) or {})


def _public_url() -> str:
    value = str(_config().get("PUBLIC_URL") or "http://localhost:8000/")
    return value if value.endswith("/") else value + "/"


def _static_resources_url() -> str:
    value = str(_config().get("STATIC_RESOURCES_URL") or DEFAULT_STATIC_RESOURCES_URL)
    return value.rstrip("/")


def resolve_placeholders(value: str) -> str:
    """Sustituye los marcadores del catálogo por URLs de este despliegue."""
    return value.replace(PUBLIC_PLACEHOLDER, _public_url()).replace(
        STATIC_PLACEHOLDER, _static_resources_url()
    )


def resolve_tree(value: Any) -> Any:
    if isinstance(value, str):
        return resolve_placeholders(value)
    if isinstance(value, list):
        return [resolve_tree(item) for item in value]
    if isinstance(value, dict):
        return {key: resolve_tree(item) for key, item in value.items()}
    return value


# ---------------------------------------------------------------------------
# Catálogos simples
# ---------------------------------------------------------------------------
def load_controls() -> tuple[str, ...]:
    return tuple(str(item) for item in _read_json("controls.json")["controls"])


def load_services() -> tuple[str, ...]:
    return tuple(str(item) for item in _read_json("services.json")["services"])


def load_versions() -> tuple[str, ...]:
    return tuple(str(item) for item in _read_json("versions.json")["names"])


def load_projection() -> str:
    return str(_read_json("projection.json")["code"])


def load_version() -> dict[str, str]:
    return {str(key): str(value) for key, value in _read_json("version.json").items()}


def versions_payload() -> dict[str, dict[str, dict[str, str]]]:
    """Construye el mapa de versiones publicado por el servidor heredado."""
    payload: dict[str, dict[str, dict[str, str]]] = {}
    for version in load_versions():
        suffix = "" if version == "latest" else f"-{version}"
        config = f"/js/configuration{suffix}.js"
        payload[version] = {
            "ol": {
                "js": f"/js/apiidee{suffix}.ol.min.js",
                "config": config,
                "css": f"/assets/css/apiidee{suffix}.ol.min.css",
            },
            "cesium": {
                "js": f"/js/apiidee{suffix}.cesium.min.js",
                "config": config,
                "css": f"/assets/css/apiidee{suffix}.cesium.min.css",
            },
        }
    return payload


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------
def load_internal_plugins() -> tuple[dict[str, Any], ...]:
    data = _read_json("plugins.json")
    plugins = [resolve_tree(plugin) for plugin in data["plugins"]]
    return tuple(sorted(plugins, key=lambda item: str(item.get("name", ""))))


def load_external_plugin_snapshot() -> tuple[dict[str, Any], ...]:
    data = _read_json("external_plugins.json")
    return tuple(resolve_tree(plugin) for plugin in data if isinstance(plugin, dict))


def plugin_names() -> tuple[str, ...]:
    return tuple(str(plugin["name"]) for plugin in load_internal_plugins())


# ---------------------------------------------------------------------------
# Recursos SVG y geodatos
# ---------------------------------------------------------------------------
def load_resource_collections(kind: str) -> tuple[dict[str, Any], ...]:
    filename = f"resources_{kind}.json"
    path = DATA_DIR / filename
    if not path.is_file():
        raise CatalogNotFound(f"No existe la colección de recursos «{kind}».")
    data = _read_json(filename)
    return tuple(resolve_tree(collection) for collection in data["collections"])


def resources_payload(
    kind: str,
    *,
    name: str | None = None,
    nest_resources: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Devuelve las colecciones filtradas.

    ``nest_resources`` reproduce el defecto del servidor heredado, que envolvía
    la lista de recursos en un array adicional (``[[{...}]]``). La API canónica
    usa la forma plana.
    """
    collections: list[dict[str, Any]] = []
    for collection in load_resource_collections(kind):
        collection_name = str(collection.get("name", ""))
        if name is not None and name != collection_name:
            continue
        resources = list(collection.get("resources") or [])
        collections.append(
            {
                "name": collection_name,
                "resources": [resources] if nest_resources else resources,
            }
        )
        if name is not None:
            break
    return {"collections": collections}


def data_file_mtime(filename: str) -> datetime:
    """Fecha de modificación del fichero de datos, en UTC."""
    path = DATA_DIR / filename
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


__all__ = [
    "DATA_DIR",
    "CatalogNotFound",
    "clear_catalog_cache",
    "data_file_mtime",
    "load_controls",
    "load_external_plugin_snapshot",
    "load_internal_plugins",
    "load_projection",
    "load_resource_collections",
    "load_services",
    "load_version",
    "load_versions",
    "plugin_names",
    "resolve_placeholders",
    "resolve_tree",
    "resources_payload",
    "versions_payload",
]
