from __future__ import annotations

from apps.core.middleware import QueryLimitsMiddleware, SecurityHeadersMiddleware


def test_security_headers_sets_csp(rf):
    req = rf.get("/")

    def get_response(request):
        from django.http import HttpResponse

        return HttpResponse("<html></html>", content_type="text/html")

    mw = SecurityHeadersMiddleware(get_response)
    resp = mw(req)
    assert "Content-Security-Policy" in resp
    assert "nonce-" in resp["Content-Security-Policy"]


def test_query_limits_rejects_long_url(rf, settings):
    settings.API_IDEE = {**settings.API_IDEE, "MAX_URL_LENGTH": 10}
    req = rf.get("/?x=" + "a" * 100)

    def get_response(request):
        from django.http import HttpResponse

        return HttpResponse("ok")

    mw = QueryLimitsMiddleware(get_response)
    resp = mw(req)
    assert resp.status_code == 414 or resp.status_code == 400
