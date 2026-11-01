from __future__ import annotations


def test_openapi_available(client):
    r = client.get("/api/v1/openapi.json")
    assert r.status_code == 200
    assert r.json()["openapi"].startswith("3.1")
