# Catálogos de acciones y recursos

Datos de configuración que reproducen el catálogo publicado por API-IDEE 1.1.0.

| Fichero | Origen |
|---|---|
| `controls.json`, `services.json`, `versions.json`, `projection.json` | `api-idee-parent/src/main/filters/cnig-desarrollo.properties` |
| `version.json` | `api-idee-rest/src/main/resources/properties/version.properties` |
| `plugins.json` | `api-idee-rest/src/main/resources/properties/resourcesPlugins.json` |
| `resources_svg.json` | `api-idee-rest/src/main/resources/properties/resources_svg.json` |
| `resources_geodata.json` | `api-idee-rest/src/main/resources/properties/resources_geodata.json` |
| `external_plugins.json` | `api-idee-rest/src/main/webapp/data/plugins.json` (copia de respaldo) |

Referencia: `Desarrollos-IDEE/API-IDEE`, rama `develop`, commit `dd0759e` (2026-10-26).

Las URLs conservan los marcadores `${api-idee.url}` y
`${api-idee.static_resources.url}`; el cargador los sustituye con la configuración
`API_IDEE["PUBLIC_URL"]` y `API_IDEE["STATIC_RESOURCES_URL"]`. Así el catálogo no
depende del dominio de despliegue.

Al actualizar estos ficheros hay que mantener el esquema que consume el cliente
1.1.0 y revisar las pruebas de contrato de `tests/contract/actions/`.
