"""Validadores tipados de parámetros (plan §4.2)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import TypeVar

from .problems import InvalidParam, InvalidParameter, invalid_parameter

T = TypeVar("T")

INTEGER_RE = re.compile(r"^[+-]?\d+$")
DECIMAL_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
CALLBACK_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]{0,63}$")
COLOR_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
COLOR_FUNC_RE = re.compile(r"^rgba?\(\s*[\d.%\s,]+\)$", re.IGNORECASE)

TRUE_VALUES = frozenset({"true", "yes", "on"})
FALSE_VALUES = frozenset({"false", "no", "off"})
LEGACY_TRUE = frozenset({"1"})
LEGACY_FALSE = frozenset({"0"})

NAMED_COLORS = frozenset(
    {
        "aqua",
        "black",
        "blue",
        "cyan",
        "fuchsia",
        "gray",
        "green",
        "grey",
        "lime",
        "magenta",
        "maroon",
        "navy",
        "olive",
        "orange",
        "purple",
        "red",
        "silver",
        "teal",
        "transparent",
        "white",
        "yellow",
    }
)


def _text(value: str, name: str) -> str:
    if not isinstance(value, str):
        raise invalid_parameter(name, "se esperaba texto", value)
    return value.strip()


def parse_int(
    value: str,
    *,
    name: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    text = _text(value, name)
    if not INTEGER_RE.match(text):
        raise invalid_parameter(name, "se esperaba un número entero", value)
    number = int(text)
    if minimum is not None and number < minimum:
        raise invalid_parameter(name, f"debe ser mayor o igual que {minimum}", value)
    if maximum is not None and number > maximum:
        raise invalid_parameter(name, f"debe ser menor o igual que {maximum}", value)
    return number


def parse_decimal(value: str, *, name: str) -> float:
    text = _text(value, name)
    if not DECIMAL_RE.match(text):
        raise invalid_parameter(name, "se esperaba un número decimal", value)
    number = float(text)
    if number != number or number in (float("inf"), float("-inf")):
        raise invalid_parameter(name, "no se admiten NaN ni Infinity", value)
    return number


def parse_bool(value: str, *, name: str, legacy: bool = False) -> bool:
    text = _text(value, name).lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    if legacy and text in LEGACY_TRUE:
        return True
    if legacy and text in LEGACY_FALSE:
        return False
    allowed = "true|false" + ("|1|0" if legacy else "")
    raise invalid_parameter(name, f"valor booleano no válido (use {allowed})", value)


def parse_enum(
    value: str,
    allowed: Sequence[str] | Iterable[str],
    *,
    name: str,
    casefold: bool = True,
) -> str:
    options = list(allowed)
    text = _text(value, name)
    if casefold:
        lookup = {option.lower(): option for option in options}
        if text.lower() in lookup:
            return lookup[text.lower()]
    elif text in options:
        return text
    raise invalid_parameter(name, f"valor no admitido; use uno de: {', '.join(options)}", value)


def parse_list(
    value: str,
    *,
    name: str,
    separator: str = ",",
    max_items: int | None = None,
    max_item_length: int | None = None,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, str):
        raise invalid_parameter(name, "se esperaba una lista de texto", value)
    items = [item.strip() for item in value.split(separator)]
    items = [item for item in items if item]
    if not items and not allow_empty:
        raise invalid_parameter(name, "la lista no puede estar vacía", value)
    if max_items is not None and len(items) > max_items:
        raise invalid_parameter(name, f"no se admiten más de {max_items} elementos", value)
    if max_item_length is not None:
        for item in items:
            if len(item) > max_item_length:
                raise invalid_parameter(name, "algún elemento es demasiado largo", item)
    return items


def validate_callback(value: str, *, name: str = "callback") -> str:
    text = _text(value, name)
    if not CALLBACK_RE.match(text):
        raise invalid_parameter(
            name,
            "identificador JavaScript no válido (letras, dígitos, _ o $; máx. 64)",
            value,
        )
    return text


def parse_color(value: str, *, name: str) -> str:
    text = _text(value, name)
    lowered = text.lower()
    if lowered in NAMED_COLORS:
        return lowered
    if COLOR_HEX_RE.match(text) or COLOR_FUNC_RE.match(text):
        return text
    raise invalid_parameter(name, "color no válido (#RGB, #RRGGBB, nombre o rgb(...))", value)


def parse_csv_ints(value: str, *, name: str, expected: int | None = None) -> list[int]:
    items = parse_list(value, name=name)
    try:
        numbers = [int(item) for item in items]
    except ValueError as exc:
        raise invalid_parameter(
            name,
            "se esperaban números enteros separados por comas",
            value,
        ) from exc
    if expected is not None and len(numbers) != expected:
        raise invalid_parameter(name, f"se esperaban {expected} valores", value)
    return numbers


def build_invalid_params(*params: InvalidParam) -> list[InvalidParam]:
    return list(params)


__all__ = [
    "InvalidParameter",
    "build_invalid_params",
    "parse_bool",
    "parse_color",
    "parse_csv_ints",
    "parse_decimal",
    "parse_enum",
    "parse_int",
    "parse_list",
    "validate_callback",
]
