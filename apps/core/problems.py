"""Problem Details (RFC 9457) y excepciones HTTP de la API.

Todos los errores de la API deben salir como ``application/problem+json``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)

DEFAULT_TYPE_BASE = "https://componentes.idee.es/api-idee/problems/"
DEFAULT_TITLES: dict[int, str] = {
    400: "Petición no válida",
    401: "No autenticado",
    403: "Prohibido",
    404: "Recurso no encontrado",
    405: "Método no permitido",
    406: "Formato no aceptable",
    409: "Conflicto",
    413: "Contenido demasiado grande",
    414: "URI demasiado larga",
    415: "Tipo de contenido no soportado",
    422: "Entidad no procesable",
    429: "Demasiadas peticiones",
    500: "Error interno del servidor",
    502: "Error del servicio remoto",
    503: "Servicio no disponible",
    504: "Tiempo de espera agotado en el servicio remoto",
}


def _type_base() -> str:
    config = getattr(settings, "API_IDEE", None) or {}
    base = str(config.get("PROBLEM_TYPE_BASE", DEFAULT_TYPE_BASE))
    return base if base.endswith("/") else base + "/"


@dataclass(frozen=True, slots=True)
class InvalidParam:
    """Entrada de ``invalid-params``."""

    name: str
    reason: str
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"name": self.name, "reason": self.reason}
        if self.value is not None:
            texto = str(self.value)
            if len(texto) > 256:
                texto = texto[:253] + "..."
            data["value"] = texto
        return data


class ProblemError(Exception):
    """Excepción base que se serializa como Problem Details."""

    status: int = 400
    slug: str = "invalid-request"
    title: str = "Petición no válida"

    def __init__(
        self,
        detail: str | None = None,
        *,
        status: int | None = None,
        slug: str | None = None,
        title: str | None = None,
        invalid_params: list[InvalidParam] | tuple[InvalidParam, ...] = (),
        headers: dict[str, str] | None = None,
    ) -> None:
        if status is not None:
            self.status = status
        if slug is not None:
            self.slug = slug
        if title is not None:
            self.title = title
        elif self.title == ProblemError.title:
            self.title = DEFAULT_TITLES.get(self.status, self.title)

        self.detail = detail
        self.invalid_params: list[InvalidParam] = list(invalid_params)
        self.headers: dict[str, str] = dict(headers or {})
        super().__init__(detail or self.title)

    @property
    def type_uri(self) -> str:
        return f"{_type_base()}{self.slug}"

    def as_dict(self, *, instance: str | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.type_uri,
            "title": self.title,
            "status": self.status,
        }
        if self.detail:
            data["detail"] = self.detail
        if instance:
            data["instance"] = instance
        if self.invalid_params:
            data["invalid-params"] = [param.as_dict() for param in self.invalid_params]
        return data


class BadRequest(ProblemError):
    status = 400
    slug = "bad-request"


class InvalidParameter(ProblemError):
    status = 400
    slug = "invalid-parameter"
    title = "Parámetro no válido"


class Unauthorized(ProblemError):
    status = 401
    slug = "unauthorized"
    title = "No autenticado"


class Forbidden(ProblemError):
    status = 403
    slug = "forbidden"
    title = "Prohibido"


class NotFound(ProblemError):
    status = 404
    slug = "not-found"
    title = "Recurso no encontrado"


class MethodNotAllowed(ProblemError):
    status = 405
    slug = "method-not-allowed"
    title = "Método no permitido"


class NotAcceptable(ProblemError):
    status = 406
    slug = "not-acceptable"
    title = "Formato no aceptable"


class Conflict(ProblemError):
    status = 409
    slug = "conflict"
    title = "Conflicto"


class PayloadTooLarge(ProblemError):
    status = 413
    slug = "payload-too-large"
    title = "Contenido demasiado grande"


class UriTooLong(ProblemError):
    status = 414
    slug = "uri-too-long"
    title = "URI demasiado larga"


class UnsupportedMediaType(ProblemError):
    status = 415
    slug = "unsupported-media-type"
    title = "Tipo de contenido no soportado"


class UnprocessableEntity(ProblemError):
    status = 422
    slug = "unprocessable-entity"
    title = "Entidad no procesable"


class TooManyRequests(ProblemError):
    status = 429
    slug = "too-many-requests"
    title = "Demasiadas peticiones"


class InternalError(ProblemError):
    status = 500
    slug = "internal-error"
    title = "Error interno del servidor"


class UpstreamError(ProblemError):
    status = 502
    slug = "upstream-error"
    title = "Error del servicio remoto"


class ServiceUnavailable(ProblemError):
    status = 503
    slug = "service-unavailable"
    title = "Servicio no disponible"


class UpstreamTimeout(ProblemError):
    status = 504
    slug = "upstream-timeout"
    title = "Tiempo de espera agotado en el servicio remoto"


def invalid_parameter(
    name: str,
    reason: str,
    value: Any = None,
    *,
    detail: str | None = None,
) -> InvalidParameter:
    """Atajo para un 400 con una única entrada en ``invalid-params``."""
    return InvalidParameter(
        detail or f"El parámetro «{name}» no es válido: {reason}.",
        invalid_params=[InvalidParam(name, reason, value)],
    )


def problem_response(
    problem: ProblemError,
    *,
    request: HttpRequest | None = None,
    instance: str | None = None,
) -> HttpResponse:
    """Serializa una excepción como ``application/problem+json``."""
    if instance is None and request is not None:
        instance = request.get_full_path()

    response = JsonResponse(
        problem.as_dict(instance=instance),
        status=problem.status,
        json_dumps_params={"ensure_ascii": False},
    )
    response["Content-Type"] = "application/problem+json"

    for header, value in problem.headers.items():
        response[header] = value

    request_id = getattr(request, "request_id", None) if request else None
    if request_id:
        response["X-Request-Id"] = request_id

    return response


class ProblemDetailsMiddleware:
    """Convierte cualquier excepción HTTP conocida en Problem Details.

    Django ejecuta el manejo de excepciones de las vistas mediante
    ``process_exception``; el ``try`` de ``__call__`` cubre, además, los fallos
    de middlewares internos.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            return self.get_response(request)
        except Exception as exc:
            response = self._problem_for(request, exc)
            if response is None:
                raise
            return response

    def process_exception(self, request: HttpRequest, exception: Exception) -> HttpResponse | None:
        """Captura las excepciones lanzadas por las vistas."""
        return self._problem_for(request, exception)

    def _problem_for(self, request: HttpRequest, exc: Exception) -> HttpResponse | None:
        if isinstance(exc, ProblemError):
            return problem_response(exc, request=request)
        if isinstance(exc, Http404):
            return problem_response(NotFound(str(exc) or "Recurso no encontrado."), request=request)
        if isinstance(exc, PermissionDenied):
            return problem_response(
                Forbidden("No tiene permisos para acceder a este recurso."), request=request
            )
        if isinstance(exc, SuspiciousOperation):
            return problem_response(BadRequest(str(exc)), request=request)
        if getattr(settings, "DEBUG", False):
            return None
        logger.exception(
            "Excepción no controlada",
            extra={"method": request.method, "path": request.path},
        )
        return problem_response(InternalError("Se ha producido un error interno."), request=request)
