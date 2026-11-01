# Servidor Django de API-IDEE

Reimplementación en Django del servidor de API-IDEE (`api-idee-rest`, `api-idee-proxy`,
`api-idee-database`), compatible con el cliente **API-IDEE 1.1.0** y con una API canónica
OGC en `/api/v1/`.

El plan de trabajo completo está en [`docs/PLAN_SERVIDOR_DJANGO.md`](docs/PLAN_SERVIDOR_DJANGO.md).
Las decisiones de arquitectura están en [`docs/adr/`](docs/adr/).

---

## Estado del proyecto

| Fase | Contenido | Estado |
|---|---|---|
| **0. Preparación** | Esqueleto Django, CI, lint, tipos, tests, ADRs, corpus golden | ✅ Completada (2026-11-01) |
| **1. Núcleo HTTP y normalización** | `Parametros`, CRS/bbox/datetime, Problem Details, `f`/`Accept`, CORS, cabeceras | ✅ Completada (2026-11-01) |
| **2. Acciones y recursos** | `/api/actions/*`, catálogo, ETag | ⏳ Pendiente |
| **3. Visor y builder** | Plantillas, modelo de capas, `POST /api/v1/viewers` | ⏳ Pendiente |
| **4. Proxy** | GET/POST, imágenes, allowlist SSRF, caché y rate limit | ⏳ Pendiente |
| **5. Base de datos** | Datasources, introspección, OGC API Features, CQL2, MVT | ⏳ Pendiente |
| **6. Correo, legacy, estáticos y despliegue** | `/api/email`, JSP heredados, Docker/nginx, observabilidad | ⏳ Pendiente |
| **7. Cutover** | Golden master, canary, rollback | ⏳ Pendiente |

Detalle de la fase 0:

- [x] T-00.1 Corpus de URLs: **semilla de 48 URLs** en `tests/golden/urls.yaml` y script
      de captura `scripts/capture_golden.py`. Falta ejecutar la captura contra el servidor
      actual para marcarla como completa.
- [x] T-00.2 ADRs 0001–0007.
- [x] T-00.3 Esqueleto Django, `pytest`, `ruff`, `mypy` y CI de GitHub Actions.

Detalle de la fase 1:

- [x] T-01 `Parametros`: case-insensitive, coincidencia exacta, alias, duplicados y límites.
- [x] T-02 Validadores de CRS, bbox, datetime, booleanos, enums, listas y colores.
- [x] T-03 Problem Details (RFC 9457) y middleware de errores.
- [x] T-04 Negociación `f`/`Accept`, ETag/304, `Vary` y `Content-Crs`.
- [x] T-05 CORS por allowlist, CSP con nonce, `nosniff`, `Referrer-Policy`, `Permissions-Policy`.
- [x] T-06 Tests unitarios y de integración del núcleo (150 tests).

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

## Endpoints disponibles (fase 1)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/healthz` | Liveness; no toca dependencias |
| GET | `/readyz` | Readiness; comprueba la base de datos |
| GET | `/api/v1/` | Landing OGC con enlaces |
| GET | `/api/v1/conformance` | Clases de conformidad OGC |
| GET | `/api/v1/openapi.json` | Contrato OpenAPI 3.1 |
| GET | `/api/v1/docs` | Documentación interactiva |

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
│   └── core/
│       ├── params.py         # Parametros: lectura única y tipada
│       ├── validators.py     # int, bool, enum, listas, color, callback
│       ├── crs.py            # EPSG/URN/URI/CRS84 + orden de ejes
│       ├── bbox.py           # bbox 4/6, dominio y reproyección
│       ├── temporal.py       # RFC 3339 e intervalos
│       ├── problems.py       # Problem Details + middleware
│       ├── http.py           # f/Accept, ETag, JSONP, Link
│       ├── pagination.py     # limit/offset/numberMatched/links
│       ├── middleware.py     # request-id, límites, cabeceras
│       ├── logging.py        # logs JSON
│       ├── views.py          # healthz/readyz
│       └── api.py            # landing y conformance
├── tests/
│   ├── unit/core/            # 150 tests del núcleo
│   └── golden/               # corpus de URLs y capturas
├── docs/
│   ├── PLAN_SERVIDOR_DJANGO.md
│   └── adr/
└── scripts/capture_golden.py
```

Las apps `viewers`, `actions`, `catalog`, `proxy`, `databases`, `mailer` y `legacy` se
crearán en sus fases correspondientes.

---

## Configuración

Todas las variables se leen de `.env` o del entorno. Ver `.env.example`.

| Variable | Defecto | Uso |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` | Settings activos |
| `DJANGO_SECRET_KEY` | insegura en dev | Firma de sesiones |
| `DJANGO_DEBUG` | `false` | Depuración |
| `ALLOWED_HOSTS` | localhost | Hosts admitidos |
| `API_IDEE_PUBLIC_URL` | `http://localhost:8000/` | Enlaces absolutos |
| `CORS_ALLOWED_ORIGINS` | vacío | Orígenes permitidos |
| `DATABASE_URL` | SQLite local | BD de la aplicación |
| `PROXY_ALLOWED_HOSTS` | `*.idee.es,*.ign.es,*.cnig.es` | Allowlist SSRF (fase 4) |
| `PROXY_TIMEOUT` | `15` | Timeout del proxy |
| `PROXY_MAX_BYTES` | `10485760` | Tamaño máximo de respuesta |
| `LOG_FORMAT` | `console` | `console` o `json` |

Límites de la API (`API_IDEE` en `config/settings/base.py`): URL ≤ 8 KB, ≤ 50 parámetros,
valor ≤ 2 KB, `limit` 1–10 000, `offset` ≤ 1 000 000, 50 capas por visor, CQL2 ≤ 20 nodos.

---

## Convenciones

1. **Compatibilidad primero**: la fachada `/api/...` no duplica lógica; traduce al modelo
   canónico.
2. **Una sola lectura de `request.GET`** por petición: siempre a través de `Parametros`.
3. **Todo error es Problem Details** salvo JSONP heredado.
4. **Nada de SQL concatenado**: CQL2 + consultas parametrizadas (fase 5).
5. **JSONP solo en legacy**, con `callback` validado, `nosniff`, `no-store`, `Deprecation`
   y `Sunset`.
6. **Todo destino externo pasa por allowlist** y límites de tiempo/tamaño.
7. **Los parámetros obsoletos se anuncian** con `Deprecation: true` y `Warning`.

---

## Próximos pasos (fase 2)

- App `actions` con `/api/actions` y `/api/v1/actions/*` en JSON y JSONP validado.
- Catálogo versionado de controles, plugins y servicios.
- `resources/svg`, `resources/geodata` y `resourcesPlugins` con `ETag`.
- Tests de contrato contra el OpenAPI generado.

---

## Licencia

El código original de API-IDEE y la galería tienen sus propias licencias. **Revisar
`LICENSE` antes de copiar código**; este repositorio solo reimplementa comportamiento
observable.
