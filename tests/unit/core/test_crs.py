"""Tests de normalización de CRS."""

from __future__ import annotations

import pytest

from apps.core.crs import CRS84, bounds, parse_crs, same_crs
from apps.core.problems import InvalidParameter


@pytest.mark.parametrize(
    "value",
    [
        "CRS84",
        "crs84",
        "OGC:CRS84",
        "CRS:84",
        "urn:ogc:def:crs:OGC:1.3:CRS84",
        "urn:ogc:def:crs:OGC::CRS84",
        "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
    ],
)
def test_crs84_variantes(value):
    crs = parse_crs(value)
    assert crs == CRS84
    assert crs.is_crs84
    assert crs.axis_order == "xy"
    assert crs.srid == 4326


@pytest.mark.parametrize(
    "value",
    [
        "EPSG:4326",
        "epsg:4326",
        "urn:ogc:def:crs:EPSG::4326",
        "urn:ogc:def:crs:EPSG:6.6:4326",
        "http://www.opengis.net/def/crs/EPSG/0/4326",
        "https://www.opengis.net/def/crs/EPSG/0/4326",
    ],
)
def test_epsg_4326_variantes(value):
    crs = parse_crs(value)
    assert crs.authority == "EPSG"
    assert crs.code == 4326
    assert crs.axis_order == "yx"  # lat, lon
    assert crs.uri.endswith("/4326")


def test_epsg_3857_orden_xy():
    crs = parse_crs("EPSG:3857")
    assert crs.axis_order == "xy"


def test_srid_suelto_solo_con_permiso():
    with pytest.raises(InvalidParameter):
        parse_crs("4326")
    crs = parse_crs("4326", allow_srid=True)
    assert crs.code == 4326


@pytest.mark.parametrize("value", ["", "EPSG:", "EPSG:999999", "urn:foo:bar", "MERCATOR", "4326"])
def test_crs_invalidos(value):
    with pytest.raises(InvalidParameter):
        parse_crs(value)


def test_bounds_conocidos():
    assert bounds(parse_crs("EPSG:4326")) == (-180.0, -90.0, 180.0, 90.0)
    mercator = bounds(parse_crs("EPSG:3857"))
    assert mercator is not None
    assert mercator[0] < 0 < mercator[2]


def test_same_crs_crs84_y_4326():
    assert same_crs(CRS84, parse_crs("EPSG:4326"))
    assert not same_crs(CRS84, parse_crs("EPSG:3857"))
