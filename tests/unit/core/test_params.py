"""Tests del parser de parámetros (plan §4.2, R-01 a R-12)."""

from __future__ import annotations

import pytest

from apps.core.crs import CRS84
from apps.core.limits import Limits
from apps.core.params import Parametros
from apps.core.problems import InvalidParameter, ProblemError, UriTooLong


def test_nombres_case_insensitive(make_params):
    params = make_params("LIMIT=10")
    assert params.entero("limit") == 10
    assert "limit" in params


def test_coincidencia_exacta_no_es_subcadena(make_params):
    params = make_params("myzoom=5")
    assert params.tiene("myzoom")
    assert not params.tiene("zoom")


def test_alias_formato_a_f(make_params):
    params = make_params("formato=geojson")
    assert params.texto("f") == "geojson"
    assert ("formato", "f") in params.deprecations


def test_alias_projection_a_crs(make_params):
    params = make_params("projection=EPSG:3857")
    assert params.crs().name == "EPSG:3857"


def test_parametro_repetido_es_error(make_params):
    with pytest.raises(InvalidParameter) as excinfo:
        make_params("limit=1&limit=2")
    assert excinfo.value.status == 400
    assert excinfo.value.invalid_params[0].name == "limit"
    assert excinfo.value.invalid_params[0].reason == "parámetro repetido"


def test_repetido_ignorando_mayusculas(make_params):
    with pytest.raises(InvalidParameter):
        make_params("LIMIT=1&limit=2")


def test_alias_y_canonico_duplicado_es_error(make_params):
    with pytest.raises(InvalidParameter):
        make_params("crs=EPSG:3857&projection=EPSG:4326")


def test_multivaluado_permitido(make_params):
    params = make_params("layer=a&layer=b")
    assert params.lista("layer") == ["a", "b"]
    assert params["layer"] == ("a", "b")


def test_valor_vacio_opcional_es_ausente(make_params):
    params = make_params("zoom=")
    assert params.entero("zoom", defecto=5) == 5
    assert not params.tiene("zoom")


def test_valor_vacio_obligatorio_es_error(make_params):
    params = make_params("zoom=")
    with pytest.raises(InvalidParameter):
        params.texto("zoom", obligatorio=True)


def test_obligatorio_ausente_es_error(make_params):
    with pytest.raises(InvalidParameter):
        make_params("").texto("url", obligatorio=True)


def test_entero_fuera_de_rango(make_params):
    params = make_params("limit=50000")
    with pytest.raises(InvalidParameter):
        params.entero("limit", minimo=1, maximo=10000)


def test_entero_no_numerico(make_params):
    with pytest.raises(InvalidParameter):
        make_params("limit=diez").entero("limit")


def test_decimal_rechaza_nan_e_infinito(make_params):
    for raw in ("NaN", "Infinity", "-Infinity", "1,5", "1e"):
        with pytest.raises(InvalidParameter):
            make_params(f"valor={raw}").decimal("valor")


def test_booleano_estricto_y_legacy(make_params):
    assert make_params("visible=TRUE").booleano("visible") is True
    assert make_params("visible=off").booleano("visible") is False
    with pytest.raises(InvalidParameter):
        make_params("visible=1").booleano("visible")
    assert make_params("visible=1").booleano("visible", legacy=True) is True


def test_lista_recorta_y_elimina_vacios(make_params):
    params = make_params("controls=scale,%20scaleline,,toc")
    assert params.lista("controls") == ["scale", "scaleline", "toc"]


def test_lista_max_items(make_params):
    with pytest.raises(InvalidParameter):
        make_params("controls=a,b,c").lista("controls", max_items=2)


def test_enum_case_insensitive(make_params):
    params = make_params("f=GeoJSON")
    assert params.enum("f", ["json", "geojson"]) == "geojson"


def test_enum_invalido(make_params):
    with pytest.raises(InvalidParameter):
        make_params("f=xml").enum("f", ["json", "geojson"])


def test_crs_y_bbox_4326_orden_de_ejes(make_params):
    params = make_params("bbox-crs=EPSG:4326&bbox=40.3,-3.8,40.5,-3.6")
    crs = params.crs("bbox-crs")
    bbox = params.bbox(crs=crs)
    assert bbox is not None
    assert (bbox.minx, bbox.miny, bbox.maxx, bbox.maxy) == (-3.8, 40.3, -3.6, 40.5)


def test_crs_84_por_defecto(make_params):
    params = make_params("bbox=-3.8,40.3,-3.6,40.5")
    bbox = params.bbox()
    assert bbox is not None
    assert bbox.crs == CRS84


def test_fecha_hora_intervalo(make_params):
    interval = make_params("datetime=2026-01-01T00:00:00Z/2026-12-31T23:59:59Z").fecha_hora()
    assert interval is not None
    assert interval.start is not None and interval.end is not None
    assert interval.start.year == 2026


def test_desconocidos_y_rechazo(make_params):
    params = make_params("zoom=3&raro=1")
    assert params.desconocidos(["zoom"]) == ["raro"]
    with pytest.raises(InvalidParameter) as excinfo:
        params.rechazar_desconocidos(["zoom"])
    assert excinfo.value.invalid_params[0].name == "raro"


def test_percent_decoding_y_mas(make_params):
    params = make_params("label=Hola%20mundo&otro=a+b")
    assert params.texto("label") == "Hola mundo"
    assert params.texto("otro") == "a b"


def test_percent_encoding_invalido():
    with pytest.raises(ProblemError):
        Parametros.desde_query_string("label=%FF")


def test_limite_de_longitud_de_query():
    limits = Limits(max_url_length=10)
    with pytest.raises(UriTooLong):
        Parametros.desde_query_string("a=1234567890", limits=limits)


def test_limite_de_numero_de_parametros():
    limits = Limits(max_params=2)
    with pytest.raises(ProblemError):
        Parametros.desde_query_string("a=1&b=2&c=3", limits=limits)


def test_limite_de_longitud_de_valor():
    limits = Limits(max_value_length=3)
    with pytest.raises(InvalidParameter):
        Parametros.desde_query_string("a=1234", limits=limits)


def test_secretos_ocultos_en_log(make_params):
    params = make_params("token=abc&query=SELECT%201")
    data = params.a_dict()
    assert data["token"] == ["***"]
    assert data["query"] == ["SELECT 1"]


def test_orden_y_longitud_limites_por_defecto():
    limits = Limits()
    assert limits.max_url_length == 8192
    assert limits.default_limit == 100
