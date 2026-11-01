"""Tests de integración: salud, cabeceras, CORS, límites y OpenAPI."""

from __future__ import annotations

import json

import pytest
from django.http import HttpResponse
from django.test import Client

from apps.core.middleware import SecurityHeadersMiddleware


@pytest.fixture
def client() -> Client:
    return Client()


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ok"}


@pytest.mark.django_db
def test_readyz(client):
    response = client.get("/readyz")
    assert response.status_code == 200
    assert json.loads(response.content) == {"status": "ready"}


def test_readyz_sin_base_de_datos(client, monkeypatch):
    class BrokenConnection:
        def cursor(self):
            raise RuntimeError("sin conexión")

    monkeypatch.setattr("apps.core.views.connection", BrokenConnection())
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response["Content-Type"] == "application/problem+json"


def test_request_id_generado(client):
    response = client.get("/healthz")
    assert len(response["X-Request-Id"]) == 32


def test_request_id_respetado(client):
    response = client.get("/healthz", headers={"X-Request-Id": "abc-123_DEF.456"})
    assert response["X-Request-Id"] == "abc-123_DEF.456"


def test_request_id_invalido_se_reemplaza(client):
    response = client.get("/healthz", headers={"X-Request-Id": "ab"})
    assert response["X-Request-Id"] != "ab"
    assert len(response["X-Request-Id"]) == 32


def test_cabeceras_de_seguridad(client):
    response = client.get("/healthz")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Frame-Options"] == "SAMEORIGIN"
    assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response["Permissions-Policy"]
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"


def test_csp_en_respuestas_html(rf):
    def get_response(request):
        return HttpResponse("<html><body>hola</body></html>", content_type="text/html")

    response = SecurityHeadersMiddleware(get_response)(rf.get("/"))
    csp = response["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "nonce-" in csp
    assert "object-src 'none'" in csp


def test_csp_no_se_aplica_a_json(client):
    response = client.get("/healthz")
    assert "Content-Security-Policy" not in response


def test_cors_origen_permitido(client):
    response = client.get("/api/v1/", headers={"Origin": "https://www.idee.es"})
    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] in {"*", "https://www.idee.es"}


def test_404_es_problem_json(client):
    response = client.get("/no-existe")
    assert response.status_code == 404
    assert response["Content-Type"] == "application/problem+json"
    body = json.loads(response.content)
    assert body["status"] == 404
    assert body["instance"] == "/no-existe"


def test_url_demasiado_larga(client):
    response = client.get("/healthz?x=" + "a" * 8300)
    assert response.status_code == 414
    assert response["Content-Type"] == "application/problem+json"


def test_demasiados_parametros(client):
    query = "&".join(f"p{index}=1" for index in range(60))
    response = client.get("/healthz?" + query)
    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"


def test_landing(client):
    response = client.get("/api/v1/")
    body = json.loads(response.content)
    assert response.status_code == 200
    assert body["title"] == "API-IDEE"
    rels = {link["rel"] for link in body["links"]}
    assert {"self", "conformance", "service-desc"} <= rels


def test_conformance(client):
    response = client.get("/api/v1/conformance")
    body = json.loads(response.content)
    assert response.status_code == 200
    assert any("ogcapi-features-1" in uri for uri in body["conformsTo"])


def test_openapi(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    body = json.loads(response.content)
    assert body["openapi"].startswith("3.")
    assert body["info"]["title"] == "API-IDEE"


def test_landing_formato_invalido(client):
    response = client.get("/api/v1/?f=xml")
    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    assert json.loads(response.content)["invalid-params"][0]["name"] == "f"


def test_landing_accept_no_soportado(client):
    response = client.get("/api/v1/", headers={"Accept": "application/xml"})
    assert response.status_code == 406
    assert response["Content-Type"] == "application/problem+json"


def test_landing_accept_html_no_soportado(client):
    response = client.get("/api/v1/", headers={"Accept": "text/html"})
    assert response.status_code == 406
