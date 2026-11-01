"""Tests de Problem Details (RFC 9457) y del middleware de errores."""

from __future__ import annotations

import json

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import override_settings

from apps.core.problems import (
    BadRequest,
    InvalidParam,
    NotFound,
    ProblemDetailsMiddleware,
    ProblemError,
    UnprocessableEntity,
    problem_response,
)


def test_problem_as_dict_completo():
    problem = UnprocessableEntity(
        "Falta un campo obligatorio.",
        invalid_params=[InvalidParam("nombre", "es obligatorio", "abc")],
    )
    data = problem.as_dict(instance="/api/v1/recurso")
    assert data["type"].endswith("/unprocessable-entity")
    assert data["title"] == "Entidad no procesable"
    assert data["status"] == 422
    assert data["instance"] == "/api/v1/recurso"
    assert data["invalid-params"] == [
        {"name": "nombre", "reason": "es obligatorio", "value": "abc"}
    ]


def test_problem_sin_detalle_ni_invalid_params():
    data = BadRequest().as_dict()
    assert "detail" not in data
    assert "invalid-params" not in data


def test_valor_largo_se_recorta():
    data = BadRequest(invalid_params=[InvalidParam("x", "largo", "a" * 500)]).as_dict()
    assert len(data["invalid-params"][0]["value"]) == 256


def test_problem_response_content_type(make_request):
    response = problem_response(NotFound("No existe."), request=make_request("/x"))
    assert response.status_code == 404
    assert response["Content-Type"] == "application/problem+json"
    body = json.loads(response.content)
    assert body["status"] == 404
    assert body["instance"] == "/x"


def test_type_uri_configurable():
    with override_settings(API_IDEE={"PROBLEM_TYPE_BASE": "https://example.test/p/"}):
        assert BadRequest().type_uri == "https://example.test/p/bad-request"


def _raising_middleware(exc: Exception):
    def get_response(request):
        raise exc

    return ProblemDetailsMiddleware(get_response)


def test_middleware_convierte_problem_error(make_request):
    request = make_request("/api/v1/x")
    response = _raising_middleware(BadRequest("mal"))(request)
    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"


def test_middleware_convierte_404(make_request):
    response = _raising_middleware(Http404("nada"))(make_request("/nada"))
    assert response.status_code == 404
    assert json.loads(response.content)["title"] == "Recurso no encontrado"


def test_middleware_convierte_permission_denied(make_request):
    response = _raising_middleware(PermissionDenied())(make_request("/privado"))
    assert response.status_code == 403


def test_middleware_error_inesperado_en_produccion(make_request):
    request = make_request("/api/v1/x")
    with override_settings(DEBUG=False):
        response = _raising_middleware(RuntimeError("boom"))(request)
    assert response.status_code == 500
    assert json.loads(response.content)["status"] == 500


def test_middleware_error_inesperado_en_debug_se_propaga(make_request):
    with override_settings(DEBUG=True), pytest.raises(RuntimeError):
        _raising_middleware(RuntimeError("boom"))(make_request("/api/v1/x"))


def test_problem_hereda_de_exception():
    with pytest.raises(ProblemError):
        raise BadRequest("x")
