# Inferencia LayoutLMv3 de una página

## 1. Propósito y alcance

Esta carpeta contiene el paquete Python `inference`, un adaptador experimental para detectar la distribución visual (*document layout*) de **una página de un artículo científico** mediante LayoutLMv3. Forma parte del proyecto `nasa_research`, cuyo objetivo documental es localizar regiones de los PDFs y conservar su procedencia para que otras herramientas extraigan después su contenido.

Una región es un rectángulo de la página asociado a una categoría y una puntuación del detector. Por ejemplo, una predicción `table` indica dónde está una posible tabla; no devuelve sus filas, celdas, valores ni unidades científicas. El resultado se conserva en JSON y se representa sobre una copia de la imagen mediante un *overlay* para revisión.

### Contexto del proyecto superior

La documentación de `nasa_research` sitúa este trabajo en la etapa de *parsing* de documentos científicos. Las colecciones descritas corresponden a materiales SiC y propiedades de tracción de probetas pequeñas. Su [contexto y alcance](../../../docs/contexto/01-contexto-y-alcance.md) establece como prioridades evitar omisiones y recortes incompletos, conservar trazabilidad y reducir correcciones manuales.

El objetivo final documentado es ejecución local y gratuita. La prueba histórica en Colab T4 es una excepción experimental: comprobar viabilidad en esa VM no demuestra viabilidad, rendimiento o gratuidad en el equipo local.

Este paquete implementa un ensayo pequeño para investigar al candidato LayoutLMv3 antes de procesar una colección. El [diseño general del parsing](../../../docs/arquitectura/02-arquitectura-del-parsing.md) también considera Table Transformer y MinerU, pero su integración es conceptual y no está implementada en esta carpeta.

### Qué sistema se está inspeccionando

| Elemento | Significado en este paquete |
|---|---|
| PDF y página | Documento de origen y número físico de la página seleccionada. |
| Render | Imagen RGB de toda la página, producida antes de invocar el modelo. |
| Detector | Configuración visual LayoutLMv3 de cinco categorías, ejecutada con Detectron2. |
| Checkpoint | Archivo de pesos preentrenados; este paquete los carga, no los entrena. |
| Predicciones | Cajas, categorías y scores tras el postprocessing del detector. |
| Resultado de ejecución | Archivos exportados y estado de la ejecución; no equivale a evaluación de calidad. |

El candidato configurado es `HYPJUDY/layoutlmv3-base-finetuned-publaynet`, revisión `1c4d2cf657feafac1f53b6f92afe23b279d4f45b`. Sus categorías son `text`, `title`, `list`, `table` y `figure`. La configuración es *image-only*: recibe la imagen, sin palabras ni cajas de OCR como entrada. No debe confundirse este flujo con etiquetado de tokens, donde las cajas de palabras ya se proporcionan al modelo.

### Frontera de responsabilidad

El paquete renderiza una página PDF, construye/carga el detector y exporta regiones, overlay y trazabilidad. No hace OCR, entrenamiento, unión de cajas ni extracción del contenido interno de tablas. Tampoco interpreta propiedades de materiales, valores o unidades científicas, ni implementa el pipeline completo de curación de datos.

La descarga del modelo, la preparación del entorno, el empaquetado y la operación de sesiones remotas corresponden a componentes externos. `run_page.py` consume archivos locales preparados y coordina una página; no crea ni cierra una sesión Colab. Las configuraciones y los pesos no se incluyen en este directorio.

### Ejemplo del recorrido previsto

El ensayo seleccionado utiliza `SiC_papers/12.pdf`, página física 3. El renderer produce una imagen RGB a 200 dpi. El adaptador prepara una entrada redimensionada según 800/1333, solicita predicciones y conserva sus cajas en el sistema de coordenadas del render original. El exportador escribe JSON y una imagen con las cajas para inspección humana.

Este recorrido describe la implementación y el ensayo previsto. No afirma que el detector real haya completado ese recorrido: la sección siguiente delimita la evidencia disponible.

### Cómo leer la documentación

1. Para comprender el componente, leer las secciones 1–4 de este README.
2. Para preparar una ejecución, consultar requisitos, entradas y salidas en las secciones 5–6 y el estado del proyecto superior.
3. Para evaluar una afirmación, consultar las pruebas y evidencias de la sección 7; distinguir siempre código inspeccionado, dobles y detector real.
4. Para analizar una función concreta, consultar su docstring y la [vista canónica por símbolo](../../documentation/documentation-inference/views/documentation.md).

Los registros JSONL externos son la fuente canónica de contratos y evidencias. Este README proporciona el contexto de entrada, el mapa del paquete y la navegación. Los docstrings acercan el contrato pertinente al código sin sustituir la procedencia registrada.

## 2. Estado y límites de validación

Estado documental al 19 de octubre de 2026:

- **Implementado:** renderizado de una página, construcción y carga del detector, predicción y exportación de regiones, overlay y metadatos. La existencia de estas operaciones en el código no acredita su ejecución completa con el detector real.
- **Evidencia disponible:** render local real y registros históricos de pruebas locales, incluidas pruebas con dobles del detector. También está documentada la instalación y comprobación de imports/configuración en Tesla T4. Los alcances y rutas de evidencia se detallan en la sección 7.
- **Pendiente de acreditar:** construcción del detector, carga efectiva del checkpoint e inferencia mediante este adaptador con el modelo real. Tampoco hay evaluación acreditada de la calidad de las regiones.
- **Correspondencia de versiones:** la edición de docstrings cambió los hashes de las fuentes. Los resultados históricos corresponden a las fuentes anteriores, vinculadas mediante [source-state.json](../../documentation/documentation-inference/data/source-state.json); no se atribuyen automáticamente a la versión actual. Ese registro documenta una comparación del AST sin docstrings, no una nueva ejecución de pruebas ni del detector.

Durante esta actualización documental no se ejecutó el proyecto ni se repitió la suite histórica.

## 3. Mapa y navegación

| Archivo | Responsabilidad, interfaz y dependencias |
|---|---|
| __init__.py | Declara el paquete; importarlo no carga el modelo. |
| types.py | RenderedPage, Predictions, LoadReport y RunResult; NumPy/dataclasses; datos para render, detector, outputs y coordinador. |
| render.py | render_page: PDF/página/dpi → RenderedPage; pypdf/PDFium; sin escritura. |
| detector.py | LayoutLMv3Detector, compare_state_dicts y file_sha256; config/pesos/RGB → informe/predicciones; PyTorch/Detectron2 diferidos. |
| outputs.py | save_json, render_geometry, save_regions, save_overlay y save_manifest; datos → JSON/PNG; NumPy/Pillow. |
| run_page.py | run_page, parse_args y main; coordina entradas y directorio nuevo → RunResult/archivos. |
| __pycache__/ | [Cache generada](__pycache__/README.md); bytecode preservado, no prueba de ejecución. |

Documentación canónica: [README externo](../../documentation/documentation-inference/README.md), [registros JSONL](../../documentation/documentation-inference/data/records.jsonl), [vista por símbolo](../../documentation/documentation-inference/views/documentation.md) y [README histórico](../../documentation/documentation-inference/views/historico-inference-20261019.md). No hay configuraciones, scripts de lanzamiento ni pruebas dentro de esta carpeta: se consultan en la superior.

## 4. Flujo y contratos compartidos

Inputs → render → load → predict → export. Los contratos completos están en la vista canónica (INF-002 a INF-008). Página física desde 1; dpi positivo. RGB uint8 con shape (height, width, 3). PDF en puntos de 1/72 de pulgada, origen inferior izquierdo; render en píxeles, origen superior izquierdo. CropBox y rotación forman parte de las matrices PDF-render. UserUnit distinto de 1 se rechaza.

El detector exige entrada 800/1333, image-only, RGB y clases text/title/list/table/figure. Entrega height/width originales al modelo para postprocessing; no aplica segunda escala. El manifest conserva configuración efectiva. La compatibilidad estricta compara claves y shapes, no calidad ni valores esperados.

## 5. Requisitos y ejecución

La [lista de render](../requirements-page.txt) fija pypdfium2 5.14.0 y pypdf 6.10.0. El detector depende del entorno aislado descrito en [estado del proyecto](../../../docs/continuidad/04-estado-de-la-prueba.md), incluidos PyTorch/Detectron2 y vendor/modelos. Python 3.9 tiene comprobación histórica de sintaxis, no ejecución acreditada de este adaptador; los tests locales históricos usaron Python 3.12.14. No instalar el stack antiguo en el kernel moderno para recuperar contexto.

Desde code/layoutlmv3/, con las dependencias pertinentes disponibles:

```bash
python -m inference.run_page --help
python -m inference.run_page --pdf ../../SiC_papers/12.pdf --page 3 --dpi 200 --output ../results/layoutlmv3-page/primer-ensayo
```

Ejemplos de interfaz, no ejecuciones realizadas en esta edición. --output debe ser nuevo; --device acepta cuda o cpu, default cuda. Las rutas default de config/checkpoint/model-config-dir parten de code/; pueden sobrescribirse explícitamente. --pdf y --page son obligatorios. --help puede salir con 0, argumentos inválidos con 2; main devuelve 0 si RunResult.succeeded y 1 en los fallos que maneja. Otros errores pueden propagarse.

El [lanzador externo](../test_page.sh) opera sobre una sesión existente; documentación operativa en [continuación](../../../docs/continuidad/05-continuacion-de-la-prueba.md). No ejecutarlo ni asignar recursos de pago por el mero hecho de leer este README.

## 6. Entradas y salidas

Entradas: PDF legible, página física, dpi, YAML cascade junto a ditod, checkpoint y directorio local con config.json/download-manifest.json. El ensayo seleccionado es SiC_papers/12.pdf, página física 3 (impresa 157), render 200 dpi. La vista histórica local mide 1654 × 2205 px; no son dimensiones universales.

| Archivo generado | Contenido |
|---|---|
| render.png | Render RGB completo. |
| run-manifest.json | Identidades/hashes, versiones, geometría, configuración y tiempos. |
| load-report.json | Diferencias de parámetros cuando hay informe disponible. |
| regions.json | Regiones identificadas con página, tipo, score y caja XYXY. |
| regions-raw.json | Arrays tras filtering/NMS y postprocessing; no logits ni propuestas previas. |
| overlay.png | Copia del render con cajas, IDs y etiquetas. |
| page-status.json | completed/failed, etapa, conteo, error y tiempos. |
| error.log | Traceback de Exception capturada dentro del bloque de etapas. |

Cero regiones puede ser completed; conteo None indica predict no completado. Una exportación parcial falla. El directorio existente se rechaza, pero save_json sí reemplaza archivos dentro de una ejecución mediante .part. No se garantiza diagnóstico si falla la preparación inicial o el almacenamiento en except/finally. No hay garantía de recuperación si se pierde la VM.

## 7. Pruebas y evidencia

[test_inference.py](../test_inference.py) cubre render, CropBox/rotación, matrices, validaciones, comparación de parámetros y coordinación con dobles. [verification.json](../../results/inference-local-checks/verification.json) y [tests.log](../../results/inference-local-checks/tests.log) registran la suite histórica de 20 tests; documentos de continuidad reportan ampliación a 22. No se confunden ambos alcances ni se presenta el reporte como ejecución del código con nuevos hashes.

[source-state.json](../../documentation/documentation-inference/data/source-state.json) conserva correspondencia antes/después de esta edición. Verificar AST sin docstrings preserva estructura ejecutable, pero no implica identidad de __doc__, hashes o bytecode. No reemplaza integración GPU ni evaluación de detecciones.

## 8. Glosario

- Render: imagen raster completa de la página; distinto de la entrada redimensionada del modelo.
- XYXY: (x0, y0, x1, y1), en píxeles del render.
- Checkpoint: pesos deserializados por torch.load y comparados estrictamente.
- Postprocessing: transformación/filtrado del detector antes de exportar arrays.
- Doble: sustituto explícito del detector en pruebas; no modelo real.
- Manifest: registro de procedencia/configuración; no evaluación de calidad.

## 9. Limitaciones y referencias

Cinco categorías nativas; no captions/footers nuevos por renombrado. No orden de lectura garantizado. Los fallos de librerías y GPU pueden propagarse. La factory de pruebas debe proveer load, predict, load_report y metadata; no existe un protocolo formal declarado.

La [documentación canónica](../../documentation/documentation-inference/README.md) conserva procedencia y límites. El [histórico](../../documentation/documentation-inference/views/historico-inference-20261019.md) preserva instrucciones y parámetros anteriores, incluidos ejemplos remotos. El estado remoto no se infiere de esos archivos.
