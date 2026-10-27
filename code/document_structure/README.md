# Evidencia nativa y ensayos estructurales

El paquete ya no contiene solo T0. Sus módulos offline se reutilizan en la
[integración canónica de15 papers](../document_pipeline/README.md), vigente y congelada.
La existencia de código no autoriza relanzar modelos o exportaciones.

| Componente | Guía / estado |
| --- | --- |
| T0/LayoutReader | Validación estática histórica; incompatibilidades no reparadas por rutina |
| Docling ReadingOrderPredictor | [DOCLING_TRIAL.md](DOCLING_TRIAL.md); baseline geométrico aprobado de12, mismo componente usado en otros14 |
| Evidencia nativa/B-native | [NATIVE_STRUCTURE.md](NATIVE_STRUCTURE.md); capa offline implementada, fuentes conservadas |
| GROBID adaptador/cliente/evaluación/visor | [GROBID_TRIAL.md](GROBID_TRIAL.md); probado con fixtures, sin ensayo ni C real; pospuesto por usuario |
| Estructura y orden operativos activos | [document_pipeline](../document_pipeline/README.md); JSON/vista canónicos por paper |

No se usa LayoutReader ni GROBID para el resultado activo. No ejecutar un pipeline
neuronal completo de Docling: la integración actual usa su componente geométrico.
Fuente/metadatos/T0 no equivalen a runtime de modelos verificado. Ver
[estado narrativo](../../docs/continuidad/13-estado-y-ciclo-experimental.md).
