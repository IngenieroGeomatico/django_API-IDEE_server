from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from django.conf import settings

from apps.core.limits import load_limits
from apps.core.problems import Forbidden, invalid_parameter


def _config() -> dict:
    return getattr(settings, "API_IDEE", None) or {}


def _allowed_hosts() -> list[str]:
    return list(_config().get("PROXY_ALLOWED_HOSTS") or [])


def _allowed_ports() -> list[str]:
    return list(_config().get("PROXY_ALLOWED_PORTS") or [])


def _is_private_ip(ip: str | int) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast:
        return True
    if addr.is_reserved or addr.is_unspecified:
        return True
    # Metadata endpoints
    return str(addr) in {"169.254.169.254", "fd00:ec2::254"}


def _host_matches(host: str, patterns: list[str]) -> bool:
    host = host.lower()
    if not patterns:
        return True
    for pattern in patterns:
        pattern = pattern.strip().lower()
        if not pattern:
            continue
        if pattern.startswith("*."):
            suffix = pattern[1:]
            if host.endswith(suffix) and host != suffix.lstrip("."):
                return True
        elif host == pattern:
            return True
    return False


def validate_proxy_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        raise invalid_parameter("url", "la URL es obligatoria")
    parsed = urlparse(text)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise invalid_parameter("url", "esquema no permitido; use http o https", text)
    if not parsed.hostname:
        raise invalid_parameter("url", "host no válido", text)
    if parsed.username or parsed.password:
        raise invalid_parameter("url", "no se admiten credenciales en la URL", text)

    hosts = _allowed_hosts()
    if hosts and not _host_matches(parsed.hostname, hosts):
        raise Forbidden("El host no está en la allowlist del proxy.")

    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    ports = _allowed_ports()
    if ports and str(port) not in {str(p).strip() for p in ports}:
        raise Forbidden("El puerto no está permitido por el proxy.")

    # SSRF: resolve and block private/reserved IPs
    limits = load_limits()
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise invalid_parameter("url", "no se pudo resolver el host", text) from exc
    for info in infos:
        ip = info[4][0]
        if _is_private_ip(ip):
            raise Forbidden("El destino resuelve a una dirección no permitida.")

    # Length guard
    if len(text) > limits.max_value_length * 4:
        raise invalid_parameter("url", "la URL supera la longitud máxima", text)

    return text
