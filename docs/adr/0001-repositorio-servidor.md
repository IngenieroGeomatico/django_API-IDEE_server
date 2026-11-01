# ADR 0001 — Repositorio propio para el servidor

| Campo | Valor |
|---|---|
| Estado | Aceptado |
| Fecha | 2026-11-01 |
| Decisión | D-01 del plan |

## Contexto

La galería (`Galeria_de_mapas`) es un sitio estático con el cliente API-IDEE 1.1.0.
El plan de migración propone reimplementar en Django los módulos Java del servidor
(`api-idee-rest`, `api-idee-proxy`, `api-idee-database`).

## Decisión

El servidor vive en su propio repositorio (`django_API-IDEE_server`). La galería solo
consume las URLs públicas del servicio. Se copia el plan en `docs/PLAN_SERVIDOR_DJANGO.md`
para mantener las fases y criterios de aceptación junto al código.

## Consecuencias

- Ciclos de vida, CI y despliegue independientes de la galería.
- Hay que versionar el contrato (OpenAPI) para que la galería sepa contra qué habla.
- Cambios de URLs públicas se coordinan con la galería y se anuncian con `Deprecation`/`Sunset`.
