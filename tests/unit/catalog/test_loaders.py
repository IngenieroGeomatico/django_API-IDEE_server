"""Pruebas del cargador del catálogo versionado."""

from __future__ import annotations

from datetime import UTC

import pytest

from apps.catalog import loaders
from apps.catalog.loaders import CatalogNotFound


@pytest.fixture(autouse=True)
def _fresh_catalog():
    loaders.clear_catalog_cache()
    yield
    loaders.clear_catalog_cache()


def test_controls_reproduce_el_catalogo_real():
    assert loaders.load_controls() == (
        "scale",
        "scaleline",
        "panzoombar",
        "panzoom",
        "location",
        "getfeatureinfo",
        "rotate",
        "backgroundlayers",
        "attributions",
        "implementationswitcher",
    )


def test_services_reproduce_el_catalogo_real():
    services = loaders.load_services()
    assert len(services) == 23
    assert services[:4] == ("WMS", "WMS_FULL", "KML", "LayerGroup")
    assert "OGCAPIFeatures" in services
    assert "GeoPackageTile" in services


def test_version_y_versiones():
    assert loaders.load_version() == {
        "date": "04-09-2026",
        "number": "1.1.0",
        "number-ol": "10.7.0",
        "number-cesium": "1.118.0",
    }
    assert loaders.load_versions() == ("1.1.0", "latest")
    assert loaders.load_projection() == "EPSG:3857"


def test_versions_payload_usa_el_esquema_del_cliente_110():
    payload = loaders.versions_payload()

    assert set(payload) == {"1.1.0", "latest"}
    assert payload["1.1.0"]["ol"] == {
        "js": "/js/apiidee-1.1.0.ol.min.js",
        "config": "/js/configuration-1.1.0.js",
        "css": "/assets/css/apiidee-1.1.0.ol.min.css",
    }
    assert payload["latest"]["ol"] == {
        "js": "/js/apiidee.ol.min.js",
        "config": "/js/configuration.js",
        "css": "/assets/css/apiidee.ol.min.css",
    }
    assert payload["latest"]["cesium"]["js"] == "/js/apiidee.cesium.min.js"


def test_resolve_placeholders_usa_la_configuracion(settings):
    settings.API_IDEE = {
        **settings.API_IDEE,
        "PUBLIC_URL": "https://servidor.test/api-idee",
        "STATIC_RESOURCES_URL": "https://estaticos.test/recursos",
    }

    assert (
        loaders.resolve_placeholders("${api-idee.url}plugins/x.js")
        == "https://servidor.test/api-idee/plugins/x.js"
    )
    assert (
        loaders.resolve_placeholders("${api-idee.static_resources.url}/Datos/x.kml")
        == "https://estaticos.test/recursos/Datos/x.kml"
    )


def test_resolve_tree_recorre_listas_y_diccionarios():
    tree = {
        "a": ["${api-idee.url}uno", {"b": "${api-idee.url}dos"}],
        "n": 1,
    }
    resolved = loaders.resolve_tree(tree)

    assert resolved["a"][0].endswith("/uno")
    assert resolved["a"][1]["b"].endswith("/dos")
    assert resolved["n"] == 1
    assert "${api-idee.url}" not in str(resolved)


def test_plugins_internos_ordenados_y_sin_marcadores():
    plugins = loaders.load_internal_plugins()

    names = [plugin["name"] for plugin in plugins]
    assert names == sorted(names)
    assert len(names) == 30
    assert names[0] == "backimglayer"
    assert "${api-idee.url}" not in str(plugins)


def test_plugin_names_es_la_lista_publica():
    names = loaders.plugin_names()

    assert len(names) == 30
    assert list(names) == sorted(names)


def test_recursos_svg_por_coleccion():
    collections = loaders.load_resource_collections("svg")

    assert [collection["name"] for collection in collections] == ["circleIcons", "mtn"]
    assert len(collections[0]["resources"]) == 9
    assert collections[0]["resources"][0]["file"] == "accidenteGeografico.svg"
    assert "${api-idee.static_resources.url}" not in str(collections)


def test_recursos_geodata_por_coleccion():
    collections = loaders.load_resource_collections("geodata")

    assert [collection["name"] for collection in collections] == [
        "KML",
        "WMC",
        "geojson",
        "mbtiles",
        "geopackage",
    ]
    assert all(collection["resources"] for collection in collections)


def test_resources_payload_plano_y_anidado():
    flat = loaders.resources_payload("svg", name="circleIcons")
    nested = loaders.resources_payload("svg", name="circleIcons", nest_resources=True)

    assert [item["name"] for item in flat["collections"]] == ["circleIcons"]
    assert flat["collections"][0]["resources"][0]["file"] == "accidenteGeografico.svg"
    assert nested["collections"][0]["resources"][0][0]["file"] == "accidenteGeografico.svg"


def test_resources_payload_nombre_desconocido_devuelve_lista_vacia():
    assert loaders.resources_payload("svg", name="no-existe") == {"collections": []}


def test_resources_payload_tipo_desconocido():
    with pytest.raises(CatalogNotFound):
        loaders.load_resource_collections("desconocido")


def test_data_file_mtime_es_utc_aware():
    mtime = loaders.data_file_mtime("controls.json")

    assert mtime.tzinfo is UTC
