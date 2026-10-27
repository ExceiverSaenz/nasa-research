# Conciliación autónoma offline v1

Diseño aprobado: ../../analytics/analyses/paper/autonomous-reconciliation-design.md.
Motor genérico `engine.reconcile(page)`; adaptador `inputs.load_evaluation(directory)`
para exportaciones document_trial con MinerU 4.0.12 y contratos LM/TATR originales.
No importa modelos, ejecuta OCR ni consulta red. No consume aceptación humana.

Desde raíz en PowerShell:

```powershell
$env:PYTHONPATH='code'
python -m unittest discover -s code/reconciliation -t code -v
python -m reconciliation.export RUTA_EVALUACION DIRECTORIO_NUEVO
```

El adaptador descubre las páginas declaradas en el manifiesto, no trece páginas
fijas. Verifica hashes, identidad, render y versiones de paquetes que definen los
contratos externos. Transformación MinerU normalizado→píxeles; LM/TATR ya están
en píxeles según este contrato de exportación. Otro formato/configuración requiere
adaptador versionado: no adivinar escalas ni aceptar versiones desconocidas.

API común `canonical-v1`: identity(document_sha256,physical_page,render_sha256,
width_px,height_px); parsers(model→status); records(id,parser,native_type,bbox,
native,parent,role,source(path,sha256,pointer),transform,text); incidents. `bbox`
ya está en píxeles XYXY, origen superior izquierdo; `transform` documenta la
transformación afín [a,b,c,d,e,f] desde caja nativa. Quien cree un adaptador debe
verificar esa transformación contra su fuente antes de entregar registros.
El núcleo es una API de confianza interna; no abre archivos de source ni aplica
una transformación por segunda vez. El exportador suministrado verifica fuentes.

Salidas: document.json, manifest.json, review.html. Cuatro vistas: automática,
MinerU, TATR y LM; selección de página/categoría, contenedores, grupos e inspector.
La automática conserva cajas/texto MinerU y añade relaciones. Resultados humanos
anteriores permanecen separados. No corrige bordes ni recupera etiquetas históricas.

Reglas: normalización explícita de ocho clases; correspondencia mutua >=0.90
única por pareja de parsers; multipanel con soporte LM y estructura/caption MinerU,
sin conflictos internos o externos comparables. Scores no seleccionan ganadores.
Fuentes fallidas se preservan sin apoyar decisiones. Fallo de integridad local
bloquea página, no todo documento; manifiesto global inválido impide cargarlo.
Geometría inválida bloquea relaciones de la página. Números no finitos se exportan
como `{"$nonfinite":"nan"}` (o inf/-inf), sin recortarlos ni borrarlos.

Límite: probado en regresión 12.pdf y fixtures de contrato. No se ha evaluado
generalidad en otros papers; tampoco exactitud OCR/lectura. Las correspondencias
geométricas no son identidad semántica validada. Configuración nueva no soportada
se bloquea; esto es una limitación explícita, no un fallo del parser.

## Entrada de ZIP nativo consolidado v1

`consolidated_inputs.py` adapta `sic-native-archive-consolidation/1` a páginas
`canonical-v1`, separadas por SHA256 de documento. No ejecuta el motor, modelos,
OCR ni nuevos renders; no modifica `inputs.py`, `engine.py` o reglas/umbrales.
MinerU se lee desde `middle-native.json`, con transformación normalizado→píxeles
verificada contra su exportación; LM/TATR desde sus `regions.json` en píxeles.
Se conservan registros nativos completos, jerarquía, scores, clases desconocidas
y geometría inválida. Ninguna caja se recorta ni se usa un score para filtrar.

Preparación offline, una sola vez y con destino nuevo:

```powershell
$env:PYTHONPATH='code'
python -B -m reconciliation.consolidated_inputs ARCHIVO.zip DESTINO_NUEVO
```

Exige el sidecar `.sha256`, formatos/versiones soportados y correspondencia de
documento/página/render/estado. Copia solo fuentes necesarias a `sources/`, con
bytes intactos, y escribe `documents/<SHA256>/input.json` y
`adaptation-manifest.json`. Si la preparación falla, conservar el directorio
parcial para revisión; no sobrescribirlo ni reintentar automáticamente.

API de carga verificada, sin conciliación automática:

```python
from reconciliation.consolidated_inputs import load_document
data = load_document("DESTINO_PREPARADO", "SHA256_DEL_DOCUMENTO")
# data['pages'] contiene el contrato de entrada de engine.reconcile(page).
```

El CLI histórico `reconciliation.export` sigue recibiendo evaluaciones antiguas;
no pasarle directamente este ZIP o la colección preparada. Cada documento debe
consumirse por separado para no confundir páginas físicas con igual número.
Las rutas de procedencia de los inputs preparados son absolutas: mover la carpeta
requiere una nueva preparación trazable, no editar punteros/hashes manualmente.
Preparar la entrada no valida la generalidad del reconciliador entre papers.

Pruebas: `python -B -m unittest reconciliation.test_consolidated_inputs -v`.
