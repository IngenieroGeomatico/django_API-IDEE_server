"""Modelo canónico de capas y adaptador del DSL posicional heredado (plan §4.5).

El cliente API-IDEE 1.1.0 entiende las capas como cadenas posicionales, por
ejemplo ``WMS*leyenda*https://...*capa*true``. Aquí se define un modelo
nombrado y validado y un adaptador que traduce el DSL al modelo sin perder los
campos vacíos significativos.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from apps.core.crs import parse_crs
from apps.core.limits import load_limits
from apps.core.problems import InvalidParam, InvalidParameter, invalid_parameter

MAX_TEXT = 2048
NUMBER_LIST_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
    r"(?:,[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?){3,5}$"
)
TOKEN_SEPARATOR = "*"  # noqa: S105


class LayerType(StrEnum):
    """Tipos de capa conocidos por el cliente API-IDEE."""

    QUICK = "QUICK"
    WMS = "WMS"
    WMTS = "WMTS"
    TMS = "TMS"
    XYZ = "XYZ"
    WFS = "WFS"
    WFST = "WFST"
    GEOJSON = "GeoJSON"
    OGCAPIFEATURES = "OGCAPIFeatures"
    MVT = "MVT"
    GEOTIFF = "GeoTIFF"
    MBTILES = "MBTiles"
    LAYERGROUP = "LayerGroup"
    KML = "KML"
    OSM = "OSM"
    VECTOR = "Vector"
    MAPLIBRE = "MapLibre"
    MBTILESVECTOR = "MBTilesVector"
    GENERICRASTER = "GenericRaster"
    GENERICVECTOR = "GenericVector"
    TILES3D = "Tiles3D"
    TERRAIN = "Terrain"
    GEOPACKAGE = "GeoPackage"
    GEOPACKAGETILE = "GeoPackageTile"
    WMC = "WMC"


_TYPE_ALIASES = {
    "quick": LayerType.QUICK,
    "wms": LayerType.WMS,
    "wms_full": LayerType.WMS,
    "wmts": LayerType.WMTS,
    "tms": LayerType.TMS,
    "xyz": LayerType.XYZ,
    "wfs": LayerType.WFS,
    "wfst": LayerType.WFST,
    "geojson": LayerType.GEOJSON,
    "ogcapifeatures": LayerType.OGCAPIFEATURES,
    "mvt": LayerType.MVT,
    "geotiff": LayerType.GEOTIFF,
    "mbtiles": LayerType.MBTILES,
    "layergroup": LayerType.LAYERGROUP,
    "kml": LayerType.KML,
    "osm": LayerType.OSM,
    "vector": LayerType.VECTOR,
    "maplibre": LayerType.MAPLIBRE,
    "mbtilesvector": LayerType.MBTILESVECTOR,
    "genericraster": LayerType.GENERICRASTER,
    "genericvector": LayerType.GENERICVECTOR,
    "tiles3d": LayerType.TILES3D,
    "terrain": LayerType.TERRAIN,
    "geopackage": LayerType.GEOPACKAGE,
    "geopackagetile": LayerType.GEOPACKAGETILE,
    "wmc": LayerType.WMC,
}

# Tipos documentados y exportables por la API canónica (plan §4.5).
SUPPORTED_TYPES: frozenset[LayerType] = frozenset(
    {
        LayerType.QUICK,
        LayerType.WMS,
        LayerType.WMTS,
        LayerType.TMS,
        LayerType.XYZ,
        LayerType.WFS,
        LayerType.WFST,
        LayerType.GEOJSON,
        LayerType.OGCAPIFEATURES,
        LayerType.MVT,
        LayerType.GEOTIFF,
        LayerType.MBTILES,
        LayerType.LAYERGROUP,
    }
)

# Orden posicional del DSL heredado por tipo. Los campos vacíos intermedios se
# conservan porque el cliente los interpreta como ``undefined``.
_LAYOUTS: dict[LayerType, tuple[str, ...]] = {
    LayerType.WMS: (
        "legend",
        "url",
        "layers",
        "transparent",
        "tiled",
        "max_extent",
        "in_toc",
        "queryable",
        "visible",
        "version",
        "use_capabilities",
    ),
    LayerType.WMTS: (
        "url",
        "layer",
        "matrix_set",
        "legend",
        "transparent",
        "format",
        "in_toc",
        "queryable",
        "visible",
        "use_capabilities",
    ),
    LayerType.TMS: (
        "id",
        "url",
        "visible",
        "transparent",
        "tile_grid_max_zoom",
        "in_toc",
        "legend",
        "tile_size",
    ),
    LayerType.XYZ: ("id", "url", "visible", "transparent", "in_toc", "legend"),
    LayerType.WFS: ("legend", "url", "type_name", "geometry_type", "ids", "filter", "style"),
    LayerType.WFST: ("legend", "url", "type_name", "geometry_type", "ids", "filter", "style"),
    LayerType.GEOJSON: ("id", "url", "extract", "style"),
    LayerType.OGCAPIFEATURES: (
        "legend",
        "url",
        "collection",
        "limit",
        "bbox",
        "feature_id",
        "offset",
        "format",
        "style",
        "extract",
    ),
    LayerType.MVT: ("url", "id", "crs"),
    LayerType.GEOTIFF: ("legend", "url", "id", "transparent", "crs", "in_toc", "visible"),
    LayerType.MBTILES: (
        "legend",
        "url",
        "id",
        "transparent",
        "visible",
        "opacity",
        "max_zoom_level",
        "max_extent",
        "tile_size",
    ),
    LayerType.QUICK: ("id",),
}

_REQUIRED: dict[LayerType, tuple[str, ...]] = {
    LayerType.QUICK: ("id",),
    LayerType.WMS: ("url", "layers"),
    LayerType.WMTS: ("url", "layer"),
    LayerType.TMS: ("id", "url"),
    LayerType.XYZ: ("id", "url"),
    LayerType.WFS: ("url", "type_name"),
    LayerType.WFST: ("url", "type_name"),
    LayerType.GEOJSON: ("id", "url"),
    LayerType.OGCAPIFEATURES: ("url", "collection"),
    LayerType.MVT: ("url",),
    LayerType.GEOTIFF: ("url",),
    LayerType.MBTILES: ("url",),
    LayerType.LAYERGROUP: ("id",),
}

_TEXT_FIELDS = frozenset(
    {
        "id",
        "legend",
        "url",
        "layers",
        "layer",
        "matrix_set",
        "version",
        "format",
        "type_name",
        "geometry_type",
        "ids",
        "filter",
        "collection",
        "bbox",
        "feature_id",
        "crs",
        "max_extent",
    }
)

_INT_FIELDS = frozenset(
    {
        "tile_grid_max_zoom",
        "tile_size",
        "limit",
        "offset",
        "opacity",
        "max_zoom_level",
    }
)

_BOOL_FIELDS = frozenset(
    {
        "transparent",
        "tiled",
        "in_toc",
        "queryable",
        "visible",
        "use_capabilities",
        "extract",
    }
)

_TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
_FALSE_VALUES = frozenset({"false", "0", "no", "off"})


def canonical_layer_type(value: str) -> LayerType:
    """Normaliza el nombre de un tipo de capa sin distinguir mayúsculas."""
    text = (value or "").strip()
    if not text:
        raise invalid_parameter("layers", "el tipo de capa está vacío")
    try:
        return _TYPE_ALIASES[text.casefold()]
    except KeyError as exc:
        allowed = ", ".join(sorted(item.value for item in LayerType))
        raise invalid_parameter(
            "layers", f"tipo de capa desconocido «{text}»; use uno de: {allowed}", text
        ) from exc


class LayerConfig(BaseModel):
    """Configuración nombrada de una capa del visualizador."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, use_enum_values=False)

    type: LayerType
    id: str | None = None
    legend: str | None = None
    url: str | None = None
    layers: str | list[LayerConfig] | None = None
    layer: str | None = None
    matrix_set: str | None = Field(default=None, alias="matrixSet")
    version: str | None = None
    transparent: bool | None = None
    tiled: bool | None = None
    max_extent: str | None = Field(default=None, alias="maxExtent")
    in_toc: bool | None = Field(default=None, alias="inToc")
    queryable: bool | None = None
    visible: bool | None = None
    use_capabilities: bool | None = Field(default=None, alias="useCapabilities")
    format: str | None = None
    tile_grid_max_zoom: int | None = Field(default=None, alias="tileGridMaxZoom")
    tile_size: int | None = Field(default=None, alias="tileSize")
    type_name: str | None = Field(default=None, alias="typeName")
    geometry_type: str | None = Field(default=None, alias="geometryType")
    ids: str | None = None
    filter: str | None = None
    style: dict[str, Any] | str | None = None
    extract: bool | None = None
    collection: str | None = None
    limit: int | None = None
    bbox: str | None = None
    feature_id: str | None = Field(default=None, alias="featureId")
    offset: int | None = None
    crs: str | None = None
    opacity: int | None = None
    max_zoom_level: int | None = Field(default=None, alias="maxZoomLevel")
    raw: str | None = Field(default=None, exclude=True)

    @field_validator("type", mode="before")
    @classmethod
    def _type(cls, value: Any) -> LayerType:
        if isinstance(value, LayerType):
            return value
        return canonical_layer_type(str(value))

    @field_validator("url", mode="before")
    @classmethod
    def _url(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if len(text) > MAX_TEXT:
            raise ValueError(f"la URL supera {MAX_TEXT} caracteres")
        parsed = urlparse(text)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            raise ValueError("debe ser una URL http(s) absoluta")
        if parsed.username or parsed.password:
            raise ValueError("no se admiten credenciales embebidas en la URL")
        if any(char.isspace() for char in text):
            raise ValueError("la URL no puede contener espacios")
        return text

    @field_validator("crs", mode="before")
    @classmethod
    def _crs(cls, value: Any) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        text = str(value).strip()
        try:
            parse_crs(text, name="crs")
        except InvalidParameter as exc:
            raise ValueError("CRS no válido") from exc
        return text

    @field_validator("bbox", "max_extent", mode="before")
    @classmethod
    def _number_list(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, Sequence) and not isinstance(value, str):
            parts = [str(item) for item in value]
            text = ",".join(parts)
        else:
            text = str(value).strip()
        if not text:
            return None
        if not NUMBER_LIST_RE.match(text):
            raise ValueError("se esperaban 4 o 6 números separados por comas")
        return text

    @field_validator("style", mode="before")
    @classmethod
    def _style(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, dict)):
            return value
        raise ValueError("debe ser texto o un objeto JSON")

    @field_validator(*_TEXT_FIELDS, mode="before")
    @classmethod
    def _text(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        text = str(value)
        if len(text) > MAX_TEXT:
            raise ValueError(f"supera {MAX_TEXT} caracteres")
        return text

    @field_validator(*_INT_FIELDS, mode="before")
    @classmethod
    def _int(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            raise ValueError("se esperaba un número entero")
        try:
            return int(str(value).strip())
        except (TypeError, ValueError) as exc:
            raise ValueError("se esperaba un número entero") from exc

    @field_validator(*_BOOL_FIELDS, mode="before")
    @classmethod
    def _bool(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, bool):
            return value
        text = str(value).strip().casefold()
        if text in _TRUE_VALUES:
            return True
        if text in _FALSE_VALUES:
            return False
        raise ValueError("se esperaba un valor booleano (true|false)")

    @model_validator(mode="after")
    def _check(self) -> LayerConfig:
        if self.type is LayerType.LAYERGROUP:
            if not isinstance(self.layers, list) or not self.layers:
                raise ValueError("LayerGroup requiere una lista «layers» con al menos una capa")
            return self
        if self.type is LayerType.WMS and not isinstance(self.layers, str):
            raise ValueError("WMS requiere «layers» como texto")
        if self.type is not LayerType.WMS and isinstance(self.layers, list):
            raise ValueError("«layers» solo puede ser una lista en LayerGroup")
        for field in _REQUIRED.get(self.type, ()):
            value = getattr(self, field)
            if value is None or value == "":
                raise ValueError(f"el campo «{field}» es obligatorio para {self.type.value}")
        if self.type is LayerType.WMS and self.layers == "":
            raise ValueError("WMS requiere al menos una capa")
        if self.zoom_bounds_invalid():
            raise ValueError("nivel de zoom fuera de rango")
        return self

    def zoom_bounds_invalid(self) -> bool:
        for field in ("tile_grid_max_zoom", "max_zoom_level"):
            value = getattr(self, field)
            if value is not None and not 0 <= value <= 30:
                return True
        return bool(self.opacity is not None and not 0 <= self.opacity <= 100)

    # ------------------------------------------------------------------
    # Serialización
    # ------------------------------------------------------------------
    def to_dsl(self) -> str:
        """Devuelve la representación posicional que consume el cliente."""
        if self.raw:
            return self.raw
        if self.type is LayerType.LAYERGROUP:
            return self._layergroup_dsl()
        layout = _LAYOUTS.get(self.type)
        if layout is None:
            return self.type.value
        tokens = [self.type.value]
        tokens.extend(_format_token(getattr(self, field)) for field in layout)
        return _join_tokens(tokens)

    def _layergroup_dsl(self) -> str:
        children = self.layers if isinstance(self.layers, list) else []
        parts = [
            self.type.value,
            self.id or "",
            self.legend or "",
            _format_token(self.visible),
            _format_token(self.transparent),
            _format_token(self.in_toc),
        ]
        inner = ",".join(child.to_dsl() for child in children)
        parts.append(f"[{inner}]")
        return _join_tokens(parts, trim=False)

    def dump(self) -> dict[str, Any]:
        """JSON canónico, con alias del cliente y sin campos vacíos."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


# Pydantic necesita reconstruir el modelo por la referencia recursiva.
LayerConfig.model_rebuild()


# ---------------------------------------------------------------------------
# Adaptador del DSL heredado
# ---------------------------------------------------------------------------
def _split_top_level(value: str, separator: str) -> list[str]:
    """Divide respetando los corchetes de ``LayerGroup``."""
    parts: list[str] = []
    buffer: list[str] = []
    depth = 0
    for char in value:
        if char == "[":
            depth += 1
        elif char == "]":
            depth = max(0, depth - 1)
        if char == separator and depth == 0:
            parts.append("".join(buffer))
            buffer = []
            continue
        buffer.append(char)
    parts.append("".join(buffer))
    return parts


def _split_fields(value: str) -> list[str]:
    return [part.strip() for part in _split_top_level(value, TOKEN_SEPARATOR)]


def split_legacy_layers(raw: str) -> list[str]:
    """Separa una lista ``layers`` en tokens, conservando los grupos anidados."""
    if raw is None or not raw.strip():
        return []
    tokens: list[str] = []
    for part in _split_top_level(raw, ","):
        part = part.strip()
        if not part:
            continue
        if part.endswith("!") and part.casefold().startswith("layergroup*"):
            part = part[:-1].rstrip()
        if part:
            tokens.append(part)
    return tokens


def _parse_bool_token(token: str, *, name: str) -> bool | None:
    if token == "":
        return None
    lowered = token.casefold()
    if lowered in _TRUE_VALUES:
        return True
    if lowered in _FALSE_VALUES:
        return False
    raise invalid_parameter(name, "se esperaba un valor booleano (true|false)", token)


def _parse_int_token(token: str, *, name: str) -> int | None:
    if token == "":
        return None
    try:
        return int(token)
    except ValueError as exc:
        raise invalid_parameter(name, "se esperaba un número entero", token) from exc


def _value_for_field(field: str, token: str, *, name: str) -> Any:
    if field in _BOOL_FIELDS:
        return _parse_bool_token(token, name=name)
    if field in _INT_FIELDS:
        return _parse_int_token(token, name=name)
    return token or None


def _group_inner(remainder: str) -> str | None:
    """Extrae el contenido del primer bloque ``[...]`` equilibrado."""
    start = remainder.find("[")
    if start < 0:
        return None
    depth = 0
    for index in range(start, len(remainder)):
        char = remainder[index]
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return remainder[start + 1 : index]
    return None


def parse_legacy_layer(token: str, *, name: str = "layers") -> LayerConfig:
    """Convierte una capa del DSL posicional al modelo canónico."""
    token = token.strip()
    if not token:
        raise invalid_parameter(name, "capa vacía")
    fields = _split_fields(token)
    layer_type = canonical_layer_type(fields[0])
    if layer_type is LayerType.LAYERGROUP:
        return _parse_legacy_layergroup(fields, name=name)
    layout = _LAYOUTS.get(layer_type)
    if layout is None:
        # Tipos conocidos por el cliente pero no documentados: se conservan tal cual.
        return LayerConfig(type=layer_type, raw=token)
    values: dict[str, Any] = {}
    for index, field in enumerate(layout, start=1):
        raw_value = fields[index] if index < len(fields) else ""
        values[field] = _value_for_field(field, raw_value, name=f"{name}[{field}]")
    try:
        return LayerConfig(type=layer_type, **values)
    except ValidationError as exc:
        raise _validation_error(exc, prefix=name) from exc


def _parse_legacy_layergroup(fields: list[str], *, name: str) -> LayerConfig:
    if len(fields) < 2 or not fields[1]:
        raise invalid_parameter(name, "LayerGroup requiere un nombre")
    values: dict[str, Any] = {
        "type": LayerType.LAYERGROUP,
        "id": fields[1],
        "legend": fields[2] if len(fields) > 2 else "",
        "visible": _parse_bool_token(fields[3] if len(fields) > 3 else "", name=name),
        "transparent": _parse_bool_token(fields[4] if len(fields) > 4 else "", name=name),
        "in_toc": _parse_bool_token(fields[5] if len(fields) > 5 else "", name=name),
    }
    remainder = "*".join(fields[6:]) if len(fields) > 6 else ""
    inner = _group_inner(remainder)
    if inner is None:
        raise invalid_parameter(name, "LayerGroup requiere una lista de capas entre corchetes")
    children = [
        parse_legacy_layer(part.strip(), name=name)
        for part in _split_top_level(inner, ",")
        if part.strip()
    ]
    if not children:
        raise invalid_parameter(name, "LayerGroup requiere una lista de capas entre corchetes")
    values["layers"] = children
    try:
        return LayerConfig(**values)
    except ValidationError as exc:
        raise _validation_error(exc, prefix=name) from exc


def _validation_error(exc: ValidationError, *, prefix: str) -> InvalidParameter:
    params: list[InvalidParam] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ())) or "layer"
        params.append(
            InvalidParam(
                f"{prefix}.{location}",
                str(error.get("msg", "valor no válido")),
            )
        )
    return InvalidParameter("La capa no cumple el esquema esperado.", invalid_params=params)


def parse_legacy_layers(raw: str, *, name: str = "layers") -> list[LayerConfig]:
    """Convierte el parámetro ``layers`` completo, agregando todos los errores."""
    tokens = split_legacy_layers(raw)
    maximum = load_limits().max_layers
    if len(tokens) > maximum:
        raise invalid_parameter(name, f"no se admiten más de {maximum} capas", len(tokens))
    layers: list[LayerConfig] = []
    problems: list[InvalidParam] = []
    for index, token in enumerate(tokens):
        try:
            layers.append(parse_legacy_layer(token, name=f"{name}[{index}]"))
        except InvalidParameter as exc:
            problems.extend(
                exc.invalid_params or [InvalidParam(f"{name}[{index}]", exc.detail or "")]
            )
    if problems:
        raise InvalidParameter(
            "Hay capas que no cumplen el esquema esperado.",
            invalid_params=problems,
        )
    return layers


# ---------------------------------------------------------------------------
# Utilidades de formato
# ---------------------------------------------------------------------------
def _format_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and math.isfinite(value):
        return f"{value:.12f}".rstrip("0").rstrip(".")
    return str(value).replace(TOKEN_SEPARATOR, "%2A").replace(",", "%2C")


def _join_tokens(tokens: list[str], *, trim: bool = True) -> str:
    if trim:
        while len(tokens) > 1 and tokens[-1] == "":
            tokens.pop()
    return TOKEN_SEPARATOR.join(tokens)


def legacy_layer_strings(raw: str) -> list[str]:
    """Tokens originales (sin canonicalizar) para el JS heredado."""
    return split_legacy_layers(raw)


__all__ = [
    "SUPPORTED_TYPES",
    "LayerConfig",
    "LayerType",
    "canonical_layer_type",
    "legacy_layer_strings",
    "parse_legacy_layer",
    "parse_legacy_layers",
    "split_fields",
    "split_legacy_layers",
]

# Alias usado por los tests y por otros módulos.
split_fields = _split_fields
