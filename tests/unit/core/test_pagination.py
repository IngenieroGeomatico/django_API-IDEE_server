"""Tests de paginación OGC."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from django.http import HttpResponse

from apps.core.http import link_header
from apps.core.limits import Limits
from apps.core.pagination import Page, apply_page_headers, build_page_links, paginated, parse_page
from apps.core.problems import InvalidParameter


def test_page_por_defecto(make_params):
    page = parse_page(make_params(""), limits=Limits())
    assert page == Page(limit=100, offset=0)


def test_page_explicita(make_params):
    page = parse_page(make_params("limit=25&offset=50"), limits=Limits())
    assert page.limit == 25
    assert page.offset == 50
    assert page.end == 75


@pytest.mark.parametrize("query", ["limit=0", "limit=10001", "offset=-1", "offset=1000001"])
def test_page_fuera_de_rango(make_params, query):
    with pytest.raises(InvalidParameter):
        parse_page(make_params(query), limits=Limits())


def test_links_self_next_prev(make_request):
    request = make_request("/api/v1/items?limit=10&offset=10&f=json")
    links = build_page_links(request, Page(10, 10), number_matched=100, number_returned=10)
    by_rel = {link["rel"]: link for link in links}
    assert set(by_rel) == {"self", "next", "prev"}

    self_query = parse_qs(urlparse(by_rel["self"]["href"]).query)
    next_query = parse_qs(urlparse(by_rel["next"]["href"]).query)
    prev_query = parse_qs(urlparse(by_rel["prev"]["href"]).query)

    assert self_query["offset"] == ["10"]
    assert next_query["offset"] == ["20"]
    assert prev_query["offset"] == ["0"]
    assert next_query["f"] == ["json"]


def test_links_sin_prev_en_primera_pagina(make_request):
    links = build_page_links(
        make_request("/api/v1/items"),
        Page(10, 0),
        number_matched=5,
        number_returned=5,
    )
    assert [link["rel"] for link in links] == ["self"]


def test_links_sin_next_en_ultima_pagina(make_request):
    links = build_page_links(
        make_request("/api/v1/items"),
        Page(10, 90),
        number_matched=95,
        number_returned=5,
    )
    assert [link["rel"] for link in links] == ["self", "prev"]


def test_paginated_metadatos(make_request):
    meta, links = paginated(
        make_request("/api/v1/items"),
        Page(10, 0),
        number_matched=25,
        number_returned=10,
        media_type="application/geo+json",
    )
    assert meta["numberMatched"] == 25
    assert meta["numberReturned"] == 10
    assert meta["links"] == links


def test_cabecera_link_sin_self(make_request):
    links = build_page_links(
        make_request("/api/v1/items"),
        Page(10, 10),
        number_matched=100,
        number_returned=10,
    )
    response = apply_page_headers(HttpResponse(), links)
    header = response["Link"]
    assert 'rel="next"' in header
    assert 'rel="prev"' in header
    assert 'rel="self"' not in header
    assert header == link_header([link for link in links if link["rel"] != "self"])
