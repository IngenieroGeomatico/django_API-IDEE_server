"""Configuración común a todos los entornos."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_SECRET_KEY=(str, "insecure-dev-key-change-me"),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "[::1]"]),
    CORS_ALLOWED_ORIGINS=(list, []),
    CORS_ALLOW_ALL_ORIGINS=(bool, False),
    LOG_LEVEL=(str, "INFO"),
    LOG_FORMAT=(str, "console"),
)

# Carga .env si existe; en producción se usan variables reales del entorno.
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# Aplicaciones y middleware
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.staticfiles",
    "corsheaders",
    "ninja",
    "apps.core",
    "apps.catalog",
    "apps.actions",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Cabeceras de seguridad las primeras: así también cubren los errores.
    "apps.core.middleware.SecurityHeadersMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "apps.core.middleware.RequestIdMiddleware",
    "apps.core.middleware.QueryLimitsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Problem Details va el último (el más interno) para envolver directamente
    # la vista: Django convierte las excepciones en cada capa de middleware.
    "apps.core.middleware.ProblemDetailsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Base de datos de la aplicación (no los datasources PostGIS de /api/database)
# ---------------------------------------------------------------------------
if env.str("DATABASE_URL", default=""):
    DATABASES = {"default": env.db("DATABASE_URL")}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Estáticos
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ---------------------------------------------------------------------------
# CORS (allowlist por origen; nunca "*" en producción)
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS")
CORS_ALLOW_CREDENTIALS = False
CORS_URLS_REGEX = r"^/(api|proxy|assets|js|plugins|wasm|data)/.*$"
CORS_ALLOW_METHODS = ["GET", "POST", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-language",
    "authorization",
    "content-disposition",
    "content-type",
    "origin",
    "user-agent",
    "x-requested-with",
    "x-request-id",
    "x-target-url",
]
CORS_EXPOSE_HEADERS = [
    "content-crs",
    "content-disposition",
    "deprecation",
    "etag",
    "link",
    "sunset",
    "x-request-id",
    "x-upstream-status",
]
CORS_PREFLIGHT_MAX_AGE = 86400

# ---------------------------------------------------------------------------
# Seguridad HTTP
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "SAMEORIGIN"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Límites de cuerpo (proxy POST, correo, WFS-T)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 256

# ---------------------------------------------------------------------------
# Configuración propia de API-IDEE
# ---------------------------------------------------------------------------
API_IDEE = {
    "PUBLIC_URL": env("API_IDEE_PUBLIC_URL", default="http://localhost:8000/"),
    "PROBLEM_TYPE_BASE": env(
        "API_IDEE_PROBLEM_TYPE_BASE",
        default="https://componentes.idee.es/api-idee/problems/",
    ),
    # Límites de petición (plan §4.13)
    "MAX_URL_LENGTH": env.int("API_IDEE_MAX_URL_LENGTH", default=8192),
    "MAX_PARAMS": env.int("API_IDEE_MAX_PARAMS", default=50),
    "MAX_VALUE_LENGTH": env.int("API_IDEE_MAX_VALUE_LENGTH", default=2048),
    # Paginación OGC
    "DEFAULT_LIMIT": env.int("API_IDEE_DEFAULT_LIMIT", default=100),
    "MAX_LIMIT": env.int("API_IDEE_MAX_LIMIT", default=10_000),
    "MAX_OFFSET": env.int("API_IDEE_MAX_OFFSET", default=1_000_000),
    # Visor
    "MAX_LAYERS": env.int("API_IDEE_MAX_LAYERS", default=50),
    # Proxy (fase 4)
    "PROXY_TIMEOUT": env.float("PROXY_TIMEOUT", default=15.0),
    "PROXY_MAX_BYTES": env.int("PROXY_MAX_BYTES", default=10 * 1024 * 1024),
    "PROXY_MAX_REDIRECTS": env.int("PROXY_MAX_REDIRECTS", default=3),
    "PROXY_ALLOWED_HOSTS": env.list(
        "PROXY_ALLOWED_HOSTS", default=["*.idee.es", "*.ign.es", "*.cnig.es"]
    ),
    "PROXY_ALLOWED_PORTS": env.list("PROXY_ALLOWED_PORTS", default=["80", "443"]),
    # JSONP heredado
    "JSONP_ENABLED": env.bool("JSONP_ENABLED", default=True),
    "JSONP_SUNSET": env("JSONP_SUNSET", default="Wed, 30 Jun 2027 00:00:00 GMT"),
    # Deprecación de rutas heredadas
    "LEGACY_SUNSET": env("LEGACY_SUNSET", default="Wed, 30 Jun 2027 00:00:00 GMT"),
    # Catálogo estático de recursos (SVG y geodatos)
    "STATIC_RESOURCES_URL": env(
        "API_IDEE_STATIC_RESOURCES_URL",
        default="https://componentes.idee.es/estaticos",
    ),
    # Plugins externos. Vacío = solo el snapshot local, sin tráfico de red.
    "EXTERNAL_PLUGINS_BASE_URL": env("API_IDEE_EXTERNAL_PLUGINS_BASE_URL", default=""),
    "EXTERNAL_PLUGINS_TTL": env.float("API_IDEE_EXTERNAL_PLUGINS_TTL", default=300.0),
    "EXTERNAL_PLUGINS_TIMEOUT": env.float("API_IDEE_EXTERNAL_PLUGINS_TIMEOUT", default=5.0),
    "EXTERNAL_PLUGINS_MAX_BYTES": env.int(
        "API_IDEE_EXTERNAL_PLUGINS_MAX_BYTES", default=2 * 1024 * 1024
    ),
    "EXTERNAL_PLUGINS_ALLOWED_HOSTS": env.list(
        "API_IDEE_EXTERNAL_PLUGINS_ALLOWED_HOSTS",
        default=["*.idee.es", "*.ign.es", "*.cnig.es"],
    ),
    # Ficheros JS/CSS de los plugins
    "PLUGIN_ASSET_TIMEOUT": env.float("API_IDEE_PLUGIN_ASSET_TIMEOUT", default=5.0),
    "PLUGIN_ASSET_MAX_BYTES": env.int("API_IDEE_PLUGIN_ASSET_MAX_BYTES", default=2 * 1024 * 1024),
    # Política de caché (segundos)
    "CATALOG_MAX_AGE": env.int("API_IDEE_CATALOG_MAX_AGE", default=300),
    "RESOURCE_MAX_AGE": env.int("API_IDEE_RESOURCE_MAX_AGE", default=86400),
    "PLUGIN_ASSET_MAX_AGE": env.int("API_IDEE_PLUGIN_ASSET_MAX_AGE", default=3600),
}

# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
LOG_LEVEL = env("LOG_LEVEL")
LOG_FORMAT = env("LOG_FORMAT")  # "console" o "json"

LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.core.logging.RequestIdFilter"},
    },
    "formatters": {
        "console": {
            "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
        },
        "json": {"()": "apps.core.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": LOG_FORMAT,
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

# ---------------------------------------------------------------------------
# Correo (fase 6)
# ---------------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="mail-cnig-noreply@cnig.es")
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=15)
