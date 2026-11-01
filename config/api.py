"""Instancia de Django Ninja para ``/api/v1`` y traducción de errores."""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from ninja import NinjaAPI
from ninja.errors import ValidationError as NinjaValidationError

from apps.core.api import router as core_router
from apps.core.problems import (
    InternalError,
    InvalidParam,
    NotFound,
    ProblemError,
    UnprocessableEntity,
    problem_response,
)

logger = logging.getLogger("apps.api")

api = NinjaAPI(
    title="API-IDEE",
    version="1.0.0",
    description=(
        "Servicio compatible con el cliente API-IDEE 1.1.0. "
        "La fachada heredada vive en /api/; la API canónica en /api/v1/."
    ),
    urls_namespace="api-v1",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

api.add_router("", core_router)


@api.exception_handler(ProblemError)
def handle_problem(request: HttpRequest, exc: ProblemError) -> HttpResponse:
    return problem_response(exc, request=request)


@api.exception_handler(NinjaValidationError)
def handle_validation(request: HttpRequest, exc: NinjaValidationError) -> HttpResponse:
    invalid = [
        InvalidParam(
            name=".".join(str(part) for part in error.get("loc", ())) or "body",
            reason=str(error.get("msg", "valor no válido")),
        )
        for error in exc.errors
    ]
    return problem_response(
        UnprocessableEntity("La petición no cumple el esquema esperado.", invalid_params=invalid),
        request=request,
    )


@api.exception_handler(Http404)
def handle_404(request: HttpRequest, exc: Http404) -> HttpResponse:
    return problem_response(NotFound("Recurso no encontrado."), request=request)


@api.exception_handler(Exception)
def handle_unexpected(request: HttpRequest, exc: Exception) -> HttpResponse:
    if getattr(settings, "DEBUG", False):
        raise exc
    logger.exception(
        "Excepción no controlada en la API",
        extra={"method": request.method, "path": request.path},
    )
    return problem_response(InternalError("Se ha producido un error interno."), request=request)
