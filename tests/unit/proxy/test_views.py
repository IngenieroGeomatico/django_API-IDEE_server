from __future__ import annotations

import httpx
import pytest
import respx


@pytest.fixture(autouse=True)
def _allow(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PROXY_ALLOWED_HOSTS": ["*.ign.es"],
        "PROXY_ALLOWED_PORTS": ["80", "443"],
    }


def test_proxy_canonical_get(client):
    with respx.mock:
        respx.get("https://www.ign.es/x").mock(
            return_value=httpx.Response(200, text="hello", headers={"Content-Type": "text/plain"})
        )
        r = client.get("/api/v1/proxy?url=https://www.ign.es/x")
        assert r.status_code == 200
        assert b"hello" in b"".join(r.streaming_content)
        assert r["X-Upstream-Status"] == "200"


def test_proxy_legacy_jsonp(client):
    with respx.mock:
        respx.get("https://www.ign.es/x").mock(
            return_value=httpx.Response(200, text="hello", headers={"Content-Type": "text/plain"})
        )
        r = client.get("/api/proxy?url=https://www.ign.es/x&callback=cb")
        assert r.status_code == 200
        assert r.content.startswith(b"cb(")


def test_proxy_image(client):
    with respx.mock:
        respx.get("https://www.ign.es/img.png").mock(
            return_value=httpx.Response(
                200, content=b"\x89PNG", headers={"Content-Type": "image/png"}
            )
        )
        url = "/api/proxy/image?url=https://www.ign.es/img.png"
        r = client.get(url)
        assert r.status_code == 200
        assert r["Content-Type"] == "image/png"
