"""Landing y conformidad de la API canónica ``/api/v1``."""

from __future__ import annotations

from django.http import HttpRequest
from ninja import Router

from .http import negotiate
from .params import Parametros

router = Router(tags=["meta"])

CONFORMANCE_CLASSES = [
    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/json",
    "http://www.opengis.net/spec/ogcapi-common-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/core",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/oas30",
    "http://www.opengis.net/spec/ogcapi-features-1/1.0/conf/geojson",
    "http://www.opengis.net/spec/ogcapi-features-2/1.0/conf/crs",
    "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/filter",
    "http://www.opengis.net/spec/ogcapi-features-3/1.0/conf/features-filter",
]


@router.get("/", summary="Landing de la API")
def landing(request: HttpRequest) -> dict:
    # Fase 1 solo sirve JSON; si piden otro formato se responde 406.
    params = Parametros.desde_request(request)
    negotiate(request, params, supported=("json",))

    base = request.build_absolute_uri("/api/v1/")
    return {
        "title": "API-IDEE",
        "description": "Servicio compatible con el cliente API-IDEE 1.1.0 y API canónica OGC",
        "links": [
            {"href": base, "rel": "self", "type": "application/json"},
            {"href": f"{base}conformance", "rel": "conformance", "type": "application/json"},
            {"href": f"{base}openapi.json", "rel": "service-desc", "type": "application/json"},
            {"href": f"{base}docs", "rel": "service-doc", "type": "text/html"},
        ],
    }


@router.get("/conformance", summary="Clases de conformidad OGC")
def conformance(request: HttpRequest) -> dict:
    return {"conformsTo": CONFORMANCE_CLASSES}


__all__ = ["CONFORMANCE_CLASSES", "router"]
