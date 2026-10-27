# Estado vigente: parsing operativo de la colección SiC

Fuente narrativa canónica. Complementa [study_progress.json](../../analytics/config/study_progress.json)
y el [handoff](session-handoff.md). El diagnóstico inicial de una página y los planes
previos son historia; no describen por sí solos el alcance actual.

## Resultado activo

`analytics/results/sic_collection/parsing-operational-v1/` es la salida canónica vigente
de **esta etapa de parsing**. [Índice de vistas/JSON](../../analytics/results/sic_collection/parsing-operational-v1/index.html).
Entrada reproducible: `code/document_pipeline/pipeline.py`. No sustituye los parsers
remotos ni modifica sus ZIP, resultados, texto, cajas o clasificaciones originales.

Se ejecutaron **15 papers y 397 páginas**, con idénticos código/configuración y cero
overrides manuales. En12.pdf se reutilizaron Docling y evidencia nativa verificados;
en los otros14 se aplicaron el mismo componente geométrico y extracción nativa PDF.
No se repitieron parsers, OCR, modelos neuronales ni GROBID. No es solo una prueba de12.pdf.

| Elemento | Estado y fuente |
| --- | --- |
| Conciliación | Implementada con pendientes; `autonomous-reconciliation-v1` preservada |
| Clasificación funcional | v2 sobre unidades conciliadas; parsers como evidencia. v1 por fuentes es intento histórico de alcance incorrecto |
| Reading v1 | Baseline histórico; calidad insuficiente detectada en12.pdf |
| Docling | Componente de orden geométrico, baseline aprobado con errores; no se ejecutó el pipeline neuronal completo de Docling |
| Evidencia nativa | PyMuPDF, estilos, XMP, outlines, enlaces/estructura cuando existen; evidencia, no GT |
| Estructura y recorrido operativos | Integrados automáticamente con cápsulas, zonas y precedencias locales; ambigüedad conservada |
| Integración canónica | Completada técnicamente para los15 papers en parsing-operational-v1 |
| Calidad semántica / QA visual / V&V de exactitud | Pendientes; no confundir con integridad técnica o pruebas DOM |
| GROBID | Código offline preparado, pero pospuesto por peso/coste; sin inferencia ni C real |

## Cuentas verificadas

- 5.374 unidades originales y4.512 apariciones de contenido; cero duplicación/pérdida según contratos.
- 374 hijos sin bbox,19 padres y17 páginas con abstención preservados. No asignar caja del padre al hijo.
- 478 nodos de sección propuestos,185con parent,198con nivel desconocido. No478secciones confirmadas.
- 3.298 unidades con contexto de sección;1.622fragmentos de párrafo, sin concatenación irreversible.
- 24 cápsulas pasan a metadata;4.595precedencias locales propuestas y4suspendidas; cero ciclos operativos.
- 13 tests y4.764 casos DOM en397 páginas;397 renders copiados byte a byte. No QA visual real.
- 176archivos protegidos previos,462fuentes de entrada y535archivos de salida verificados en la auditoría del run.

[Informe técnico](../../analytics/reports/sic-parsing-operational-v1.md),
[auditoría](../../analytics/results/sic_collection/parsing-operational-v1-audit/verification.json),
[comparación](../../analytics/results/sic_collection/parsing-operational-v1-audit/comparison.json).
Esta actualización documental no reejecuta dichas pruebas ni modifica esas evidencias congeladas.

## Evaluación y pendientes reales

El MVP es más completo y trazable que el baseline de orden aislado; no hay una tasa
de exactitud global validada.174de23.563 pares comparables cambian de sentido (0,74%);
no174correcciones demostradas.1.139posiciones distintas incluyen desplazamientos de
índice al mover metadata. En12.pdf se mantienen129 relaciones previamente consideradas
correcciones por el agente;4regresiones cambian de sentido y2quedan entre flujos
separados. Es comparación acotada, no GT humano ni validación de los otros14 papers.

Todas5.374 unidades quedan en revisión final por política; no son5.374errores.
1.292 unidades tienen categoría o función desconocida;25tienen contradicción semántica.
La función no resuelta de1.127 unidades incluye374 hijos diferidos,457 contenedores y
296 apariciones de contenido (6,6%de4.512). Además:10 nodos con numeración ambigua,
10sin localizar,123 unidades principales sin contexto de sección,102 continuidades
ambiguas y16bloqueadas. No sumar granularidades ni solapamientos.127 continuidades
con soporte siguen siendo propuestas, no vínculos validados.

[Evaluación completa y tabla por paper](../../analytics/reports/sic-parsing-operational-v1-evaluation.md).
La jerarquía es especialmente incompleta en1,11y17. Los cambios de orden se concentran
en6,7y5; son prioridad de verificación, no errores confirmados. Persisten aliases de
headings por codificación, niveles nativos vs profundidad de marcador, pertenencia
temática visual y separación incierta de columnas/flujos. Metadatos mixtos pueden
seguir en su ruta previa. Rol documental desconocido no elimina categoría/función anterior.

## Decisiones conservadas

- Caption primero dentro de asociaciones utilizables existentes; captions compartidos sin duplicar contenido.
- Precedencia, consecutividad, pertenencia y continuidad son relaciones distintas; no fusionar textos.
- Evidencia directa verificable puede bastar por dimensión. Conflictos conservan alternativas/avisos; no votar fuentes correlacionadas.
- Revisión humana after_full_mvp, agrupada y no bloqueante. No pedir etiquetado caso a caso ahora.
- Sin reglas por autor/título/página/ID de12.pdf. La colección se ejecutó con configuración congelada.
- Table1 de12.pdf:página3 sigue advertencia histórica, recuperación detenida; Table2 conserva su aceptación específica. No generalizar esos dictámenes.
- Los seis vínculos multipanel revisados por usuario siguen aceptados en su alcance; no validan una regla global. Fig6 conserva pendiente de solapamiento.

## GROBID y entorno

Se implementó adaptador/runner/exportador/evaluador/visor offline y se probó con
fixtures, sin presentar datos simulados como resultados del paper. Docker Linux llegó
a arrancar tras preservar directorios de sockets obsoletos; el antiguo diagnóstico
«motor no disponible» ya no es el estado más reciente conocido. La descarga de la
imagen fijada (~14,8GBcomprimidos) fue iniciada y después se detuvo1cliente al posponer
GROBID. No se borraron imágenes/volúmenes/cachés ni se ejecutó el servicio GROBID.
No se acredita descarga completa ni runtime/modelos/configuración G0 verificados.
No consultar ni arrancar Docker/WSL/Colab/GCE para recuperar contexto.

## Continuación autorizada

Entrega posterior de presentación: `analytics/results/sic_collection/collection-stage-view-v1/`
ofrece HTML offline en inglés de los15 papers/397 páginas: comparación de parsers,
clasificación Category/Subtype/Function con Route, orden Readingv1/Docling y recorrido
operativo. No ejecuta etapas científicas ni reemplaza el canónico. Fuentes y cajas
preservadas; QA visual pendiente por rechazo de file:// en la herramienta de navegador.
Ver `code/collection_view/README.md` y verification.json del visor.

Petición anterior completada: preparar una demo Jupyter de toda la integración
en `demo/integration_structure/`, con notebook y paquete autónomo para **A100**.
Incluye las entradas existentes, PDFs y código científico copiado sin cambios;
9 pruebas sintéticas con APIs reales y hashes/sintaxis verificados. No se ejecutó
el notebook en A100 ni se volvió a exportar la colección. El usuario ejecutará
la demo en un intento nuevo; [guía](../../demo/integration_structure/README.md).
El resultado operativo canónico permanece congelado. Una futura mejora requiere problema/evidencia, alcance y criterio de
aceptación/regresión; escribir una versión nueva y preservar la anterior.
Las etapas Extract/Curate/Discover no se dan por implementadas por cerrar técnicamente Parse.

Historial exacto anterior de esta consolidación en
[before](../history/parsing-operational-documentation-consolidation-v1/before/).
