# ADR 0006 — Autenticación con Bearer y datasources opacos

| Campo | Valor |
|---|---|
| Estado | Aceptado |
| Fecha | 2026-11-01 |
| Decisión | D-08 del plan |

## Contexto

El servidor actual transporta el ticket y las credenciales de base de datos en la query
string (`token` en base64). Eso filtra secretos a logs, historial, proxies y `Referer`.

## Decisión

- Tokens en `Authorization: Bearer` (RFC 6750); nunca en la query.
- Los datasources se referencian con un ID opaco; la credencial se guarda cifrada en
  servidor (Fernet/KMS) o se inyecta por entorno.
- Los tokens son firmados (HMAC) o de sesión, con rotación y revocación.
- Rate limit por token además de por IP.
- `token` y `ticket` heredados se aceptan solo en la fachada legacy, con aviso y sin
  registrarse en logs.

## Consecuencias

- Hay que definir el emisor de tokens antes de exponer datasources privados (fase 5).
- La fachada legacy puede seguir validando tickets existentes durante la transición.
