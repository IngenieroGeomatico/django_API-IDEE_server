from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from ninja import Router, Schema

from .views import proxy_canonical

router = Router(tags=["proxy"])


class ProxyIn(Schema):
    url: str
    method: str = "GET"
    headers: dict[str, str] | None = None
    body: str | None = None


@router.get("/proxy", summary="Proxy GET canónico")
def proxy_get(request: HttpRequest, url: str) -> HttpResponse:
    return proxy_canonical(request)


@router.post("/proxy", summary="Proxy POST canónico")
def proxy_post_canonical(request: HttpRequest, payload: ProxyIn | None = None) -> HttpResponse:
    # Delegate to canonical handler which reads request body
    return proxy_canonical(request)


__all__ = ["router"]
