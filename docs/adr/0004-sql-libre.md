# ADR 0004 — Sin SQL libre en la API pública

| Campo | Valor |
|---|---|
| Estado | Aceptado |
| Fecha | 2026-11-01 |
| Decisión | D-03 del plan |

## Contexto

El servidor actual expone `query`, `select`, `where`, `groupby`, `having`, `orderby` y
`layerfilter` sobre las bases PostGIS, además de un `token` que es la cadena de conexión
en base64. Es una superficie de inyección SQL y de exfiltración.

## Decisión

- La API pública (`/api/v1`) no acepta fragmentos SQL ni credenciales.
- El filtrado se expresa con CQL2 (`filter`, `filter-lang`, `filter-crs`) y se traduce a
  SQL parametrizado.
- Los datasources se identifican con un ID opaco; las credenciales viven en servidor.
- Las consultas usan `psycopg.sql.Identifier` para identificadores y `%s` para valores,
  con `statement_timeout` y transacción de solo lectura.
- Cualquier consola SQL queda en un endpoint de administración autenticado y auditado,
  fuera de este repositorio público.

## Consecuencias

- Los consumidores del SQL libre deberán migrar a CQL2 (guía en fase 5).
- Se elimina la posibilidad de inyección por `filter`, `sortby`, `properties` o `schema`.
