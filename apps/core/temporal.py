"""Fechas y horas RFC 3339 y el parámetro ``datetime`` de OGC API."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .problems import invalid_parameter

INSTANT_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$"
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OPEN = ".."


def parse_datetime(value: str, *, name: str = "datetime") -> datetime:
    """Interpreta un instante RFC 3339. Fechas sin hora se asumen UTC."""
    text = value.strip()
    if DATE_RE.match(text):
        try:
            return datetime.fromisoformat(text).replace(tzinfo=UTC)
        except ValueError as exc:
            raise invalid_parameter(name, "fecha no válida", value) from exc
    if not INSTANT_RE.match(text):
        raise invalid_parameter(
            name,
            "fecha no válida (se espera RFC 3339, p. ej. 2026-10-30T12:00:00Z)",
            value,
        )
    normalised = text[:-1] + "+00:00" if text[-1] in "Zz" else text
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError as exc:
        raise invalid_parameter(name, "fecha no válida", value) from exc
    if parsed.tzinfo is None:  # pragma: no cover - cubierto por el regex
        raise invalid_parameter(name, "la fecha debe incluir zona horaria", value)
    return parsed


def format_datetime(value: datetime) -> str:
    """Serializa un instante en UTC con sufijo ``Z``."""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class DatetimeInterval:
    """Intervalo cerrado o abierto de ``datetime``."""

    start: datetime | None = None
    end: datetime | None = None

    @property
    def open_start(self) -> bool:
        return self.start is None

    @property
    def open_end(self) -> bool:
        return self.end is None

    @property
    def is_instant(self) -> bool:
        return self.start is not None and self.end is not None and self.start == self.end

    def contains(self, moment: datetime) -> bool:
        if self.start is not None and moment < self.start:
            return False
        return not (self.end is not None and moment > self.end)

    def as_string(self) -> str:
        start = format_datetime(self.start) if self.start is not None else OPEN
        end = format_datetime(self.end) if self.end is not None else OPEN
        return f"{start}/{end}"


def parse_datetime_interval(value: str, *, name: str = "datetime") -> DatetimeInterval:
    """Interpreta ``instante``, ``inicio/fin``, ``../fin`` o ``inicio/..``."""
    text = value.strip()
    if not text:
        raise invalid_parameter(name, "no puede estar vacío", value)

    parts = text.split("/")
    if len(parts) > 2:
        raise invalid_parameter(name, "intervalo no válido (demasiadas barras)", value)

    if len(parts) == 1:
        instant = parse_datetime(parts[0], name=name)
        return DatetimeInterval(instant, instant)

    raw_start, raw_end = (part.strip() for part in parts)
    if raw_start == OPEN and raw_end == OPEN:
        raise invalid_parameter(
            name,
            "un intervalo no puede estar abierto por ambos extremos",
            value,
        )

    start = None if raw_start == OPEN else parse_datetime(raw_start, name=name)
    end = None if raw_end == OPEN else parse_datetime(raw_end, name=name)
    if start is not None and end is not None and start > end:
        raise invalid_parameter(name, "el inicio del intervalo es posterior al fin", value)
    return DatetimeInterval(start, end)
