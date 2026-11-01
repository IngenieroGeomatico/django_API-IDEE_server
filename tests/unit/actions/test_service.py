"""Pruebas de la lógica de acciones y recursos."""

from __future__ import annotations

import httpx
import pytest
import respx

from apps.actions import service
from apps.catalog import external
from apps.core.problems import InvalidParameter, NotFound, UpstreamError


@pytest.fixture(autouse=True)
def _clean_external():
    external.reset_external_cache()
    yield
    external.reset_external_cache()


def test_indice_heredado_reproduce_todas_las_rutas():
    assert service.action_index() == [
        "/controls",
        "/services",
        "/version",
        "/projection",
        "/plugins",
        "/plugins/external",
        "/plugins/external/reload",
        "/resourcesPlugins",
        "/versions",
        "/resources/svg",
        "/resources/geodata",
        "/../../doc",
        "/../../doc/ol",
        "/../../doc/cesium",
    ]


def test_indice_canonico_usa_enlaces_absolutos(settings):
    settings.API_IDEE = {**settings.API_IDEE, "PUBLIC_URL": "https://servidor.test/"}

    index = service.canonical_index()

    assert index["title"] == "Acciones y recursos de API-IDEE"
    assert len(index["links"]) == 11
    assert index["links"][0] == {
        "href": "https://servidor.test/api/v1/actions/controls",
        "rel": "controls",
        "type": "application/json",
    }
    assert all(link["href"].startswith("https://servidor.test/api/v1/") for link in index["links"])


def test_catalogo_simple():
    assert service.controls()[0] == "scale"
    assert len(service.services()) == 23
    assert service.projection() == {"code": "EPSG:3857"}
    assert service.version()["number"] == "1.1.0"
    assert set(service.versions()) == {"1.1.0", "latest"}


def test_plugins_internos_y_externos():
    assert len(service.plugins()) == 30
    externos = service.external_plugins()

    assert len(externos) == 31
    assert externos == sorted(externos)


def test_reload_plugins_devuelve_el_mensaje_heredado():
    result = service.reload_plugins()

    assert result["success"] is True
    assert result["message"] == "Lista de plugins externos recargada correctamente"
    assert result["count"] == len(service.external_plugins())


def test_resources_plugins_sin_filtros():
    payload = service.resources_plugins()

    assert len(payload) == 30
    assert payload[0]["name"] == "backimglayer"
    assert set(payload[0]) == {"name", "obsolete", "resources"}
    assert isinstance(payload[0]["obsolete"], str)
    assert payload[0]["resources"]


def test_resources_plugins_filtra_por_nombre_y_version():
    by_name = service.resources_plugins(name="backimglayer")
    by_version = service.resources_plugins(name="backimglayer", version="1.1.0")

    assert len(by_name) == 1
    assert len(by_version) == 1
    assert [item["api-idee"] for item in by_version[0]["resources"]] == ["1.1.0"]


def test_resources_plugins_desconocido_devuelve_lista_vacia():
    assert service.resources_plugins(name="no-existe") == []
    assert service.resources_plugins(name="backimglayer", version="0.0.0") == []


def test_plugin_asset_api_idee_devuelve_la_version():
    asset = service.plugin_asset("backimglayer", "1.1.0", "api-idee")

    assert asset.content == b"1.1.0"
    assert asset.media_type.startswith("text/html")
    assert asset.etag.startswith('"sha256-')


def test_plugin_asset_tipo_invalido():
    with pytest.raises(InvalidParameter) as info:
        service.plugin_asset("backimglayer", "1.1.0", "ol")

    assert info.value.status == 400


def test_plugin_asset_desconocido():
    with pytest.raises(NotFound):
        service.plugin_asset("no-existe", "1.1.0", "js")


def test_plugin_asset_local(settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PUBLIC_URL": "http://testserver/",
        "STATIC_RESOURCES_URL": "https://estaticos.test",
    }
    relative = "plugins/backimglayer/backimglayer-1.0.1.ol.min.js"
    target = tmp_path / "static" / relative
    target.parent.mkdir(parents=True)
    target.write_text("console.log('demo');", encoding="utf-8")

    asset = service.plugin_asset("backimglayer", "1.1.0", "js")

    assert asset.content == b"console.log('demo');"
    assert asset.media_type == "application/javascript"
    assert asset.etag.startswith('"sha256-')


@respx.mock
def test_plugin_asset_remoto(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PUBLIC_URL": "http://testserver/",
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.test"],
    }
    target = "https://plugins.test/demo.css"
    respx.get(target).mock(
        return_value=httpx.Response(200, text="body{}", headers={"Content-Type": "text/css"})
    )

    asset = service._fetch_asset(target, "css")

    assert asset.content == b"body{}"
    assert asset.media_type == "text/css"


@respx.mock
def test_plugin_asset_remoto_rechaza_host_no_permitido(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PUBLIC_URL": "http://testserver/",
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.test"],
    }

    with pytest.raises(NotFound):
        service._fetch_asset("https://example.org/demo.js", "js")


@respx.mock
def test_plugin_asset_remoto_limita_tamano(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PUBLIC_URL": "http://testserver/",
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.test"],
        "PLUGIN_ASSET_MAX_BYTES": 4,
    }
    respx.get("https://plugins.test/demo.js").mock(
        return_value=httpx.Response(200, content=b"12345")
    )

    with pytest.raises(UpstreamError):
        service._fetch_asset("https://plugins.test/demo.js", "js")


@respx.mock
def test_plugin_asset_remoto_error_http(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PUBLIC_URL": "http://testserver/",
        "EXTERNAL_PLUGINS_ALLOWED_HOSTS": ["*.test"],
    }
    respx.get("https://plugins.test/demo.js").mock(return_value=httpx.Response(500))

    with pytest.raises(UpstreamError):
        service._fetch_asset("https://plugins.test/demo.js", "js")


def test_politicas_de_cache_configurables(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "CATALOG_MAX_AGE": 10,
        "RESOURCE_MAX_AGE": 20,
        "PLUGIN_ASSET_MAX_AGE": 30,
    }

    assert service.catalog_cache_control() == "public, max-age=10"
    assert service.resources_cache_control() == "public, max-age=20"
    assert service.asset_cache_control() == "public, max-age=30"
