# Parsing operativo automatizado

[Contrato de campos/estados](../../docs/arquitectura/parsing-operativo-contrato.md) ·
[Evaluación de los15 papers](../../analytics/reports/sic-parsing-operational-v1-evaluation.md) ·
[Estado vigente](../../docs/continuidad/13-estado-y-ciclo-experimental.md).
Estos enlaces consolidan documentación; no se reejecutó ni cambió el código/configuración del run.

Entrada canónica offline para integrar salidas conciliadas existentes con estructura,
evidencia nativa y recorrido. Sin GROBID, OCR, modelos neuronales, nuevos renders o
etiquetado manual. Los parsers remotos y sus resultados originales no se modifican.

Salida vigente de15 papers/397 páginas:
`analytics/results/sic_collection/parsing-operational-v1/index.html`.
Por paper: `document.json` canónico, `baseline-docling.json`, `native-evidence.json`,
`native-analysis.json`, `review-queue.json`, `verification.json`, `manifest.json`,
`view/index.html`. Colección: summary/manifest/cola e índice. Manifest protege hashes
de inputs, fuentes, código reutilizado/nuevo, configuración y renders originales.

## Uso y contrato

El incremento ya fue ejecutado una vez. No repetir ni sobrescribir para recuperar
contexto. Una futura ejecución autorizada requiere destino nuevo y fuentes verificadas:

```text
PYTHONPATH=code python -B -m document_pipeline.pipeline SOURCE_READING_V1 NEW_DEST --approved-order VERIFIED_DOCLING_JSON --native-cache VERIFIED_NATIVE_JSON
```

Los cachés son opcionales y se seleccionan automáticamente por identidad/hash, no
por número de paper. Se reutilizaron Docling y nativo aprobados de12.pdf. Los otros14
recibieron exactamente el mismo componente Docling geométrico y método nativo,
sin adaptar configuración entre papers. No se ejecuta el antiguo ordenador XY como
orden nuevo: readingv1 aporta inventario/cápsulas/procedencia y Docling es baseline.

- `structure.build_structure`: combina outlines, títulos conservados, marcadores
  jerárquicos auxiliares y tipografía relativa. Una lista numerada sin otro soporte
  no se promociona a heading. Nombres/secuencia de secciones no están prefijados.

- `order.connect_order`: opera cápsulas enteras, conserva caption primero y refs
  compartidas; propone routing frontal cuando toda la cápsula tiene soporte nativo.
  Zonas geométricas separan anchos completos/columnas; precedencias locales y
  padre→subsección compatibles con geometría se resuelven sin ciclos. Restricciones
  incompatibles quedan suspendidas con alternativas. Docling rompe empates.

- `pipeline.assemble/validate/export_collection`: orquesta, valida y exporta una vez.
  Inventario/clasificación/bbox/texto originales íntegros; semántica operativa en
  `operational_semantics`, estructura en `structure`, recorrido en steps/routes.

- `view`: extensión del visor existente sin modificar sus templates originales.
  Toggle Docling/operativo, navegación por secciones, fuentes y avisos; PNG originales
  sin recompresión, ajuste CSS/zoom. No recalcula decisiones al navegar.

`structure.sections` son hipótesis, no secciones confirmadas. `level` conserva el
nivel nativo cuando existe; `numbering_level_candidate` expresa profundidad del
marcador, que puede tener distinto origen por una raíz documental. No equiparar
ambos sin considerar basis. Parent refs forman un grafo válido; parent_candidates
y ambigüedades conservan alternativas. Un outline no localizado y un heading textual
pueden seguir como hipótesis distintas: no fusionarlos manualmente en los resultados.

Pertenencia física depende del recorrido propuesto. Figuras/tablas/captions conservan
contexto físico y asociaciones originales; pertenencia temática permanece desconocida
sin evidencia suficiente. Párrafos son referencias a fragmentos, sin concatenar;
paragraph_continues no equivale a next_in_route. Continuidad `blocked_deferred`
incluye alineación nativa no utilizable/abstención; no son todos hijos sin bbox.

Las páginas abstendidas no se reordenan ni cambian de ruta. Padres/hijos sin bbox
permanecen íntegros; no se localiza un hijo usando caja del padre. Dos columnas no
prueban flujos independientes: la serialización Docling sigue provisional y la
ambigüedad se explicita. Flujos ya separados no reciben precedencia global nueva.

## Evaluación y límites

Pruebas: `PYTHONPATH=code python -B -m unittest discover -s code/document_pipeline -t code -p 'test_*.py'`.
DOM de un HTML ya exportado: `node code/document_pipeline/test_view.js HTML_PATH`.
13 tests offline pasan; revisión independiente sin P1/P2 reproducibles y freeze
de dependencias fortalecido con regresión RED→GREEN. Los15HTML pasaron pruebas DOM
en397 páginas,4764 casos página/flujo/versión. No equivalen a QA visual de navegador.

Resultados conservan todas las advertencias y requieren validación humana al final
del MVP. Contar warnings no cuenta errores: todas5374 unidades están en cola final
por política. Rol documental desconocido no borra categoría/función previa.
Contar cambios de posición global también incluye desplazamientos por routing de
metadata: usar audit/comparison.json para diferencias de pares comparables.

La integración técnica está completada en la colección; exactitud semántica,
jerarquía correcta, pertenencia temática y continuidad siguen sin GT humano.
No entrenar ni ajustar reglas por12.pdf o por cada paper. Próximo incremento debe
partir de errores trazables; no repetir esta exportación congelada por rutina.
