# Arquitectura vigente del parsing

La etapa Parse tiene un MVP operativo ejecutado técnicamente en15 papers/397 páginas.
Es una capa automática sobre resultados de parsers existentes, con incertidumbre y
procedencia conservadas. [Estado](../continuidad/13-estado-y-ciclo-experimental.md),
[contrato JSON](parsing-operativo-contrato.md) y [código](../../code/document_pipeline/README.md).

## Capas y responsabilidades

| Capa | Implementación / entrada | Salida y límite |
| --- | --- | --- |
| Detección/OCR originales | LayoutLMv3, Table Transformer, MinerU; salidas históricas conservadas | No se reejecutan en la integración actual; no ganador global validado |
| Conciliación | autonomous-reconciliation-v1 | Unidades por paper; fuentes/parsers como evidencia, no nuevas unidades principales por parser |
| Clasificación funcional | functional-classification-reconciled-v2 | Categoría/subtipo/función y avisos sobre conciliación; v1 por fuentes es histórica |
| Orden geométrico | ReadingOrderPredictor de Docling, componente basado en reglas | Baseline de cápsulas; no se ejecutó el pipeline neuronal completo de Docling |
| Evidencia nativa | PyMuPDF: texto/spans/estilos, XMP, outlines, enlaces y recursos | Complementa, no sustituye OCR previo ni proporciona GT |
| Estructura operativa | document_pipeline/structure.py | Encabezados, jerarquía parcial, pertenencias y fragmentos candidatos |
| Conexión estructura/recorrido | document_pipeline/order.py | Routing de cápsulas, zonas, precedencias locales; conflictos suspendidos |
| Integración canónica | document_pipeline/pipeline.py | JSON/cola/manifest y vista por paper, índice/métricas de colección |
| Evaluación final | Auditoría técnica existente; semántica/QA visual pendientes | Integridad y DOM no son exactitud; revisión humana after_full_mvp |

## Flujo implementado

1. Verificar manifiestos de readingv1, clasificación conciliada, reconciliación y PDF.
2. Reutilizar cachés aprobados por identidad/hash o aplicar mismo Docling geométrico y método nativo a cada documento.
3. Conservar inventario original y generar semántica operativa separada; no sustituir labels/cajas originales.
4. Construir estructura parcial con outlines, títulos conservados, numeración auxiliar y tipografía relativa.
5. Operar cápsulas enteras: caption primero dentro de asociaciones utilizables, metadatos respaldados a su flujo y precedencias sin ciclos; Docling conserva alternativa y desempates.
6. Asignar contexto de sección/fragmentos mediante referencias, sin concatenar ni aceptar nuevas asociaciones solo por cercanía.
7. Exportar en destino nuevo, validar hashes/contratos y generar vistas con PNG originales. Congelar código/configuración iguales en los15 papers.

## Relaciones y geometría

`precedes`, `next_in_route`, `paragraph_continues`, pertenencia y asociaciones son
conceptos diferentes. El orden físico no prueba pertenencia temática. Dos columnas
no prueban independencia ni continuidad. Ambigüedad permanece con alternativas y
«Requiere validación humana», sin bloquear las salidas.

Las cajas originales mantienen su sistema/origen/transformaciones. Zonas/extensiones
derivadas no son bbox nuevas de regiones.374 hijos sin bbox/19 padres/17 páginas abstendidas
se conservan; no se hereda caja del padre ni se levanta abstención por texto nativo.
No fusionar predicciones, promediar scores entre modelos o imputar confianza.

## Qué está fuera o pospuesto

GROBID: código offline conservado, sin ensayo ni C real; pospuesto por peso/coste.
No añadirlo como dependencia obligatoria ni cambiar motores silenciosamente.
LayoutReader legacy quedó como investigación de compatibilidad; no reparar/ejecutar
por rutina. No nuevos modelos, OCR, Colab/GCE o selección de GPU por documentación.
La representación de celdas/tablas, semántica completa y etapas Extract/Curate/Discover
no se dan por implementadas por terminar técnicamente esta integración Parse.

Detalles anteriores de modelos/checkpoints, propuestas y ensayos específicos se
conservan íntegros en [el snapshot de esta arquitectura](../history/parsing-operational-documentation-consolidation-v1/before/docs/arquitectura/02-arquitectura-del-parsing.md).
No interpretarlos como autorización vigente ni como ejecución actual pendiente.
