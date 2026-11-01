from __future__ import annotations


def test_actions_endpoint(client):
    r = client.get("/api/v1/actions")
    assert r.status_code == 200


def test_actions_controls(client):
    r = client.get("/api/v1/actions/controls")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
