# Capa nativa aditiva B-native

## Integración actual

B-native de12.pdf es evidencia/caché histórica preservada. La integración canónica
actual está en [document_pipeline](../document_pipeline/README.md), ejecutada en15 papers
con el mismo método y sin GROBID. No repetir esta exportación por contexto. Sus
propuestas no son GT ni validación semántica. El resto describe la capa B original.

Autorización y alcance: `analytics/analyses/paper/sic12-native-structure-implementation-scope.md`.
Entrada: PDF original, conciliación/clasificación v2 y recorrido Docling aprobado.
No ejecuta Docling, OCR, GROBID ni modelos. No cambia clasificación, cajas, grupos,
texto ni recorrido originales. Salida independiente con propuestas operativas
provisionales: no sustituyen automáticamente el pipeline canónico.

## Componentes

- `native.py`: PyMuPDF1.27.2.3, Python3.13.5. Texto/spans/estilos, XMP/metadata,
  outlines, anotaciones, recursos de imágenes, estructura y article threads.
  Sin renderizar ni decodificar imágenes. Conserva xref/puntero y hash del PDF.

- `align.py`: transforma extensiones conciliadas a puntos relativos al crop;
  vincula spans cuyos centros caen en la caja. Es correspondencia muchos-a-muchos,
  no identidad ni nueva segmentación. El texto alineado es una vista de comparación,
  no reemplaza la transcripción. Rotación no cero y geometría inválida se abstienen;
  hijos sin bbox no reciben cajas y se conserva su padre.

- `claims.py`: reconciliación por dimensión. Una afirmación directa verificable
  puede bastar; valores directos incompatibles dejan la propuesta sin resolver.
  Diferencia con evidencia retenida o inferida conserva conflicto y alternativas.
  No vota fuentes correlacionadas ni fabrica scores/probabilidades.

- `structure.py`: roles frontales contextualizados, jerarquía declarada por outlines,
  enlaces exactos Unicode normalizados a encabezados localizados. Sin jerarquía
  declarada, conserva títulos existentes como candidatos de nivel desconocido.
  Metadata puede identificarse sin outlines. Mención parcial de autor ≠ autoría.
  Pertenencia a secciones inferida del recorrido provisional; pertenencia temática de
  visualizaciones se mantiene separada. Párrafos por referencias, con continuidades
  candidatas al cambiar columna/página; no concatena textos ni las acepta como GT.

- `native_export.py`: verifica hashes y contratos, rechaza sobrescritura y exporta
  `native-evidence.json`, `document.json`, `summary.json`, `review-queue.json`, manifest.

- `native_view.py`/`native_view.*`: inspección responsive con cajas originales,
  jerarquía, clasificación anterior/propuesta, contradicciones y evidencia.
  Copia PNG originales byte a byte; zoom CSS opcional, sin recompresión.

## Contrato

`inventory`, `approved_routes` y `approved_steps` son copias íntegras del baseline.
`classification_proposals` contiene decisiones por categoría, función, rol documental
y flujo. Cada decisión conserva claims, alternativas, procedencia, estado y aviso
«Requiere validación humana». `operational_proposal` pertenece a la capa nueva;
`applied_to_baseline=false`. Una propuesta respaldada no equivale a validación humana.
`contradictions` permite inspección agrupada. Se conserva la cola after_full_mvp sin bloqueo.

`document_structure` separa secciones, pertenencia contextual/temática, fragmentos
y continuidades candidatas. No deduce orden global de enlaces, recursos, tags Figure
ni article threads. Atributos geométricos compartidos del StructTree no localizan
figuras individuales. Missing data y matches múltiples permanecen explícitos.

## Verificación y operación

Pruebas: `PYTHONPATH=code python -B -m unittest document_structure.test_native_structure`.
DOM: `node code/document_structure/test_native_view.js [HTML_exportado]`.
No son validación semántica ni QA visual real del navegador.
La exportación ya realizada queda congelada; no repetir ni ajustar reglas sobre12.pdf.
Los comandos de módulos exportadores exigen destinos nuevos y autorización de alcance.
Congelación de librería en `native-requirements.txt`; no instalar ni ejecutar modelos.

Limitaciones: matching por centros puede asociar spans de regiones solapadas; exact
matching de encabezados no resuelve automáticamente todo título partido entre cajas.
Autores con variantes/afiliaciones mezcladas conservan candidatos sin aplicar. Los
roles desconocidos no se fuerzan. La jerarquía depende de la calidad de outlines;
pertenencia/continuidad heredan errores del recorrido. Sin GT, no se informa accuracy.
