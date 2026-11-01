"""Parámetro ``bbox``: 4 o 6 valores, orden de ejes y reproyección."""

from __future__ import annotations

from dataclasses import dataclass

from .crs import CRS84, Crs, bounds, same_crs
from .problems import invalid_parameter
from .validators import parse_decimal


@dataclass(frozen=True, slots=True)
class Bbox:
    """Caja envolvente en orden interno (x, y), opcionalmente 3D."""

    minx: float
    miny: float
    maxx: float
    maxy: float
    minz: float | None = None
    maxz: float | None = None
    crs: Crs = CRS84

    @property
    def is_3d(self) -> bool:
        return self.minz is not None and self.maxz is not None

    def as_tuple(self) -> tuple[float, ...]:
        if self.is_3d:
            assert self.minz is not None and self.maxz is not None  # noqa: S101
            return (self.minx, self.miny, self.minz, self.maxx, self.maxy, self.maxz)
        return (self.minx, self.miny, self.maxx, self.maxy)

    def as_string(self, *, axis_order: str | None = None) -> str:
        order = axis_order or self.crs.axis_order
        values: tuple[float, ...]
        if order == "yx":
            if self.is_3d:
                assert self.minz is not None and self.maxz is not None  # noqa: S101
                values = (self.miny, self.minx, self.minz, self.maxy, self.maxx, self.maxz)
            else:
                values = (self.miny, self.minx, self.maxy, self.maxx)
        else:
            values = self.as_tuple()
        return ",".join(_format_number(value) for value in values)

    def intersects(self, other: Bbox) -> bool:
        return not (
            self.maxx < other.minx
            or self.minx > other.maxx
            or self.maxy < other.miny
            or self.miny > other.maxy
        )

    def transformed(self, target: Crs) -> Bbox:
        if same_crs(self.crs, target):
            return Bbox(self.minx, self.miny, self.maxx, self.maxy, self.minz, self.maxz, target)

        pyproj = _pyproj()
        if pyproj is None:  # pragma: no cover - pyproj es dependencia del proyecto
            raise invalid_parameter("bbox", "no se puede reproyectar: falta pyproj")

        source_srid = self.crs.srid
        target_srid = target.srid
        if source_srid is None or target_srid is None:  # pragma: no cover - CRS siempre tiene SRID
            raise invalid_parameter("bbox", "CRS sin SRID para reproyectar")

        transformer = pyproj.Transformer.from_crs(source_srid, target_srid, always_xy=True)
        xs, ys = transformer.transform(
            [self.minx, self.minx, self.maxx, self.maxx],
            [self.miny, self.maxy, self.miny, self.maxy],
        )
        return Bbox(
            min(xs),
            min(ys),
            max(xs),
            max(ys),
            self.minz,
            self.maxz,
            target,
        )


def _pyproj():
    try:
        import pyproj
    except ImportError:  # pragma: no cover
        return None
    return pyproj


def _format_number(value: float) -> str:
    text = f"{value:.12f}".rstrip("0").rstrip(".")
    return text or "0"


def parse_bbox(
    value: str,
    *,
    crs: Crs = CRS84,
    name: str = "bbox",
    dimensions: tuple[int, ...] = (4, 6),
    check_domain: bool = True,
) -> Bbox:
    """Interpreta ``minx,miny,maxx,maxy[,minz,maxz]``.

    Si el CRS tiene orden de ejes ``yx`` (p. ej. EPSG:4326), la entrada se
    interpreta como ``lat,lon,lat,lon`` y se normaliza a orden x,y interno.
    """
    if not value or not value.strip():
        raise invalid_parameter(name, "no puede estar vacío", value)

    parts = [part.strip() for part in value.split(",")]
    if len(parts) not in dimensions:
        expected = " o ".join(str(item) for item in dimensions)
        raise invalid_parameter(name, f"se esperaban {expected} valores separados por comas", value)

    numbers = [parse_decimal(part, name=name) for part in parts]

    if crs.axis_order == "yx":
        if len(numbers) == 4:
            miny, minx, maxy, maxx = numbers
            bbox = Bbox(minx, miny, maxx, maxy, crs=crs)
        else:
            miny, minx, minz, maxy, maxx, maxz = numbers
            bbox = Bbox(minx, miny, maxx, maxy, minz, maxz, crs)
    else:
        if len(numbers) == 4:
            bbox = Bbox(numbers[0], numbers[1], numbers[2], numbers[3], crs=crs)
        else:
            minx, miny, minz, maxx, maxy, maxz = numbers
            bbox = Bbox(minx, miny, maxx, maxy, minz, maxz, crs)

    if bbox.minx >= bbox.maxx:
        raise invalid_parameter(name, "minx debe ser menor que maxx", value)
    if bbox.miny >= bbox.maxy:
        raise invalid_parameter(name, "miny debe ser menor que maxy", value)
    if bbox.minz is not None and bbox.maxz is not None and bbox.minz >= bbox.maxz:
        raise invalid_parameter(name, "minz debe ser menor que maxz", value)

    if check_domain:
        domain = bounds(crs)
        if domain is not None:
            domain_bbox = Bbox(domain[0], domain[1], domain[2], domain[3], crs=crs)
            if not bbox.intersects(domain_bbox):
                raise invalid_parameter(
                    name,
                    f"el bbox no intersecta el dominio de {crs.name}",
                    value,
                )

    return bbox


__all__ = ["Bbox", "parse_bbox"]
