"""Tests de negociación de formato, ETag y JSONP."""

from __future__ import annotations

import json

import pytest
from django.http import HttpResponse

from apps.core.http import (
    REPRESENTATIONS,
    add_vary,
    best_media_type,
    common_headers,
    conditional_response,
    content_disposition,
    etag_for,
    json_response,
    jsonp_response,
    link_header,
    negotiate,
)
from apps.core.limits import Limits
from apps.core.params import Parametros
from apps.core.problems import InvalidParameter, NotAcceptable


def test_best_media_type_exacto():
    assert (
        best_media_type("application/geo+json", ["application/json", "application/geo+json"])
        == "application/geo+json"
    )


def test_best_media_type_q_values():
    rangos = "application/json;q=0.5, application/geo+json;q=0.9"
    assert best_media_type(rangos, ["application/json", "application/geo+json"]) == (
        "application/geo+json"
    )


def test_best_media_type_wildcard():
    assert best_media_type("*/*", ["application/json"]) == "application/json"
    assert best_media_type("application/*", ["text/html", "application/json"]) == "application/json"


def test_best_media_type_sin_encaje():
    assert best_media_type("application/xml", ["application/json"]) is None


def test_negotiate_por_f(make_request):
    params = Parametros.desde_query_string("f=geojson")
    representation = negotiate(make_request("/x"), params)
    assert representation.key == "geojson"
    assert representation.media_type == "application/geo+json"


def test_negotiate_por_accept(make_request):
    representation = negotiate(make_request("/x", accept="text/html"), supported=("json", "html"))
    assert representation.key == "html"


def test_negotiate_accept_tiene_prioridad_sobre_defecto(make_request):
    representation = negotiate(make_request("/x", accept="application/geo+json"))
    assert representation.key == "geojson"


def test_negotiate_f_invalido(make_request):
    params = Parametros.desde_query_string("f=xml")
    with pytest.raises(InvalidParameter):
        negotiate(make_request("/x"), params)


def test_negotiate_406(make_request):
    with pytest.raises(NotAcceptable) as excinfo:
        negotiate(make_request("/x", accept="application/xml"), supported=("json",))
    assert excinfo.value.status == 406
    assert "Accept" in excinfo.value.headers


def test_add_vary_sin_duplicados():
    response = HttpResponse()
    add_vary(response, "Accept")
    add_vary(response, "accept", "Accept-Encoding")
    assert response["Vary"] == "Accept, Accept-Encoding"


def test_etag_estable():
    assert etag_for("hola") == etag_for("hola")
    assert etag_for("hola") != etag_for("adios")
    assert etag_for("hola").startswith('"sha256-')


def test_conditional_response_304(make_request):
    payload = {"a": 1}
    etag = etag_for(json.dumps(payload))
    request = make_request("/x", **{"If-None-Match": etag})
    response = json_response(payload)
    conditional_response(request, response, etag=etag)
    assert response.status_code == 304
    assert response.content == b""


def test_conditional_response_200_con_etag(make_request):
    etag = etag_for("x")
    response = json_response({"a": 1})
    conditional_response(make_request("/x"), response, etag=etag)
    assert response.status_code == 200
    assert response["ETag"] == etag


def test_jsonp_valido():
    response = jsonp_response({"a": "<script>"}, "miCallback")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/javascript; charset=utf-8"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Cache-Control"] == "no-store"
    assert response["Deprecation"] == "true"
    body = response.content.decode()
    assert body.startswith("miCallback(")
    assert body.endswith(");")
    assert "<script>" not in body


@pytest.mark.parametrize(
    "callback",
    ["alert(1)", "1abc", "", "a" * 65, "cb-name", "cb;alert(1)"],
)
def test_jsonp_callback_invalido(callback):
    with pytest.raises(InvalidParameter):
        jsonp_response({}, callback)


def test_common_headers_crs_y_cache():
    response = HttpResponse()
    params = Parametros.desde_query_string("formato=geojson")
    common_headers(
        response,
        params=params,
        crs_uri="http://www.opengis.net/def/crs/OGC/1.3/CRS84",
        cache_control="public, max-age=60",
    )
    assert response["Content-Crs"] == "<http://www.opengis.net/def/crs/OGC/1.3/CRS84>"
    assert response["Cache-Control"] == "public, max-age=60"
    assert response["Deprecation"] == "true"
    assert "Accept" in response["Vary"]


def test_content_disposition_sanea_nombre():
    header = content_disposition('../../etc/passwd"; rm -rf')
    assert header.startswith("attachment;")
    assert ".." not in header
    assert "/" not in header
    assert header.count('"') == 2


def test_link_header():
    value = link_header(
        [
            {"href": "/a", "rel": "self", "type": "application/json"},
            {"href": "/b", "rel": "next"},
        ]
    )
    assert value == '</a>; rel="self"; type="application/json", </b>; rel="next"'


def test_representaciones_disponibles():
    assert set(REPRESENTATIONS) >= {"json", "html", "geojson", "gml", "kml", "mvt"}


def test_limites_por_defecto_de_paginacion():
    assert Limits().default_limit == 100
    assert Limits().max_limit == 10_000
