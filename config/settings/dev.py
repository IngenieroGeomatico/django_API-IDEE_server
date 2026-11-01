"""Entorno de desarrollo local."""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ["*"]

# En desarrollo se permite cualquier origen para no bloquear la galería.
CORS_ALLOW_ALL_ORIGINS = True

# El visor y el proxy se depuran con consola legible.
LOG_LEVEL = "DEBUG"
LOGGING["root"]["level"] = LOG_LEVEL
