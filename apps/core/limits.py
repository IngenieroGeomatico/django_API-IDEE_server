"""Límites configurables de la API (plan §4.13)."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

DEFAULTS: dict[str, int | float] = {
    "MAX_URL_LENGTH": 8192,
    "MAX_PARAMS": 50,
    "MAX_VALUE_LENGTH": 2048,
    "DEFAULT_LIMIT": 100,
    "MAX_LIMIT": 10_000,
    "MAX_OFFSET": 1_000_000,
    "MAX_LAYERS": 50,
    "MAX_CQL_DEPTH": 20,
    "MAX_BODY_BYTES": 10 * 1024 * 1024,
    "PROXY_TIMEOUT": 15.0,
    "PROXY_MAX_BYTES": 10 * 1024 * 1024,
    "PROXY_MAX_REDIRECTS": 3,
}


@dataclass(frozen=True, slots=True)
class Limits:
    """Límites efectivos de una petición."""

    max_url_length: int = 8192
    max_params: int = 50
    max_value_length: int = 2048
    default_limit: int = 100
    max_limit: int = 10_000
    max_offset: int = 1_000_000
    max_layers: int = 50
    max_cql_depth: int = 20
    max_body_bytes: int = 10 * 1024 * 1024
    proxy_timeout: float = 15.0
    proxy_max_bytes: int = 10 * 1024 * 1024
    proxy_max_redirects: int = 3

    @classmethod
    def from_settings(cls) -> Limits:
        config = getattr(settings, "API_IDEE", None) or {}

        def get(key: str) -> int | float:
            return config.get(key, DEFAULTS[key])

        return cls(
            max_url_length=int(get("MAX_URL_LENGTH")),
            max_params=int(get("MAX_PARAMS")),
            max_value_length=int(get("MAX_VALUE_LENGTH")),
            default_limit=int(get("DEFAULT_LIMIT")),
            max_limit=int(get("MAX_LIMIT")),
            max_offset=int(get("MAX_OFFSET")),
            max_layers=int(get("MAX_LAYERS")),
            max_cql_depth=int(get("MAX_CQL_DEPTH")),
            max_body_bytes=int(get("MAX_BODY_BYTES")),
            proxy_timeout=float(get("PROXY_TIMEOUT")),
            proxy_max_bytes=int(get("PROXY_MAX_BYTES")),
            proxy_max_redirects=int(get("PROXY_MAX_REDIRECTS")),
        )


def load_limits() -> Limits:
    """Devuelve los límites vigentes (sin caché, para respetar override_settings)."""
    return Limits.from_settings()
