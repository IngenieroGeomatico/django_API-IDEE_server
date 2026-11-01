from __future__ import annotations

import json


def test_index_renders_map(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b'id="map"' in r.content


def test_index_jsp_alias(client):
    r = client.get("/index.jsp")
    assert r.status_code == 200


def test_visualizador_renders_mapjs(client):
    r = client.get("/visualizador")
    assert r.status_code == 200
    assert b'id="mapjs"' in r.content


def test_visor_alias(client):
    r = client.get("/visor")
    assert r.status_code == 200


def test_visor_jsp_alias(client):
    r = client.get("/visor.jsp")
    assert r.status_code == 200


def test_api_js_get_content_type(client):
    r = client.get("/api/js")
    assert r.status_code == 200
    assert "application/javascript" in r["Content-Type"]


def test_api_js_post_requires_json(client):
    r = client.post("/api/js", data="{}", content_type="text/plain")
    assert r.status_code == 415


def test_api_js_post_works(client):
    r = client.post(
        "/api/js",
        data=json.dumps({"layers": ["QUICK*c"]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert b"IDEE.map" in r.content


def test_api_js_deprecation_header(client):
    r = client.get("/api/js")
    assert r["Deprecation"] == "true"


def test_csp_nonce_on_visualizador(client):
    r = client.get("/visualizador")
    csp = r.get("Content-Security-Policy", "")
    assert "nonce-" in csp
