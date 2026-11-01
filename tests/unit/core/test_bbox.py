"""Tests de ``bbox``: dimensiones, orden de ejes y dominio."""

from __future__ import annotations

import pytest

from apps.core.bbox import Bbox, parse_bbox
from apps.core.crs import parse_crs
from apps.core.problems import InvalidParameter


def test_bbox_4_crs84():
    bbox = parse_bbox("-3.8,40.3,-3.6,40.5")
    assert (bbox.minx, bbox.miny, bbox.maxx, bbox.maxy) == (-3.8, 40.3, -3.6, 40.5)
    assert bbox.as_string() == "-3.8,40.3,-3.6,40.5"


def test_bbox_4326_ordena_ejes():
    bbox = parse_bbox("40.3,-3.8,40.5,-3.6", crs=parse_crs("EPSG:4326"))
    assert (bbox.minx, bbox.miny) == (-3.8, 40.3)
    assert bbox.as_string() == "40.3,-3.8,40.5,-3.6"


def test_bbox_6_valores():
    bbox = parse_bbox("-1,-2,0,1,2,3")
    assert bbox.is_3d
    assert bbox.minz == 0 and bbox.maxz == 3
    assert bbox.as_tuple() == (-1.0, -2.0, 0.0, 1.0, 2.0, 3.0)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "1,2,3",
        "1,2,3,4,5",
        "a,2,3,4",
        "NaN,2,3,4",
        "Infinity,2,3,4",
    ],
)
def test_bbox_invalido(value):
    with pytest.raises(InvalidParameter):
        parse_bbox(value)


def test_bbox_orden_invertido():
    with pytest.raises(InvalidParameter):
        parse_bbox("4,2,3,4")
    with pytest.raises(InvalidParameter):
        parse_bbox("1,4,3,2")


def test_bbox_fuera_de_dominio():
    with pytest.raises(InvalidParameter):
        parse_bbox("200,0,201,1")


def test_bbox_sin_comprobar_dominio():
    bbox = parse_bbox("200,0,201,1", check_domain=False)
    assert bbox.maxx == 201


def test_reproyeccion_4326_a_3857():
    origen = parse_bbox("40.4168,-3.7038,40.5,-3.6", crs=parse_crs("EPSG:4326"))
    destino = origen.transformed(parse_crs("EPSG:3857"))
    assert destino.crs.code == 3857
    assert destino.minx < -400_000
    assert destino.maxx > destino.minx
    assert destino.maxy > 4_900_000


def test_dos_bbox_intersecan():
    primera = parse_bbox("-3.8,40.3,-3.6,40.5")
    segunda = parse_bbox("-3.7,40.4,-3.5,40.6")
    tercera = parse_bbox("-1,1,0,2")
    assert primera.intersects(segunda)
    assert not primera.intersects(tercera)


def test_formato_de_numero_sin_ruido():
    bbox = Bbox(1.0, 2.5, 3.25, 4.0)
    assert bbox.as_string() == "1,2.5,3.25,4"
