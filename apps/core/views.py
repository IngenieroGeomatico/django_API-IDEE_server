"""Endpoints de salud y disponibilidad."""

from __future__ import annotations

from django.db import connection
from django.http import HttpRequest, HttpResponse

from .http import json_response
from .problems import ServiceUnavailable, problem_response


def healthz(request: HttpRequest) -> HttpResponse:
    """Liveness: no toca dependencias."""
    return json_response({"status": "ok"})


def readyz(request: HttpRequest) -> HttpResponse:
    """Readiness: comprueba la base de datos de la aplicación."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return problem_response(
            ServiceUnavailable("La base de datos no está disponible."),
            request=request,
        )
    return json_response({"status": "ready"})
