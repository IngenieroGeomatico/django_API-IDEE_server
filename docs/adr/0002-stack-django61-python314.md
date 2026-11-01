# ADR 0002 — Django 6.1 sobre Python 3.14

| Campo | Valor |
|---|---|
| Estado | Aceptado |
| Fecha | 2026-11-01 |
| Sustituye a | Plan §3.4 (Django 5.2 LTS + Python 3.12) |

## Contexto

El plan fija Django 5.2 LTS y Python 3.12. La máquina de desarrollo tiene Python 3.14.2
y Django 5.2 no soporta esa versión de Python. Django 6.1 es la estable actual y sí
soporta Python 3.14.

## Decisión

- Python 3.14.2 (entorno `.venv` del repositorio).
- Django 6.1.2.
- `requires-python = ">=3.12"` y `ruff` con `target-version = "py312"` para no introducir
  sintaxis exclusiva de 3.14 y mantener la puerta abierta a desplegar en 3.12.

## Consecuencias

- Se gana soporte nativo de 3.14 y se evita instalar un intérprete adicional.
- Django 6.1 no es LTS: habrá que planificar la actualización a la próxima LTS (6.2).
- Las dependencias deben comprobar su compatibilidad con 3.14 en cada actualización.
- La CI usa Python 3.14; si se despliega en 3.12, añadir una matriz 3.12/3.14.
