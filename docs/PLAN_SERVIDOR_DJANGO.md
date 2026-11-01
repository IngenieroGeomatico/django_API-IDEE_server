# Plan de migración del servidor de API-IDEE a Django y normalización de parámetros GET

| Campo | Valor |
|---|---|
| **Estado** | Estudio previo y plan de trabajos |
| **Fecha** | 30 de octubre de 2026 |
| **Ámbito** | Parte servidor de API-IDEE (`api-idee-rest`, `api-idee-proxy`, `api-idee-database`, `api-idee-parent`) y parámetros GET de la API |
| **Referencia** | `Desarrollos-IDEE/API-IDEE`, rama `develop`, commit `dd0759e` (2026-10-26) |
| **Destino** | Servicio Django 5.2 LTS + Python 3.12, compatible con el cliente API-IDEE 1.1.0 |
| **Documento** | `.opencode/docs/PLAN_SERVIDOR_DJANGO.md` |

> Este documento es un plan de trabajo, no una implementación. Las estimaciones son orientativas y suponen un desarrollador con experiencia en Django y SIG. Las rutas y nombres de parámetros actuales se han extraído del código de la rama `develop` y de la wiki oficial, no de su documentación de usuario.

---

## Estado de implementación

| Fase | Estado | Fecha | Evidencia |
|---|---|---|---|
| 0. Preparación | ✅ Completada (T-00.1 parcial) | 2026-11-01 | `config/`, `tests/golden/urls.yaml`, `docs/adr/`, CI |
| 1. Núcleo HTTP y normalización | ✅ Completada | 2026-11-01 | `apps/core/`, 150 tests, `/api/v1/`, Problem Details |
| 2. Acciones y recursos | ⏳ Pendiente | — | — |
| 3. Visor y builder | ⏳ Pendiente | — | — |
| 4. Proxy | ⏳ Pendiente | — | — |
| 5. Base de datos | ⏳ Pendiente | — | — |
| 6. Correo, legacy, estáticos y despliegue | ⏳ Pendiente | — | — |
| 7. Cutover | ⏳ Pendiente | — | — |

**Desviaciones aprobadas respecto a este plan**

- **Stack**: Django 6.1.2 + Python 3.14 (el plan fijaba Django 5.2 LTS + Python 3.12; 5.2 no soporta 3.14). Ver `docs/adr/0002-stack-django61-python314.md`.
- **Repositorio**: servidor en repositorio propio; la galería solo consume. Ver `docs/adr/0001-repositorio-servidor.md`.
- **BD de la aplicación**: SQLite en desarrollo y tests; los datasources PostGIS se configuran aparte en la fase 5. Ver `docs/adr/0007-base-de-datos-dev.md`.
- **T-00.1**: se ha creado una semilla de 48 URLs y el script `scripts/capture_golden.py`; la captura real contra el servidor actual queda pendiente de acceso al entorno.

**Entregado en la fase 0**

- Proyecto Django con settings `base`/`dev`/`prod`/`test`, `.env.example` y `pyproject.toml`.
- `ruff`, `ruff format`, `mypy` y `pytest` en verde; CI en `.github/workflows/ci.yml`.
- ADRs 0001–0007.
- Corpus golden y validador de estructura.

**Entregado en la fase 1**

- `Parametros`: lectura única, case-insensitive, alias con `Deprecation`, duplicados, límites y accesores tipados.
- CRS (EPSG/URN/URI/CRS84, orden de ejes), `bbox` 4/6, dominio y reproyección, RFC 3339 e intervalos.
- Problem Details (RFC 9457) + middleware, handlers 4xx/5xx y traducción de errores de Django Ninja.
- Negociación `f`/`Accept` con 406, ETag/304, `Vary`, `Content-Crs`, JSONP validado y `Link`.
- Paginación OGC (`limit`/`offset`/`numberMatched`/`links`).
- CORS por allowlist, CSP con nonce, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `X-Request-Id` y logs estructurados.

---

## Índice

0. [Resumen ejecutivo](#0-resumen-ejecutivo)
1. [Alcance](#1-alcance)
2. [Estudio del servidor actual](#2-estudio-del-servidor-actual)
3. [Arquitectura Django propuesta](#3-arquitectura-django-propuesta)
4. [Normalización de parámetros GET](#4-normalización-de-parámetros-get)
5. [Plan de trabajos](#5-plan-de-trabajos)
6. [Pruebas y validación](#6-pruebas-y-validación)
7. [Seguridad](#7-seguridad)
8. [Observabilidad y operación](#8-observabilidad-y-operación)
9. [Riesgos](#9-riesgos)
10. [Decisiones abiertas](#10-decisiones-abiertas)
- [Anexo A. Inventario de endpoints](#anexo-a-inventario-de-endpoints)
- [Anexo B. Inventario de parámetros GET](#anexo-b-inventario-de-parámetros-get)
- [Anexo C. Referencias](#anexo-c-referencias)
- [Anexo D. Checklist de arranque](#anexo-d-checklist-de-arranque)

---

## 0. Resumen ejecutivo

El servidor de API-IDEE es un **WAR de Java** con cuatro responsabilidades bien separadas:

1. **Generar el visor** a partir de parámetros GET (`index.jsp`, `visor.jsp`, `GET/POST /api/js`).
2. **Servir metadatos** de la propia API (`/api/actions/*`): controles, plugins, servicios, versión, recursos SVG/geodatos.
3. **Hacer de proxy** para saltar CORS (`/api/proxy`, `/api/proxy/image`, `/proxyPost`).
4. **Exponer bases de datos PostGIS** (`/api/database/*`) y **enviar correo** (`/api/email`).

La migración a Django es viable y recomendable, pero **no es un port línea a línea**: el código actual arrastra tres problemas estructurales que conviene corregir en el mismo movimiento:

- **Seguridad**: el proxy no valida destinos (SSRF), la base de datos acepta SQL arbitrario y credenciales codificadas en la URL, el JSONP no valida el callback y CORS está abierto a `*`.
- **Interoperabilidad**: los parámetros GET son un dialecto propio (`layers` posicional con `*`, `formato` en vez de `f`, `bbox-crs` como SRID, `%` sustituido por `*`), con nombres duplicados o mal escritos (`projection`/`srs`, `zoomConstrains`).
- **Mantenibilidad**: 74 JSP heredados, generación de JavaScript por concatenación de cadenas y ausencia de contrato OpenAPI.

La propuesta es una migración **estranguladora** en dos capas:

- **Capa de compatibilidad** en las rutas actuales (`/api/...`, `/proxyPost`, `/`), para que el cliente 1.1.0 y los visores existentes sigan funcionando sin tocar código.
- **Capa canónica** `/api/v1/...`, con parámetros normalizados según OGC API - Features/Common, CQL2, RFC 3986/9110/9457 y Problem Details.

El esfuerzo orientativo es de **~80 jornadas** (16-17 semanas con una persona, 8-9 con dos), repartidas en ocho fases. La normalización de parámetros es transversal: se implementa en la fase 1 y se aplica en cada fase siguiente.

---

## 1. Alcance

### 1.1 Dentro del alcance

- Reimplementar en Django los módulos `api-idee-rest`, `api-idee-proxy` y `api-idee-database`.
- Mantener las rutas públicas actuales y el comportamiento observable del cliente API-IDEE 1.1.0.
- Sustituir la generación de JavaScript por plantillas y configuración JSON segura.
- Normalizar los parámetros GET de la API conforme a estándares abiertos (OGC, IETF, ISO).
- Sustituir el acceso a base de datos por consultas parametrizadas, introspección cacheada y filtros CQL2.
- Endurecer proxy, CORS, JSONP, correo y cabeceras HTTP.
- Despliegue en contenedor, observabilidad y documentación OpenAPI.

### 1.2 Fuera del alcance

- Reescribir la librería JavaScript `api-idee-js` (se mantiene; solo cambian las URLs de configuración).
- Reescribir los 74 JSP heredados de `api-idee-legacy` (se congelan o se redirigen).
- Implementar un servidor WMS/WFS/WMTS propio: la API **consume** esos servicios, no los sirve.
- Renderizado de mapas en servidor (OGC API - Maps). Se deja como línea futura.
- Cambiar el modelo de datos de la galería (`mapas/`, `ext/`), que es estática.

### 1.3 Supuestos

- Se puede desplegar un servicio nuevo con Python 3.12 y PostgreSQL/PostGIS.
- El dominio público (`componentes.idee.es/api-idee/`) se puede mantener o redirigir; la migración no obliga a cambiar la URL pública.
- El cliente 1.1.0 seguirá siendo el principal durante la transición.
- Hay acceso a un entorno de preproducción con los mismos servicios WMS/WFS que producción.
- La licencia del código original permite la reimplementación; **revisar `LICENSE` antes de copiar código** (la galería es CC BY-NC).

---

## 2. Estudio del servidor actual

### 2.1 Mapa de módulos

| Módulo | Tecnología | Responsabilidad | Destino en Django |
|---|---|---|---|
| `api-idee-rest` | Java 8+, Jersey (JAX-RS), JSP, Maven | Visor, builder, acciones, proxy GET, BD, correo | Apps `viewers`, `actions`, `proxy`, `databases`, `mailer` |
| `api-idee-proxy` | Servlet Java | Proxy POST (`/proxyPost`) | App `proxy` |
| `api-idee-database` | JDBC, HikariCP, PostgreSQL/PostGIS | Conexión, introspección y consultas | App `databases` |
| `api-idee-parent` | Maven | Empaquetado WAR y filtros por entorno | `pyproject.toml`, Docker, settings por entorno |
| `api-idee-js` | JavaScript + webpack | Cliente de la API | Sin cambios (solo configuración de URLs) |
| `api-idee-legacy` | JSP | 74 componentes de la versión 1.0 | Congelar, redirigir o dar de baja |

El despliegue se resuelve con un `web.xml` que mapea `/api/*` a Jersey y `/proxyPost` al servlet `ProxyRedirect`. CORS se configura con `org.apache.catalina.filters.CorsFilter` y `cors.allowed.origins=*`.

### 2.2 Superficie HTTP

#### 2.2.1 Visor y builder

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| GET | `/` (`index.jsp`) | Parámetros GET del visor | HTML con CSS/JS y arranque de la API |
| GET | `/visor.jsp` | Parámetros GET del visor | HTML de visor para iframe |
| GET | `/api/js` | Parámetros GET del visor | JavaScript que crea el mapa |
| POST | `/api/js` | JSON `{ "map": {...}, "metadata": {...} }` | JavaScript que crea el mapa |

Los parámetros del visor se leen en **dos sitios distintos**:

- `ParametersParser` (servidor): `container`, `wmcfile`, `layers`, `controls`, `label`, `getfeatureinfo`, `zoom`, `projection`, `center`, `bbox`, `maxextent`, `callback`, `ticket`, `zoomConstrains`, `viewextent`, `bgcolorcontainer`.
- `configuration-1.1.0.js` (cliente): `center`, `zoom`, `srs`, `layers`, `zoomConstrains`, `extentConstrains`.

Esa duplicidad es la causa de varias inconsistencias (ver F-08 y F-09).

#### 2.2.2 Acciones y recursos

| Método | Ruta | Parámetros | Salida |
|---|---|---|---|
| GET | `/api/actions` | `callback` | Lista de rutas |
| GET | `/api/actions/controls` | `callback` | Lista de controles |
| GET | `/api/actions/services` | `callback` | Lista de tipos de capa |
| GET | `/api/actions/projection` | `callback` | `{ "code": "EPSG:3857" }` |
| GET | `/api/actions/plugins` | `callback` | Lista de plugins |
| GET | `/api/actions/plugins/external` | `callback` | Lista de plugins externos |
| GET | `/api/actions/plugins/external/reload` | `callback` | Resultado de la recarga |
| GET | `/api/actions/version` | `callback` | Versiones OL/Cesium/API y fecha |
| GET | `/api/actions/versions` | `callback` | Versiones publicadas |
| GET | `/api/actions/resources/svg` | `callback`, `name` | Colecciones SVG |
| GET | `/api/actions/resources/geodata` | `callback`, `name` | Colecciones de geodatos |
| GET | `/api/actions/resourcesPlugins` | `callback`, `name`, `version`, `type` | Recursos de plugins |

Todas responden `application/javascript` y envuelven el JSON en `callback(...)` si se pasa `callback`.

#### 2.2.3 Proxy

| Método | Ruta | Parámetros | Salida |
|---|---|---|---|
| GET | `/api/proxy` | `url` (obligatorio), `ticket`, `method` (`GET`/`POST`), `callback` | JSONP con el cuerpo remoto |
| GET | `/api/proxy/image` | `url` (obligatorio) | Imagen remota (máx. 1 MB) |
| GET/POST | `/proxyPost` | `url` (obligatorio), `ticket`; cuerpo en POST | Cuerpo remoto o error XML |

`/proxyPost` reconoce además marcas dentro de la URL (`apiideeop=wmc`, `kml`, `wmsfull`, `wmsinfo`, `geosearch`, `geoprint`, y cadenas como `wfst`, `wfs`, `ows`, `getcapabilities`, `wsdl`, `/processes/`, `legendgraphic`). Es una lista de casos especiales frágil y sensible a mayúsculas.

#### 2.2.4 Base de datos

| Método | Ruta | Parámetros | Salida |
|---|---|---|---|
| GET | `/api/database` | `callback` | Datasources configurados |
| GET | `/api/database/conformance` | — | Conformidad OGC API Features |
| GET | `/api/database/{ds}/collections` | `limit`, `offset`, `token`, `callback` | Tablas geográficas |
| GET | `/api/database/{ds}/attributes/{tabla}` | `schema`, `limit`, `offset`, `token`, `callback` | Columnas y tipos |
| GET | `/api/database/{ds}/collections/{tabla}/items` | `schema`, `limit`, `offset`, `token`, `formato`, `consumible`, `bbox`, `bbox-crs`, `aliasgeom`, `callback`, filtros `columna=valor`, `busquedaGeneral` | Filas en WKT/KML/GML/GeoJSON/MVT |
| GET | `/api/database/{ds}/{tabla}/sql` | `schema`, `select`, `where`, `groupby`, `having`, `orderby`, `limit`, `offset`, `token`, `callback` | Consulta personalizada |
| GET | `/api/database/{ds}` | `query`, `token`, `callback` | Consulta SQL nativa |
| GET | `/api/database/{ds}/layerfilter` | `layer`, `select`, `where`, `groupby`, `having`, `orderby`, `limit`, `offset`, `formato`, `token`, `callback` | Filtrado espacial |
| GET | `/api/database/{ds}/{tabla}/domain/{columna}` | `schema`, `token`, `callback` | Valores de dominio |

El parámetro `token` **no es un token**: es la base64 de la cadena de conexión (`host:puerto/bd...`), que se decodifica en el servidor y se usa para crear un `DataSource` al vuelo. Está documentado como “no recomendado en producción”, pero sigue expuesto.

#### 2.2.5 Correo

| Método | Ruta | Entrada | Salida |
|---|---|---|---|
| POST | `/api/email` | `multipart/form-data`: `subject`, `mailto`, `body` (JSON), `file` opcional, `callback` | Resultado del envío |

#### 2.2.6 Estáticos y JSP heredados

| Ruta | Contenido |
|---|---|
| `/assets/` | Temas, CSS e imágenes de la API |
| `/js/` | Bundles `apiidee.ol.min.js`, `apiidee.cesium.min.js`, `configuration.js` |
| `/plugins/` | Plugins compilados |
| `/wasm/` | `sql.js` y otros binarios WASM |
| `/data/` | `plugins.json`, `rest.json`, `others.json` |
| `/doc/` | Documentación JSDoc |
| `/*.jsp` | 74 componentes heredados (toc, printermap, getfeatureinfo, etc.) |

### 2.3 Formatos de respuesta

- **JSONP** por defecto en `/api/actions/*` y `/api/proxy`: `callback({...});` con `Content-Type: application/javascript`.
- **JSON** en `/api/database/*`, pero con claves en español (`Nombre`, `TipoDato`, `results`, `links`) y paginación propia (`totalElementos`, `numPagina`, `tamPagina`).
- **XML** de error en `/proxyPost`: `<error><descripcion>...</descripcion></error>`.
- **Texto plano** en varios errores de base de datos (`Response.status(400).entity("La conexión indicada no es válida")`).
- **CORS** `*` en todas las rutas.

### 2.4 Configuración

La configuración se reparte entre `configuration.properties`, `config-databases.properties` y los filtros Maven (`cnig-desarrollo.properties`, `local.properties`). Contiene:

- URLs públicas (`api-idee.url`, `api-idee.proxy.url`, `api-idee.proxy_post.url`, `api-idee.theme.url`).
- Listas de controles y servicios.
- `max.image.size` (1 MB).
- Credenciales SMTP y de base de datos.
- `database.whitelist`, `database.blacklist`, `database.list`.
- `plugins.external.base.url`.

### 2.5 Hallazgos del estudio

| ID | Severidad | Hallazgo | Impacto | Corrección propuesta |
|---|---|---|---|---|
| F-01 | **Crítica** | `Proxy.checkRequest()` está vacío y no hay allowlist de destinos | SSRF: acceso a red interna, metadata cloud, `file:` | Allowlist de esquemas/hosts/puertos, resolución y bloqueo de IP privadas |
| F-02 | **Crítica** | `/api/database/{ds}` acepta `query` SQL libre; `sql` acepta `select`, `where`, `groupby`, `having`, `orderby` | SQL injection y exfiltración | Retirar del API público; CQL2 + consultas parametrizadas; endpoint admin auditado |
| F-03 | **Crítica** | `token` = base64 de credenciales de conexión en la URL | Credenciales en logs, historial y referer | ID opaco firmado (HMAC) o sesión; credenciales solo en servidor |
| F-04 | **Alta** | JSONP sin validar `callback` | XSS reflejado | Validar `^[A-Za-z_$][A-Za-z0-9_$]{0,63}$`; deprecar JSONP |
| F-05 | **Alta** | CORS `*` en `web.xml` | Lectura cross-origin de endpoints con datos | Allowlist por origen; `*` solo en recursos públicos |
| F-06 | **Alta** | `JSBuilder` concatena parámetros en JavaScript | XSS si un valor contiene `"` o `</script>` | JSON + `json_script`, CSP con nonce |
| F-07 | **Alta** | `ticket` viaja en la query | Fuga en logs, proxies y `Referer` | `Authorization: Bearer` (RFC 6750) |
| F-08 | **Media** | `configuration.js` parsea con `indexOf` sobre `clave=valor` | Colisiones (`?myzoom=5` activa `zoom`), valores con `=` se truncan | Parser exacto y case-insensitive |
| F-09 | **Media** | Nombres duplicados o mal escritos: `projection`/`srs`, `zoomConstrains`/`extentConstrains`, `maxextent`/`maxExtent`, `bgcolorcontainer` | Comportamiento distinto entre servidor y cliente | Catálogo canónico + alias |
| F-10 | **Media** | `bbox-crs` es un SRID numérico, sin orden de ejes documentado | Interpretación errónea de bbox en 4326 | URI de CRS y orden de ejes explícito |
| F-11 | **Media** | `%` se sustituye por `*` en `LIKE` | Codificación no estándar y resultados inesperados | Percent-encoding RFC 3986 (`%25`) |
| F-12 | **Media** | `formato` en vez de `f`/`Accept`; `consumible` booleano ad hoc | Cliente y servidor acoplados; difícil de cachear | `f` + `Accept` + `Content-Disposition` |
| F-13 | **Media** | `post()` del proxy GET devuelve `null`; `checkResponse()` vacío | Errores 500 y validación inexistente | Implementar o eliminar la rama |
| F-14 | **Media** | 74 JSP heredados sin versión ni tests | Superficie de ataque y mantenimiento | Congelar, redirigir o 410 |
| F-15 | **Baja** | Paginación propia sin `links` `next`/`prev` ni `numberMatched` | Clientes no interoperables | OGC API Features |
| F-16 | **Baja** | Sin contrato OpenAPI ni tests de contrato | Regresiones silenciosas | OpenAPI 3.1 + Schemathesis |
| F-17 | **Media** | Sin límites de tiempo/tamaño en el proxy (salvo imagen 1 MB) | DoS y consumo de memoria | Timeouts, tamaño máximo, streaming |
| F-18 | **Baja** | `index.jsp`/`visor.jsp` dependen de `PluginsManager` y del sistema de ficheros | Difícil de desplegar y testear | Plantillas Django + catálogo en BD/cache |

### 2.6 Qué usa realmente el cliente 1.1.0

En el bundle `apiidee-1.1.0.ol.min.js` de esta galería, las únicas rutas del servidor que aparecen de forma literal son:

- `GET /api/actions/controls` (validación de nombres de control).
- `GET /api/actions/resources/svg` (enlace de ayuda del gestor de estilos).
- `GET /api/proxy` (JSONP) y `GET /api/proxy/image` (construidos desde `IDEE.config.PROXY_URL`).
- `POST /proxyPost` (construido desde `IDEE.config.PROXY_POST_URL`).
- Estáticos `/assets/`, `/wasm/`, `/js/`, `/plugins/`.
- `GET /` para el visor.

El resto de endpoints (`/api/actions/version`, `/plugins`, `/services`, `/projection`, `/api/database`, `/api/email`) no los consume el bundle 1.1.0, pero **sí forman parte del contrato público** y de la documentación. Deben portarse por compatibilidad, aunque se puedan priorizar después.

**Consecuencia para el plan:** la compatibilidad crítica es visor + proxy + estáticos + `actions/controls`. La base de datos y el correo se pueden migrar después sin romper la galería.

---

## 3. Arquitectura Django propuesta

### 3.1 Principios

1. **Compatibilidad primero**: las rutas actuales siguen respondiendo; el cliente 1.1.0 no se toca.
2. **Canónico después**: `/api/v1/...` con parámetros normalizados y OpenAPI.
3. **Sin estado en el servidor** salvo caché y sesiones firmadas.
4. **Todo parámetro se valida antes de usarse**; nada se reenvía “tal cual”.
5. **Todo error es Problem Details** (`application/problem+json`), salvo el JSONP heredado.
6. **Todo acceso a datos es parametrizado**; nunca SQL concatenado.
7. **Todo destino externo pasa por allowlist** y límites de tiempo/tamaño.
8. **Los recursos públicos se cachean**; los autenticados, no.

### 3.2 Arquitectura

```
                         ┌──────────────────────────────┐
  navegador / visor ───▶ │  nginx (TLS, gzip, límites)  │
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │  Django 5.2 (ASGI + WSGI)    │
                         │  ├─ viewers   (HTML/JS)      │
                         │  ├─ actions   (catálogo)     │
                         │  ├─ proxy     (streaming)    │
                         │  ├─ databases (OGC API)      │
                         │  ├─ mailer    (SMTP)         │
                         │  └─ core      (params/errores)│
                         └───────┬──────────────┬───────┘
                                 │              │
                    ┌────────────▼───┐   ┌──────▼─────────┐
                    │ PostgreSQL/     │   │ Redis (caché,  │
                    │ PostGIS         │   │ rate limit)    │
                    └────────────────┘   └────────────────┘
                                 │
                    ┌────────────▼─────────────────────────┐
                    │ Servicios OGC externos (WMS/WFS/WMTS) │
                    │ y recursos públicos (WMC, SVG, etc.)  │
                    └───────────────────────────────────────┘
```

### 3.3 Estructura del proyecto

```
api-idee-django/
├── manage.py
├── pyproject.toml
├── README.md
├── .env.example
├── config/
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   ├── prod.py
│   │   └── test.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/
│   ├── core/            # Parametros, CRS, bbox, Problem Details, paginación
│   ├── viewers/         # index, visor, builder, /api/v1/viewers
│   ├── actions/         # /api/actions/*
│   ├── catalog/         # recursos SVG/geodata/plugins
│   ├── proxy/           # /api/proxy, /api/proxy/image, /proxyPost
│   ├── databases/       # /api/database/* y /api/v1/datasources/*
│   ├── mailer/          # /api/email
│   └── legacy/          # redirecciones y 410 de los JSP
├── static/
│   ├── assets/
│   ├── js/
│   ├── plugins/
│   ├── wasm/
│   └── data/
├── templates/
│   ├── viewer.html
│   ├── visor.html
│   └── errors/
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── golden/
│   └── security/
└── deploy/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── nginx.conf
    └── entrypoint.sh
```

### 3.4 Stack y dependencias

| Pieza | Elección | Motivo |
|---|---|---|
| Framework | Django 5.2 LTS | Soporte hasta 2028; madurez |
| Python | 3.12 | Soportado por Django 5.2 |
| API canónica | Django Ninja | Tipado con Pydantic v2, OpenAPI 3.1, async |
| Alternativa | Django REST Framework + drf-spectacular | Si el equipo ya lo domina |
| HTTP cliente | `httpx` | Streaming async, timeouts, HTTP/2 |
| BD | `psycopg[binary,pool]` 3.x | Parametrización y pool |
| GIS | `django.contrib.gis`, `pyproj`, `shapely` | CRS, geometrías, transformaciones |
| CQL2 | `pygeofilter` | Parser CQL2 texto/JSON y backend SQL |
| CORS | `django-cors-headers` | Allowlist por origen |
| Estáticos | WhiteNoise (pequeños) + nginx (grandes/WASM) | Simplicidad y rendimiento |
| Config | `django-environ` | Variables de entorno |
| Tests | `pytest`, `pytest-django`, `respx`, `schemathesis` | Unitarios, mocks HTTP, contrato |
| Calidad | `ruff`, `mypy` | Lint y tipos |
| Servidor | `gunicorn` + `uvicorn` workers, o `uvicorn` | WSGI/ASGI |
| Observabilidad | `django-prometheus`, OpenTelemetry | Métricas y trazas |

> **Decisión recomendada:** Django Ninja para `/api/v1` y vistas Django normales para la fachada heredada (JSONP, streaming, HTML). No mezclar DRF y Ninja en el mismo servicio salvo que haya una razón fuerte.

### 3.5 Configuración y secretos

Variables de entorno (nunca en el repositorio):

| Variable | Ejemplo | Uso |
|---|---|---|
| `DJANGO_SECRET_KEY` | — | Firma de sesiones y tokens |
| `DJANGO_DEBUG` | `false` | Depuración |
| `ALLOWED_HOSTS` | `componentes.idee.es,localhost` | Hosts |
| `CORS_ALLOWED_ORIGINS` | `https://www.idee.es,https://componentes.idee.es` | CORS |
| `API_IDEE_PUBLIC_URL` | `https://componentes.idee.es/api-idee/` | URLs generadas |
| `PROXY_ALLOWED_HOSTS` | `*.idee.es,*.ign.es` | Allowlist SSRF |
| `PROXY_TIMEOUT` | `15` | Segundos |
| `PROXY_MAX_BYTES` | `10485760` | Tamaño máximo |
| `DB_DATASOURCES` | JSON o ruta | Datasources |
| `DB_STATEMENT_TIMEOUT` | `15000` | ms |
| `REDIS_URL` | `redis://redis:6379/0` | Caché y rate limit |
| `EMAIL_HOST` | — | SMTP |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | — | SMTP |
| `DEFAULT_FROM_EMAIL` | `mail-cnig-noreply@cnig.es` | Remitente |

Los datasources se guardan en base de datos con la contraseña cifrada (Fernet/KMS) o se inyectan por entorno. **Nunca** se aceptan credenciales desde la URL.

### 3.6 Mapa de rutas legacy → nueva

| Ruta actual | Ruta canónica | Estrategia |
|---|---|---|
| `/` | `/` | Se mantiene; internamente usa el modelo canónico |
| `/visor.jsp` | `/visor` | 301 a `/visor`; se conserva alias |
| `/api/js` (GET/POST) | `/api/v1/viewers` | GET legacy sigue; POST canónico |
| `/api/actions` | `/api/v1/actions` | Alias |
| `/api/actions/controls` | `/api/v1/actions/controls` | Alias |
| `/api/actions/services` | `/api/v1/actions/services` | Alias |
| `/api/actions/projection` | `/api/v1/actions/projection` | Alias |
| `/api/actions/plugins` | `/api/v1/actions/plugins` | Alias |
| `/api/actions/version` | `/api/v1/actions/version` | Alias |
| `/api/actions/resources/svg` | `/api/v1/resources/svg` | Alias |
| `/api/actions/resources/geodata` | `/api/v1/resources/geodata` | Alias |
| `/api/proxy` | `/api/v1/proxy` | Alias JSONP + canónico |
| `/api/proxy/image` | `/api/v1/proxy/image` | Alias |
| `/proxyPost` | `/api/v1/proxy` (POST) | Alias |
| `/api/database` | `/api/v1/datasources` | Alias |
| `/api/database/{ds}/...` | `/api/v1/datasources/{ds}/...` | Alias |
| `/api/email` | `/api/v1/email` | Alias |
| `/*.jsp` (74) | `/api/v1/legacy/{name}` o 410 | Congelar; `Link` a la nueva |

La fachada legacy **no duplica lógica**: traduce la petición al modelo canónico y llama al mismo servicio. Así se evita que las dos capas se desincronicen.

### 3.7 Núcleo común (`apps/core`)

Responsabilidades:

- `Parametros`: lectura case-insensitive, resolución de alias, detección de duplicados, conversión tipada.
- `Crs`: validación y normalización de CRS (`EPSG:4326`, URN, URI), orden de ejes, transformación con `pyproj`.
- `Bbox`: parseo de 4/6 valores, validación, reproyección, `bbox-crs`.
- `ProblemDetails`: excepción y manejador que devuelve `application/problem+json`.
- `Paginacion`: `limit`/`offset`, `numberMatched`, `numberReturned`, `links`.
- `Negociacion`: `f` + `Accept`, `Vary`, `ETag`, `Content-Crs`.
- `Limites`: longitudes máximas, número máximo de parámetros, profundidad de filtro.

Esbozo de la pieza central:

```python
# apps/core/params.py
from dataclasses import dataclass

ALIASES = {
    "srs": "crs",
    "projection": "crs",
    "maxextent": "max-extent",
    "zoomconstrains": "zoom-constraints",
    "extentconstrains": "extent-constraints",
    "viewextent": "view-extent",
    "bgcolorcontainer": "bgcolor",
    "getfeatureinfo": "info-format",
    "wmcfile": "wmc",
    "implementation": "impl",
    "formato": "f",
}

@dataclass(frozen=True)
class Parametros:
    crudo: dict[str, list[str]]

    @classmethod
    def desde_request(cls, request):
        # 1. claves en minúsculas, 2. alias, 3. duplicados
        ...

    def texto(self, nombre, *, obligatorio=False, max_len=2048): ...
    def entero(self, nombre, *, defecto=None, minimo=None, maximo=None): ...
    def booleano(self, nombre, *, defecto=False): ...
    def lista(self, nombre, *, separador=","): ...
    def crs(self, nombre="crs", *, defecto="CRS84"): ...
    def bbox(self, nombre="bbox", *, crs="CRS84"): ...
```

Regla: **una sola lectura de `request.GET`**; las vistas no vuelven a leer `request.GET` directamente.

### 3.8 Proxy

Diseño:

- `GET /api/v1/proxy?url=...` → cuerpo remoto tal cual, con `Content-Type` del origen y `X-Upstream-Status`.
- `POST /api/v1/proxy` → cuerpo remoto; el destino va en `X-Target-URL` o en el JSON `{ "url": ..., "method": ..., "headers": {...}, "body": ... }`.
- `GET /api/proxy` (legacy) → JSONP si hay `callback`; si no, JSON `{ status, headers, body }`.
- `GET /api/proxy/image?url=...` → streaming de imagen con `Content-Type` validado y tamaño máximo.
- `/proxyPost` (legacy) → mismo motor, sin JSONP.

Componentes:

1. **Validador de URL** (`apps/proxy/validators.py`):
   - Esquemas permitidos: `http`, `https`.
   - Sin credenciales embebidas (`user:pass@`).
   - Puerto permitido: 80, 443 o allowlist.
   - Host en allowlist (sufijos `*.idee.es`, `*.ign.es`, configurables).
   - Resolución DNS y bloqueo de rangos privados, loopback, link-local, multicast, reservados y metadata (`169.254.169.254`, `fd00:ec2::254`).
   - Revalidación en cada redirección (máx. 3) o redirecciones deshabilitadas.
2. **Cliente** (`apps/proxy/client.py`): `httpx.AsyncClient` con `timeout`, `follow_redirects=False`, `max_redirects`, `limits`.
3. **Streaming**: `StreamingHttpResponse` con iterador async; corte al superar `PROXY_MAX_BYTES`.
4. **Caché**: solo GET idempotentes y respuestas 200; clave = URL canónica + `Accept`; TTL configurable; `Vary: Accept`.
5. **Rate limit**: por IP y por ruta, con Redis; `429` + `Retry-After`.

Puntos críticos:

- **No** reenviar `Cookie`, `Authorization` ni cabeceras hop-by-hop del cliente.
- **No** devolver `Set-Cookie` del origen.
- **No** permitir `file:`, `gopher:`, `ftp:`, `data:`.
- **No** confiar en `Content-Length` del origen; contar bytes reales.
- **Sí** propagar `Content-Type` solo si está en allowlist (`text/*`, `application/json`, `application/xml`, `image/*`, `application/gml+xml`, `application/geo+json`).
- **Sí** añadir `X-Content-Type-Options: nosniff`.

### 3.9 Base de datos

Modelo:

- `DataSource`: nombre, host, puerto, base, usuario, contraseña cifrada, srid, opciones, activo.
- `Dataset` (opcional): tabla/vista publicada, esquema, columna geométrica, título, descripción, licencia.
- La introspección (`information_schema`, `pg_class`, `geometry_columns`) se cachea en Redis con TTL.

Endpoints canónicos (OGC API - Features):

```
GET /api/v1/datasources
GET /api/v1/datasources/{ds}
GET /api/v1/datasources/{ds}/conformance
GET /api/v1/datasources/{ds}/collections
GET /api/v1/datasources/{ds}/collections/{collectionId}
GET /api/v1/datasources/{ds}/collections/{collectionId}/items
GET /api/v1/datasources/{ds}/collections/{collectionId}/items/{featureId}
GET /api/v1/datasources/{ds}/collections/{collectionId}/queryables
```

Parámetros: `f`, `limit`, `offset`, `bbox`, `bbox-crs`, `crs`, `datetime`, `filter`, `filter-lang`, `filter-crs`, `sortby`, `properties`.

Consultas:

- Identificadores con `psycopg.sql.Identifier`, valores con `%s`.
- `LIMIT`/`OFFSET` acotados.
- `SET LOCAL statement_timeout`, `SET LOCAL default_transaction_read_only = on`.
- Rol de BD de solo lectura.
- `COUNT(*)` para `numberMatched`, con caché corta.
- MVT con `ST_AsMVT` y `ST_TileEnvelope`; validar `z/x/y`.

Lo que **no** se porta al API público:

- `query` (SQL nativo).
- `select`, `where`, `groupby`, `having`, `orderby` como fragmentos.
- `layerfilter` con GeoJSON y SQL.
- `token` base64.

Se pueden conservar en un endpoint **admin** (`/api/v1/admin/query`) con autenticación, allowlist de tablas, auditoría y `statement_timeout`, o eliminarse definitivamente. Recomendación: eliminarlos y ofrecer CQL2.

### 3.10 Visor y builder

- `GET /` y `GET /visor` con plantillas Django.
- `GET /api/js` legacy: sigue devolviendo JavaScript, pero generado desde un **JSON de configuración** y con escapado seguro.
- `POST /api/v1/viewers` con JSON:

```json
{
  "container": "map",
  "view": {
    "crs": "EPSG:3857",
    "center": [-3.7038, 40.4168],
    "zoom": 5
  },
  "layers": [
    {
      "type": "WMS",
      "id": "unidades",
      "url": "https://www.ign.es/wms-inspire/unidades-administrativas",
      "layers": "AU.AdministrativeUnit",
      "version": "1.3.0",
      "transparent": true,
      "queryable": true
    }
  ],
  "controls": ["scale", "scaleline"],
  "plugins": [{ "type": "toc" }]
}
```

- Respuesta: `201 Created`, `Location: /api/v1/viewers/{id}`, cuerpo HTML o JSON según `f`.
- El servidor transforma `center` de `view.crs` a EPSG:3857 (2D) o EPSG:4326 (Cesium) antes de emitir la configuración al cliente. Así se resuelve de una vez la ambigüedad 2D/3D documentada en esta galería.

### 3.11 Acciones y recursos

- `GET /api/v1/actions` → índice con `links`.
- Catálogo de controles/plugins/servicios en BD o en un JSON versionado; cacheado con `ETag`.
- Recursos SVG/geodata: servir desde fichero o BD, con `ETag`, `Last-Modified` y `Cache-Control`.
- Plugins externos: listar desde `plugins.external.base.url` con TTL y allowlist de host.

### 3.12 Correo

- `POST /api/v1/email` con JSON o multipart.
- Validar `mailto` con `validate_email`, asunto con longitud máxima, cuerpo con esquema Pydantic.
- Adjunto: tamaño máximo, tipos permitidos, nombre saneado.
- Rate limit por IP y por destinatario.
- `EmailMultiAlternatives` con versión texto y HTML.
- Sin `callback` (no tiene sentido en POST).

### 3.13 Estáticos

- `/assets/`, `/js/`, `/plugins/`, `/wasm/`, `/data/`, `/doc/`.
- Ficheros con hash: `Cache-Control: public, max-age=31536000, immutable`.
- `configuration.js` sin caché larga (o con `ETag`), porque cambia con el despliegue.
- `Cross-Origin-Resource-Policy: cross-origin` para assets consumidos por terceros.
- nginx para WASM (MIME `application/wasm`) y ficheros grandes.

### 3.14 Despliegue

- Docker multi-stage (`python:3.12-slim`), usuario no root.
- `gunicorn` con workers `uvicorn` para vistas async, o `uvicorn --workers`.
- nginx: TLS, gzip/brotli, `client_max_body_size` para WFS-T/print, `proxy_read_timeout`, `limit_req`.
- Migraciones en el entrypoint (con lock) o job separado.
- Healthchecks `/healthz` y `/readyz`.
- CI: lint, tipos, tests, build de imagen, escaneo de dependencias.

---

## 4. Normalización de parámetros GET

### 4.1 Normas de referencia

| Norma | Uso en el proyecto |
|---|---|
| **RFC 3986** | Sintaxis de URI, percent-encoding, componentes |
| **RFC 9110 / 9111** | Semántica HTTP, métodos, caché |
| **RFC 9457** | Problem Details para errores |
| **RFC 6750** | `Authorization: Bearer` |
| **RFC 8288** | Cabecera `Link` (`self`, `next`, `prev`, `service-desc`) |
| **RFC 8594** | `Sunset` para retirada de rutas |
| **RFC 9745** | `Deprecation` |
| **RFC 7946** | GeoJSON y CRS84 |
| **RFC 3339** | `datetime` |
| **OGC WMS 1.3.0 (06-042)** | KVP de mapas |
| **OGC WMS 1.1.1 (01-068r3)** | Compatibilidad `SRS` |
| **OGC WFS 2.0.0 (09-025r1)** | KVP de features |
| **OGC WMTS 1.0.0 (07-057r7)** | KVP de teselas |
| **OGC CSW 2.0.2 / 3.0.0** | KVP de catálogo |
| **OGC API - Features Part 1 (17-069r4)** | Landing, colecciones, items, `limit`, `bbox`, `datetime` |
| **OGC API - Features Part 2 (18-058r1)** | `crs`, `bbox-crs`, `Content-Crs` |
| **OGC API - Features Part 3 (19-079)** | `filter`, `filter-lang`, `filter-crs` |
| **OGC API - Features Part 6** | `properties` (selección de propiedades) |
| **OGC API - Features Part 8** | `sortby` (ordenación) |
| **OGC API - Common Part 1 (19-072)** | `f`, landing, conformance |
| **OGC API - Tiles Part 1** | Teselas vectoriales/ráster |
| **CQL2 (21-065)** | Lenguaje de filtro |
| **INSPIRE** | `language` ISO 639-2/B |
| **OpenAPI 3.1** | Contrato del API |

### 4.2 Reglas transversales

| ID | Regla | Detalle |
|---|---|---|
| R-01 | **Nombres de parámetro case-insensitive** | Se aceptan `LIMIT`, `limit`, `Limit`; se canonicaliza a minúsculas |
| R-02 | **Coincidencia exacta de clave** | Nunca `indexOf`/substring; `myzoom` no es `zoom` |
| R-03 | **Sin duplicados** | Un parámetro repetido → `400` salvo los multivaluados declarados (`layer`, `collection`, `property`) |
| R-04 | **Percent-decoding estricto** | `%20` para espacio; se acepta `+` solo por compatibilidad y se documenta |
| R-05 | **Valores vacíos** | Opcional vacío = ausente; obligatorio vacío = `400` |
| R-06 | **Booleanos** | `true|false` (case-insensitive); alias `1|0` solo en legacy |
| R-07 | **Números** | Punto decimal, sin separador de miles, sin `NaN`/`Infinity` |
| R-08 | **Enumeraciones** | Case-insensitive; se canonicaliza a mayúsculas/minúsculas según norma |
| R-09 | **Listas** | Separador `,`; sin espacios alrededor; se recortan y se eliminan vacíos |
| R-10 | **Longitud** | URL ≤ 8 KB, ≤ 50 parámetros, valor ≤ 2 KB (configurable) |
| R-11 | **Nada de secretos en query** | Tokens y credenciales solo en cabeceras o cuerpo |
| R-12 | **Errores uniformes** | Problem Details con `invalid-params` |

### 4.3 Catálogo canónico

#### Comunes (OGC API / HTTP)

| Parámetro | Tipo | Norma | Valores | Notas |
|---|---|---|---|---|
| `f` | enum | OGC API Common | `json`, `html`, `geojson`, `gml`, `mvt` | Sustituye a `formato`; `Accept` manda si no hay `f` |
| `lang` | string | RFC 9110 / INSPIRE | `es`, `en`, `spa`, `eng` | `Accept-Language` como alternativa |
| `limit` | int | OGC API Features 1 | 1..10000, defecto 100 | Acotado por configuración |
| `offset` | int | OGC API Features 1 (ejemplos) | ≥ 0 | Paginación por desplazamiento |
| `bbox` | lista 4/6 | OGC API Features 1 | `minx,miny,maxx,maxy[,minz,maxz]` | Orden según CRS |
| `bbox-crs` | CRS | OGC API Features 2 | URI o `EPSG:n` | Defecto CRS84 |
| `crs` | CRS | OGC API Features 2 | URI o `EPSG:n` | CRS de salida |
| `datetime` | string | OGC API Features 1 | RFC 3339 o intervalo `a/b`, `../b`, `a/..` | |
| `filter` | string/JSON | OGC API Features 3 | CQL2 texto o JSON | Sustituye a `where`/`busquedaGeneral` |
| `filter-lang` | enum | OGC API Features 3 | `cql2-text`, `cql2-json` | Defecto `cql2-text` |
| `filter-crs` | CRS | OGC API Features 3 | URI o `EPSG:n` | CRS de las geometrías del filtro |
| `properties` | lista | OGC API Features 6 | `prop1,prop2` | Proyección de columnas |
| `sortby` | lista | OGC API Features 8 | `+prop,-prop` | `+` ascendente, `-` descendente |

#### Visor

| Parámetro | Tipo | Norma / referencia | Valores | Notas |
|---|---|---|---|---|
| `container` | string | Extensión | id DOM | Defecto `map` |
| `layers` | DSL / lista | Extensión (legacy) | `TIPO*campo*...` | Se mantiene como alias; canónico `collections` o JSON |
| `controls` | lista | Extensión | `scale,scaleline,...` | Validar contra catálogo |
| `plugins` | lista | Extensión | `toc,measurebar,...` | Validar contra catálogo |
| `wmc` | lista | OGC WMC 1.0.0 | `url*nombre` | Alias `wmcfile` |
| `center` | lista 2/3 | Extensión | `x,y[,pin]` | Acompañar de `center-crs` |
| `center-crs` | CRS | Extensión | `EPSG:3857` | Defecto `EPSG:3857` (legacy) |
| `zoom` | int | Extensión | 0..28 | Preferir `bbox` en clientes nuevos |
| `max-extent` | lista 4 | Extensión | `minx,miny,maxx,maxy` | Alias `maxextent` |
| `max-extent-crs` | CRS | Extensión | `EPSG:3857` | |
| `zoom-constraints` | string | Extensión | `min,max` | Alias `zoomConstrains` |
| `extent-constraints` | lista 4 | Extensión | `minx,miny,maxx,maxy` | Alias `extentConstrains` |
| `view-extent` | lista 4 | Extensión | `minx,miny,maxx,maxy` | Alias `viewextent` |
| `bgcolor` | color | WMS-like | `#RRGGBB`, `red`, `rgba(...)` | Alias `bgcolorcontainer` |
| `label` | string | Extensión | Texto | **Escapado obligatorio**; no HTML |
| `info-format` | enum | Extensión | `text/plain`, `text/html`, `application/json` | Alias `getfeatureinfo` |
| `impl` | enum | Extensión | `ol`, `cesium` | Alias `implementation` |
| `callback` | string | JSONP (obsoleto) | identificador JS | Validar y deprecar |
| `ticket` | string | Obsoleto | — | Sustituir por `Authorization` |

#### OGC KVP reenviados

| Parámetro | Norma | Notas |
|---|---|---|
| `service` | WMS/WFS/WMTS/CSW | `WMS`, `WFS`, `WMTS`, `CSW` |
| `request` | WMS/WFS/WMTS/CSW | `GetCapabilities`, `GetMap`, `GetFeatureInfo`, `GetRecords`... |
| `version` | WMS/WFS/WMTS/CSW | `1.3.0`, `2.0.0`, `1.0.0`, `2.0.2` |
| `layers` / `layer` | WMS / WMTS | Lista vs único |
| `styles` | WMS | Uno por capa; vacío permitido |
| `crs` / `srs` | WMS 1.3.0 / 1.1.1 | `srs` solo legacy |
| `bbox` | WMS/WFS | Orden de ejes según CRS |
| `width` / `height` | WMS | Enteros positivos |
| `format` | WMS | MIME (`image/png`) |
| `transparent` | WMS | `TRUE|FALSE` |
| `bgcolor` | WMS | `0xRRGGBB` |
| `exceptions` | WMS | `XML|INIMAGE|BLANK` |
| `time` / `elevation` / `dim_*` | WMS | ISO 8601 |
| `typenames` / `typename` | WFS 2.0 / 1.1 | Alias |
| `srsname` | WFS | CRS URI |
| `count` / `maxfeatures` | WFS 2.0 / 1.1 | Alias |
| `startindex` | WFS 2.0 | ≥ 0 |
| `propertyname` | WFS | Lista |
| `sortby` | WFS | `prop A|D`; en OGC API `+prop,-prop` |
| `outputformat` | WFS | MIME |
| `resulttype` | WFS | `results|hits` |
| `filter` / `cql_filter` | WFS / CQL2 | `cql_filter` → `filter` + `filter-lang=cql2-text` |
| `language` | INSPIRE | ISO 639-2/B |

#### Base de datos

| Parámetro | Tipo | Norma | Notas |
|---|---|---|---|
| `ds` | string | Extensión | ID opaco del datasource (sustituye a `token`) |
| `schema` | string | Extensión | Defecto `public`; validar contra introspección |
| `limit` / `offset` | int | OGC API Features 1 | Acotados |
| `bbox` / `bbox-crs` / `crs` | — | OGC API Features 1/2 | |
| `f` | enum | OGC API Common | `json`, `geojson`, `gml`, `kml`, `mvt`, `html` |
| `filter` / `filter-lang` / `filter-crs` | — | OGC API Features 3 / CQL2 | |
| `sortby` | lista | OGC API Features 8 | |
| `properties` | lista | OGC API Features 6 | |
| `datetime` | string | OGC API Features 1 | Si la tabla tiene columna temporal |

### 4.4 Alias legacy

| Legacy | Canónico | Acción |
|---|---|---|
| `projection` | `crs` | Aceptar con `Deprecation: true`; el sufijo `*d` se traduce a `crs` + `center-crs` |
| `srs` | `crs` | Aceptar; unificar con `projection` |
| `maxextent` / `maxExtent` | `max-extent` | Aceptar ambos |
| `zoomConstrains` | `zoom-constraints` | Aceptar el typo histórico |
| `extentConstrains` | `extent-constraints` | Aceptar el typo histórico |
| `viewextent` | `view-extent` | Aceptar |
| `bgcolorcontainer` | `bgcolor` | Aceptar |
| `getfeatureinfo` | `info-format` | Aceptar |
| `wmcfile` | `wmc` | Aceptar |
| `implementation` | `impl` | Aceptar |
| `formato` | `f` | Aceptar; `Accept` tiene prioridad |
| `token` | `ds` | **No aceptar en `/api/v1`**; solo legacy con aviso |
| `consumible` | — | Deprecar; usar `f` y `Content-Disposition` |
| `aliasgeom` | `geometry-name` | Deprecar |
| `busquedaGeneral` | `filter` | Traducir a CQL2 |
| `query` / `select` / `where` / `groupby` / `having` / `orderby` | `filter` / `sortby` / `properties` | **No aceptar en `/api/v1`** |
| `TYPENAME` | `typenames` | Aceptar en reenvío WFS |
| `MAXFEATURES` | `count` | Aceptar en reenvío WFS 1.1 |
| `SRS` | `crs` | Aceptar en reenvío WMS 1.1.1 |
| `CQL_FILTER` | `filter` + `filter-lang=cql2-text` | Aceptar |
| `FORMATO` | `f` | Aceptar |
| `callback` | — | Deprecar; validar si se mantiene |
| `ticket` | `Authorization` | Deprecar; no registrar |

### 4.5 Capas: del DSL posicional a un modelo

El parámetro `layers` actual es un mini-lenguaje posicional:

```
layers=WMS*Unidad administrativa*https://.../wms?*AU.AdministrativeUnit*true*false**true*true*true*1.3.0
```

Problemas:

- El orden de los campos cambia por tipo de capa.
- Los campos vacíos (`**`) son significativos.
- Las URLs pueden contener `,` o `*`, que rompen el parser.
- No hay validación de tipos ni de campos obligatorios.
- El cliente y el servidor tienen parsers distintos.

Propuesta:

1. **Modelo canónico** `LayerConfig` (Pydantic) con campos nombrados y validados.
2. **Adaptador legacy** `parse_legacy_layers()` que convierte el DSL al modelo, con errores claros.
3. **Nuevo parámetro** `layers` como JSON (URL-encoded) o `collections` repetido; recomendación: JSON en `POST /api/v1/viewers`.
4. **Validación** de URL, tipo, campos obligatorios y límites (máx. 50 capas).

Ejemplo de modelo:

```json
{
  "type": "WMS",
  "id": "unidades",
  "url": "https://www.ign.es/wms-inspire/unidades-administrativas",
  "layers": "AU.AdministrativeUnit",
  "version": "1.3.0",
  "transparent": true,
  "tiled": false,
  "queryable": true,
  "visible": true,
  "legend": "Unidades administrativas"
}
```

Tabla de mapeo por tipo:

| Tipo | Campos actuales (posicionales) | Modelo canónico |
|---|---|---|
| `QUICK` | `nombreCapa` | `{ "type": "QUICK", "id": "..." }` |
| `WMS` | `nombreLeyenda, url, capa, transparente, teselado, userMaxExtent, toc, consultable, visible, version, useCapabilities` | `legend, url, layers, transparent, tiled, maxExtent, inToc, queryable, visible, version, useCapabilities` |
| `WMTS` | `url, capa, matrixSet, descripción, transparente, formato, toc, consultable, visible, useCapabilities` | `url, layer, matrixSet, legend, transparent, format, inToc, queryable, visible, useCapabilities` |
| `TMS` | `nombre, url, visible, transparente, tileGridMaxZoom, displayInLayerSwitcher, legend, tileSize` | `id, url, visible, transparent, tileGridMaxZoom, inToc, legend, tileSize` |
| `XYZ` | `nombre, url, visible, transparente, displayInLayerSwitcher, legend` | `id, url, visible, transparent, inToc, legend` |
| `WFS`/`WFST` | `leyenda, url, namespace:name, geometría, ids, cql, style` | `legend, url, typeName, geometryType, ids, filter, style` |
| `GeoJSON` | `nombre, url, extract, style` | `id, url, extract, style` |
| `OGCAPIFeatures` | `leyenda, url, capa, límite, bbox, id, offset, formato, estilo, extract` | `legend, url, collection, limit, bbox, featureId, offset, format, style, extract` |
| `MVT` | `url, nombre, proyección` | `url, id, crs` |
| `GeoTIFF` | `leyenda, url, nombre, transparente, proyección, displayInLayerSwitcher, visible` | `legend, url, id, transparent, crs, inToc, visible` |
| `MBTiles` | `leyenda, url, nombre, transparente, visible, opacidad, maxZoomLevel, maxExtent, tileSize` | `legend, url, id, transparent, visible, opacity, maxZoomLevel, maxExtent, tileSize` |

### 4.6 Controles, plugins y WMC

- `controls=scale,scaleline` → lista validada contra `/api/v1/actions/controls`.
- `plugins=toc,measurebar` → lista validada contra `/api/v1/actions/plugins`.
- `wmcfile=url*nombre,url*nombre` → lista de `{ url, name }`; validar URL y esquema.
- En canónico: `controls` y `plugins` como arrays JSON; en GET, lista separada por comas.
- Nombres case-insensitive; se canonicaliza al nombre del catálogo.
- Los controles con opciones (`scale*true`) se modelan como objeto: `{ "type": "scale", "options": { "showScale": true } }`.

### 4.7 BBox y CRS

Reglas:

1. `bbox` tiene 4 o 6 números: `minx,miny,maxx,maxy[,minz,maxz]`.
2. Si no hay `bbox-crs`, se interpreta en **CRS84** (lon, lat).
3. Si `bbox-crs=EPSG:4326`, se usa el **orden de ejes de la autoridad** (lat, lon), no el orden “x,y”.
4. Si `crs=EPSG:3857`, el orden es (x, y).
5. Se valida `minx < maxx`, `miny < maxy`, y que el bbox intersecte el dominio del CRS.
6. Se devuelve `Content-Crs: <URI>` en la respuesta.
7. En reenvío WMS 1.3.0, `CRS=EPSG:4326` implica `BBOX=lat,lon`; en WMS 1.1.1, `SRS=EPSG:4326` implica `lon,lat`. El adaptador debe convertir explícitamente.

Ejemplos:

```
# CRS84: lon,lat
?bbox=-3.8,40.3,-3.6,40.5

# EPSG:4326: lat,lon
?bbox=40.3,-3.8,40.5,-3.6&bbox-crs=EPSG:4326

# EPSG:3857: x,y
?bbox=-423000,4920000,-400000,4940000&bbox-crs=EPSG:3857
```

### 4.8 Filtrado: CQL2 en lugar de SQL

Situación actual:

- `where=nombre like '*al*'` (con `%` sustituido por `*`).
- `busquedaGeneral=Atributo1,Atributo2@Valor1,Valor2`.
- `query=SELECT ...` (SQL nativo).
- `select`, `groupby`, `having`, `orderby`.

Propuesta:

- `filter` con CQL2 texto o JSON; `filter-lang` para elegir.
- `filter-crs` para geometrías.
- Traducción con `pygeofilter` a SQL parametrizado.
- Validación de propiedades contra la introspección (solo columnas publicadas).
- Límite de profundidad (p. ej. 20 nodos) y de longitud (2 KB).
- Timeout de consulta.
- `sortby` para ordenación; `properties` para selección.

Ejemplos:

```
# CQL2 texto
?filter=nombre LIKE '%al%' AND poblacion > 1000

# CQL2 JSON
?filter={"op":"and","args":[{"op":"like","args":[{"property":"nombre"},"%al%"]},{"op":">","args":[{"property":"poblacion"},1000]}]}&filter-lang=cql2-json

# Espacial
?filter=INTERSECTS(geom,POLYGON((-3.8 40.3,-3.6 40.3,-3.6 40.5,-3.8 40.5,-3.8 40.3)))&filter-crs=CRS84
```

Equivalencias:

| Legacy | CQL2 |
|---|---|
| `where=nombre like '*al*'` | `filter=nombre LIKE '%al%'` |
| `busquedaGeneral=nombre,localidad@Alcalá,Madrid` | `filter=nombre LIKE '%Alcalá%' OR localidad LIKE '%Madrid%'` |
| `orderby=localidad desc` | `sortby=-localidad` |
| `select=id,nombre` | `properties=id,nombre` |
| `limit=100&offset=200` | `limit=100&offset=200` |

### 4.9 Paginación y enlaces

Respuesta canónica:

```json
{
  "type": "FeatureCollection",
  "features": [],
  "numberMatched": 1234,
  "numberReturned": 0,
  "links": [
    { "href": ".../items?limit=100&offset=0", "rel": "self", "type": "application/geo+json" },
    { "href": ".../items?limit=100&offset=100", "rel": "next", "type": "application/geo+json" },
    { "href": ".../items?limit=100&offset=0", "rel": "prev", "type": "application/geo+json" }
  ],
  "timeStamp": "2026-10-30T12:00:00Z"
}
```

Reglas:

- `limit` por defecto 100; máximo configurable (10 000).
- `offset` ≥ 0; máximo configurable.
- `numberMatched` puede ser una estimación si el `COUNT` es caro; documentarlo.
- `links` con `self`, `next`, `prev`, `alternate` (`f=html`).
- `Link` HTTP además del JSON, para clientes que no lean el cuerpo.

### 4.10 Formato y negociación

- `f=json|html|geojson|gml|kml|mvt`.
- `Accept` con q-values; si no hay `f`, manda `Accept`.
- `406 Not Acceptable` si no se puede satisfacer.
- `Vary: Accept, Accept-Encoding`.
- `Content-Type` correcto: `application/geo+json`, `application/gml+xml`, `application/vnd.mapbox-vector-tile`, `text/html`.
- `Content-Disposition` para descargas (`kml`, `gml`, `mvt`).
- `ETag` y `Last-Modified` en recursos estáticos y catálogos.
- JSONP: solo legacy, `application/javascript`, `X-Content-Type-Options: nosniff`.

### 4.11 Errores

Formato único:

```json
{
  "type": "https://componentes.idee.es/api-idee/problems/invalid-parameter",
  "title": "Parámetro no válido",
  "status": 400,
  "detail": "El parámetro 'limit' debe estar entre 1 y 10000.",
  "instance": "/api/v1/datasources/nomenclator/collections/municipios/items",
  "invalid-params": [
    { "name": "limit", "reason": "fuera de rango", "value": "50000" }
  ]
}
```

Reglas:

- `Content-Type: application/problem+json`.
- Sin trazas ni rutas internas.
- `instance` con la ruta solicitada.
- `type` como URI estable y documentada.
- `400` para sintaxis, `422` para semántica, `404` para recurso, `406` para formato, `429` para límite, `502/504` para fallo del upstream.
- Correlación con `X-Request-Id`.

### 4.12 JSONP y `callback`

- **Deprecar** JSONP en `/api/v1`.
- En legacy, validar `callback` con `^[A-Za-z_$][A-Za-z0-9_$]{0,63}$`.
- `Content-Type: application/javascript; charset=utf-8`.
- `X-Content-Type-Options: nosniff`.
- `Cache-Control: no-store` si hay `callback`.
- Anunciar retirada con `Deprecation: true` y `Sunset`.
- Alternativa: CORS + `fetch` (el cliente 1.1.0 ya lo soporta si el proxy está desactivado).

### 4.13 Límites y validación

| Límite | Valor propuesto | Configurable |
|---|---|---|
| URL completa | 8 KB | Sí |
| Nº de parámetros | 50 | Sí |
| Longitud de valor | 2 KB | Sí |
| `limit` | 1..10 000 | Sí |
| `offset` | 0..1 000 000 | Sí |
| Capas por visor | 50 | Sí |
| Profundidad CQL2 | 20 nodos | Sí |
| Tamaño de respuesta proxy | 10 MB | Sí |
| Timeout proxy | 15 s | Sí |
| Timeout BD | 15 s | Sí |
| Redirecciones proxy | 3 | Sí |

### 4.14 Ejemplos antes / después

**Visor**

Antes:

```
/?layers=WMS*Unidad%20administrativa*http://www.ign.es/wms-inspire/unidades-administrativas?*AU.AdministrativeUnit*true*false**true*true*true*1.3.0&center=-1264453.9,4323899.8&zoom=5
```

Después (compatible):

```
/?layers=WMS*Unidad%20administrativa*https%3A%2F%2Fwww.ign.es%2Fwms-inspire%2Funidades-administrativas*AU.AdministrativeUnit*true*false**true*true*true*1.3.0&center=-3.7,40.4&center-crs=CRS84&zoom=5
```

Canónico:

```
POST /api/v1/viewers
{
  "container": "map",
  "view": { "crs": "CRS84", "center": [-3.7, 40.4], "zoom": 5 },
  "layers": [{ "type": "WMS", "url": "https://www.ign.es/wms-inspire/unidades-administrativas", "layers": "AU.AdministrativeUnit", "version": "1.3.0" }]
}
```

**Base de datos**

Antes:

```
/api/database/nomenclator/collections/municipios/items?where=nombre%20like%20'*al*'&limit=50&formato=geojson
```

Después:

```
/api/v1/datasources/nomenclator/collections/municipios/items?filter=nombre%20LIKE%20'%25al%25'&limit=50&f=geojson
```

**Proxy**

Antes:

```
/api/proxy?url=https%3A%2F%2Fwww.ign.es%2Fwmts%2Fign-base%3Frequest%3DGetCapabilities%26service%3DWMTS&callback=cb
```

Después:

```
GET /api/v1/proxy?url=https%3A%2F%2Fwww.ign.es%2Fwmts%2Fign-base%3Frequest%3DGetCapabilities%26service%3DWMTS
Accept: application/xml
```

---

## 5. Plan de trabajos

### 5.1 Fases

Las tareas usan IDs `T-xx`. La estimación es en jornadas de una persona. Las dependencias se indican entre paréntesis.

#### Fase 0 — Preparación (5 d) ✅ Completada (2026-11-01; T-00.1 pendiente de captura real)

| ID | Tarea | Entregable | Criterio de aceptación | D |
|---|---|---|---|---|
| T-00.1 | Congelar inventario y corpus de URLs | `tests/golden/urls.yaml` con 100+ URLs reales | Todas responden hoy y quedan registradas | 2 |
| T-00.2 | ADRs: monorepo, JSONP, SQL, versionado, auth | `docs/adr/000x-*.md` | Decisiones aprobadas | 1 |
| T-00.3 | Esqueleto Django + CI + lint + pytest | Proyecto arrancando en local | `pytest`, `ruff`, `mypy` en verde | 2 |

#### Fase 1 — Núcleo HTTP y normalización (10 d) ✅ Completada (2026-11-01)

| ID | Tarea | Entregable | Criterio de aceptación | D |
|---|---|---|---|---|
| T-01 | `Parametros` (case-insensitive, alias, duplicados) | `apps/core/params.py` | Tests de colisión y duplicados | 3 |
| T-02 | Validadores CRS, bbox, datetime, boolean, enum, listas | `apps/core/validators.py` | Cobertura ≥ 90 % | 3 |
| T-03 | Problem Details + excepciones | `apps/core/problems.py` | Todos los errores en `problem+json` | 1 |
| T-04 | Negociación `f`/`Accept`, ETag, `Vary`, `Content-Crs` | `apps/core/http.py` | Tests 200/406 y cabeceras | 1 |
| T-05 | CORS y cabeceras de seguridad | Settings + middleware | Orígenes permitidos y `nosniff` | 1 |
| T-06 | Tests unitarios del núcleo | `tests/unit/core/` | Verde en CI | 1 |

#### Fase 2 — Acciones y recursos (5 d)

| ID | Tarea | Entregable | Criterio de aceptación | D |
|---|---|---|---|---|
| T-07 | `/api/actions/*` en JSON y JSONP validado | `apps/actions/` | Paridad con el servidor actual | 2 |
| T-08 | Catálogo de controles/plugins/servicios | JSON versionado + loader | Validación contra catálogo | 1 |
| T-09 | `resources/svg`, `geodata`, `resourcesPlugins` + caché | Vistas + ETag | `304` con `If-None-Match` | 1 |
| T-10 | Tests de contrato | `tests/contract/actions/` | OpenAPI válido | 1 |

#### Fase 3 — Visor y builder (12 d)

| ID | Tarea | Entregable | Criterio de aceptación | D |
|---|---|---|---|---|
| T-11 | Plantillas `index` y `visor` | `templates/viewer.html`, `visor.html` | Render sin JSP | 3 |
| T-12 | Modelo de capas + parser DSL legacy | `apps/viewers/layers.py` | 100 % de los tipos documentados | 3 |
| T-13 | Validación de controles/plugins + catálogo | `apps/viewers/validate.py` | Nombres inválidos → 400 | 1 |
| T-14 | `POST /api/v1/viewers` + `GET /{id}` | Endpoints + almacenamiento | `201` + `Location` | 2 |
| T-15 | Escape seguro y CSP | `json_script`, nonce | Sin XSS en parámetros | 1 |
| T-16 | Compatibilidad `index.jsp`/`visor.jsp` | Redirecciones/alias | URLs antiguas funcionan | 2 |

#### Fase 4 — Proxy (12 d)

| ID | Tarea | Entregable | Criterio de aceptación | D |
|---|---|---|---|---|
| T-17 | Proxy GET legacy con JSONP validado | `apps/proxy/legacy.py` | Paridad con `/api/proxy` | 2 |
| T-18 | Proxy GET canónico con streaming | `apps/proxy/views.py` | Sin cargar en memoria | 2 |
| T-19 | Proxy de imagen | Vista + límites | Máx. 1 MB / configurable | 1 |
| T-20 | Proxy POST (`/proxyPost`) | Vista + cuerpo | WFS-T de prueba OK | 2 |
| T-21 | SSRF guard + timeouts + tamaño | `apps/proxy/validators.py` | Tests de IP privada/metadata | 3 |
| T-22 | Caché y rate limit | Redis | `429` + `Retry-After` | 1 |
| T-23 | Tests de seguridad del proxy | `tests/security/proxy/` | 0 hallazgos críticos | 1 |

#### Fase 5 — Base de datos (18 d)

| ID | Tarea | Entregable | Criterio de aceptación | D |
|---|---|---|---|---|
| T-24 | Modelo `DataSource` + secretos | Migraciones + admin | Sin credenciales en URL | 3 |
| T-25 | Introspección + caché | `apps/databases/introspect.py` | Tablas/columnas en < 100 ms | 2 |
| T-26 | `collections`, `collection`, `attributes` | Endpoints | Respuesta OGC válida | 2 |
| T-27 | `items` + paginación + bbox/CRS | Endpoint | `numberMatched` y `links` | 3 |
| T-28 | CQL2 texto/JSON → SQL | `apps/databases/filters.py` | 20 casos de prueba | 4 |
| T-29 | `domain` + MVT | Endpoints | MVT válido en QGIS | 2 |
| T-30 | Retirada de SQL/query/layerfilter | Guía + 410 | Sin rutas públicas | 1 |
| T-31 | Límites, timeouts, read-only | Settings + tests | Consulta lenta cortada | 1 |

#### Fase 6 — Correo, legacy, estáticos y despliegue (12 d)

| ID | Tarea | Entregable | Criterio de aceptación | D |
|---|---|---|---|---|
| T-32 | `/api/email` con Django email | Vista + plantilla | Envío de prueba | 2 |
| T-33 | JSP legacy: redirecciones/410 | `apps/legacy/` | Matriz de rutas | 2 |
| T-34 | Estáticos (`assets`, `js`, `plugins`, `wasm`) | nginx/WhiteNoise | MIME y caché correctos | 2 |
| T-35 | Docker + nginx + CI | `deploy/` | `docker compose up` | 2 |
| T-36 | Observabilidad | Logs JSON, métricas, trazas | Panel básico | 2 |
| T-37 | OpenAPI + guía de migración | `/api/v1/openapi.json` | Schemathesis en verde | 2 |

#### Fase 7 — Cutover (8 d)

| ID | Tarea | Entregable | Criterio de aceptación | D |
|---|---|---|---|---|
| T-38 | Golden master | Comparador antiguo/nuevo | ≥ 95 % de URLs equivalentes | 3 |
| T-39 | Canary / dual-run | Despliegue | 10 % → 50 % → 100 % | 2 |
| T-40 | Rollback y sunset | Runbook | Vuelta < 15 min | 1 |
| T-41 | Retro y backlog residual | Documento | — | 1 |

**Total orientativo: ~82 jornadas.**

### 5.2 Backlog de normalización

| ID | Trabajo | Prioridad | Norma | Aceptación |
|---|---|---|---|---|
| N-01 | Case-insensitive + coincidencia exacta | P0 | RFC 3986 / OGC KVP | Tests de colisión |
| N-02 | Detección de duplicados | P0 | OGC KVP | 400 con `invalid-params` |
| N-03 | Percent-encoding estricto | P0 | RFC 3986 | `%20`/`+` documentados |
| N-04 | CRS URI + orden de ejes | P0 | OGC API Features 2 | 4326/3857/CRS84 |
| N-05 | `bbox` 4/6 + validación | P0 | OGC API Features 1 | Bbox inválido → 400 |
| N-06 | `datetime` RFC 3339 | P1 | OGC API Features 1 | Intervalos abiertos |
| N-07 | `limit`/`offset` + `links` | P0 | OGC API Features 1 | `next`/`prev` |
| N-08 | `f` + `Accept` | P0 | OGC API Common | 406 correcto |
| N-09 | Problem Details | P0 | RFC 9457 | Todos los errores |
| N-10 | CQL2 | P0 | OGC API Features 3 / CQL2 | 20 casos |
| N-11 | `sortby` y `properties` | P1 | Partes 8 y 6 | Orden y proyección |
| N-12 | `Deprecation`/`Sunset` | P1 | RFC 9745 / 8594 | Cabeceras en legacy |
| N-13 | JSONP validado y deprecado | P0 | — | Sin XSS |
| N-14 | `token` → `ds` opaco | P0 | — | Sin credenciales en URL |
| N-15 | DSL de capas → JSON | P0 | — | Paridad 100 % |
| N-16 | Controles/plugins validados | P1 | — | Catálogo |
| N-17 | KVP WMS/WFS/WMTS canónico | P1 | OGC | Reenvío correcto |
| N-18 | `language` INSPIRE | P2 | INSPIRE | ISO 639-2/B |
| N-19 | Límites de URL/parámetros | P0 | RFC 9110 | 414/400 |
| N-20 | OpenAPI 3.1 | P1 | OpenAPI | Schemathesis |

### 5.3 Dependencias y cronograma

```
Fase 0 ──▶ Fase 1 ──▶ Fase 2 ──▶ Fase 3 ──▶ Fase 4 ──▶ Fase 5 ──▶ Fase 6 ──▶ Fase 7
              │                       │                       │
              └──── normalización ────┴──── normalización ────┘
```

- La fase 1 es bloqueante para todas.
- Las fases 2 y 3 pueden solaparse una semana.
- La fase 4 (proxy) puede empezar en paralelo con la 3 si hay dos personas.
- La fase 5 (BD) depende de la 1 y de la 4 (para reutilizar límites y errores).
- La fase 6 depende de 2, 3 y 4.
- La fase 7 es la última.

### 5.4 Estimación

| Escenario | Duración | Notas |
|---|---|---|
| 1 desarrollador | 16-17 semanas | Sin contar gestión ni imprevistos |
| 2 desarrolladores | 8-9 semanas | Paralelizando 3/4 y 5 |
| 1 dev + 1 SIG | 10-12 semanas | El SIG ayuda en CQL2 y CRS |

### 5.5 Definición de hecho (por tarea)

- Código con tests y `ruff`/`mypy` en verde.
- Documentación de la ruta y parámetros en OpenAPI.
- Error en `problem+json` con `invalid-params`.
- Log con `X-Request-Id` y sin datos sensibles.
- Revisión de seguridad si toca proxy, BD o auth.
- Actualización del golden master.

---

## 6. Pruebas y validación

### 6.1 Unitarias

- Parser de parámetros: alias, duplicados, case-insensitive, valores vacíos, longitudes.
- CRS/bbox: 4326, 3857, CRS84, URN, URI, bbox 4/6, orden de ejes.
- CQL2: texto/JSON, operadores, geometrías, errores.
- Problem Details: códigos y estructura.
- Paginación: límites, `next`/`prev`.

### 6.2 Contrato

- OpenAPI 3.1 generado y validado.
- `schemathesis` contra el esquema.
- Tests de compatibilidad de rutas legacy.

### 6.3 Golden master

- Corpus de URLs reales (visor, acciones, proxy, BD, correo).
- Captura de respuestas actuales (cuerpo, código, cabeceras relevantes).
- Comparación semántica:
  - JSON: normalizar claves y orden.
  - HTML: DOM equivalente.
  - JavaScript: AST o ejecución en un DOM de prueba.
- Umbral: ≥ 95 % de URLs equivalentes; diferencias justificadas.

### 6.4 Conformidad OGC

- OGC API Features: validador oficial (`cite.opengeospatial.org`) para Part 1 y Part 2.
- WMS/WFS: no se sirven, pero se valida el reenvío con un servicio de prueba.
- CQL2: casos de la especificación.
- OpenAPI: `spectral` o `redocly lint`.

### 6.5 Carga

- `k6` o Locust:
  - 100 req/s al proxy con respuestas de 100 KB.
  - 50 req/s a `items` con `limit=1000`.
  - 20 req/s a MVT.
- Medir p95, errores, memoria y conexiones.
- Objetivo: p95 < 500 ms en proxy y < 1 s en BD.

### 6.6 Seguridad

- SSRF: IP privada, loopback, link-local, metadata, DNS rebinding, redirecciones.
- SQL injection: `filter`, `sortby`, `properties`, `schema`, `collection`.
- XSS: `label`, `callback`, nombres de capa, JSON del visor.
- CORS: origen permitido/no permitido.
- Rate limit: 429 y `Retry-After`.
- Cabeceras: `nosniff`, CSP, HSTS, `Referrer-Policy`.

### 6.7 Matriz de aceptación

| Requisito | Prueba | Criterio |
|---|---|---|
| El visor 1.1.0 funciona | E2E con Playwright | Mapa, controles y plugins OK |
| El proxy no accede a red interna | Tests SSRF | 100 % bloqueado |
| La BD no acepta SQL libre | Tests de inyección | 100 % bloqueado |
| Los parámetros son canónicos | Tests de alias | Todos los alias mapeados |
| Los errores son Problem Details | Tests de contrato | 100 % |
| La paginación es OGC | Tests de `links` | `next`/`prev` correctos |
| CQL2 funciona | 20 casos | 20/20 |
| Rendimiento | k6 | p95 < 500 ms |

---

## 7. Seguridad

### 7.1 SSRF (proxy)

- Allowlist de hosts y puertos.
- Bloqueo de IP privadas, loopback, link-local, multicast, reservadas y metadata.
- Resolución DNS y revalidación en redirecciones.
- Sin `file:`, `gopher:`, `ftp:`, `data:`.
- Timeouts y tamaño máximo.
- En producción, proxy de salida con allowlist (defensa en profundidad).
- Log de destino (sin credenciales) y de decisión.

### 7.2 SQL

- Sin SQL concatenado.
- Identificadores con `psycopg.sql.Identifier`.
- Valores con `%s`.
- Introspección y allowlist de tablas/columnas.
- Rol de solo lectura.
- `statement_timeout` y `default_transaction_read_only`.
- CQL2 en lugar de `where`/`query`.

### 7.3 XSS y JSONP

- `json_script` para datos en HTML.
- CSP con nonce.
- `callback` validado.
- `label` como texto, no HTML (o sanitizar con `bleach` si se permite HTML).
- `X-Content-Type-Options: nosniff`.

### 7.4 CORS

- Allowlist por origen.
- `*` solo para recursos públicos sin credenciales.
- `Access-Control-Allow-Credentials` solo con orígenes explícitos.
- `Vary: Origin`.

### 7.5 Autenticación y tokens

- `Authorization: Bearer` (RFC 6750).
- Tokens de datasource opacos y firmados (HMAC) o sesión.
- Sin credenciales en URL.
- Rotación y revocación.
- Rate limit por token.

### 7.6 Checklist OWASP API Top 10

- [ ] API1 BOLA: autorización por datasource/colección.
- [ ] API2 Autenticación: tokens fuertes, sin query.
- [ ] API3 Propiedad de objetos: no exponer IDs internos.
- [ ] API4 Consumo: límites y timeouts.
- [ ] API5 Funciones: admin separado.
- [ ] API6 Negocio: rate limit en correo.
- [ ] API7 SSRF: allowlist.
- [ ] API8 Configuración: sin `DEBUG`, cabeceras.
- [ ] API9 Inventario: OpenAPI y versionado.
- [ ] API10 Consumo de terceros: validar respuestas.

---

## 8. Observabilidad y operación

- **Logs** JSON con `request_id`, ruta, método, código, duración, destino (sin credenciales).
- **Métricas**: `http_requests_total`, `http_request_duration_seconds`, `proxy_upstream_seconds`, `db_query_seconds`, `cache_hits`.
- **Trazas** OpenTelemetry: spans de proxy y BD.
- **Alertas**: 5xx > 1 %, p95 > 1 s, errores de upstream, saturación de pool.
- **Dashboards**: tráfico, errores, latencia, caché, rate limit.
- **Runbook**: proxy caído, BD lenta, upstream 5xx, rollback.
- **Backups**: configuración y datasources (sin contraseñas en claro).

---

## 9. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| El cliente 1.1.0 depende de JSONP y del DSL | Alta | Alto | Fachada legacy + golden master |
| El proxy actual se usa para servicios internos | Media | Alto | Allowlist configurable por entorno |
| La BD expone SQL usado por terceros | Alta | Alto | Periodo de gracia + 410 + guía |
| CQL2 no cubre todos los casos | Media | Medio | Extensión documentada + fallback admin |
| Rendimiento de introspección | Media | Medio | Caché Redis + TTL |
| Licencia del código original | Media | Alto | Revisión legal antes de copiar |
| Diferencias de CRS entre 2D/3D | Alta | Medio | Normalizar en servidor |
| Falta de tests del cliente | Alta | Medio | Playwright + corpus |
| Cambios en servicios OGC externos | Media | Medio | Mocks + monitorización |

---

## 10. Decisiones abiertas

| ID | Decisión | Opciones | Recomendación |
|---|---|---|---|
| D-01 | ¿Monorepo o repo separado? | `servidor/` en esta galería / repo propio | Repo propio; la galería solo consume |
| D-02 | ¿Mantener JSONP? | Sí (legacy) / No | Sí, solo legacy y con `Sunset` |
| D-03 | ¿Mantener SQL libre? | Público / Admin / Eliminar | Eliminar del público; admin auditado |
| D-04 | ¿Django Ninja o DRF? | Ninja / DRF | Ninja para `/api/v1` |
| D-05 | ¿OGC API Features completo o subconjunto? | Completo / Core+CRS+CQL2 | Core + CRS + CQL2 + sortby/properties |
| D-06 | ¿Renderizado de mapas en servidor? | No / OGC API Maps | No en esta fase |
| D-07 | ¿Versionado? | `/api/v1` / cabecera | `/api/v1` |
| D-08 | ¿Autenticación de datasources? | HMAC / Sesión / OAuth2 | HMAC para servicio; OAuth2 si hay usuarios |
| D-09 | ¿Cache de proxy? | No / Redis | Redis para GET públicos |
| D-10 | ¿Idioma de errores? | Español / Bilingüe | Español + `lang` |

---

## Anexo A. Inventario de endpoints

| Método | Ruta actual | Parámetros | Respuesta | Destino |
|---|---|---|---|---|
| GET | `/` | Visor | HTML | `viewers.index` |
| GET | `/visor.jsp` | Visor | HTML | `viewers.visor` |
| GET | `/api/js` | Visor | JS | `viewers.builder_legacy` |
| POST | `/api/js` | JSON | JS | `viewers.builder` |
| GET | `/api/actions` | `callback` | JSONP/JSON | `actions.index` |
| GET | `/api/actions/controls` | `callback` | JSONP/JSON | `actions.controls` |
| GET | `/api/actions/services` | `callback` | JSONP/JSON | `actions.services` |
| GET | `/api/actions/projection` | `callback` | JSONP/JSON | `actions.projection` |
| GET | `/api/actions/plugins` | `callback` | JSONP/JSON | `actions.plugins` |
| GET | `/api/actions/plugins/external` | `callback` | JSONP/JSON | `actions.plugins_external` |
| GET | `/api/actions/plugins/external/reload` | `callback` | JSONP/JSON | `actions.plugins_reload` |
| GET | `/api/actions/version` | `callback` | JSONP/JSON | `actions.version` |
| GET | `/api/actions/versions` | `callback` | JSONP/JSON | `actions.versions` |
| GET | `/api/actions/resources/svg` | `callback`, `name` | JSONP/JSON | `catalog.svg` |
| GET | `/api/actions/resources/geodata` | `callback`, `name` | JSONP/JSON | `catalog.geodata` |
| GET | `/api/actions/resourcesPlugins` | `callback`, `name`, `version`, `type` | JSONP/JSON | `catalog.plugins` |
| GET | `/api/proxy` | `url`, `ticket`, `method`, `callback` | JSONP | `proxy.legacy` |
| GET | `/api/proxy/image` | `url` | Imagen | `proxy.image` |
| GET/POST | `/proxyPost` | `url`, `ticket` | Texto/XML | `proxy.post` |
| GET | `/api/database` | `callback` | JSON | `databases.index` |
| GET | `/api/database/conformance` | — | JSON | `databases.conformance` |
| GET | `/api/database/{ds}/collections` | `limit`, `offset`, `token`, `callback` | JSON | `databases.collections` |
| GET | `/api/database/{ds}/attributes/{tabla}` | `schema`, `limit`, `offset`, `token`, `callback` | JSON | `databases.attributes` |
| GET | `/api/database/{ds}/collections/{tabla}/items` | Ver anexo B | JSON/GeoJSON/GML/KML/MVT | `databases.items` |
| GET | `/api/database/{ds}/{tabla}/sql` | `select`, `where`, `groupby`, `having`, `orderby`, `limit`, `offset`, `token` | JSON | `databases.sql` (admin) |
| GET | `/api/database/{ds}` | `query`, `token` | JSON | `databases.native` (admin) |
| GET | `/api/database/{ds}/layerfilter` | `layer`, `select`, `where`, ..., `formato` | JSON | `databases.layerfilter` (admin) |
| GET | `/api/database/{ds}/{tabla}/domain/{columna}` | `schema`, `token` | JSON | `databases.domain` |
| POST | `/api/email` | `subject`, `mailto`, `body`, `file`, `callback` | JSON | `mailer.send` |
| GET | `/*.jsp` (74) | Variables | HTML | `legacy.*` |

---

## Anexo B. Inventario de parámetros GET

### B.1 Visor

| Parámetro | Tipo | Obligatorio | Defecto | Observaciones |
|---|---|---|---|---|
| `container` | string | No | `map` | ID del contenedor |
| `layers` | DSL | No | — | Lista de capas |
| `controls` | lista | No | — | Controles |
| `plugins` | lista | No | — | Plugins |
| `wmcfile` | lista | No | — | `url*nombre` |
| `zoom` | int | No | — | 0..28 |
| `center` | lista | No | — | `x,y[,pin]` |
| `bbox` | lista 4 | No | — | `minx,miny,maxx,maxy` |
| `maxextent` | lista 4 | No | — | Límite |
| `projection` | string | No | `EPSG:3857` | Sufijo `*d` |
| `srs` | string | No | — | Solo cliente |
| `label` | string | No | — | HTML |
| `bgcolorcontainer` | color | No | — | Fondo |
| `getfeatureinfo` | string | No | — | Formato |
| `implementation` | enum | No | `ol` | `ol`/`cesium` |
| `callback` | string | No | — | JSONP |
| `ticket` | string | No | — | Auth |
| `zoomConstrains` | string | No | — | Límites |
| `extentConstrains` | lista | No | — | Solo cliente |
| `viewextent` | lista | No | — | Extensión |

### B.2 Base de datos

| Parámetro | Tipo | Obligatorio | Defecto | Observaciones |
|---|---|---|---|---|
| `limit` | int | No | 5 | Máx. configurable |
| `offset` | int | No | 0 | |
| `token` | bool/string | No | `false` | Credenciales base64 (a retirar) |
| `schema` | string | No | `public` | |
| `formato` | enum | No | `wkt`/`geojson` | `wkt`, `kml`, `gml`, `geojson`, `mvt` |
| `consumible` | bool | No | `false` | |
| `bbox` | lista 4/6 | No | — | |
| `bbox-crs` | int | No | `4326` | SRID |
| `aliasgeom` | string | No | `geometry` | |
| `select` | string | No | `*` | SQL |
| `where` | string | No | — | SQL, `*` por `%` |
| `groupby` | string | No | — | SQL |
| `having` | string | No | — | SQL |
| `orderby` | string | No | — | SQL |
| `query` | string | Sí (nativa) | — | SQL libre |
| `layer` | string | No | — | GeoJSON |
| `busquedaGeneral` | string | No | — | `col;...@val;...` |
| `callback` | string | No | — | JSONP |

### B.3 Reenvío OGC

| Parámetro | Servicio | Observaciones |
|---|---|---|
| `service` | WMS/WFS/WMTS/CSW | Case-insensitive |
| `request` | WMS/WFS/WMTS/CSW | Case-insensitive |
| `version` | WMS/WFS/WMTS/CSW | |
| `layers` | WMS | Lista |
| `styles` | WMS | Uno por capa |
| `crs`/`srs` | WMS | 1.3.0/1.1.1 |
| `bbox` | WMS/WFS | Orden de ejes |
| `width`/`height` | WMS | |
| `format` | WMS | MIME |
| `transparent` | WMS | |
| `bgcolor` | WMS | |
| `exceptions` | WMS | |
| `time`/`elevation`/`dim_*` | WMS | |
| `typenames`/`typename` | WFS | |
| `srsname` | WFS | |
| `count`/`maxfeatures` | WFS | |
| `startindex` | WFS | |
| `propertyname` | WFS | |
| `sortby` | WFS | |
| `outputformat` | WFS | |
| `resulttype` | WFS | |
| `filter`/`cql_filter` | WFS | |
| `language` | INSPIRE | ISO 639-2/B |

---

## Anexo C. Referencias

### Código y documentación consultados

- `Desarrollos-IDEE/API-IDEE`, rama `develop`, commit `dd0759e` (2026-10-26):
  - `api-idee-rest/src/main/java/es/api_idee/api/*.java`
  - `api-idee-rest/src/main/java/es/api_idee/parameter/Parameters.java`
  - `api-idee-rest/src/main/java/es/api_idee/parameter/parser/ParametersParser.java`
  - `api-idee-rest/src/main/java/es/api_idee/builder/JSBuilder.java`
  - `api-idee-rest/src/main/webapp/WEB-INF/web.xml`
  - `api-idee-rest/src/main/resources/properties/configuration.properties`
  - `api-idee-proxy/src/main/java/es/api_idee/proxy/ProxyRedirect.java`
  - `api-idee-database/src/main/java/es/api_idee/database/**`
  - `api-idee-parent/src/main/filters/*.properties`
- Wiki oficial:
  - `4.-Proxy`
  - `5.-API-REST`
  - `5.1.-Parametrización-API-REST`
  - `5.2.-Base-de-datos-API-REST`
  - `5.3.-API-REST-Actions`
  - `5.4.-Servicio-de-correos-electrónicos`
- Cliente de esta galería:
  - `js/api-idee/apiidee-1.1.0.ol.min.js`
  - `js/api-idee/configuration-1.1.0.js`

### Estándares

- IETF RFC 3986 (URI), 9110/9111 (HTTP/caché), 9457 (Problem Details), 6750 (Bearer), 8288 (Link), 8594 (Sunset), 9745 (Deprecation), 7946 (GeoJSON), 3339 (fecha/hora).
- OGC WMS 1.3.0 (06-042) y 1.1.1 (01-068r3).
- OGC WFS 2.0.0 (09-025r1).
- OGC WMTS 1.0.0 (07-057r7).
- OGC CSW 2.0.2 / 3.0.0.
- OGC API - Features Part 1 (17-069r4), Part 2 (18-058r1), Part 3 (19-079), Part 6, Part 8.
- OGC API - Common Part 1 (19-072).
- OGC API - Tiles Part 1.
- OGC CQL2 (21-065).
- INSPIRE Technical Guidance.
- OpenAPI 3.1.

### Documentación interna

- `.opencode/docs/API-IDEE.md`
- `.opencode/docs/OpenLayers.md`
- `.opencode/docs/Cesium.md`
- `.opencode/docs/Capas3Den2D.md`

---

## Anexo D. Checklist de arranque

Primer día del equipo:

- [ ] Leer este documento y los ADRs.
- [ ] Clonar el repo del servidor nuevo y arrancar `docker compose up`.
- [ ] Ejecutar `pytest` y comprobar que el golden master pasa.
- [ ] Revisar el corpus de URLs (`tests/golden/urls.yaml`).
- [ ] Verificar acceso a un WMS/WFS de pruebas y a una BD PostGIS.
- [ ] Configurar `PROXY_ALLOWED_HOSTS` y `CORS_ALLOWED_ORIGINS` del entorno.
- [ ] Revisar la licencia del código original.
- [ ] Abrir las decisiones D-01 a D-10 y cerrar las bloqueantes.

Antes de cada despliegue:

- [ ] `ruff` y `mypy` en verde.
- [ ] Tests unitarios, contrato y seguridad en verde.
- [ ] Golden master ≥ 95 %.
- [ ] OpenAPI regenerado.
- [ ] Migraciones revisadas.
- [ ] Cabeceras de seguridad comprobadas.
- [ ] Rate limit y timeouts configurados.
- [ ] Plan de rollback actualizado.

---

*Fin del documento.*
