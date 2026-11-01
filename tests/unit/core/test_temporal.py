"""Tests de fechas RFC 3339 e intervalos."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.core.problems import InvalidParameter
from apps.core.temporal import (
    DatetimeInterval,
    format_datetime,
    parse_datetime,
    parse_datetime_interval,
)


def test_instante_con_z():
    value = parse_datetime("2026-10-30T12:00:00Z")
    assert value.tzinfo is not None
    assert value.astimezone(UTC).hour == 12


def test_instante_con_offset():
    value = parse_datetime("2026-10-30T14:00:00+02:00")
    assert value.astimezone(UTC).hour == 12


def test_fecha_sin_hora_es_utc():
    value = parse_datetime("2026-10-30")
    assert value.tzinfo == UTC
    assert value.hour == 0


@pytest.mark.parametrize(
    "value",
    ["", "2026-13-01", "2026-10-30 12:00:00", "2026-10-30T12:00:00", "ayer"],
)
def test_fechas_invalidas(value):
    with pytest.raises(InvalidParameter):
        parse_datetime(value)


def test_intervalo_cerrado():
    interval = parse_datetime_interval("2026-01-01T00:00:00Z/2026-02-01T00:00:00Z")
    assert interval.start is not None and interval.end is not None
    assert interval.contains(datetime(2026, 1, 15, tzinfo=UTC))


def test_intervalo_abierto_al_inicio():
    interval = parse_datetime_interval("../2026-02-01T00:00:00Z")
    assert interval.open_start
    assert interval.end is not None


def test_intervalo_abierto_al_fin():
    interval = parse_datetime_interval("2026-01-01T00:00:00Z/..")
    assert interval.open_end
    assert interval.start is not None


def test_intervalo_ambos_abiertos_es_error():
    with pytest.raises(InvalidParameter):
        parse_datetime_interval("../..")


def test_intervalo_invertido_es_error():
    with pytest.raises(InvalidParameter):
        parse_datetime_interval("2026-02-01T00:00:00Z/2026-01-01T00:00:00Z")


def test_instante_unico():
    interval = parse_datetime_interval("2026-01-01T00:00:00Z")
    assert interval.is_instant


def test_format_datetime_utc():
    value = datetime(2026, 10, 30, 12, 0, tzinfo=UTC)
    assert format_datetime(value) == "2026-10-30T12:00:00Z"


def test_contains_con_extremos_abiertos():
    interval = DatetimeInterval(None, None)
    assert interval.open_start and interval.open_end
    assert interval.contains(datetime.now(UTC))
