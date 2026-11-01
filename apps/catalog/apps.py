"""Configuración de la app catalog."""

from __future__ import annotations

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = "apps.catalog"
    verbose_name = "Catálogo de acciones y recursos"
