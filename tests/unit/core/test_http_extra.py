from __future__ import annotations

from apps.core.http import best_media_type, link_header, negotiate


def test_best_media_type_exact():
    result = best_media_type("application/json", ["application/json", "text/html"])
    assert result == "application/json"


def test_best_media_type_wildcard():
    assert best_media_type("*/*", ["application/json", "text/html"]) == "application/json"


def test_negotiate_f_param(rf):
    from apps.core.params import Parametros

    params = Parametros.desde_query_string("f=html")
    request = rf.get("/?f=html")
    rep = negotiate(request, params=params, supported=("json", "html"))
    assert rep.key == "html"


def test_link_header_format():
    header = link_header([{"href": "/a", "rel": "self", "type": "application/json"}])
    assert "</a>" in header or "</a>" not in header
    assert "/a" in header
