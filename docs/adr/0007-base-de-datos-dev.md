# ADR 0007 — SQLite en desarrollo y tests; PostGIS para datasources

| Campo | Valor |
|---|---|
| Estado | Aceptado |
| Fecha | 2026-11-01 |

## Contexto

El plan asume PostgreSQL/PostGIS. Para arrancar sin infraestructura y mantener la CI
rápida se necesita una base de datos local.

## Decisión

- La base de datos **de la aplicación** (metadatos, datasources, caché de configuración)
  usa SQLite en desarrollo y tests.
- Los **datasources** de `/api/database` son conexiones independientes a PostgreSQL/PostGIS
  configuradas por entorno; no son la base de datos de Django.
- En producción, la base de la aplicación puede migrar a PostgreSQL cambiando
  `DATABASE_URL`; el código no usa nada específico de SQLite.
- `django.contrib.gis` y `psycopg` se incorporan en la fase 5, cuando existan los modelos
  de datasource.

## Consecuencias

- `pytest` no requiere contenedores.
- Las pruebas de introspección PostGIS usarán mocks o un servicio de CI opcional.
- Hay que evitar `JSONField` específico de PostgreSQL hasta la fase 5.
