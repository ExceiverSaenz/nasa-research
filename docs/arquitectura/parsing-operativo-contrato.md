# Contrato vigente: parsing-operational/1

Describe los archivos ya exportados, no propone cambios. Fuente:
[README](../../code/document_pipeline/README.md), [informe técnico](../../analytics/reports/sic-parsing-operational-v1.md)
y [manifest canónico](../../analytics/results/sic_collection/parsing-operational-v1/manifest.json).
Estado técnico operativo, con exactitud semántica/QA visual pendientes.

## Organización de archivos

Raíz `analytics/results/sic_collection/parsing-operational-v1/`:
`index.html`, `summary.json`, `manifest.json`, `review-queue.json`, `papers/{id}/`.
Cada paper contiene `document.json`, `baseline-docling.json`, `native-evidence.json`,
`native-analysis.json`, `review-queue.json`, `verification.json`, `manifest.json`
y `view/index.html` con `images/` originales. El índice enlaza todos15 papers.

| Campo / archivo | Qué representa |
| --- | --- |
| inventory | Unidades conciliadas y grupos originales íntegros; original_unit conserva texto/bbox/clasificación y origen |
| classification_source / reconciliation_source | Refs y hashes de fuentes originales |
| canonical_sources | Baselinev1, Docling y archivos nativos; cachés reutilizados por identidad cuando corresponde |
| operational_semantics | Función, rol, flow, ruta efectiva, decisiones, alternativas y avisos por unidad; no edición de original_unit |
| native-analysis.json | Propuestas de clasificación/evidencia nativa previas a la conexión operativa |
| native_links / native-evidence.json | Alineación de spans, fuente, texto de comparación y transformación; no texto OCR reemplazado |
| structure | Secciones, raíces candidatas, pertenencias, fragmentos y continuidades candidatas |
| steps / routes | Cápsulas y recorrido de presentación operativo; referencias compartidas sin duplicar contenido |
| relations | Precedencia, consecutividad y continuidad con ámbitos explícitos |
| operational_connection | Routing, zonas, precedencias propuestas y suspendidas, alternativa baseline |
| original_page_context | Identidades y estados/incidentes conservados de páginas; no levantar abstenciones |
| operational_config / metrics / validation | Configuración congelada, contabilidad y validación técnica; semantic_accuracy=null |
| manifest.json | Hashes de inputs, outputs, código nuevo/reutilizado y runtime; no sustituye evaluación semántica |

## Identidades y referencias

IDs de unidades no se regeneran por parser/página/visualización. El paper es la
unidad documental; su recorrido atraviesa páginas. Inventario, apariciones y visitas
no son el mismo denominador. Resolver `unit_ref` contra inventory, `step` contra
steps y refs de sección contra structure.sections. Referencias compartidas apuntan a
la primera aparición, no a una copia del texto.

Claims nativos `baseline:/...` se interpretan respecto a baseline-docling.json.
Refs `native:...` y punteros de spans se resuelven en native-evidence.json.
Texto normalizado/alineado se usa para comparación y no reemplaza el original.
Sin bbox propia no se dibuja posición inventada; padre conservado no localiza al hijo.

## Semántica y jerarquía parcial

`operational_semantics.role` puede incorporar section_heading_candidate desde la
capa estructural; `decisions.document_role` conserva la decisión de la capa nativa.
No son dos etiquetas confirmadas ni deben sobrescribirse para aparentar acuerdo.
Rol auxiliar desconocido no borra categoría/función anterior.

Las secciones son propuestas. `heading_ref` puede ser null; heading_candidates y
parent_candidates conservan alternativas no operativas. `parent_ref` forma jerarquía
operativa acíclica. Ausencia de parent puede ser raíz válida o desconocimiento.
`level` conserva el nivel declarado por PDF si existe; numbering_level_candidate
es profundidad del marcador y puede excluir la raíz de artículo. No equiparar
ambas escalas; interpretar basis y parent_ref. Diferencias de codificación pueden
mantener aliases/hipótesis distintas del mismo encabezado sin afirmar identidad.

Pertenencia física usa contexto del recorrido; thematic_section_candidates puede
estar vacío aun con figura localizada y caption vinculado. No implica pérdida.
Cada paragraph fragment conserva sus unit refs y text_concatenated=false.

## Estados y advertencias

| Estado o medida | Interpretación |
| --- | --- |
| aligned_unique | Alineación nativa única; no validación humana |
| heading_proposal / unresolved_heading_candidate | Propuesta basada en clasificación/estilo; no sección confirmada |
| ambiguous_numbering / unlocated | Ambigüedad o falta de localización explícita, sin descartar nodo |
| inferred_from_operational_order / physical_context_only | Contexto propuesto, no pertenencia temática demostrada |
| deferred / geometry abstention | Decisión conservada; no inferir coordenadas ni orden de hijos |
| candidate_supported | Continuidad con soporte heurístico; no párrafo aceptado |
| candidate_ambiguous / blocked_deferred | Continuidad incierta/bloqueada por abstención o alineación no utilizable; no equiparar con cuenta de hijos |
| Suspended constraint | Conflicto conservado como alternativa; no usado para producir un ciclo |
| after_full_mvp | Cola de revisión final no bloqueante, incluso para decisiones automáticas únicas |

Todas5.374 unidades requieren revisión por política, no5.374errores. No sumar
nodos/relaciones/unidades ni avisos solapados. Los pares reordenados y posiciones
cambiadas no miden errores corregidos; cambios de ruta pueden desplazar índices.

## Conservación y uso

No modificar originales ni resultados congelados. No introducir overrides manuales
por paper para aparentar calidad. Una nueva corrección requiere incremento y destino
separados. El visor alterna Docling/operativo sin recalcular, conserva los renders
por bytes y ajusta ancho con CSS. DOM no es QA visual ni prueba de exactitud.
