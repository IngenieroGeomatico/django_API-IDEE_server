"""Almacenamiento de visualizadores canónicos (T-14)."""

from __future__ import annotations

import uuid

from django.db import models


class Viewer(models.Model):
    """Visualizador creado por ``POST /api/v1/viewers``.

    La configuración se guarda ya validada y normalizada; el identificador es
    un UUID no adivinable que sirve como enlace público de solo lectura.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "visualizador"
        verbose_name_plural = "visualizadores"

    def __str__(self) -> str:
        return str(self.id)
