# Handoff vigente

## Dónde quedó el proyecto

Parsing operativo canónico integrado y ejecutado sobre15 papers/397 páginas;5.374 unidades,
4.512 apariciones de contenido. Código `code/document_pipeline/`, salida
`analytics/results/sic_collection/parsing-operational-v1/index.html` con JSON/vista
por paper. Misma configuración y código, cero ajustes manuales por documento.
12.pdf reutiliza cachés aprobados; otros14 usan idéntico Docling geométrico y nativo.
Sin nuevos parsers, OCR, modelos neuronales, GROBID o Colab.

374 hijos sin bbox/19 padres/17 páginas abstendidas íntegros.478 nodos de sección propuestos,
185con parent,198nivel desconocido; no afirmar estructura completa/validada.
Integridad técnica y pruebas DOM verificadas; exactitud semántica/QA visual real
pendientes. Todas5.374 unidades en cola after_full_mvp por política, no por error.

## Qué consultar

1. [Estado narrativo completo](13-estado-y-ciclo-experimental.md).
2. [Estado JSON](../../analytics/config/study_progress.json), campo `active_parsing_artifact`.
3. [Informe técnico](../../analytics/reports/sic-parsing-operational-v1.md) y
   [evaluación de los15 papers](../../analytics/reports/sic-parsing-operational-v1-evaluation.md).
4. [Contrato](../arquitectura/parsing-operativo-contrato.md) y [README](../../code/document_pipeline/README.md).
5. [Auditoría](../../analytics/results/sic_collection/parsing-operational-v1-audit/verification.json).

## Pendientes y límites

296 apariciones de contenido sin función operativa,25 unidades con contradicción;
10 nodos de numeración ambigua/10sin localizar;102 continuidades ambiguas/16bloqueadas.
Hay hipótesis duplicadas por codificación y niveles de distinto origen. No sumar
estas cuentas: granularidades/solapamientos distintos. Mejora respaldada acotada en12,
no exactitud global de15 papers ni GT humano. Revisión final no bloquea las salidas.

GROBID pospuesto por coste/peso. Código offline conservado, sin C ni ensayo real.
Docker Linux llegó a estar disponible; descarga detenida sin borrar cachés. G0 sigue
sin completar. No retomar Docker/GROBID/descargas/modelos automáticamente.

## Qué sigue

La actualización documental quedó completada y verificada. El usuario cierra esta
conversación el 27 de octubre de 2026 para continuar en otra; no queda trabajo en ejecución.
No repetir exportaciones/pruebas/modelos por contexto ni ajustar reglas por paper.
Reanudar resumiendo estado y delimitando la nueva solicitud. Revisiones/correcciones
futuras van en incremento nuevo con baseline y aceptación, conservando esta versión.
No pedir revisión humana anticipada caso a caso ni imputar coordenadas a hijos.

[Snapshot anterior completo](../history/parsing-operational-documentation-consolidation-v1/before/).

## Cierre documental

Índices, arquitectura, contrato, evaluación, continuidad y estado JSON sincronizados.
Verificación documental: 20 archivos de código, 462 entradas y 535 salidas canónicas
sin diferencias de hash; enlaces locales y JSON comprobados. No se reejecutó procesamiento.
Auditoría: `docs/history/parsing-operational-documentation-consolidation-v1/verification.json`.
La siguiente conversación debe seguir el protocolo de reanudación y esperar la nueva
solicitud antes de abrir un incremento; GROBID continúa pospuesto.
