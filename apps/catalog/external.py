"""Plugins externos: lista remota con TTL, allowlist y respaldo local (plan §3.11)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any
from urllib.parse import urlparse

import httpx
from django.conf import settings

from .loaders import load_external_plugin_snapshot

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_HOSTS = ("*.idee.es", "*.ign.es", "*.cnig.es")
DEFAULT_TIMEOUT = 5.0
DEFAULT_TTL = 300.0
DEFAULT_MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class ExternalPlugins:
    """Estado de la lista de plugins externos."""

    names: tuple[str, ...] = ()
    resources: tuple[dict[str, Any], ...] = ()
    source: str = "snapshot"
    fetched_at: float = 0.0
    errors: tuple[str, ...] = field(default=())


_cache: ExternalPlugins | None = None


def _config() -> dict[str, Any]:
    return dict(getattr(settings, "API_IDEE", None) or {})


def _base_url() -> str:
    return str(_config().get("EXTERNAL_PLUGINS_BASE_URL") or "").rstrip("/")


def _allowed_hosts() -> tuple[str, ...]:
    raw = _config().get("EXTERNAL_PLUGINS_ALLOWED_HOSTS")
    if isinstance(raw, str):
        values = [item.strip() for item in raw.split(",") if item.strip()]
    elif raw:
        values = [str(item) for item in raw]
    else:
        values = list(DEFAULT_ALLOWED_HOSTS)
    return tuple(values)


def is_allowed_url(url: str) -> bool:
    """Comprueba que la URL remota pertenece a la allowlist configurada."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return any(fnmatch(host, pattern.lower()) for pattern in _allowed_hosts())


def _snapshot() -> ExternalPlugins:
    entries = load_external_plugin_snapshot()
    names = sorted(
        {
            str(entry.get("name", "")).lower()
            for entry in entries
            if entry.get("name") and not _is_obsolete(entry.get("obsolete"))
        }
    )
    return ExternalPlugins(names=tuple(names), source="snapshot", fetched_at=time.time())


def _is_obsolete(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _fetch_json(url: str) -> Any:
    config = _config()
    timeout = float(config.get("EXTERNAL_PLUGINS_TIMEOUT", DEFAULT_TIMEOUT))
    max_bytes = int(config.get("EXTERNAL_PLUGINS_MAX_BYTES", DEFAULT_MAX_BYTES))
    if not is_allowed_url(url):
        raise ValueError(f"Host no permitido para plugins externos: {url}")

    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        response = client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        if len(response.content) > max_bytes:
            raise ValueError(f"Respuesta demasiado grande: {url}")
        return response.json()


def _load_remote(base_url: str) -> ExternalPlugins:
    errors: list[str] = []
    names: set[str] = set()
    resources: list[dict[str, Any]] = []

    try:
        catalogue = _fetch_json(f"{base_url}/data/plugins.json")
        if isinstance(catalogue, list):
            for entry in catalogue:
                if not isinstance(entry, dict) or _is_obsolete(entry.get("obsolete")):
                    continue
                name = entry.get("name")
                if name:
                    names.add(str(name).lower())
    except Exception as exc:
        errors.append(f"plugins.json: {exc}")
        logger.warning("No se pudo leer la lista de plugins externos: %s", exc)

    try:
        catalogue = _fetch_json(f"{base_url}/data/resourcesPlugins.json")
        if isinstance(catalogue, dict):
            resources = [
                plugin for plugin in catalogue.get("plugins", []) if isinstance(plugin, dict)
            ]
    except Exception as exc:
        errors.append(f"resourcesPlugins.json: {exc}")
        logger.info("No se pudo leer resourcesPlugins.json externo: %s", exc)

    return ExternalPlugins(
        names=tuple(sorted(names)),
        resources=tuple(resources),
        source="remote",
        fetched_at=time.time(),
        errors=tuple(errors),
    )


def get_external_plugins(*, force: bool = False) -> ExternalPlugins:
    """Devuelve la lista externa vigente, respetando el TTL configurado."""
    global _cache

    ttl = float(_config().get("EXTERNAL_PLUGINS_TTL", DEFAULT_TTL))
    if not force and _cache is not None and (time.time() - _cache.fetched_at) < ttl:
        return _cache

    base_url = _base_url()
    if base_url:
        state = _load_remote(base_url)
        # Si la descarga falla por completo, se conserva el respaldo local.
        if not state.names and not state.resources:
            snapshot = _snapshot()
            state = ExternalPlugins(
                names=snapshot.names,
                resources=(),
                source="snapshot",
                fetched_at=state.fetched_at,
                errors=state.errors,
            )
    else:
        state = _snapshot()

    _cache = state
    return state


def reload_external_plugins() -> ExternalPlugins:
    """Fuerza la recarga y devuelve el nuevo estado."""
    return get_external_plugins(force=True)


def reset_external_cache() -> None:
    """Limpia la caché de proceso (tests y cambios de configuración)."""
    global _cache
    _cache = None


__all__ = [
    "ExternalPlugins",
    "get_external_plugins",
    "is_allowed_url",
    "reload_external_plugins",
    "reset_external_cache",
]
