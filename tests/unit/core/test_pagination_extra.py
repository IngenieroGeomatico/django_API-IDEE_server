from __future__ import annotations

from apps.core.pagination import Page, build_page_links, parse_page
from apps.core.params import Parametros


def test_parse_page_defaults():
    params = Parametros.desde_query_string("")
    page = parse_page(params)
    assert page.limit == 100
    assert page.offset == 0
    assert page.end == 100


def test_build_page_links_next_and_prev(rf):
    request = rf.get("/items?limit=2&offset=2")
    page = Page(limit=2, offset=2)
    links = build_page_links(request, page, number_matched=10, number_returned=2)
    rels = [link["rel"] for link in links]
    assert "self" in rels
    assert "next" in rels
    assert "prev" in rels
