"""Entorno de producción.

Los valores sensibles se toman siempre de variables de entorno.
"""

from .base import *

DEBUG = False

# TLS termina en nginx; Django confía en la cabecera del proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31_536_000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

# Sin "*": la allowlist viene de CORS_ALLOWED_ORIGINS.
CORS_ALLOW_ALL_ORIGINS = False

LOG_FORMAT = env("LOG_FORMAT", default="json")
LOGGING["handlers"]["console"]["formatter"] = LOG_FORMAT
