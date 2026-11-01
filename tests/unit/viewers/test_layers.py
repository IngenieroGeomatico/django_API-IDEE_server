from __future__ import annotations

import pytest

from apps.core.problems import InvalidParameter
from apps.viewers.layers import (
    LayerConfig,
    LayerType,
    canonical_layer_type,
    parse_legacy_layer,
    parse_legacy_layers,
    split_legacy_layers,
)


def test_canonical_layer_type_case_insensitive():
    assert canonical_layer_type("wms") is LayerType.WMS
    assert canonical_layer_type("WMS") is LayerType.WMS


def test_canonical_layer_type_unknown_raises():
    with pytest.raises(InvalidParameter):
        canonical_layer_type("nope")


def test_split_legacy_layers_keeps_groups():
    raw = "WMS*a*b,LayerGroup*g*[]*[WMS*x*y]"
    # grupo anidado con un hijo
    raw = "WMS*a*b,LayerGroup*g*ley*true*false*true*[WMS*x*http://u?*l*true]"
    tokens = split_legacy_layers(raw)
    assert len(tokens) == 2
    assert tokens[0].startswith("WMS")
    assert tokens[1].startswith("LayerGroup")


def test_parse_legacy_layer_wms_roundtrip():
    dsl = "WMS*ley*http://u?*capa*true*false**true*true*true*1.3.0"
    layer = parse_legacy_layer(dsl)
    assert layer.type is LayerType.WMS
    assert layer.to_dsl() == dsl


def test_parse_legacy_layer_quick():
    layer = parse_legacy_layer("QUICK*capa")
    assert layer.type is LayerType.QUICK
    assert layer.id == "capa"
    assert layer.to_dsl() == "QUICK*capa"


def test_parse_legacy_layers_limit():
    many = ",".join(f"QUICK*c{i}" for i in range(60))
    with pytest.raises(InvalidParameter):
        parse_legacy_layers(many)


def test_layergroup_roundtrip():
    dsl = "LayerGroup*g*ley*true*false*true*[WMS*a*http://u?*l*true,WMTS*http://v?*cap*Google*cap*true*image/png]"
    layer = parse_legacy_layer(dsl)
    assert layer.type is LayerType.LAYERGROUP
    assert layer.to_dsl() == dsl
    assert len(layer.layers) == 2


def test_layerconfig_rejects_extra():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        LayerConfig.model_validate({"type": "QUICK", "id": "x", "foo": 1})


def test_layerconfig_wms_requires_layers():
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        LayerConfig.model_validate({"type": "WMS", "url": "https://example.com/wms"})
