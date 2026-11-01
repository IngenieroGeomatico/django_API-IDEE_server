"""Sistemas de referencia de coordenadas (CRS) y orden de ejes.

Acepta ``EPSG:4326``, URN, URI de OGC y ``CRS84`` (plan §4.7).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from .problems import invalid_parameter

CRS84_URI = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
WEB_MERCATOR_HALF = 20037508.342789244

_CRS84_PATTERNS = (
    re.compile(r"^(?:OGC:)?CRS84$", re.IGNORECASE),
    re.compile(r"^CRS:84$", re.IGNORECASE),
    re.compile(r"^urn:ogc:def:crs:OGC(?::[\w.]*)*:CRS84$", re.IGNORECASE),
    re.compile(r"^https?://www\.opengis\.net/def/crs/OGC/[^/]+/CRS84$", re.IGNORECASE),
)

_EPSG_PATTERNS = (
    re.compile(r"^EPSG:(\d{3,6})$", re.IGNORECASE),
    re.compile(r"^EPSG::(\d{3,6})$", re.IGNORECASE),
    re.compile(r"^urn:ogc:def:crs:EPSG(?::[\w.]*)*:(\d{3,6})$", re.IGNORECASE),
    re.compile(r"^https?://www\.opengis\.net/def/crs/EPSG/[^/]*/(\d{3,6})$", re.IGNORECASE),
)

_SRID_RE = re.compile(r"^(\d{3,6})$")

# Orden de ejes por autoridad para los códigos más usados.
_AXIS_ORDER = {
    4326: "yx",  # lat, lon
    4258: "yx",  # ETRS89 lat, lon
    4322: "yx",
    4324: "yx",
}

_KNOWN_BOUNDS: dict[int, tuple[float, float, float, float]] = {
    4326: (-180.0, -90.0, 180.0, 90.0),
    4258: (-16.1, 32.88, 40.18, 84.73),
    3857: (-WEB_MERCATOR_HALF, -WEB_MERCATOR_HALF, WEB_MERCATOR_HALF, WEB_MERCATOR_HALF),
}


@dataclass(frozen=True, slots=True)
class Crs:
    """CRS normalizado."""

    authority: str
    code: int | None
    uri: str
    axis_order: str = "xy"

    @property
    def is_crs84(self) -> bool:
        return self.authority == "OGC" and self.code is None

    @property
    def srid(self) -> int | None:
        """SRID para pyproj (CRS84 se trata como 4326 con ejes x,y)."""
        return 4326 if self.is_crs84 else self.code

    @property
    def name(self) -> str:
        return "CRS84" if self.is_crs84 else f"{self.authority}:{self.code}"

    def __str__(self) -> str:
        return self.name


CRS84 = Crs("OGC", None, CRS84_URI, "xy")
WGS84 = Crs("EPSG", 4326, "http://www.opengis.net/def/crs/EPSG/0/4326", "yx")
WEB_MERCATOR = Crs("EPSG", 3857, "http://www.opengis.net/def/crs/EPSG/0/3857", "xy")


def _pyproj():
    try:
        import pyproj
    except ImportError:  # pragma: no cover - depende del entorno
        return None
    return pyproj


@lru_cache(maxsize=128)
def _axis_order_cached(code: int) -> str:
    pyproj = _pyproj()
    if pyproj is not None:
        try:
            crs = pyproj.CRS.from_epsg(code)
        except Exception:
            return "xy"
        axes = crs.axis_info
        if axes and axes[0].direction.lower() in {"north", "south"}:
            return "yx"
        return "xy"
    return "xy"


def parse_crs(
    value: str,
    *,
    name: str = "crs",
    allow_srid: bool = False,
) -> Crs:
    """Normaliza un CRS a :class:`Crs`.

    ``allow_srid`` acepta un número suelto (compatibilidad con ``bbox-crs=4326``).
    """
    text = (value or "").strip()
    if not text:
        raise invalid_parameter(name, "no puede estar vacío", value)

    for pattern in _CRS84_PATTERNS:
        if pattern.match(text):
            return CRS84

    for pattern in _EPSG_PATTERNS:
        match = pattern.match(text)
        if match:
            code = int(match.group(1))
            return _build_epsg(code, name=name, value=value)

    if allow_srid:
        match = _SRID_RE.match(text)
        if match:
            return _build_epsg(int(match.group(1)), name=name, value=value)

    raise invalid_parameter(
        name,
        "CRS no válido; use EPSG:n, URN, URI de OGC o CRS84",
        value,
    )


def _build_epsg(code: int, *, name: str, value: str) -> Crs:
    pyproj = _pyproj()
    if pyproj is not None:
        try:
            pyproj.CRS.from_epsg(code)
        except Exception as exc:
            raise invalid_parameter(name, f"CRS desconocido: EPSG:{code}", value) from exc
    elif code not in _AXIS_ORDER and code not in _KNOWN_BOUNDS:
        raise invalid_parameter(name, f"CRS desconocido: EPSG:{code}", value)
    axis_order = _AXIS_ORDER.get(code) or _axis_order_cached(code)
    return Crs("EPSG", code, f"http://www.opengis.net/def/crs/EPSG/0/{code}", axis_order)


def bounds(crs: Crs) -> tuple[float, float, float, float] | None:
    """Extensión geográfica del CRS, si se conoce."""
    srid = crs.srid
    if srid is None:
        return None
    if srid in _KNOWN_BOUNDS:
        return _KNOWN_BOUNDS[srid]
    pyproj = _pyproj()
    if pyproj is None:
        return None
    try:
        area = pyproj.CRS.from_epsg(srid).area_of_use
    except Exception:
        return None
    if area is None:
        return None
    return (area.west, area.south, area.east, area.north)


def same_crs(left: Crs, right: Crs) -> bool:
    return left.srid == right.srid


__all__ = [
    "CRS84",
    "WEB_MERCATOR",
    "WGS84",
    "Crs",
    "bounds",
    "parse_crs",
    "same_crs",
]
