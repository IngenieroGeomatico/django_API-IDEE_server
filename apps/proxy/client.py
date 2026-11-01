from __future__ import annotations

import httpx
from django.conf import settings

from apps.core.limits import load_limits

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "set-cookie",
}


def _limits():
    return load_limits()


def _config():
    return getattr(settings, "API_IDEE", None) or {}


def _timeout():
    return float(_config().get("PROXY_TIMEOUT", _limits().proxy_timeout))


def _max_bytes():
    return int(_config().get("PROXY_MAX_BYTES", _limits().proxy_max_bytes))


def _max_redirects():
    return int(_config().get("PROXY_MAX_REDIRECTS", 3))


BLOCKED_REQUEST_HEADERS = {"cookie", "authorization", "host", "content-length"}


def _forward_request_headers(request) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() in BLOCKED_REQUEST_HEADERS or key.lower() in HOP_BY_HOP:
            continue
        headers[key] = value
    return headers


def fetch_stream(url: str, method: str = "GET", *, headers=None, content=None):
    """Devuelve (status_code, headers_dict, iterator) con streaming y límite de bytes."""
    from .validators import validate_proxy_url

    validate_proxy_url(url)
    timeout = _timeout()
    max_bytes = _max_bytes()
    max_redirects = _max_redirects()
    headers = dict(headers or {})
    current_url = url
    redirect_count = 0

    while True:
        client = httpx.Client(timeout=timeout, follow_redirects=False)
        try:
            req = client.build_request(
                method.upper(), current_url, headers=headers, content=content
            )
            response = client.send(req, stream=True)
        except Exception:
            client.close()
            raise

        if response.status_code in {301, 302, 303, 307, 308} and "location" in response.headers:
            location = response.headers["location"]
            response.close()
            client.close()
            from urllib.parse import urljoin

            next_url = urljoin(current_url, location)
            validate_proxy_url(next_url)
            current_url = next_url
            redirect_count += 1
            if redirect_count > max_redirects:
                raise ValueError("Demasiadas redirecciones")
            # Convert POST to GET on 301/302/303
            if response.status_code in {301, 302, 303} and method.upper() == "POST":
                method = "GET"
                content = None
            continue

        # Prepare headers (exclude hop-by-hop)
        out_headers = {}
        for key, value in response.headers.items():
            if key.lower() in HOP_BY_HOP:
                continue
            out_headers[key.title()] = value

        def iterator(response=response, client=client):
            total = 0
            try:
                for chunk in response.iter_bytes(chunk_size=8192):
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Respuesta supera el límite de tamaño")
                    yield chunk
            finally:
                response.close()
                client.close()

        return response.status_code, out_headers, iterator()


def fetch_bytes(url: str, method: str = "GET", *, headers=None, content=None):
    status, headers, iterator = fetch_stream(url, method, headers=headers, content=content)
    data = bytearray()
    for chunk in iterator:
        data.extend(chunk)
    return status, headers, bytes(data)
