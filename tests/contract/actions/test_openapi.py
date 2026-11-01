"""Contrato OpenAPI de las acciones y recursos canónicos."""

from __future__ import annotations

import pytest

ACTION_PATHS = {
    "/api/v1/actions",
    "/api/v1/actions/controls",
    "/api/v1/actions/services",
    "/api/v1/actions/projection",
    "/api/v1/actions/plugins",
    "/api/v1/actions/plugins/external",
    "/api/v1/actions/plugins/external/reload",
    "/api/v1/actions/version",
    "/api/v1/actions/versions",
    "/api/v1/actions/resourcesPlugins",
    "/api/v1/resources/svg",
    "/api/v1/resources/geodata",
}


@pytest.fixture
def spec(client):
    response = client.get("/api/v1/openapi.json")

    assert response.status_code == 200
    return response.json()


def test_openapi_es_31_y_tiene_info(spec):
    assert spec["openapi"].startswith("3.1")
    assert spec["info"]["title"] == "API-IDEE"
    assert spec["info"]["version"] == "1.0.0"


def test_todas_las_rutas_de_acciones_estan_documentadas(spec):
    assert set(spec["paths"]) >= ACTION_PATHS


@pytest.mark.parametrize("path", sorted(ACTION_PATHS))
def test_cada_ruta_documenta_get_y_respuesta_json(spec, path):
    operation = spec["paths"][path]["get"]

    assert operation["responses"]["200"]["content"]
    assert "application/json" in operation["responses"]["200"]["content"]
    assert operation["operationId"]


def test_los_operation_id_son_unicos(spec):
    operation_ids = [
        operation["operationId"]
        for path in spec["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "put", "delete", "patch"}
    ]

    assert len(operation_ids) == len(set(operation_ids))


def test_esquema_de_version_conserva_los_alias_del_cliente(spec):
    version = spec["components"]["schemas"]["VersionInfo"]

    assert set(version["properties"]) == {
        "date",
        "number",
        "number-ol",
        "number-cesium",
    }
    assert set(version["required"]) == set(version["properties"])


def test_esquema_de_plugin_conserva_los_alias_del_cliente(spec):
    plugin = spec["components"]["schemas"]["PluginResource"]

    assert set(plugin["properties"]) == {"api-idee", "js", "css"}


def test_resources_plugins_documenta_sus_parametros(spec):
    parameters = spec["paths"]["/api/v1/actions/resourcesPlugins"]["get"]["parameters"]
    names = {parameter["name"] for parameter in parameters}

    assert names == {"f", "name", "version", "type"}
    type_param = next(parameter for parameter in parameters if parameter["name"] == "type")
    assert set(type_param["schema"]["enum"]) == {"api-idee", "css", "js"}


def test_resources_svg_y_geodata_documentan_name(spec):
    for path in ("/api/v1/resources/svg", "/api/v1/resources/geodata"):
        parameters = spec["paths"][path]["get"]["parameters"]
        assert {parameter["name"] for parameter in parameters} == {"f", "name"}
