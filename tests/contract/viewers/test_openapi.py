from __future__ import annotations

import pytest

VIEWER_PATHS = {
    "/api/v1/viewers",
    "/api/v1/viewers/{viewer_id}",
}


@pytest.fixture
def spec(client):
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    return response.json()


def test_viewer_paths_documented(spec):
    assert set(spec["paths"]) >= VIEWER_PATHS
