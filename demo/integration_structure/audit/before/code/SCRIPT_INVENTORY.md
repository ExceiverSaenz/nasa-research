# Inventario de scripts ejecutables

Estado actual: parsing operativo ya ejecutado en15 papers; [entrada canónica](document_pipeline/README.md).
Consultar [handoff](../docs/continuidad/session-handoff.md) antes de usar scripts.
GROBID pospuesto y Table1 histórica detenida. Los bloques fechados de preparación
no autorizan reintentos ni recuperación automática. Esta consolidación no ejecuta scripts de procesamiento.

## Parsing operativo de colección autorizado (26oct2026)

`document_pipeline/structure.py`, `order.py`: estructura/zonas y conexión a recorrido;
`pipeline.py`: entrada canónica automatizada offline; `view.py`, `viewer_extra.js`: vistas;
`test_*.py/js`: fixtures/DOM, sin modelos. Solo salida nueva; fuentes intactas.


## Integración GROBID offline autorizada (26oct2026)

`document_structure/grobid_adapter.py`, `grobid_align.py`, `grobid_reconcile.py`,
`grobid_evaluation.py`, `grobid_export.py`, `grobid_view.py`, `grobid_mapping.json`:
adaptación de TEI guardado, sin llamadas al servicio. `runners/grobid_trial.py`:
runner futuro aislado; requiere lock completo y autorización de ejecución.
`test_grobid_*.py` y `test_grobid_view.js`: fixtures/DOM sin modelos ni red.


## Evidencia nativa y estructura (26oct2026)

- `document_structure/native.py`, `align.py`: lectura PDF sin OCR y enlaces a unidades
  conciliadas; no cajas imputadas ni modificación de salidas anteriores.

- `document_structure/claims.py`, `structure.py`: propuestas/reconciliación internas,
  jerarquía y párrafos referenciados; sin modelos ni cambios del orden Docling.

- `document_structure/native_export.py`, `native_view.py`: exportación nueva exclusiva
  sobre12.pdf y visor; sin llamadores de GROBID, Docling o modelos neuronales.

- `document_structure/test_native_structure.py`: fixtures/offline; no OCR/modelos.
- `document_structure/test_native_view.js`, `native_view.*`: DOM y vista responsive; no son QA visual.
- Exportación B-native de12.pdf completada/congelada; no repetir automáticamente.

## Ensayo Docling geométrico (26oct2026)

- `document_structure/docling_trial.py`: ordena cápsulas conciliadas existentes
  usando solo predict_reading_order basado en reglas; exportación nueva no-overwrite.

- `document_structure/docling_comparison.py`, plantillas `comparison.*`: comparación
  responsive baseline/candidato; imágenes originales y datos por referencia.

- `document_structure/test_docling_trial.py`: fixtures e integridad offline; sin OCR
  ni imports/conversores/modelos neuronales. Solo ensayo de12.pdf autorizado.

## T0 estructura documental v2 (26oct2026)

- `document_structure/test_t0_contract.py`: pruebas de contratos de versiones y
  cabeceras de tensores con fixtures; sin pesos, imports de torch, modelos ni OCR.

- `document_structure/t0_contract.py`: validación estática de locks y formas de
  tensores; no carga pesos ni ejecuta código descargado. Solo T0 autorizado.

## Orden documental MVP v1 (26oct2026)

- `reading_order/engine.py`, `layout.py`: propuestas offline sobre conciliación
  clasificada; sin OCR/modelos/red ni cambios de categorías o cajas.

- `reading_order/export.py`: exportación verificada por paper a destino nuevo.
- `reading_order/view.py`, `viewer.html/js/css`: website responsive de12.pdf,
  PNG originales copiados, cajas/flechas/lista sincronizadas sin nuevo análisis.

- `reading_order/test_engine.py`, `test_io.py`, `test_view.js`: pruebas offline,
  fixtures y simulación DOM; no lanzadores de parsers ni inferencia.

## Clasificación de conciliación v2 y vista responsive (26oct2026)

- `functional_classification/reconciled.py`: clasifica solo objetos/contenedores y
  grupos declarados; categorías conciliadas como semilla, parsers como evidencia.

- `functional_classification/export_reconciled.py`: exportación offline separada;
  originales y v1 preservados, sin OCR/modelos/Colab.

- `functional_classification/view.py`, `viewer.html/js/css`: website local responsive
  para paper conciliado; imágenes originales copiadas sin recomprimir, sin clasificar.

- `functional_classification/test_reconciled.py`, `test_view.py/js`: pruebas offline
  de selección/evidencia/contrato y presentación; sin inferencias ni red externa.

## Clasificación funcional MVP v1 (26oct2026)

- `functional_classification/classifier.py`: API pura de reglas geométricas/NLP
  sobre registros existentes; sin modelos/OCR/red ni modificación de originales.

- `functional_classification/export.py`: exportación offline autorizada a destino
  nuevo, fuentes verificadas, manifest y cola de revisión diferida.

- `functional_classification/test_classifier.py`: pruebas offline de contrato,
  conflictos, invariancia e integridad. Guía: `functional_classification/README.md`.

## Compute Engine v1 (26oct2026)

- `document_trial/gce_package.py`: preparación offline desde paquete original,
  derivación explícita de plataforma y TAR para transferencia; sin modelos/red.

- `document_trial/gce_entry.py`: entrada exclusiva del usuario en GCE y verificador
  offline; importa modelos solo mediante coordinador cuando usuario inicia run.

- `document_trial/gce.sh`: create/bootstrap/submit/status/collect/stop, exclusivamente
  usuario. Agente no invoca con gcloud real; tests solo cloud simulado.

- `document_trial/gce_bootstrap.sh`: preparación de sistema/driver en VM nueva,
  solo usuario; no parsers. Instrucciones canónicas `document_trial/GCE.md`.

- `document_trial/test_gce.py`: pruebas offline de derivación, identidad/recepción,
  fallo de setup y orquestación con gcloud falso. Sin GPU/modelos/red.

Actualizado: 24 de octubre de 2026. Inventario documental; no se ejecutaron
scripts para elaborarlo. Los estados describen el uso permitido por la
documentación vigente, no una validación nueva del código.

## Adaptadores y lanzadores

| Ruta | Función | Estado | Regla |
| --- | --- | --- | --- |
| `layoutlmv3/cli_job.py` | trabajo CLI LayoutLMv3 | histórico/experimental | No ejecutar para recuperar contexto |
| `layoutlmv3/page_remote.py` | preparación remota de página | experimental | Requiere incremento y run registrado |
| `layoutlmv3/prepare_page.py` | preparación local | soporte del adaptador | Usar solo dentro de un incremento autorizado |
| `layoutlmv3/setup_env.py` | configuración de entorno | histórico | No repetir instalación por rutina |
| `layoutlmv3/install_detector.py` | instalación del detector | histórico | No ejecutar sin autorización específica |
| `mineru_probe/remote_job.py` | trabajo remoto MinerU | histórico de página | No reintentar por contexto |
| `mineru_probe/run_image.py` | ejecución de imagen MinerU | histórico/experimental | Requiere run registrado |
| `table_transformer/remote_job.py` | trabajo remoto TATR | histórico/experimental | Requiere run registrado |
| `table_transformer/run_image.py` | ejecución de imagen TATR | histórico/experimental | Requiere run registrado |
| `page_integration/remote_header.py` | Table1 header | incremento específico | Solo según `HEADER.md` y run registrado |
| `page_integration/remote_square.py` | Table1 square | incremento específico | Solo según `SQUARE.md` y run registrado |
| `page_integration/remote_labels.py` | rótulos localizados | incremento específico | Solo según `README.md` y run registrado |
| `document_trial/run_document.sh` | tres parsers por PDF o lote; paquete explícito | parametrizado, preparado | Ejecución exclusiva del usuario; sin conciliación |

Lote SiC: `document_trial/prepare_batch.py` prepara offline los paquetes ya
verificados; `document_trial/batch.py` coordina documentos dentro de remote.py.
`document_trial/test_batch.py` usa callbacks inertes y enlace de pesos simulado
en Windows. Paquete: `code/packages/sic-parsing-all-v1`, un respaldo/cierre final.

`document_trial/transfer.py`: fragmentación local y generación del ensamblaje
remoto sin modelos; invocado por el lanzador del usuario. `test_transfer.py`:
pruebas offline de bytes, hash, orden y no sobrescritura. Diagnósticos puntuales
guardados en `analytics/results/sic_collection/upload-diagnostic-v1/` son evidencia,
no herramientas vigentes ni autorización para repetir transferencias.

## Scripts de análisis

| Ruta | Función | Estado |
| --- | --- | --- |
| `analytics/src/preprocessing/run_prepare.py` | preparación | histórico/preparado; no ejecutar sin incremento |
| `analytics/src/preprocessing/run_features.py` | features | histórico/preparado; no ejecutar sin decisión |
| `analytics/src/preprocessing/run_views.py` | vistas | histórico/preparado; no ejecutar sin decisión |
| `analytics/src/exploration/run_associations.py` | asociaciones | A03 ya realizado; no repetir |
| `analytics/src/exploration/run_composition.py` | composición | E02 ya disponible; no repetir por contexto |
| `analytics/src/mining/clustering.py` | clustering | propuesto/no requerido; no ejecutar por defecto |

## Scripts de resultados históricos

Los siguientes scripts están dentro de `code/results/` y no son herramientas
vigentes:

- `code/results/table-clustering/cluster_tables.py`;
- `code/results/table-transformer-local-checks/transformers-4.49.0-source.py`;
- `code/results/table-transformer-page/20261023T165937Z/recover_exports.py`.

Estado: `historical_only`. No ejecutar, mover ni convertir en código vigente sin
una decisión explícita y un nuevo incremento.

## Scripts de retry

- `code/table_transformer/retry_job.sh`;
- `code/table_transformer/retry_page.sh`.

Estado: `manual_review_only`. No iniciar reintentos automáticos ni usar estos
scripts para resolver un timeout o recuperar contexto. Cualquier reintento debe
tener autorización, nuevo run ID y registro en `analytics/config/remote_runs.json`.

## Pruebas

Los archivos `test_*.py` y `test_*.sh` deben clasificarse antes de ejecutarse:

```text
offline / empaquetado / launcher / transferencia / workflow / ejecución remota
```

Una prueba offline no demuestra que una inferencia remota sea compatible. No
ejecutar una familia completa de pruebas si una verificación puntual responde la
pregunta actual.

## Código generado o externo

- `__pycache__/` y `*.pyc`: artefactos generados; no leer como fuente.
- `code/vendor/`: dependencia vendorizada; no editar como parte de un incremento.
- logs, ZIP y manifests: evidencia; consultar resumen y verificación antes del
  contenido completo.

## Fig6 explicit association v1

- document_trial/explicit_association.py: approved offline sidecar API; no CLI/inference.
- document_trial/test_explicit_association.py: offline contract/regression tests.
- Instructions: document_trial/EXPLICIT_ASSOCIATION.md.


## Multipanel candidates v1

- document_trial/multipanel_candidates.py: approved offline candidate API, four-page scope.
- document_trial/test_multipanel_candidates.py: offline tests, no remote/model calls.
- Instructions: document_trial/MULTIPANEL_CANDIDATES.md.

## Final reconciliation v1

- document_trial/final_reconciliation.py: approved offline composition API; no model/remote calls.
- document_trial/test_final_reconciliation.py: offline acceptance/integrity tests.
- Instructions: document_trial/FINAL_RECONCILIATION.md.

## Full paper comparison view v1

- document_trial/comparison_view.py: approved offline presentation API, no inference.
- document_trial/comparison_view.js and comparison_view.css: local viewer assets.
- document_trial/test_comparison_view.py: offline fidelity/protection tests.
- document_trial/test_comparison_view.js: offline JS logic checks, no browser.
- Instructions: document_trial/COMPARISON_VIEW.md.

## Conciliación autónoma offline

- reconciliation/engine.py: reglas puras, ocho categorías y abstención; sin modelos.
- reconciliation/inputs.py: adaptador versionado de evidencia guardada; hashes y marcos.
- reconciliation/export.py: CLI offline, directorio nuevo; no OCR/inferencia/red.
- reconciliation/test_engine.py, test_inputs.py, test_export.py: contratos y regresión.
- reconciliation/consolidated_inputs.py: ZIP nativo consolidado a canonical-v1;
  preparación/carga offline, destino nuevo; no invoca el motor ni modelos.

- reconciliation/test_consolidated_inputs.py: contratos sintéticos de entrada,
  procedencia, transformaciones, integridad y rechazo; sin reconciliación real.

- Instrucciones: reconciliation/README.md. Diseño aprobado 26oct2026.


## Parsing local WSL v1

- document_trial/local.py: prepara entornos/pesos sin inferencia; run exclusivo del usuario.
- document_trial/test_local.py: contratos offline.
- Instrucciones: document_trial/LOCAL.md.

- document_trial/local_install.py: reparación explícita de instalación, sin modelos; bloqueos por entorno.
- document_trial/local_download.py: transporte reanudable con SHA256 oficial, sin inferencia.

Lectura MVP: `code/reading_order/test_view.js` simula el DOM offline sobre HTML ya exportado; no valida render visual ni ejecuta análisis. README del módulo documenta pruebas y política de no repetición.
