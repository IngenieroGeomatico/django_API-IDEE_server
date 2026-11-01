from __future__ import annotations

import pytest

from apps.core.params import Parametros
from apps.core.problems import InvalidParameter
from apps.viewers.builder import (
    ViewConfig,
    build_legacy_js,
    build_post_js,
    js_literal,
    transform_center,
    viewer_payload,
)
from apps.viewers.layers import parse_legacy_layers
from apps.viewers.validate import normalize_controls, normalize_plugins


def test_js_literal_escapes():
    assert "\\u003c" in js_literal("<")
    assert "\\u003e" in js_literal(">")
    assert "\\u0026" in js_literal("&")
    assert "\\u2028" in js_literal("\u2028")


def test_build_legacy_js_callback():
    params = Parametros.desde_query_string("callback=cb&layers=QUICK*c")
    code = build_legacy_js(params)
    assert code.startswith("cb(")
    assert "IDEE.map" in code


def test_build_legacy_js_preserves_layers():
    params = Parametros.desde_query_string("layers=WMS*l*http://u?*capa*true")
    code = build_legacy_js(params)
    assert "capa" in code


def test_build_post_js_basic():
    body = {"container": "map", "layers": ["QUICK*c"], "controls": ["scale"]}
    code = build_post_js(body)
    assert "IDEE.map" in code
    assert "scale" in code


def test_build_post_js_invalid_layer_raises():
    with pytest.raises(InvalidParameter):
        build_post_js({"layers": [{"type": "WMS", "url": "https://example.com/wms"}]})


def test_transform_center_plan_example():
    from apps.core.crs import parse_crs

    result = transform_center([-3.7038, 40.4168], parse_crs("EPSG:3857"), parse_crs("EPSG:3857"))
    assert result[0] < 0 and result[1] > 0


def test_viewer_payload_transforms_center():
    view = ViewConfig(crs="EPSG:4326", center=[-3.7, 40.4], zoom=5)
    layers = parse_legacy_layers("QUICK*c")
    controls = normalize_controls(["scale"])
    plugins = normalize_plugins([])
    payload = viewer_payload(
        container="map", view=view, layers=layers, controls=controls, plugins=plugins
    )
    assert payload["map"]["projection"] == "EPSG:3857"
    assert payload["map"]["center"][0] < 0


def test_viewer_payload_cesium():
    view = ViewConfig(crs="EPSG:4326", center=[-3.7, 40.4], zoom=5)
    layers = parse_legacy_layers("QUICK*c")
    controls = normalize_controls([])
    plugins = normalize_plugins([])
    payload = viewer_payload(
        container="map",
        view=view,
        layers=layers,
        controls=controls,
        plugins=plugins,
        implementation="cesium",
    )
    assert payload["map"]["projection"] == "EPSG:4326"
