"""Pruebas de integración de la fachada heredada y la API canónica."""

from __future__ import annotations

import json

import pytest

from apps.catalog import external


@pytest.fixture(autouse=True)
def _clean_external():
    external.reset_external_cache()
    yield
    external.reset_external_cache()


LEGACY_JSON_ENDPOINTS = [
    "/api/actions",
    "/api/actions/controls",
    "/api/actions/services",
    "/api/actions/projection",
    "/api/actions/plugins",
    "/api/actions/plugins/external",
    "/api/actions/version",
    "/api/actions/versions",
    "/api/actions/resources/svg",
    "/api/actions/resources/geodata",
]

CANONICAL_ENDPOINTS = [
    "/api/v1/actions",
    "/api/v1/actions/controls",
    "/api/v1/actions/services",
    "/api/v1/actions/projection",
    "/api/v1/actions/plugins",
    "/api/v1/actions/plugins/external",
    "/api/v1/actions/version",
    "/api/v1/actions/versions",
    "/api/v1/actions/resourcesPlugins",
    "/api/v1/resources/svg",
    "/api/v1/resources/geodata",
]


@pytest.mark.parametrize("path", LEGACY_JSON_ENDPOINTS)
def test_legacy_declara_javascript_aunque_no_haya_callback(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    json.loads(response.content)
    assert response["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("path", LEGACY_JSON_ENDPOINTS)
def test_legacy_jsonp_validado(client, path):
    response = client.get(path, {"callback": "miCallback"})

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/javascript")
    assert response["Deprecation"] == "true"
    assert response["Sunset"]
    assert response["Cache-Control"] == "no-store"
    body = response.content.decode()
    assert body.startswith("miCallback(")
    assert body.endswith(");")
    json.loads(body[len("miCallback(") : -2])


def test_legacy_jsonp_escapa_html(client):
    response = client.get("/api/actions", {"callback": "cb"})
    body = response.content.decode()

    assert "<" not in body
    assert ">" not in body


def test_legacy_callback_invalido_devuelve_problem(client):
    response = client.get("/api/actions/controls", {"callback": "alert(1)"})

    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    payload = response.json()
    assert payload["status"] == 400
    assert payload["invalid-params"][0]["name"] == "callback"


def test_legacy_tolera_parametros_desconocidos(client):
    response = client.get("/api/actions/controls", {"desconocido": "1"})

    assert response.status_code == 200


def test_legacy_resources_plugins_es_json_sin_callback(client):
    response = client.get("/api/actions/resourcesPlugins")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    payload = response.json()
    assert len(payload) == 30
    assert payload[0]["name"] == "backimglayer"


def test_legacy_resources_plugins_admite_jsonp(client):
    response = client.get("/api/actions/resourcesPlugins", {"callback": "cb"})

    assert response.status_code == 200
    assert response.content.startswith(b"cb(")


def test_legacy_resources_plugins_sirve_el_fichero(client, settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PUBLIC_URL": "http://testserver/",
        "STATIC_RESOURCES_URL": "https://estaticos.test",
    }
    target = tmp_path / "static/plugins/backimglayer/backimglayer-1.0.1.ol.min.js"
    target.parent.mkdir(parents=True)
    target.write_text("console.log('plugin');", encoding="utf-8")

    response = client.get(
        "/api/actions/resourcesPlugins",
        {"name": "backimglayer", "version": "1.1.0", "type": "js"},
    )

    assert response.status_code == 200
    assert response.content == b"console.log('plugin');"
    assert response["Cache-Control"].startswith("public, max-age=")
    assert response["ETag"]


def test_legacy_resources_plugins_304(client, settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PUBLIC_URL": "http://testserver/",
        "STATIC_RESOURCES_URL": "https://estaticos.test",
    }
    target = tmp_path / "static/plugins/backimglayer/backimglayer-1.0.1.ol.min.js"
    target.parent.mkdir(parents=True)
    target.write_text("console.log('plugin');", encoding="utf-8")
    params = {"name": "backimglayer", "version": "1.1.0", "type": "js"}

    first = client.get("/api/actions/resourcesPlugins", params)
    second = client.get(
        "/api/actions/resourcesPlugins",
        params,
        HTTP_IF_NONE_MATCH=first["ETag"],
    )

    assert first.status_code == 200
    assert second.status_code == 304
    assert second.content == b""


def test_legacy_anida_los_recursos(client):
    response = client.get("/api/actions/resources/svg", {"name": "circleIcons"})

    payload = json.loads(response.content)
    resource = payload["collections"][0]["resources"][0][0]
    assert resource["file"] == "accidenteGeografico.svg"


def test_legacy_reload_no_se_cachea(client):
    response = client.get("/api/actions/plugins/external/reload")

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    payload = json.loads(response.content)
    assert payload["success"] is True
    assert payload["count"] == 31


def test_legacy_admite_barra_final(client):
    assert client.get("/api/actions/controls/").status_code == 200
    assert client.get("/api/actions/resources/svg/").status_code == 200


@pytest.mark.parametrize("path", CANONICAL_ENDPOINTS)
def test_canonico_solo_json(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    json.loads(response.content)


def test_canonico_rechaza_callback(client):
    response = client.get("/api/v1/actions/controls", {"callback": "cb"})

    assert response.status_code == 400
    assert response["Content-Type"] == "application/problem+json"
    assert response.json()["invalid-params"][0]["name"] == "callback"


def test_canonico_rechaza_formato_no_json(client):
    response = client.get("/api/v1/actions/controls", HTTP_ACCEPT="text/html")

    assert response.status_code == 406
    assert response["Content-Type"] == "application/problem+json"


def test_canonico_rechaza_parametros_desconocidos(client):
    response = client.get("/api/v1/actions/controls", {"desconocido": "1"})

    assert response.status_code == 400
    assert response.json()["invalid-params"][0]["name"] == "desconocido"


def test_canonico_devuelve_recursos_planos(client):
    response = client.get("/api/v1/resources/svg", {"name": "circleIcons"})

    resource = response.json()["collections"][0]["resources"][0]
    assert resource["file"] == "accidenteGeografico.svg"


def test_canonico_etag_y_304(client):
    first = client.get("/api/v1/actions/controls")

    assert first.status_code == 200
    assert first["ETag"]

    second = client.get("/api/v1/actions/controls", HTTP_IF_NONE_MATCH=first["ETag"])

    assert second.status_code == 304
    assert second.content == b""


def test_canonico_indice_enlaza_los_recursos(client, settings):
    settings.API_IDEE = {**settings.API_IDEE, "PUBLIC_URL": "https://servidor.test/"}

    payload = client.get("/api/v1/actions").json()

    assert len(payload["links"]) == 11
    assert payload["links"][0]["href"].startswith("https://servidor.test/api/v1/")
