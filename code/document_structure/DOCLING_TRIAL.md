# Ensayo Docling de orden geométrico

Código nuevo, separado del MVP v1 y de los validadores T0:
`docling_trial.py` propone orden entre cápsulas existentes;
`docling_comparison.py` y `comparison.html/css/js` muestran baseline y candidato.

Docling2.123.1, docling-core2.92.0, rtree1.4.1, pydantic2.12.5. Usar únicamente
ReadingOrderPredictor.predict_reading_order; no DocumentConverter, OCR, redes ni
modelos neuronales. Las cajas se adaptan explícitamente a BOTTOMLEFT antes de crear
PageElement: la conversión TOPLEFT de la dependencia devuelve BoundingBox y pierde
cid. No se parchea la librería. Inputs, fuente y defaults quedan trazados.

Conserva inventario, clasificación, rutas y orden interno de grupos del baseline;
caption primero y referencias compartidas intactos. Orden de referencias compartidas
puede restringir la propuesta Docling, registrando el override. No se ejecutan merges
ni asociaciones de captions. Continuidades v1 quedan como evidencia histórica, no
relaciones nuevas. Los fallos preservan baseline de la página/ruta con advertencia.

Pruebas desde raíz, PYTHONPATH=code:

```text
python -B -m unittest document_structure.test_docling_trial -v
node code/document_structure/test_comparison.js
node code/document_structure/test_comparison_child.js analytics/results/sic12_document/docling-order-trial-v1-view/baseline.html
node code/document_structure/test_comparison_child.js analytics/results/sic12_document/docling-order-trial-v1-view/docling.html
```

Nueve pruebas Python pasan; una expectedFailure mantiene visible una limitación
semántica del componente: intercalar columnas bajo encabezado ancho en un fixture.
No ajustar parámetros para hacerla pasar en este ensayo. DOM simulado no es QA visual.

Exportación de12.pdf ya ejecutada una vez: no repetir por rutina. Datos en
`analytics/results/sic12_document/docling-order-trial-v1/`, vista en
`analytics/results/sic12_document/docling-order-trial-v1-view/index.html`, informe
`analytics/reports/sic12-docling-order-trial-v1.md`. Diferencias no son exactitud.
