"""Pruebas de plugins externos: snapshot, TTL, allowlist y respaldo."""

from __future__ import annotations

import httpx
import pytest
import respx

from apps.catalog import external

BASE = "https://plugins.test/api-idee"
PLUGINS_URL = f"{BASE}/data/plugins.json"
RESOURCES_URL = f"{BASE}/data/resourcesPlugins.json"


@pytest.fixture(autouse=True)
def _clean_cache():
    external.reset_external_cache()
    yield
    external.reset_external_cache()


def test_sin_url_remota_solo_usa_el_snapshot(settings):
    settings.API_IDEE = {**settings.API_IDEE, "EXTERNAL_PLUGINS_BASE_URL": ""}

    state = external.get_external_plugins()

    assert state.source == "snapshot"
    assert "backimglayer" in state.names
    assert state.names == tuple(sorted(state.names))
    assert all(name == name.lower() for name in state.names)
    assert len(state.names) == 31


def test_is_allowed_url_respeta_la_allowlist(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.idee.es", "*.test"],
    }

    assert external.is_allowed_url("https://www.idee.es/a.js")
    assert external.is_allowed_url("https://plugins.test/a.js")
    assert not external.is_allowed_url("https://example.org/a.js")
    assert not external.is_allowed_url("ftp://plugins.test/a.js")
    assert not external.is_allowed_url("/relativa.js")


@respx.mock
def test_remoto_correcto_devuelve_nombres_y_recursos(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "EXTERNAL_PLUGINS_BASE_URL": BASE,
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.test"],
    }
    respx.get(PLUGINS_URL).mock(
        return_value=httpx.Response(
            200,
            json=[
                {"name": "PluginB", "obsolete": False},
                {"name": "plugina", "obsolete": False},
                {"name": "obsoleto", "obsolete": True},
            ],
        )
    )
    respx.get(RESOURCES_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "plugins": [
                    {
                        "name": "PluginB",
                        "obsolete": "false",
                        "versions": [{"api-idee": "1.1.0", "js": "b.js", "css": "b.css"}],
                    }
                ]
            },
        )
    )

    state = external.get_external_plugins()

    assert state.source == "remote"
    assert state.names == ("plugina", "pluginb")
    assert state.resources[0]["name"] == "PluginB"
    assert state.errors == ()


@respx.mock
def test_fallo_remoto_cae_al_snapshot(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "EXTERNAL_PLUGINS_BASE_URL": BASE,
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.test"],
    }
    respx.get(PLUGINS_URL).mock(side_effect=httpx.ConnectError("sin red"))
    respx.get(RESOURCES_URL).mock(side_effect=httpx.ConnectError("sin red"))

    state = external.get_external_plugins()

    assert state.source == "snapshot"
    assert state.names
    assert state.resources == ()
    assert len(state.errors) == 2


@respx.mock
def test_ttl_reutiliza_la_cache_y_force_la_refresca(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "EXTERNAL_PLUGINS_BASE_URL": BASE,
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.test"],
        "EXTERNAL_PLUGINS_TTL": 300.0,
    }
    plugins_route = respx.get(PLUGINS_URL).mock(
        return_value=httpx.Response(200, json=[{"name": "uno", "obsolete": False}])
    )
    respx.get(RESOURCES_URL).mock(return_value=httpx.Response(200, json={"plugins": []}))

    first = external.get_external_plugins()
    second = external.get_external_plugins()

    assert first is second
    assert plugins_route.call_count == 1

    external.reload_external_plugins()

    assert plugins_route.call_count == 2


@respx.mock
def test_timeout_configurado_se_aplica(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "EXTERNAL_PLUGINS_BASE_URL": BASE,
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.test"],
        "EXTERNAL_PLUGINS_TIMEOUT": 0.5,
    }
    respx.get(PLUGINS_URL).mock(side_effect=httpx.ReadTimeout("agotado"))
    respx.get(RESOURCES_URL).mock(side_effect=httpx.ReadTimeout("agotado"))

    state = external.get_external_plugins()

    assert state.source == "snapshot"
    assert state.errors
