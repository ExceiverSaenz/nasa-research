# Parsing operativo de colección — resultados

26oct2026. Incremento autorizado sin GROBID: estructura operativa, conexión a recorrido
 e integración canónica automatizadas. Se procesaron15papers/397páginas con el mismo
código/configuración, sin ajustes por paper ni intervención manual. Fuente: versión
conciliada/clasificaciónv2 y readingv1; Docling geométrico como baseline. Cachés
aprobados de12.pdf reutilizados por identidad, sin repetir su ensayo anterior.

[Índice y vistas de todos los papers](../results/sic_collection/parsing-operational-v1/index.html),
[métricas](../results/sic_collection/parsing-operational-v1/summary.json),
[cola final](../results/sic_collection/parsing-operational-v1/review-queue.json),
[manifest](../results/sic_collection/parsing-operational-v1/manifest.json),
[auditoría](../results/sic_collection/parsing-operational-v1-audit/verification.json),
[comparación de órdenes](../results/sic_collection/parsing-operational-v1-audit/comparison.json).
Contrato/métodos: [README](../../code/document_pipeline/README.md).

## Resultado técnico

5374/5374unidades y4512apariciones de contenido conservadas.374hijos sin bbox,
19padres y17páginas con abstención intactos: no cajas imputadas ni abstenciones
levantadas.478nodos de sección propuestos,185con parent y198con nivel desconocido;
no son478secciones confirmadas.3298unidades tienen contexto de sección propuesto;
1622fragmentos de párrafo sin concatenar.24cápsulas cambian a flujo metadata.
4595precedencias locales propuestas,4suspendidas; cero ciclos operativos.
Todas las fuentes, clasificaciones originales, cajas, textos y asociaciones previas
permanecen verificables. Sin OCR, nuevas inferencias, GROBID, renders o Colab.

|Paper|Páginas|Unidades|Secciones propuestas|Con parent|Nivel desconocido|Hijos diferidos|Cambios de ruta|
|---|---:|---:|---:|---:|---:|---:|---:|
|1|26|331|27|0|27|20|0|
|2|12|303|21|9|1|20|0|
|3|4|89|11|3|4|0|0|
|4|4|94|12|4|4|0|0|
|5|9|204|17|8|1|0|3|
|6|26|390|29|19|5|0|0|
|7|14|299|25|12|3|0|5|
|8|49|607|66|27|30|24|8|
|9|12|187|9|0|0|0|2|
|10|9|69|8|0|1|0|1|
|11|21|365|29|0|25|0|0|
|12|13|293|21|10|4|0|5|
|14|68|740|61|40|12|100|0|
|15|59|694|68|53|9|135|0|
|17|71|709|74|0|72|75|0|

## Conexión y comparación

La estructura aporta precedencias padre→subsección cuando geometría y jerarquía son
compatibles. Zonas/cápsulas delimitan relaciones locales; metadatos solo migran si
todo el contenido de la cápsula tiene soporte frontal. Ciclos/conflictos suspenden
nueva propuesta y conservan alternativas; orden interno caption-first intacto.
Contenedores y referencias compartidas se mantienen; ninguna región se elimina.

1139posiciones de contenido difieren de Docling, incluidas variaciones de índices
por mover metadata: no1139errores corregidos. En23563pares comparables dentro de la
misma página/flujo,174cambian de sentido; no se puntúan pares entre flujos diferentes.
Auditoría guarda diferencias readingv1→Docling→operativo por paper.

Contraste acotado con revisión previa del agente en12.pdf:129/129relaciones que se
habían considerado correcciones Docling conservan su sentido. De6regresiones previas,
4invierten su sentido y2quedan entre flujos separados. No implica exactitud global:
la revisión anterior no es GT humano y solo abarcaba168pares.33indeterminados
siguen sin adjudicación (25mismo sentido,3cambiados,5flujos distintos).

## Validación y límites

13tests offline pasan, incluida exportación automática de dos fixtures, identidad,
no-overwrite, cápsulas, páginas abstendidas, jerarquía y ausencia de dependencia de
nombres de secciones. Revisión independiente sin P1/P2 reproducibles. Freeze del
código nuevo y dependencias/templates reutilizados verificado antes/después.
4764casos DOM en los15HTML/397páginas,10748selecciones de pasos y navegación de
secciones; no QA visual real. Política previa file:// impide automatizar esa revisión;
no se intentó sortearla. PNG originales copiados byte a byte, sin recompresión.

La estructura sigue parcial. Outlines no localizados y headings con diferencias de
codificación pueden permanecer como hipótesis distintas con numeración ambigua.
Niveles nativos y profundidad de marcador tienen orígenes distintos y se conservan
por separado. Clasificación semántica, pertenencia temática visual y continuidad
requieren evaluación final; coincidencia geométrica no demuestra misma sección.
Sin texto nativo suficiente, se conserva fuente parser y abstención por dimensión.
No se aprendieron pesos ni se entrenó sobre12.pdf; solo heurísticas genéricas congeladas.

Las5374unidades conservan advertencia por política after_full_mvp, no5374errores.
Un rol nuevo desconocido no invalida su categoría física o función anterior.
Metadatos ambiguos o cápsulas mixtas pueden seguir en el flujo previo con aviso;
no se garantiza separación semántica perfecta. Dos columnas no bastan para decidir
independencia: presentación Docling provisional y alternativas explícitas.

La integración canónica de esta etapa tiene entrada única y resultados por paper;
no cambia parsers/ZIP ni inventa un ensemble validado. Calidad semántica, QA visual
y V&V con referencia independiente pendientes. No declarar mejora universal porque
los15papers terminaron técnicamente. Revisión humana se acumula al final, sin bloqueo.
GROBID queda pospuesto por decisión del usuario; su descarga fue detenida, sin borrar
cachés ni modificar el código conservado. No reanudarlo automáticamente.

Exportación congelada: no repetir ni ajustar reglas por documento. Nuevos errores
se documentan para un incremento separado, sin modificar estos resultados.

Continuidad candidata por estado: {"candidate_ambiguous": 102, "candidate_supported": 127, "blocked_deferred": 16}.
Estados de secciones: {"aligned_unique": 103, "ambiguous_numbering": 10, "heading_proposal": 120, "unresolved_heading_candidate": 235, "unlocated": 10}.
Papers con fallo de extracción nativa conservado: [].
