# Servidor Django de API-IDEE

Reimplementación en Django del servidor de API-IDEE (`api-idee-rest`, `api-idee-proxy`),
compatible con el cliente **API-IDEE 1.1.0** y con una API canónica OGC en `/api/v1/`.

Las decisiones de arquitectura están en [`docs/adr/`](docs/adr/).

> **Alcance actual:** visualizadores por API y proxy. Las fases de bases de datos, correo,
> estáticos y cutover quedan fuera de alcance.

---

## Estado del proyecto

| Fase | Contenido | Estado |
|---|---|---|
| **0. Preparación** | Esqueleto Django, CI, lint, tipos, tests, ADRs, corpus golden | ✅ Completada (2026-11-01) |
| **1. Núcleo HTTP y normalización** | `Parametros`, CRS/bbox/datetime, Problem Details, `f`/`Accept`, CORS, cabeceras | ✅ Completada (2026-11-01) |
| **2. Acciones y recursos** | `/api/actions/*`, catálogo, ETag | ✅ Completada (2026-11-01) |
| **3. Visualizador y builder** | Plantillas, modelo de capas, `POST /api/v1/viewers` | ✅ Completada (2026-11-01) |
| **4. Proxy** | GET/POST, imágenes, allowlist SSRF, streaming | ✅ Completada (2026-11-01) |
| **5. Base de datos** | Datasources, introspección, OGC API Features, CQL2, MVT | ⛔ Fuera de alcance |
| **6. Correo, legacy, estáticos y despliegue** | `/api/email`, JSP heredados, Docker/nginx, observabilidad | ⛔ Fuera de alcance |
| **7. Cutover** | Golden master, canary, rollback | ⛔ Fuera de alcance |

Tests: 318 passing. Puerta de calidad: `ruff check`, `ruff format --check`, `mypy`,
`pytest` y `manage.py check` (dev/test/prod) en verde.

---

## Stack

| Pieza | Versión | Nota |
|---|---|---|
| Python | 3.14.2 | Entorno `.venv` del repositorio |
| Django | 6.1.2 | Ver [ADR 0002](docs/adr/0002-stack-django61-python314.md) |
| Django Ninja | 1.7.3 | API canónica `/api/v1` + OpenAPI 3.1 |
| Base de datos (app) | SQLite | PostgreSQL vía `DATABASE_URL` en producción |
| CRS | pyproj 3.8 | Validación, orden de ejes y reproyección |
| HTTP cliente | httpx 0.28 | Proxy (fase 4) |
| Calidad | ruff, mypy, pytest, pytest-django | CI en `.github/workflows/ci.yml` |

---

## Puesta en marcha

```powershell
# 1. Crear y activar el entorno virtual (ya creado en el repositorio)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependencias
python -m pip install -r requirements-dev.txt

# 3. Configuración local
Copy-Item .env.example .env

# 4. Arrancar
python manage.py runserver
```

Si PowerShell bloquea la activación:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### Comandos habituales

```powershell
python manage.py check --settings=config.settings.test   # comprobaciones de Django
pytest                                                   # tests
pytest tests/unit/core/test_params.py -q                 # un módulo
ruff check .                                             # lint
ruff format .                                            # formato
mypy                                                     # tipos
python scripts/capture_golden.py --base-url https://componentes.idee.es/api-idee
```

---

## Endpoints disponibles

### Salud

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/healthz` | Liveness; no toca dependencias |
| GET | `/readyz` | Readiness; comprueba la base de datos |

### API canónica OGC (`/api/v1`)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/` | Landing OGC con enlaces |
| GET | `/api/v1/conformance` | Clases de conformidad OGC |
| GET | `/api/v1/openapi.json` | Contrato OpenAPI 3.1 |
| GET | `/api/v1/docs` | Documentación interactiva |
| GET/POST | `/api/v1/proxy` | Proxy canónico con streaming |
| POST | `/api/v1/viewers` | Crea un visualizador (`201` + `Location`) |
| GET | `/api/v1/viewers/{id}` | Recupera un visualizador (JSON o HTML según `f`) |
| GET | `/api/v1/actions/*` | Acciones y recursos canónicos |
| GET | `/api/v1/resources/svg` | Colecciones SVG (forma plana) |
| GET | `/api/v1/resources/geodata` | Colecciones de geodatos (forma plana) |

### Fachada heredada (`/api`)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/actions` | Índice heredado de acciones |
| GET | `/api/actions/controls` | Controles disponibles |
| GET | `/api/actions/services` | Tipos de capa disponibles |
| GET | `/api/actions/projection` | Proyección por defecto (`EPSG:3857`) |
| GET | `/api/actions/version` | Versión publicada de API-IDEE |
| GET | `/api/actions/versions` | Ficheros JS/CSS por versión |
| GET | `/api/actions/plugins` | Plugins internos |
| GET | `/api/actions/plugins/external` | Plugins externos no obsoletos |
| GET | `/api/actions/plugins/external/reload` | Recarga forzada de plugins externos |
| GET | `/api/actions/resourcesPlugins` | Catálogo o fichero JS/CSS de un plugin |
| GET | `/api/actions/resources/svg` | Colecciones SVG |
| GET | `/api/actions/resources/geodata` | Colecciones de geodatos |
| GET/POST | `/api/js` | Builder legacy (`IDEE.map({...})`, JSONP opcional) |
| GET | `/api/proxy` | Proxy legacy (JSON o JSONP) |
| GET | `/api/proxy/image` | Streaming de imagen |
| POST | `/proxyPost` | Proxy POST legacy |

### Visualizadores (plantillas)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Builder legacy (`viewer.html`, contenedor `#map`) |
| GET | `/index.jsp` | Alias legacy del builder |
| GET | `/visualizador` | Visualizador de ejemplo (`visualizador.html`, contenedor `#mapjs`) |
| GET | `/visualizador/` | Alias con barra final |
| GET | `/visor` | Alias legacy |
| GET | `/visor.jsp` | Alias legacy |

La fachada `/api/actions/*` reproduce el comportamiento del servidor Java: declara
`application/javascript` aunque no haya `callback`, tolera parámetros desconocidos y
`resourcesPlugins` responde JSON. La API `/api/v1` es estricta: rechaza `callback` y
parámetros no admitidos, y negocia solo JSON.

Todas las respuestas de error salen como `application/problem+json` (RFC 9457), con
`invalid-params` cuando aplica y `X-Request-Id` para correlación.

Ejemplos:

```text
GET /api/v1/conformance
GET /api/v1/?f=json
GET /api/v1/?f=xml            -> 400 invalid-parameter
GET /api/v1/ Accept: text/html -> 406 not-acceptable
GET /no-existe                -> 404 problem+json
```

---

## Estructura

```text
├── manage.py
├── pyproject.toml            # dependencias, ruff, mypy, pytest
├── requirements*.txt
├── .env.example
├── config/
│   ├── api.py                # NinjaAPI + traducción de errores
│   ├── urls.py               # salud + /api/v1 + handlers 4xx/5xx
│   └── settings/             # base, dev, prod, test
├── apps/
│   ├── actions/
│   │   ├── service.py        # lógica compartida legacy/canónica
│   │   ├── responses.py      # JSON, JSONP, ETag y assets
│   │   ├── views.py          # fachada /api/actions/*
│   │   └── api.py            # router Ninja /api/v1/actions/*
│   ├── catalog/
│   │   ├── loaders.py        # catálogo versionado y marcadores
│   │   ├── external.py       # plugins externos (TTL + allowlist)
│   │   └── data/             # JSON reales de API-IDEE 1.1.0
│   ├── core/
│   │   ├── params.py         # Parametros: lectura única y tipada
│   │   ├── validators.py     # int, bool, enum, listas, color, callback
│   │   ├── crs.py            # EPSG/URN/URI/CRS84 + orden de ejes
│   │   ├── bbox.py           # bbox 4/6, dominio y reproyección
│   │   ├── temporal.py       # RFC 3339 e intervalos
│   │   ├── problems.py       # Problem Details + middleware
│   │   ├── http.py           # f/Accept, ETag, JSONP, Link
│   │   ├── pagination.py     # limit/offset/numberMatched/links
│   │   ├── middleware.py     # request-id, límites, cabeceras
│   │   ├── logging.py        # logs JSON
│   │   ├── views.py          # healthz/readyz
│   │   └── api.py            # landing y conformance
│   ├── proxy/
│   │   ├── validators.py     # allowlist y protección SSRF
│   │   ├── client.py         # httpx streaming + redirecciones
│   │   └── views.py          # legacy, imagen y canónico
│   └── viewers/
│       ├── layers.py          # modelo de capas y parser DSL
│       ├── validate.py        # controles y plugins
│       ├── builder.py         # generación JS legacy y canónica
│       ├── render.py          # plantillas y payload por defecto
│       ├── views.py           # /, /visualizador, /api/js
│       ├── api.py             # /api/v1/viewers
│       └── models.py          # almacenamiento de visualizadores
├── templates/
│   ├── viewer.html            # contenedor #map
│   └── visualizador.html      # contenedor #mapjs
├── tests/
│   ├── unit/core/             # núcleo HTTP
│   ├── unit/catalog/          # catálogo y plugins externos
│   ├── unit/actions/          # servicio y fachada/canónica
│   ├── unit/viewers/          # capas, validación, builder, vistas
│   ├── unit/proxy/            # validadores y vistas del proxy
│   ├── contract/              # contrato OpenAPI
│   └── golden/                # corpus de URLs y capturas
├── docs/
│   └── adr/
└── scripts/capture_golden.py
```

Las apps `databases`, `mailer` y `legacy` quedan fuera del alcance actual.

---

## Configuración

Todas las variables se leen de `.env` o del entorno. Ver `.env.example`.

| Variable | Defecto | Uso |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | Settings activos |
| `DJANGO_SECRET_KEY` | insegura en dev | Firma de sesiones |
| `DJANGO_DEBUG` | `false` | Depuración |
| `ALLOWED_HOSTS` | localhost | Hosts admitidos |
| `API_IDEE_PUBLIC_URL` | `http://localhost:8000/` | Enlaces absolutos y catálogo |
| `API_IDEE_STATIC_RESOURCES_URL` | `https://componentes.idee.es/estaticos` | Recursos SVG y geodatos |
| `API_IDEE_EXTERNAL_PLUGINS_BASE_URL` | vacío (dev/test); real en prod | Catálogo remoto de plugins |
| `API_IDEE_EXTERNAL_PLUGINS_TTL` | `300` | Vigencia de la caché de plugins |
| `API_IDEE_EXTERNAL_PLUGINS_TIMEOUT` | `5` | Timeout de descarga |
| `API_IDEE_EXTERNAL_PLUGINS_MAX_BYTES` | `2097152` | Tamaño máximo del catálogo |
| `API_IDEE_EXTERNAL_PLUGINS_ALLOWED_HOSTS` | `*.idee.es,*.ign.es,*.cnig.es` | Allowlist de plugins |
| `API_IDEE_CATALOG_MAX_AGE` | `300` | `Cache-Control` del catálogo |
| `API_IDEE_RESOURCE_MAX_AGE` | `86400` | `Cache-Control` de SVG/geodatos |
| `API_IDEE_PLUGIN_ASSET_MAX_AGE` | `3600` | `Cache-Control` de JS/CSS |
| `CORS_ALLOWED_ORIGINS` | vacío | Orígenes permitidos |
| `DATABASE_URL` | SQLite local | BD de la aplicación |
| `PROXY_ALLOWED_HOSTS` | `*.idee.es,*.ign.es,*.cnig.es` | Allowlist SSRF (fase 4) |
| `PROXY_TIMEOUT` | `15` | Timeout del proxy |
| `PROXY_MAX_BYTES` | `10485760` | Tamaño máximo de respuesta |
| `LOG_FORMAT` | `console` | `console` o `json` |

Límites de la API (`API_IDEE` en `config/settings/base.py`): URL ≤ 8 KB, ≤ 50 parámetros,
valor ≤ 2 KB, `limit` 1–10 000, `offset` ≤ 1 000 000, 50 capas por visualizador.

---

## Convenciones

1. **Compatibilidad primero**: la fachada `/api/...` no duplica lógica; traduce al modelo
   canónico.
2. **Una sola lectura de `request.GET`** por petición: siempre a través de `Parametros`.
3. **Todo error es Problem Details** salvo JSONP heredado.
4. **JSONP solo en legacy**, con `callback` validado, `nosniff`, `no-store`, `Deprecation`
   y `Sunset`.
5. **Todo destino externo pasa por allowlist** y límites de tiempo/tamaño.
6. **Los parámetros obsoletos se anuncian** con `Deprecation: true` y `Warning`.

---

## Ejemplos de uso

Todos los ejemplos asumen el servidor en `http://localhost:8000`. Las respuestas de error
son `application/problem+json` (RFC 9457).

### Salud

```powershell
Invoke-RestMethod http://localhost:8000/healthz
# { "status": "ok" }
Invoke-RestMethod http://localhost:8000/readyz
# { "status": "ready" }
```

### Crear un visualizador (JSON)

```powershell
$body = @{
  container = "map"
  view = @{ crs = "EPSG:4326"; center = @(-3.7, 40.4); zoom = 5 }
  layers = @(@{ type = "WMS"; id = "u"; url = "https://example.com/wms"; layers = "L" })
  controls = @("scale")
  plugins = @(@{ type = "mousesrs" })
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/viewers `
  -ContentType "application/json" -Body $body
```

Respuesta (`201 Created`, cabecera `Location: /api/v1/viewers/{id}`):

```json
{
  "id": "a711d652-faea-4165-add6-e1d735bf26ee",
  "createdAt": "2026-11-01T15:19:28.673504+00:00",
  "links": [
    { "href": "/api/v1/viewers/a711...", "rel": "self", "type": "application/json" },
    { "href": "/api/v1/viewers/a711...", "rel": "alternate", "type": "text/html" }
  ],
  "container": "map",
  "view": { "crs": "EPSG:4326", "center": [-3.7, 40.4], "zoom": 5 },
  "layers": [{ "type": "WMS", "id": "u", "url": "https://example.com/wms", "layers": "L" }],
  "controls": [{ "type": "scale", "args": [], "options": {} }],
  "plugins": [{ "type": "mousesrs", "args": [], "params": {} }]
}
```

### Recuperar un visualizador en HTML

```powershell
Invoke-WebRequest "http://localhost:8000/api/v1/viewers/{id}?f=html"
# 200 OK, text/html, contiene <div id="mapjs"> y <script id="viewer-config">
```

### Builder legacy (GET)

```powershell
Invoke-WebRequest "http://localhost:8000/api/js?layers=QUICK*c&callback=cb"
# 200 OK, application/javascript
# cb(IDEE.map({"container":"map","layers":["QUICK*c"]}));
```

### Builder legacy (POST)

```powershell
Invoke-WebRequest -Method Post -Uri http://localhost:8000/api/js `
  -ContentType "application/json" -Body '{"layers":["QUICK*c"]}'
# IDEE.map({"container":"map","layers":["QUICK*c"]})
```

### Proxy canónico (GET, streaming)

```powershell
$r = Invoke-WebRequest "http://localhost:8000/api/v1/proxy?url=https://www.ign.es/x"
$r.StatusCode            # 200
$r.Headers["X-Upstream-Status"]  # 200
$r.Content               # cuerpo remoto tal cual
```

### Proxy de imagen

```powershell
Invoke-WebRequest "http://localhost:8000/api/proxy/image?url=https://www.ign.es/img.png"
# 200 OK, Content-Type: image/png, cuerpo binario
```

### Acciones y recursos

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/actions/controls
# [ "scale", "scaleline", "panzoombar", ... ]

Invoke-RestMethod "http://localhost:8000/api/v1/resources/svg?name=circleIcons"
# { "collections": [ { "name": "circleIcons", "resources": [ ... ] } ] }
```

### Error Problem Details

```powershell
Invoke-WebRequest "http://localhost:8000/api/v1/?f=xml"
# 400 application/problem+json
# { "type": ".../invalid-parameter", "title": "Parámetro no válido", "status": 400, ... }
```

---

## Licencia

El código original de API-IDEE y la galería tienen sus propias licencias. **Revisar
`LICENSE` antes de copiar código**; este repositorio solo reimplementa comportamiento
observable.
