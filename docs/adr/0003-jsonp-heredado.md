# ADR 0003 — JSONP solo en la fachada heredada

| Campo | Valor |
|---|---|
| Estado | Aceptado |
| Fecha | 2026-11-01 |
| Decisión | D-02 del plan |

## Contexto

El cliente API-IDEE 1.1.0 usa JSONP en `/api/proxy` y en algunas rutas de acciones.
JSONP impide usar cabeceras de autenticación y es un vector de XSS si el `callback`
no se valida.

## Decisión

- `/api/v1/**` **no** admite JSONP; solo JSON y CORS.
- La fachada heredada acepta `callback` únicamente si cumple
  `^[A-Za-z_$][A-Za-z0-9_$]{0,63}$`.
- Las respuestas JSONP llevan `application/javascript`, `nosniff`, `Cache-Control: no-store`,
  `Deprecation: true` y `Sunset`.
- El cuerpo se serializa con `json.dumps` y se escapan `<`, `>` y `&` como `\uXXXX`.

## Consecuencias

- El cliente 1.1.0 sigue funcionando sin cambios.
- Los clientes nuevos deben usar `fetch` + CORS.
- La retirada se anuncia con fecha y se puede medir por logs.
