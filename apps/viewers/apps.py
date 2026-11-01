"""Configuración de la aplicación de visualizadores."""

from __future__ import annotations

from django.apps import AppConfig


class ViewersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.viewers"
    verbose_name = "Visualizadores"
