"""Generación de JavaScript y de configuraciones de visualizador (plan §3.10)."""

from __future__ import annotations

import base64
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from apps.core.crs import CRS84, WEB_MERCATOR, WGS84, Crs, parse_crs
from apps.core.params import Parametros
from apps.core.problems import InvalidParam, InvalidParameter, invalid_parameter
from apps.core.validators import parse_decimal, validate_callback

from .layers import LayerConfig, LayerType, parse_legacy_layer, parse_legacy_layers
from .validate import (
    ControlConfig,
    PluginConfig,
    canonical_plugin,
    normalize_controls,
    normalize_plugins,
    plugin_lookup,
)

JS_MEDIA = "application/javascript; charset=utf-8"
CONTAINER_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
NUMBER_LIST_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
    r"(?:,[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?){3,5}$"
)
CONFIG_KEY_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$")
MAX_BASE64 = 8192

_JS_ESCAPES = {
    "<": "\\u003c",
    ">": "\\u003e",
    "&": "\\u0026",
    "\u2028": "\\u2028",
    "\u2029": "\\u2029",
}


def js_literal(value: Any) -> str:
    """Serializa JSON y neutraliza los caracteres peligrosos dentro de ``<script>``."""
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return "".join(_JS_ESCAPES.get(char, char) for char in text)


def validate_container(value: str, *, name: str = "container") -> str:
    text = (value or "").strip() or "map"
    if not CONTAINER_RE.match(text):
        raise invalid_parameter(
            name, "identificador HTML no válido (letras, dígitos, _ o -; máx. 128)", value
        )
    return text


# ---------------------------------------------------------------------------
# Modelo de vista y de visualizador
# ---------------------------------------------------------------------------
class ViewConfig(BaseModel):
    """Vista inicial del mapa, en el CRS indicado por el cliente."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    crs: str = "CRS84"
    center: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    zoom: float = 5.0
    max_zoom: float | None = Field(default=None, alias="maxZoom")
    min_zoom: float | None = Field(default=None, alias="minZoom")
    bbox: str | None = None
    max_extent: str | None = Field(default=None, alias="maxExtent")
    zoom_constraints: str | None = Field(default=None, alias="zoomConstraints")
    view_extent: str | None = Field(default=None, alias="viewExtent")
    bgcolor: str | None = None

    @field_validator("crs", mode="before")
    @classmethod
    def _crs(cls, value: Any) -> str:
        text = str(value or "CRS84").strip()
        try:
            parse_crs(text, name="view.crs")
        except InvalidParameter as exc:
            raise ValueError("CRS no válido") from exc
        return text

    @field_validator("center", mode="before")
    @classmethod
    def _center(cls, value: Any) -> list[float]:
        if isinstance(value, str):
            parts: Sequence[Any] = value.split(",")
        elif isinstance(value, Sequence):
            parts = value
        else:
            raise ValueError("debe ser una lista [x, y]")
        if len(parts) != 2:
            raise ValueError("debe tener exactamente dos coordenadas")
        numbers: list[float] = []
        for part in parts:
            number = float(parse_decimal(str(part), name="view.center"))
            if not math.isfinite(number):
                raise ValueError("coordenada no finita")
            numbers.append(number)
        return numbers

    @field_validator("zoom", mode="before")
    @classmethod
    def _zoom(cls, value: Any) -> float:
        if value is None or value == "":
            raise ValueError("el zoom es obligatorio")
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 30:
            raise ValueError("el zoom debe estar entre 0 y 30")
        return number

    @field_validator("max_zoom", "min_zoom", mode="before")
    @classmethod
    def _zoom_optional(cls, value: Any) -> float | None:
        if value is None or value == "":
            return None
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 30:
            raise ValueError("el zoom debe estar entre 0 y 30")
        return number

    @field_validator("bbox", "max_extent", mode="before")
    @classmethod
    def _number_list(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = ",".join(str(item) for item in value) if isinstance(value, list) else str(value)
        text = text.strip()
        if not text:
            return None
        if not NUMBER_LIST_RE.match(text):
            raise ValueError("se esperaban 4 o 6 números separados por comas")
        return text

    def crs_obj(self) -> Crs:
        return parse_crs(self.crs, name="view.crs")

    def dump(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


# ---------------------------------------------------------------------------
# Parámetros heredados
# ---------------------------------------------------------------------------
def legacy_map_payload(params: Parametros) -> tuple[dict[str, Any], list[PluginConfig]]:
    """Construye el objeto de ``IDEE.map`` y los plugins del ``/api/js`` heredado."""
    payload: dict[str, Any] = {"container": validate_container(params.texto("container") or "map")}

    wmcfiles = params.texto("wmcfiles") or params.texto("wmc")
    if wmcfiles:
        payload["wmcfiles"] = [item.strip() for item in wmcfiles.split(",") if item.strip()]

    layers = params.texto("layers")
    if layers:
        parsed = parse_legacy_layers(layers)
        payload["layers"] = [item.raw or item.to_dsl() for item in parsed]

    controls = params.texto("controls")
    if controls:
        payload["controls"] = [
            control.to_legacy()
            for control in normalize_controls([item for item in controls.split(",") if item])
        ]

    label = params.texto("label")
    if label:
        payload["label"] = label

    getfeatureinfo = params.texto("info-format")
    if getfeatureinfo:
        payload["getfeatureinfo"] = getfeatureinfo

    zoom = params.texto("zoom")
    if zoom:
        number = parse_decimal(zoom, name="zoom")
        if not 0 <= number <= 30:
            raise invalid_parameter("zoom", "debe estar entre 0 y 30", zoom)
        payload["zoom"] = zoom

    projection = params.texto("crs")
    if projection:
        parse_crs(projection, name="projection")
        payload["projection"] = projection

    center = params.texto("center")
    if center:
        _check_number_list(center, name="center", expected=(2,))
        payload["center"] = center

    bbox = params.texto("bbox")
    if bbox:
        _check_number_list(bbox, name="bbox", expected=(4, 6))
        payload["bbox"] = bbox

    max_extent = params.texto("max-extent")
    if max_extent:
        _check_number_list(max_extent, name="maxextent", expected=(4, 6))
        payload["maxExtent"] = max_extent

    ticket = params.texto("ticket")
    if ticket:
        payload["ticket"] = ticket

    zoom_constraints = params.texto("zoom-constraints")
    if zoom_constraints:
        _check_number_list(zoom_constraints, name="zoomConstrains", expected=(2,))
        payload["zoomConstrains"] = zoom_constraints

    view_extent = params.texto("view-extent")
    if view_extent:
        _check_number_list(view_extent, name="viewextent", expected=(4, 6))
        payload["viewExtent"] = view_extent

    bgcolor = params.color("bgcolor")
    if bgcolor:
        payload["bgColorContainer"] = bgcolor

    return payload, plugins_from_params(params)


def _check_number_list(value: str, *, name: str, expected: tuple[int, ...]) -> None:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) not in expected:
        expected_text = " o ".join(str(item) for item in expected)
        raise invalid_parameter(name, f"se esperaban {expected_text} valores", value)
    for part in parts:
        parse_decimal(part, name=name)


def plugins_from_params(params: Parametros) -> list[PluginConfig]:
    """Obtiene plugins del parámetro ``plugins`` y de claves con nombre de plugin."""
    lookup = plugin_lookup()
    selected: dict[str, PluginConfig] = {}

    for key in params:
        canonical = lookup.get(key.casefold())
        if canonical is None:
            continue
        selected[canonical] = _plugin_from_value(canonical, params.texto(key) or "")

    for name in params.lista("plugins", max_items=20):
        canonical = canonical_plugin(name)
        selected.setdefault(canonical, PluginConfig(type=canonical))

    return list(selected.values())


def _plugin_from_value(name: str, value: str) -> PluginConfig:
    text = value.strip()
    if not text:
        return PluginConfig(type=name)
    if text.casefold().startswith("base64="):
        encoded = text[7:]
        if len(encoded) > MAX_BASE64:
            raise invalid_parameter(name, f"el valor base64 supera {MAX_BASE64} caracteres")
        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise invalid_parameter(name, "base64 no válido", encoded[:32]) from exc
        try:
            data = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise invalid_parameter(name, "el base64 no contiene JSON válido") from exc
        return _plugin_from_data(name, data)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return PluginConfig(type=name, args=[text])
    return _plugin_from_data(name, data)


def _plugin_from_data(name: str, data: Any) -> PluginConfig:
    if isinstance(data, Mapping):
        return PluginConfig(type=name, params=dict(data))
    return PluginConfig(type=name, args=[data])


def plugin_expression(plugin: PluginConfig) -> str:
    args = plugin.invocation_args()
    inner = ",".join(js_literal(arg) for arg in args)
    return f"new IDEE.plugin.{plugin.class_name}({inner})"


def build_legacy_js(params: Parametros) -> str:
    """Genera el JavaScript de ``GET /api/js`` preservando el DSL de capas."""
    payload, plugins = legacy_map_payload(params)
    code = f"IDEE.map({js_literal(payload)})"
    for plugin in plugins:
        code += f".addPlugin({plugin_expression(plugin)})"
    callback = params.callback()
    if callback:
        code = f"{callback}({code});"
    return code


# ---------------------------------------------------------------------------
# POST /api/js
# ---------------------------------------------------------------------------
def build_post_js(body: Mapping[str, Any]) -> str:
    """Genera JavaScript desde un cuerpo JSON, sin evaluar código del cliente."""
    if not isinstance(body, Mapping):
        raise invalid_parameter("body", "se esperaba un objeto JSON")

    map_payload: dict[str, Any] = {}
    raw_map = body.get("map")
    if raw_map is not None:
        if not isinstance(raw_map, Mapping):
            raise invalid_parameter("map", "debe ser un objeto JSON")
        map_payload.update(dict(raw_map))
    else:
        for key in ("container", "center", "zoom", "projection", "bbox", "maxExtent"):
            if key in body:
                map_payload[key] = body[key]

    map_payload["container"] = validate_container(str(map_payload.get("container", "map")))

    raw_layers = body.get("layers") or []
    if not isinstance(raw_layers, list):
        raise invalid_parameter("layers", "debe ser una lista")
    layers: list[str] = []
    problems: list[InvalidParam] = []
    for index, item in enumerate(raw_layers):
        try:
            layers.append(_post_layer(item, index))
        except InvalidParameter as exc:
            problems.extend(
                exc.invalid_params or [InvalidParam(f"layers[{index}]", exc.detail or "")]
            )
    if problems:
        raise InvalidParameter("Hay capas no válidas.", invalid_params=problems)
    if layers:
        map_payload["layers"] = layers

    controls = body.get("controls") or []
    if not isinstance(controls, list):
        raise invalid_parameter("controls", "debe ser una lista")
    normalized_controls = normalize_controls(controls)
    if normalized_controls:
        map_payload["controls"] = [control.to_legacy() for control in normalized_controls]

    plugins = body.get("plugins") or []
    if not isinstance(plugins, list):
        raise invalid_parameter("plugins", "debe ser una lista")
    normalized_plugins = normalize_plugins(plugins)

    code = ""
    configuration = body.get("configuration")
    if configuration is not None:
        if not isinstance(configuration, Mapping):
            raise invalid_parameter("configuration", "debe ser un objeto JSON")
        for key, value in configuration.items():
            text = str(key)
            if not CONFIG_KEY_RE.match(text):
                raise invalid_parameter("configuration", "clave de configuración no válida", text)
            code += f"IDEE.config.{text}={js_literal(value)};"

    code += f"IDEE.map({js_literal(map_payload)})"
    for plugin in normalized_plugins:
        code += f".addPlugin({plugin_expression(plugin)})"

    callback = body.get("callback")
    if callback is not None:
        code = f"{validate_callback(str(callback))}({code});"
    return code


def _post_layer(item: Any, index: int) -> str:
    if isinstance(item, str):
        return parse_legacy_layer(item, name=f"layers[{index}]").raw or item
    if isinstance(item, Mapping):
        try:
            layer = LayerConfig.model_validate(dict(item))
        except ValidationError as exc:
            params = [
                InvalidParam(
                    f"layers[{index}].{'.'.join(str(part) for part in error.get('loc', ()))}",
                    str(error.get("msg", "valor no válido")),
                )
                for error in exc.errors()
            ]
            raise InvalidParameter("La capa no cumple el esquema.", invalid_params=params) from exc
        if layer.type not in {
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
        }:
            raise invalid_parameter(f"layers[{index}].type", "tipo no admitido en el builder")
        return layer.to_dsl()
    raise invalid_parameter(f"layers[{index}]", "se esperaba texto DSL o un objeto JSON")


# ---------------------------------------------------------------------------
# Visualizador canónico
# ---------------------------------------------------------------------------
def transform_center(center: Sequence[float], source: Crs, target: Crs) -> list[float]:
    """Reproyecta el centro de la vista al CRS que consume el cliente."""
    x, y = float(center[0]), float(center[1])
    effective = source
    # Compatibilidad con el ejemplo histórico: coordenadas lon/lat etiquetadas
    # como EPSG:3857 en lugar de CRS84.
    if source.srid == 3857 and abs(x) <= 180 and abs(y) <= 90:
        effective = CRS84
    if effective.srid == target.srid:
        return [x, y]

    try:
        import pyproj
    except ImportError as exc:  # pragma: no cover - pyproj es dependencia del proyecto
        raise invalid_parameter("view.center", "no se puede reproyectar: falta pyproj") from exc

    source_srid = effective.srid
    target_srid = target.srid
    if source_srid is None or target_srid is None:  # pragma: no cover
        raise invalid_parameter("view.center", "CRS sin SRID para reproyectar")
    try:
        transformer = pyproj.Transformer.from_crs(source_srid, target_srid, always_xy=True)
        projected_x, projected_y = transformer.transform(x, y)
    except Exception as exc:
        raise invalid_parameter("view.center", "no se pudo reproyectar el centro") from exc
    if not (math.isfinite(projected_x) and math.isfinite(projected_y)):
        raise invalid_parameter("view.center", "la reproyección devolvió coordenadas no finitas")
    return [round(projected_x, 6), round(projected_y, 6)]


def viewer_payload(
    *,
    container: str,
    view: ViewConfig,
    layers: Iterable[LayerConfig],
    controls: Iterable[ControlConfig],
    plugins: Iterable[PluginConfig],
    implementation: str = "ol",
) -> dict[str, Any]:
    """Configuración JSON que consume la plantilla del visualizador."""
    if implementation not in {"ol", "cesium"}:
        raise invalid_parameter("implementation", "use «ol» o «cesium»", implementation)
    target = WGS84 if implementation == "cesium" else WEB_MERCATOR
    center = transform_center(view.center, view.crs_obj(), target)

    map_payload: dict[str, Any] = {
        "container": validate_container(container),
        "projection": target.name,
        "center": center,
        "zoom": view.zoom,
    }
    for key in ("max_zoom", "min_zoom", "bbox", "max_extent", "zoom_constraints", "view_extent"):
        value = getattr(view, key)
        if value is None:
            continue
        alias = {
            "max_zoom": "maxZoom",
            "min_zoom": "minZoom",
            "max_extent": "maxExtent",
            "zoom_constraints": "zoomConstrains",
            "view_extent": "viewExtent",
        }.get(key, key)
        map_payload[alias] = value
    if view.bgcolor:
        map_payload["bgColorContainer"] = view.bgcolor

    map_payload["layers"] = [layer.to_dsl() for layer in layers]
    map_payload["controls"] = [control.to_legacy() for control in controls]

    plugin_payload = [
        {"class": plugin.class_name, "args": plugin.invocation_args()} for plugin in plugins
    ]
    return {"map": map_payload, "plugins": plugin_payload}


__all__ = [
    "JS_MEDIA",
    "ViewConfig",
    "build_legacy_js",
    "build_post_js",
    "js_literal",
    "legacy_map_payload",
    "plugin_expression",
    "plugins_from_params",
    "transform_center",
    "validate_container",
    "viewer_payload",
]
