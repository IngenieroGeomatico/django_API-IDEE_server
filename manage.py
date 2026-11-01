#!/usr/bin/env python
"""Utilidad de línea de comandos de Django."""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:  # pragma: no cover - arranque roto
        raise ImportError(
            "No se pudo importar Django. ¿Está activado el entorno virtual .venv?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
