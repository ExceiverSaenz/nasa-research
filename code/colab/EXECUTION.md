# Flujo único de ejecución Colab CLI

Esta es la entrada operativa común para cualquier ejecución remota. Las guías
de `code/colab/`, `code/document_trial/` y `code/page_integration/` describen
ensayos concretos, pero no sustituyen este control de estado.

## Antes de ejecutar

1. Consultar `AGENTS.md`, `docs/continuidad/session-handoff.md` y el estado
   canónico.
2. Consultar [`analytics/config/remote_runs.json`](../../analytics/config/remote_runs.json).
3. Confirmar que no existe otro run del mismo alcance en `running`,
   `timeout_manual_review` o `backup_verified` sin resolver.
4. Identificar paquete, versión, configuración, pesos, documento, páginas y
   sesión autorizada.
5. Crear un registro con estado `prepared` usando la plantilla de esta carpeta.

## Flujo controlado

```text
prepared
  → uploaded
  → running
  → backup_verified
  → accepted / failed / timeout_manual_review
  → closed
```

Cada transición debe conservar comando, salida de terminal, run ID, ZIP,
sidecar, SHA/CRC y decisión. Un timeout del cliente no demuestra que el proceso
remoto terminó; usar `timeout_manual_review` y no reintentar automáticamente.

## Criterios de cierre

Solo marcar `backup_verified` cuando el respaldo descargado, su hash/CRC, el
manifest y la identidad del paquete coincidan. Marcar `accepted` únicamente
después de la comparación autorizada con baseline. Marcar `closed` solo cuando
la sesión y el registro tengan estado confirmado.

## No repetir

- No repetir preflight, upload ni descarga de un run ya respaldado.
- No crear otra sesión para recuperar contexto.
- No cambiar paquete, configuración, pesos o hardware dentro del mismo run.
- No cerrar un proceso potencialmente activo tras un timeout sin confirmación.
- No ejecutar este flujo solo para leer documentación.
