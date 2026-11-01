"""Paginación OGC API Features: ``limit``, ``offset``, ``links`` (plan §4.9)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.http import HttpRequest, HttpResponse

from .http import link_header
from .limits import Limits, load_limits
from .params import Parametros


@dataclass(frozen=True, slots=True)
class Page:
    limit: int
    offset: int

    @property
    def end(self) -> int:
        return self.offset + self.limit


def parse_page(params: Parametros, *, limits: Limits | None = None) -> Page:
    lim = limits or load_limits()
    limit = params.entero("limit", defecto=lim.default_limit, minimo=1, maximo=lim.max_limit)
    offset = params.entero("offset", defecto=0, minimo=0, maximo=lim.max_offset)
    assert limit is not None and offset is not None  # noqa: S101 - garantizado por defecto
    return Page(limit=limit, offset=offset)


def _url_with(request: HttpRequest, *, limit: int, offset: int) -> str:
    query = request.GET.copy()
    query["limit"] = str(limit)
    query["offset"] = str(offset)
    base = request.build_absolute_uri(request.path)
    encoded = query.urlencode()
    return f"{base}?{encoded}" if encoded else base


def build_page_links(
    request: HttpRequest,
    page: Page,
    *,
    number_matched: int,
    number_returned: int,
    media_type: str = "application/json",
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = [
        {
            "href": _url_with(request, limit=page.limit, offset=page.offset),
            "rel": "self",
            "type": media_type,
        }
    ]

    if number_returned and page.offset + number_returned < number_matched:
        links.append(
            {
                "href": _url_with(request, limit=page.limit, offset=page.offset + page.limit),
                "rel": "next",
                "type": media_type,
            }
        )

    if page.offset > 0:
        links.append(
            {
                "href": _url_with(
                    request,
                    limit=page.limit,
                    offset=max(0, page.offset - page.limit),
                ),
                "rel": "prev",
                "type": media_type,
            }
        )

    return links


def apply_page_headers(response: HttpResponse, links: list[dict[str, Any]]) -> HttpResponse:
    if links:
        response["Link"] = link_header([link for link in links if link.get("rel") != "self"])
    return response


def paginated(
    request: HttpRequest,
    page: Page,
    *,
    number_matched: int,
    number_returned: int,
    media_type: str = "application/json",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Devuelve (metadatos OGC, links) para insertar en la respuesta."""
    links = build_page_links(
        request,
        page,
        number_matched=number_matched,
        number_returned=number_returned,
        media_type=media_type,
    )
    meta = {
        "numberMatched": number_matched,
        "numberReturned": number_returned,
        "links": links,
    }
    return meta, links


__all__ = ["Page", "apply_page_headers", "build_page_links", "paginated", "parse_page"]
