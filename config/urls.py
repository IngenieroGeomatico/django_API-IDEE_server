"""URLs raíz: salud, API canónica y compatibilidad heredada."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.urls import path

from apps.actions import views as actions_views
from apps.core import views as core_views
from apps.core.problems import InternalError, NotFound, problem_response
from apps.viewers import views as viewers_views
from config.api import api

urlpatterns = [
    path("healthz", core_views.healthz, name="healthz"),
    path("readyz", core_views.readyz, name="readyz"),
    path("api/v1/", api.urls),
    # Fachada heredada de acciones y recursos (cliente API-IDEE 1.1.0).
    path("api/actions", actions_views.index, name="legacy-actions"),
    path("api/actions/", actions_views.index),
    path("api/actions/controls", actions_views.controls, name="legacy-actions-controls"),
    path("api/actions/controls/", actions_views.controls),
    path("api/actions/services", actions_views.services, name="legacy-actions-services"),
    path("api/actions/services/", actions_views.services),
    path("api/actions/projection", actions_views.projection, name="legacy-actions-projection"),
    path("api/actions/projection/", actions_views.projection),
    path("api/actions/plugins", actions_views.plugins, name="legacy-actions-plugins"),
    path("api/actions/plugins/", actions_views.plugins),
    path(
        "api/actions/plugins/external",
        actions_views.plugins_external,
        name="legacy-actions-plugins-external",
    ),
    path("api/actions/plugins/external/", actions_views.plugins_external),
    path(
        "api/actions/plugins/external/reload",
        actions_views.plugins_external_reload,
        name="legacy-actions-plugins-external-reload",
    ),
    path("api/actions/plugins/external/reload/", actions_views.plugins_external_reload),
    path("api/actions/resourcesPlugins", actions_views.resources_plugins),
    path("api/actions/resourcesPlugins/", actions_views.resources_plugins),
    path("api/actions/version", actions_views.version, name="legacy-actions-version"),
    path("api/actions/version/", actions_views.version),
    path("api/actions/versions", actions_views.versions, name="legacy-actions-versions"),
    path("api/actions/versions/", actions_views.versions),
    path("api/actions/resources/svg", actions_views.resources_svg, name="legacy-resources-svg"),
    path("api/actions/resources/svg/", actions_views.resources_svg),
    path(
        "api/actions/resources/geodata",
        actions_views.resources_geodata,
        name="legacy-resources-geodata",
    ),
    path("api/actions/resources/geodata/", actions_views.resources_geodata),
    # Visualizadores: rutas nuevas y alias heredados de ``index.jsp``/``visor.jsp``.
    path("", viewers_views.index, name="viewer-index"),
    path("index.jsp", viewers_views.index, name="legacy-index-jsp"),
    path("visualizador", viewers_views.visualizador, name="visualizador"),
    path("visualizador/", viewers_views.visualizador),
    path("visor", viewers_views.visualizador, name="visor"),
    path("visor.jsp", viewers_views.visualizador, name="legacy-visor-jsp"),
    path("api/js", viewers_views.api_js, name="legacy-api-js"),
    path("api/js/", viewers_views.api_js),
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
