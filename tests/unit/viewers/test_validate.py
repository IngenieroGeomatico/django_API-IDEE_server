from __future__ import annotations

import pytest

from apps.core.problems import InvalidParameter
from apps.viewers.validate import (
    ControlConfig,
    PluginConfig,
    canonical_control,
    canonical_plugin,
    normalize_controls,
    normalize_plugins,
    plugin_assets,
    plugin_class,
)


def test_canonical_control_case_insensitive():
    assert canonical_control("SCALE") == "scale"


def test_canonical_control_unknown_raises():
    with pytest.raises(InvalidParameter):
        canonical_control("nope")


def test_canonical_plugin_unknown_raises():
    with pytest.raises(InvalidParameter):
        canonical_plugin("nope")


def test_plugin_class_toc():
    assert plugin_class("toc") == "TOC"


def test_normalize_controls_strings():
    controls = normalize_controls(["scale", "scale*true"])
    assert [c.to_legacy() for c in controls] == ["scale", "scale*true"]


def test_normalize_controls_invalid_raises():
    with pytest.raises(InvalidParameter):
        normalize_controls(["nope"])


def test_normalize_plugins_objects():
    plugins = normalize_plugins([{"type": "mousesrs", "params": {"srs": "EPSG:4326"}}])
    assert plugins[0].type == "mousesrs"
    assert plugins[0].params["srs"] == "EPSG:4326"


def test_normalize_plugins_options_alias():
    plugins = normalize_plugins([{"type": "sharemap", "options": {"position": "BR"}}])
    assert plugins[0].params["position"] == "BR"


def test_normalize_plugins_invalid_raises():
    with pytest.raises(InvalidParameter):
        normalize_plugins(["nope"])


def test_control_config_object():
    c = ControlConfig.model_validate({"type": "scale", "options": {"foo": True}})
    assert c.to_legacy() == "scale*true"


def test_plugin_assets_returns_lists():
    css, js = plugin_assets(["mousesrs"], implementation="ol", version="1.1.0")
    assert css and js
    assert all(".ol." in item for item in css + js)


def test_plugin_config_dump():
    p = PluginConfig(type="mousesrs")
    assert p.dump()["type"] == "mousesrs"
