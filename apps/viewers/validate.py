"""Validación de controles y plugins contra el catálogo (plan §3.10 y §4.6)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from apps.catalog import loaders
from apps.core.problems import InvalidParam, InvalidParameter, invalid_parameter

MAX_ITEMS = 20
MAX_PARAMS_BYTES = 4096
IDENTIFIER_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*$")

# Nombres de clase publicados por cada plugin del catálogo.
PLUGIN_CLASSES: dict[str, str] = {
    "backimglayer": "BackImgLayer",
    "basic": "Basic",
    "catalogmanager": "Catalogmanager",
    "comparators": "Comparators",
    "contactlink": "ContactLink",
    "filteredsearch": "FilteredSearch",
    "help": "Help",
    "incicarto": "Incicarto",
    "infocoordinates": "Infocoordinates",
    "information": "Information",
    "layerswitcher": "Layerswitcher",
    "locator": "Locator",
    "locatorscn": "Locatorscn",
    "magnify": "Magnify",
    "mapfooter": "Mapfooter",
    "mapheader": "Mapheader",
    "maxextzoom": "MaxExtZoom",
    "measurebar": "MeasureBar",
    "modal": "Modal",
    "mousesrs": "MouseSRS",
    "overviewmap": "OverviewMap",
    "printviewmanagement": "PrintViewManagement",
    "queryattributes": "QueryAttributes",
    "rastermanagement": "RasterManagement",
    "selectionzoom": "SelectionZoom",
    "sharemap": "ShareMap",
    "stereoscopic": "Stereoscopic",
    "storymap": "StoryMap",
    "stylemanager": "StyleManager",
    "timeline": "Timeline",
    "vectorsmanagement": "VectorsManagement",
    "viewmanagement": "ViewManagement",
    "wfstcontrols": "WFSTControls",
}


class ControlConfig(BaseModel):
    """Control validado.

    ``args`` conserva las opciones posicionales del DSL heredado
    (``scale*true``); ``options`` es la forma canónica con nombres.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: str
    args: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", mode="before")
    @classmethod
    def _type(cls, value: Any) -> str:
        return canonical_control(str(value))

    @field_validator("args", mode="before")
    @classmethod
    def _args(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    @field_validator("options", mode="before")
    @classmethod
    def _options(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return {str(key): item for key, item in value.items()}
        raise ValueError("debe ser un objeto JSON")

    def to_legacy(self) -> str:
        if self.args:
            return "*".join([self.type, *self.args])
        if self.options:
            values = [_option_token(value) for value in self.options.values()]
            return "*".join([self.type, *values])
        return self.type

    def dump(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True, mode="json")


class PluginConfig(BaseModel):
    """Plugin validado contra el catálogo interno."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: str
    args: list[Any] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type", mode="before")
    @classmethod
    def _type(cls, value: Any) -> str:
        return canonical_plugin(str(value))

    @field_validator("args", mode="before")
    @classmethod
    def _args(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    @field_validator("params", mode="before")
    @classmethod
    def _params(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("debe ser un objeto JSON")
        params = {str(key): item for key, item in value.items()}
        encoded = json.dumps(params, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_PARAMS_BYTES:
            raise ValueError(f"los parámetros superan {MAX_PARAMS_BYTES} bytes")
        return params

    @property
    def class_name(self) -> str:
        return plugin_class(self.type)

    def invocation_args(self) -> list[Any]:
        if self.args:
            return list(self.args)
        return [self.params] if self.params else []

    def dump(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True, mode="json")


# ---------------------------------------------------------------------------
# Catálogo
# ---------------------------------------------------------------------------
def _control_lookup() -> dict[str, str]:
    return {name.casefold(): name for name in loaders.load_controls()}


def plugin_lookup() -> dict[str, str]:
    return {name.casefold(): name for name in loaders.plugin_names()}


def canonical_control(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise invalid_parameter("controls", "el nombre del control está vacío")
    lookup = _control_lookup()
    try:
        return lookup[text.casefold()]
    except KeyError as exc:
        allowed = ", ".join(loaders.load_controls())
        raise invalid_parameter(
            "controls", f"control desconocido «{text}»; use uno de: {allowed}", text
        ) from exc


def canonical_plugin(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise invalid_parameter("plugins", "el nombre del plugin está vacío")
    lookup = plugin_lookup()
    try:
        return lookup[text.casefold()]
    except KeyError as exc:
        allowed = ", ".join(loaders.plugin_names())
        raise invalid_parameter(
            "plugins", f"plugin desconocido «{text}»; use uno de: {allowed}", text
        ) from exc


def plugin_class(name: str) -> str:
    canonical = canonical_plugin(name)
    if canonical in PLUGIN_CLASSES:
        return PLUGIN_CLASSES[canonical]
    # Respaldo determinista para plugins añadidos al catálogo.
    return "".join(part.capitalize() for part in re.split(r"[-_]", canonical)) or canonical


def plugin_assets(
    names: Iterable[str],
    *,
    implementation: str = "ol",
    version: str = "1.1.0",
) -> tuple[list[str], list[str]]:
    """Devuelve los ficheros CSS y JS de los plugins indicados."""
    catalog = {str(item["name"]): item for item in loaders.load_internal_plugins()}
    css: list[str] = []
    js: list[str] = []
    for name in names:
        plugin = catalog.get(name)
        if plugin is None:
            continue
        versions = list(plugin.get("versions") or [])
        chosen = next(
            (item for item in versions if str(item.get("api-idee")) == version),
            None,
        )
        if chosen is None:
            chosen = next(
                (item for item in versions if str(item.get("api-idee")) == "latest"),
                versions[0] if versions else None,
            )
        if not chosen:
            continue
        for key, target in (("css", css), ("js", js)):
            value = chosen.get(key)
            if value:
                text = str(value)
                if implementation != "ol":
                    text = text.replace(".ol.", f".{implementation}.")
                target.append(text)
    return css, js


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------
def normalize_controls(items: Sequence[Any]) -> list[ControlConfig]:
    """Convierte cadenas u objetos en ``ControlConfig`` validados."""
    if len(items) > MAX_ITEMS:
        raise invalid_parameter(
            "controls",
            f"no se admiten más de {MAX_ITEMS} controles",
            len(items),
        )
    result: list[ControlConfig] = []
    problems: list[InvalidParam] = []
    for index, item in enumerate(items):
        try:
            result.append(_normalize_control(item))
        except InvalidParameter as exc:
            problems.extend(
                exc.invalid_params or [InvalidParam(f"controls[{index}]", exc.detail or "")]
            )
    if problems:
        raise InvalidParameter(
            "Hay controles no válidos.",
            invalid_params=problems,
        )
    return result


def _normalize_control(item: Any) -> ControlConfig:
    if isinstance(item, ControlConfig):
        return item
    if isinstance(item, str):
        parts = [part.strip() for part in item.split("*")]
        name = canonical_control(parts[0])
        return ControlConfig(type=name, args=[part for part in parts[1:] if part != ""])
    if isinstance(item, Mapping):
        payload = dict(item)
        if "type" not in payload:
            raise invalid_parameter("controls", "cada control debe incluir «type»")
        payload.setdefault("options", {})
        try:
            return ControlConfig.model_validate(payload)
        except ValidationError as exc:
            raise _schema_error(exc, "controls") from exc
    raise invalid_parameter("controls", "se esperaba texto o un objeto JSON")


def normalize_plugins(items: Sequence[Any]) -> list[PluginConfig]:
    """Convierte cadenas u objetos en ``PluginConfig`` validados."""
    if len(items) > MAX_ITEMS:
        raise invalid_parameter("plugins", f"no se admiten más de {MAX_ITEMS} plugins", len(items))
    result: list[PluginConfig] = []
    problems: list[InvalidParam] = []
    for index, item in enumerate(items):
        try:
            result.append(_normalize_plugin(item))
        except InvalidParameter as exc:
            problems.extend(
                exc.invalid_params or [InvalidParam(f"plugins[{index}]", exc.detail or "")]
            )
    if problems:
        raise InvalidParameter("Hay plugins no válidos.", invalid_params=problems)
    return result


def _normalize_plugin(item: Any) -> PluginConfig:
    if isinstance(item, PluginConfig):
        return item
    if isinstance(item, str):
        return PluginConfig(type=canonical_plugin(item))
    if isinstance(item, Mapping):
        payload = dict(item)
        if "type" not in payload:
            raise invalid_parameter("plugins", "cada plugin debe incluir «type»")
        if "options" in payload and "params" not in payload:
            payload["params"] = payload.pop("options")
        payload.setdefault("params", {})
        try:
            return PluginConfig.model_validate(payload)
        except ValidationError as exc:
            raise _schema_error(exc, "plugins") from exc
    raise invalid_parameter("plugins", "se esperaba texto o un objeto JSON")


def _schema_error(exc: ValidationError, prefix: str) -> InvalidParameter:
    params = [
        InvalidParam(
            f"{prefix}.{'.'.join(str(part) for part in error.get('loc', ())) or ''}".rstrip("."),
            str(error.get("msg", "valor no válido")),
        )
        for error in exc.errors()
    ]
    return InvalidParameter(
        "El control o plugin no cumple el esquema esperado.",
        invalid_params=params,
    )


def _option_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


__all__ = [
    "PLUGIN_CLASSES",
    "ControlConfig",
    "PluginConfig",
    "canonical_control",
    "canonical_plugin",
    "normalize_controls",
    "normalize_plugins",
    "plugin_assets",
    "plugin_class",
    "plugin_lookup",
]
