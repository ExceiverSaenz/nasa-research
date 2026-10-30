# Reconciliación e integración autónomas

Entrada vigente: `run.py`; paquete: `integration/`, ambos dentro de este sistema.
La implementación procedía históricamente de `code/integration`, pero esa carpeta
o su antiguo enlace no son dependencias ni entradas requeridas en la raíz actual.

## Instalación y comprobación

La entrada predeterminada usa el mismo entorno del parser, resolviendo el candidato conjunto
[`../requirements.in`](../requirements.in) antes del lock/fingerprint.
[`requirements.in`](requirements.in) conserva las versiones científicas de Docling,
Docling Core y PyMuPDF. El perfil compartido requiere Python 3.11.16 y un venv.

```bash
python new_code/reconciliation_system/run.py --help
python new_code/reconciliation_system/run.py preflight
python new_code/reconciliation_system/run.py run --parse-run new_code/results/parse_results/intento-parser --output intento-integracion --workers 2
```

La ejecución requiere el entorno compatible; help no instala ni ejecuta etapas.
El preflight comprueba paquetes, intérprete, imports y hash del predictor geométrico.
No sustituye algoritmos ni descarga modelos. Las listas son candidatas; los
locks y recibos preservados identifican el cierre instalado de cada intento. Los controladores A100/notebook anteriores están
conservados en history, fuera del paquete activo.

## Entrada

`--parse-run` selecciona un directorio del parser. `hybrid_inputs.load_run` exige
`status: completed`, exactamente un resultado por paper/página/motor, PDF
con el hash declarado, geometría consistente y archivos nativos compatibles.
Los intentos nuevos se verifican con `manifest.json` (`parsing-hybrid-files/2`), sin exigir ZIP ni PNG. Para intentos históricos conserva la verificación del ZIP/sidecar. Rechaza archivos nativos cambiados tras el respaldo.
Adapta los formatos guardados a las estructuras canónicas existentes sin reejecutar
parsers. Mantiene registros, texto, cajas, punteros y procedencia. Un hijo sin caja
no recibe la de su padre; conserva las abstenciones del motor existente.
Los hashes registran lo consumido y su coincidencia con el respaldo original;
no acreditan exactitud semántica. En el perfil predeterminado `shared`, el recibo
debe coincidir con el usado por parsing y el PDF debe estar en la ruta registrada.
En el modo automático `integrator`, el controlador descarga el PDF desde R2,
indica su directorio en la VM y verifica el hash original sin cambiar inputs.json;
se valida un recibo propio y se registra por separado el hash del entorno fuente.

## Ejecución y resultados

Cada paper pasa por conciliación → clasificación v2 → cápsulas/recorrido →
integración operativa con evidencia PDF nativa y Docling geométrico. Papers distintos
usan procesos spawn concurrentes y limitados (`--workers`), con el mismo intérprete.
No hay un entorno por proceso ni motores neuronales nuevos en estas etapas.

Salidas en `../results/reconciliation_results/<ejecución>/`:

- inputs.json y execution-profile.json: ejecución fuente, hashes, configuración y mapa de papers.
- status.json, events.jsonl, summary.json e index.html: estado, eventos y entrada de navegación.
- papers/p000001/: etapas reconciliation, classification, capsules y operational; recibos y vistas.
- manifest.json: hashes de resultados y entradas protegidas.

Los directorios compactos y el slot interno `papers/1` son ubicaciones de transporte;
el mapa conserva el paper_id original, PDF y SHA256. No requieren nombres numéricos
para los PDFs. Cada ejecución es nueva; no sobrescribe ni reintenta automáticamente.
Un fallo conserva resultados parciales y marca el intento como fallido.
El contrato durable es el manifest por archivo; no genera ZIP automáticamente.

Las reglas científicas vigentes se conservan. Acuerdo entre parsers no es una
probabilidad ni validación semántica independiente. Revisión humana after_full_mvp,
exactitud semántica y QA visual real continúan pendientes. GROBID sigue pospuesto.


## Integración automática en Colab de resultados existentes

Desde la raíz del proyecto en Ubuntu/WSL usar
`python3 -B new_code/colab_run.py --mode integrator --parse-run NOMBRE --papers 12`
o `--all` para todos los papers de esa carpeta. El controlador envía solo la evidencia
seleccionada sin cambiar los JSON originales, obtiene los PDFs desde R2 e instala
el perfil mínimo de integración. Ver [los tres modos](../automation/README.md).

La entrada interna admite `--paper-id ID` repetible, `--pdf-directory DIRECTORIO`
y `--runtime-profile integrator`. La selección se verifica contra el manifest
original y exige el inventario exacto reducido o el inventario completo original, sin archivos extra. Los PDFs resueltos
por nombre se verifican por SHA256; la salida registra `document_source` con ambas
rutas. Los nombres no prueban identidad. El recibo del integrador se valida con sus
pins, imports, fingerprint y artefactos; el hash del entorno fuente del parser se
registra por separado. El modo predeterminado `shared` mantiene la igualdad de recibos.

La preparación mínima está en `integration/environment.py`; no requiere imports
ni pesos de los tres parsers. Reutiliza bundles de locks verificados compatibles
con Python/Ubuntu/glibc/arquitectura y el candidato vigente. Sin renders persistentes
se producen datos e índice sin las vistas que requieren PNG. No reejecuta modelos.


## Estado comprobado y límites

Se ejecutó realmente el modo integrador en A100 sobre el resultado descargado del
parser `20261030T032958Z-ba150cdc`: intento de integración
`20261030T035016Z-f35fc63e`, un paper completo (`12.pdf`, 13 páginas). También
terminó la integración del modo both `20261030T040105Z-4215756a` en la misma
sesión que su parsing. Se verificaron descargas/manifests/hashes y se cerraron
las sesiones al finalizar esas pruebas. [Evidencia](../runtime/three-mode-validation-20261030.json).

El entorno mínimo observado no incluyó MinerU ni Detectron2. Docling sí aporta
Torch y paquetes CUDA como dependencias indirectas; la integración no prepara
pesos ni ejecuta esos modelos. La misma versión científica de Docling/PyMuPDF y
el hash del predictor se comprueban tanto en perfil integrator como shared.

Esto acredita funcionamiento técnico para ese paper, no exactitud semántica ni
validación de toda la colección. El error de permisos al mover carpetas en una
prueba simulada Windows sigue [pendiente](../README.md#pendientes); no es un error
observado del motor de reconciliación y su causa no está determinada.
