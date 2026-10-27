# Orden documental MVP v1

## Papel actual de esta versión

Readingv1 es baseline histórico, con calidad insuficiente señalada en12.pdf; no es
el recorrido activo. Docling geométrico y [document_pipeline](../document_pipeline/README.md)
conectan estructura/semántica/recorrido en15 papers. Inventario/cápsulas/refs originales
siguen conservados y estas utilidades se reutilizan sin cambios de procesamiento.
No regenerar readingv1 ni confundir sus cifras con la salida canónica actual.

Capa offline aditiva sobre `functional-classification-reconciled-v2`. No ejecuta
clasificadores, parsers, OCR ni modelos. No modifica entradas ni acepta sobrescribir
la carpeta de salida. Diseño y parámetros congelados en
`analytics/analyses/collection/reading-order-reconciled-mvp-v1-{design,plan}.md`.

`engine.order_document` conserva cada unidad original en `inventory`, propone rutas
documentales y distingue `precedes`, `next_in_route` y `paragraph_continues`.
`layout.py` aplica XY-cut recursivo local y grafo acíclico determinista. Los conflictos
conservan restricciones suspendidas y alternativas; fallback no equivale a certeza.
Captions preceden al cuerpo solo en asociaciones existentes utilizables. Contenido
compartido aparece una vez; otras visitas son referencias.

Los hijos sin caja permanecen como referencias diferidas sin orden individual ni
coordenadas imputadas; sus contenedores se conservan. Las páginas abstendidas siguen
abstendidas. La revisión semántica de todas las decisiones queda `after_full_mvp`.

## Artefactos

- `export.py`: verifica hashes de entradas, exporta JSON por paper, resumen y cola.
- `view.py`: genera sitio local responsive de 12.pdf usando copias idénticas de los
  PNG originales; `viewer.html/css/js` sincronizan cajas, lista y flechas.

- JSON: `analytics/results/sic_collection/reading-order-mvp-v1/`.
- Sitio: `analytics/results/sic12_document/reading-order-mvp-v1-view/index.html`.
- Informe: `analytics/reports/sic-reading-order-mvp-v1.md`.

## Verificación offline

Desde la raíz, con `PYTHONPATH=code`:

```text
python -B -m unittest reading_order.test_engine reading_order.test_io -v
node code/reading_order/test_view.js analytics/results/sic12_document/reading-order-mvp-v1-view/index.html
```

`test_view.js` simula DOM y navegación; no sustituye inspección visual en navegador.
La exportación de colección ya registrada no debe repetirse por rutina. Cobertura
del inventario, posiciones propuestas, abstenciones y advertencias son descriptivas;
no miden exactitud frente a GT ni validación humana.
