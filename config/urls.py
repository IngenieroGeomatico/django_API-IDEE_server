"""URLs raíz: salud, API canónica y compatibilidad heredada."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import path

from apps.core import views as core_views
from apps.core.problems import InternalError, NotFound, problem_response
from config.api import api

urlpatterns = [
    path("healthz", core_views.healthz, name="healthz"),
    path("readyz", core_views.readyz, name="readyz"),
    path("api/v1/", api.urls),
]


def handler400(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    from apps.core.problems import BadRequest

    return problem_response(BadRequest("La petición no es válida."), request=request)


def handler403(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    from apps.core.problems import Forbidden

    return problem_response(Forbidden("No tiene permisos para acceder."), request=request)


def handler404(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return problem_response(NotFound("Recurso no encontrado."), request=request)


def handler500(request: HttpRequest) -> HttpResponse:
    return problem_response(InternalError("Se ha producido un error interno."), request=request)
