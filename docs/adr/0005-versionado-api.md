# ADR 0005 — Versionado `/api/v1` con fachada heredada

| Campo | Valor |
|---|---|
| Estado | Aceptado |
| Fecha | 2026-11-01 |
| Decisión | D-07 del plan |

## Contexto

El cliente 1.1.0 y los visores publicados dependen de `/api/...`, `/proxyPost` y `/`.
A la vez se quiere una API normalizada y documentada.

## Decisión

- La API canónica vive bajo `/api/v1/` y se documenta con OpenAPI 3.1.
- Las rutas heredadas (`/api/...`, `/proxyPost`, `/visor.jsp`) se mantienen como fachada
  que traduce la petición al modelo canónico; no duplican lógica.
- La versión va en la ruta, no en cabecera.
- Los cambios incompatibles crean `/api/v2`; los parámetros obsoletos se anuncian con
  `Deprecation` y `Sunset`.

## Consecuencias

- Un único servicio atiende a clientes antiguos y nuevos.
- El golden master compara ambas capas para detectar divergencias.
- La fachada heredada se puede retirar por fases sin tocar `/api/v1`.
