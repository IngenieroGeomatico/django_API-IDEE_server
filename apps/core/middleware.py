"""Middlewares transversales: request-id, límites y cabeceras de seguridad."""

from __future__ import annotations

import logging
import re
import secrets
import time
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .limits import load_limits
from .problems import BadRequest, ProblemDetailsMiddleware, UriTooLong, problem_response

logger = logging.getLogger("apps.core.request")

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,128}$")

CSP_TEMPLATE = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'self'; "
    "form-action 'self'; "
    "img-src 'self' data: blob: https:; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "worker-src 'self' blob:; "
    "connect-src 'self' https:; "
    "script-src 'self' 'nonce-{nonce}' https://*.idee.es https://*.ign.es"
)

PUBLIC_PREFIXES = ("/static/", "/assets/", "/js/", "/plugins/", "/wasm/", "/data/", "/doc/")


class RequestIdMiddleware:
    """Propaga o genera ``X-Request-Id`` y registra la petición."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get("X-Request-Id", "")
        request.request_id = incoming if REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        started = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response["X-Request-Id"] = request.request_id
        logger.info(
            "request",
            extra={
                "request_id": request.request_id,
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


class QueryLimitsMiddleware:
    """Aplica los límites de URL y número de parámetros antes de la vista."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        limits = load_limits()
        full_path = request.get_full_path()
        if len(full_path) > limits.max_url_length:
            return problem_response(
                UriTooLong(f"La URL supera el límite de {limits.max_url_length} caracteres."),
                request=request,
            )

        query_string = request.META.get("QUERY_STRING", "") or ""
        if query_string:
            pairs = query_string.count("&") + 1
            if pairs > limits.max_params:
                return problem_response(
                    BadRequest(
                        f"La petición incluye {pairs} parámetros "
                        f"y el máximo es {limits.max_params}."
                    ),
                    request=request,
                )

        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Añade cabeceras de seguridad, incluida una CSP con nonce."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)

        if "X-Frame-Options" not in response:
            response["X-Frame-Options"] = "SAMEORIGIN"
        response["X-Content-Type-Options"] = "nosniff"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response["Cross-Origin-Opener-Policy"] = "same-origin"

        content_type = response.get("Content-Type", "")
        if content_type.startswith("text/html"):
            response["Content-Security-Policy"] = CSP_TEMPLATE.format(nonce=request.csp_nonce)
        elif request.path.startswith(PUBLIC_PREFIXES):
            response["Cross-Origin-Resource-Policy"] = "cross-origin"

        return response


__all__ = [
    "ProblemDetailsMiddleware",
    "QueryLimitsMiddleware",
    "RequestIdMiddleware",
    "SecurityHeadersMiddleware",
]
