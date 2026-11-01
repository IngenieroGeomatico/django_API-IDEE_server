"""Entorno de pruebas: rápido, aislado y sin servicios externos."""

from .base import *

DEBUG = False

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# CORS abierto en tests; los casos concretos usan override_settings.
CORS_ALLOW_ALL_ORIGINS = True

# Silencia logs durante los tests salvo que se capturen explícitamente.
LOGGING["root"]["level"] = "CRITICAL"
