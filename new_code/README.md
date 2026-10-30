# Procesamiento de papers: Colab, parsing y reconciliación

`new_code` reúne la preparación del entorno, la descarga de pesos y PDFs, el
parser híbrido y la reconciliación. Sus fuentes operativas funcionan sin `code/`,
notebooks ni paquetes históricos. Los originales y resultados anteriores se conservan.

## Estructura

```text
new_code/
  colab_run.py                     controlador local Ubuntu/WSL
  automation/
    colab_worker.py                fases remotas y confirmación explícita de éxito
    selection.py                   selección y transporte de evidencia original
    integrator_bundle.py           validación local de bundles del integrador
    README.md                      detalles de automatización
  setup_environment.py             instalar, comprobar, exportar o reutilizar entorno
  setup_models.py                  descargar pesos fijados y generar runtime JSON/YAML
  prepare_papers.py                firmar solicitudes R2 y descargar PDFs verificados
  requirements.in                  candidato conjunto; no es un lock
  model_manifests/                 revisiones, tamaños y SHA256 de los tres modelos
  parse_system/                    parser híbrido; entrada run.py
  reconciliation_system/           integración; entrada run.py
  inputs/                         PDFs descargados en el equipo de ejecución
  runtime/
    environment/                  ejemplo de entorno instalado en la VM
    bundle-inputs/                bundles de entrada extraídos en la VM
    environment-bundles/           bundles conservados, incluido a100-v2
    colab-bundles/                 bundles exportados por la automatización
    colab-attempts/<id>/           estado del controlador, logs, recibos y transporte local
    model-cache/                  pesos verificados por modelo y revisión
    models-config/                configuración generada en la VM
    pip-cache/                    caché de paquetes
    setup-<fecha>-<id>/            logs y estado del instalador
  results/
    parse_results/<intento>/      resultados del parser
    reconciliation_results/<intento>/ resultados de integración
  visualization/
    build.py                      construcción local desde resultados verificados
    viewer.html                   plantilla responsive de las cuatro vistas
    index.html                    comparación de parsers e integración de 12.pdf
    verification.json             hashes, comprobaciones y límites del visor
    README.md                     uso, reconstrucción y pruebas del visualizador
```

Los PDFs originales locales están fuera de `new_code`, en
`../papers/SiC_papers/` y `../papers/Tensile_Properties_of_Sub-sized_Specimens_papers/`.
El controlador automático selecciona únicamente la colección SiC.

[Automatización](automation/README.md) · [Parser](parse_system/parsing/unified/README.md) ·
[Reconciliación](reconciliation_system/README.md).

## Ejecutar desde Ubuntu/WSL: parser, integrador o ambos

Requisitos locales: Python 3 compatible con los scripts, Colab CLI autenticada,
los PDFs SiC de referencia y credenciales R2 configuradas. Desde la raíz del proyecto:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"

# Menú: 1 parser, 2 integrador, 3 ambos; después 12, 1 3 12 o all.
python3 -B new_code/colab_run.py

# Selección directa.
python3 -B new_code/colab_run.py --papers 12
python3 -B new_code/colab_run.py --papers 1 3 12
python3 -B new_code/colab_run.py --all

# Integrador: un paper, grupo (--papers 1 3 12) o toda la carpeta (--all).
python3 -B new_code/colab_run.py --mode integrator --parse-run 20261030T021637Z-a2ba8ca7 --papers 12

# Parser e integrador en la misma sesión.
python3 -B new_code/colab_run.py --mode both --papers 12

# Comprobar selección y bundle antes de crear una VM.
python3 -B new_code/colab_run.py --papers 12 --plan
```

`12` selecciona `12.pdf`. En `parser`/`both`, `--all` selecciona los PDFs SiC
locales de referencia; en `integrator`, todos los papers de la carpeta elegida.
Cada ejecución crea una sesión **nueva A100** con nombre único y lleva una instantánea
con hashes del código vigente. Excluye runtime, resultados, inputs y cachés Python.
El controlador instala o restaura el entorno del perfil elegido. Solo `parser` y
`both` preparan pesos y ejecutan los tres motores; `integrator` consume evidencia
guardada. Los PDFs se obtienen desde R2 y las salidas se descargan y verifican.
En modo integrador se transfieren únicamente los archivos de los papers elegidos y
los metadatos originales; los PDFs se descargan desde R2 y se verifican por SHA256.
No se modifican los JSON del intento fuente. [Opciones y controles](automation/README.md).

Los resultados del parser se guardan en `results/parse_results/<id>/`; los del
integrador en `results/reconciliation_results/<id>/`. En modo `both`, ambas salidas
comparten el ID y se verifican antes de cerrar la sesión.
Los archivos auxiliares del controlador quedan en `runtime/colab-attempts/<id>/`;
no se crea una carpeta `results/colab_runs`.

La sesión se cierra después de verificar todas las salidas solicitadas y sus descargas.
Para conservarla, añadir `--keep-session`. Para ambas etapas usar `--mode both`.
Ante errores o timeouts no se reintenta ni se cierra una VM potencialmente activa.
Consultar el estado local y `colab sessions` antes de lanzar otro intento:
un timeout del cliente no demuestra que terminó el proceso remoto.

## Entorno y reutilización sin reconstrucciones innecesarias

El controlador elige un perfil: `parser` usa los requirements del parser;
`integrator` usa los de reconciliación; `both` usa `new_code/requirements.in`.
Cada perfil instala su cierre de dependencias, no las listas de los otros perfiles.
El integrador no prepara pesos ni compila Detectron2/CUDA. Los comandos anteriores
sin `--mode` y con `--papers`/`--all` mantienen el modo parser.


Antes de asignar la A100, el controlador busca bundles en `runtime/colab-bundles/`
y `runtime/environment-bundles/`, incluido `a100-v2`. Comprueba SHA256, contenido,
requirements expandidos, recibos, pins actuales e identidad del build de Detectron2.
La firma actual tiene preferencia, pero otro nombre de bundle no impide reutilizarlo
si satisface las comprobaciones del perfil elegido. En Colab se valida también la compatibilidad de
Python, Ubuntu, glibc y arquitectura antes de instalar; los perfiles que ejecutan
el parser también comprueban GPU/ABI y el build de Detectron2.

Un bundle completo compatible evita resolver dependencias. Para parser/both evita
recompilar Detectron2 e instalar herramientas de compilación CUDA. Usa el lock con hashes y `--no-deps`; los paquetes
grandes se descargan directamente en Colab. No se copia una `.venv` entre equipos.
Sin bundle propio de parser, un build conjunto compatible puede aportar solo el
wheel verificado de Detectron2 mientras se resuelve la lista mínima del parser.
Si no hay artefactos compatibles, se instala un entorno nuevo y se exporta un bundle para
las siguientes sesiones. Los bundles anteriores se conservan.

Añadir, quitar o cambiar librerías en los `requirements.in` se detecta antes de
reutilizar el entorno. Las librerías nuevas deben declararse allí; no se infieren de
los imports. Cambiar el resto del código actualiza la instantánea enviada sin obligar
a reconstruir dependencias compatibles. Las validaciones actuales siguen aplicándose.

En la VM se comprueba si ya existen un bundle extraído válido, entorno completo y
pesos/configuración válidos antes de repetir su preparación. Un entorno incompleto
o incompatible requiere revisión; no se modifica silenciosamente. No añadir paquetes
a un entorno después de publicar su fingerprint.

Los perfiles de parser usan Python 3.11.16, Torch 2.7.1+cu126 y el build fijado
de Detectron2; requieren Ubuntu 22.04/24.04 x86_64 y acceso NVIDIA. Si necesitan compilar,
instala CUDA Toolkit 12.6 sin solicitar un controlador NVIDIA. `MAX_JOBS=2` es el
valor de compilación predeterminado. El instalador conserva logs y avisos periódicos.
El perfil `integrator` usa Python 3.11.16 con los pins de Docling/PyMuPDF, valida
su propio recibo y no prepara modelos ni construye Detectron2. La distribución
fijada de Docling incorpora Torch y paquetes CUDA como dependencias indirectas;
esto no equivale a ejecutar modelos ni al paso APT de instalar CUDA Toolkit 12.6.

Los prerrequisitos de sistema se consultan en las fuentes oficiales Ubuntu ya
configuradas, manteniendo firmas y hashes. Los bundles de entrada se extraen en
`runtime/bundle-inputs/`, separados de las exportaciones nuevas. Cada fase remota
debe emitir una confirmación explícita de éxito: Colab CLI puede devolver código
cero aunque Python haya mostrado una excepción. Un fallo queda para revisión,
sin reintentar automáticamente ni sobrescribir su evidencia.

Al cerrar Colab se pierde `/content`: entorno instalado, pesos y cachés de esa VM.
El bundle local conserva locks y wheels reutilizables, no toda la instalación ni
los pesos. En una VM nueva todavía hay que descargar e instalar lo que falte.

## Pesos congelados y PDFs desde R2

`setup_models.py` descarga directamente de Hugging Face las revisiones fijadas de
LayoutLMv3, Table Transformer y MinerU. `model_manifests/` declara archivos, tamaños
y SHA256. Los pesos quedan en `runtime/model-cache/`; se reutilizan archivos válidos
y se conservan parciales para reanudar. La configuración generada apunta a esas
rutas. `parse_system` no incluye una carpeta de pesos locales `models/`.

En Ubuntu/WSL, `~/.config/nasa-research/r2.env`, con permisos 600, contiene:

```dotenv
R2_ENDPOINT_URL=https://TU_ACCOUNT_ID.r2.cloudflarestorage.com
R2_BUCKET=papers
R2_PREFIX=sic_papers/
AWS_ACCESS_KEY_ID=TU_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=TU_SECRET_ACCESS_KEY
```

Usar el endpoint exacto de Cloudflare, incluida su jurisdicción si corresponde,
sin añadir el bucket al endpoint. Las claves permanentes permanecen en WSL.

La automatización firma las solicitudes después de preparar entorno y pesos para
aprovechar su hora de validez. Colab descarga desde R2 y verifica tamaño, SHA256 y
cabecera PDF. Las solicitudes temporales se eliminan y los recibos conservan
procedencia sin URLs firmadas ni claves. Los originales locales sirven de referencia
de integridad; no se transfieren como sustituto de R2.

## Resultados compactos del parser

```text
results/parse_results/<intento>/
  inputs.json
  configuration.json
  status.json
  manifest.json
  renders/<paper-id>/<página>/identity.json
  results/<paper-id>/<página>/
    layoutlmv3/                    JSON de detecciones y metadatos
    table_transformer/             JSON de detecciones y metadatos
    mineru/                        middle-native, regions y model-native si existe
```

Las páginas se renderizan una vez a 200 DPI en staging temporal y los tres motores
comparten la imagen. El PNG se elimina cuando los tres terminan esa página.
Se conservan identidad del PDF, página física, dimensiones, DPI, crop box, rotación,
transformaciones PDF/píxeles, renderer y hash de la imagen usada por los modelos.
No se generan overlays, recortes ni la carpeta `native/` duplicada.
Un renderizador bloqueado puede dejar staging temporal identificado en el estado
para revisión; no se borra mientras siga escribiendo.

`manifest.json` (`parsing-hybrid-files/2`) registra el inventario y SHA256 de cada
archivo persistente, incluidos configuración y estado; no se incluye a sí mismo.
`status.json` conserva tareas, eventos, fingerprints, métricas y errores. Las salidas
de cada modelo permanecen separadas, sin modificar texto, cajas o scores originales.

No se exige ZIP ni sidecar para los intentos nuevos. El TAR con SHA256 que utiliza
el controlador es únicamente transporte descargable; reconciliación consume la
carpeta y su manifest. Los intentos anteriores con ZIP siguen siendo legibles.

## Reconciliar un intento completo

Para integración automática usar `--mode integrator` o `--mode both`.
En una VM con entorno conjunto conservada mediante `--mode both --keep-session`,
la entrada manual sigue disponible desde `/content/new_code`:

```bash
PYTHON="$PWD/runtime/environment/.venv/bin/python"

"$PYTHON" -B reconciliation_system/run.py preflight
"$PYTHON" -B reconciliation_system/run.py run \
  --parse-run "$PWD/results/parse_results/NOMBRE_DEL_INTENTO_COMPLETO" \
  --output intento-integracion --workers 2
```

Requiere un intento completo, su manifest válido y el PDF original accesible con
el hash declarado. Las rutas de `inputs.json` corresponden al equipo de ejecución;
una descarga local no convierte automáticamente las rutas `/content/...` en rutas
Windows/WSL. No editar los JSON protegidos para cambiar esas rutas.

La integración conserva procedencia, verifica los archivos y escribe un intento
separado en `results/reconciliation_results/`. Admite geometría sin PNG persistente;
en ese caso produce datos e índice sin generar las vistas que requieren imágenes.
No genera ZIP automáticamente y mantiene lectura del contrato histórico con ZIP.
En la entrada manual predeterminada y en modo `both`, el recibo debe coincidir
con el usado por el parser. El modo automático `integrator` valida un recibo propio
del perfil mínimo y registra por separado el hash del entorno fuente.

## Visualización HTML bajo demanda

El visor actual corresponde al intento `20261030T021637Z-a2ba8ca7`:
[abrir HTML](visualization/index.html) · [verificación](visualization/index.verification.json).
Incluye 13 páginas y 536 detecciones, selección de modelos, categoría, búsqueda,
zoom y detalle de cajas, texto disponible y procedencia.

Para construirlo explícitamente desde la raíz del proyecto, con PDFium/Pillow
instalados en el Python local utilizado:

```bash
python -B new_code/visualization/build.py \
  --run new_code/results/parse_results/20261030T021637Z-a2ba8ca7 \
  --pdf papers/SiC_papers/12.pdf \
  --output new_code/visualization/index.html
```

Las imágenes se regeneran desde el PDF y se incrustan en el HTML; no se añaden PNG
al intento del parser. Los hashes de los 13 PNG regenerados difieren de los registrados
en Colab, aunque coinciden las dimensiones. La equivalencia de píxeles y el QA visual
real no están acreditados. El visor informa esa diferencia; los JSON fuente se
verificaron contra el manifest y se conservaron intactos.

## Pruebas y evidencia

`../tests/` es una dependencia de desarrollo, no de ejecución. No hace falta enviarla
a Colab. Desde la raíz del proyecto:

```bash
python -B tests/run.py workflow --list
python -B tests/run.py workflow
python -B tests/run.py compatibility
python -B tests/run.py extended
```

[Guía de pruebas](../tests/README.md). Las suites distinguen flujo actual,
compatibilidad histórica y algoritmos/vistas opcionales. Las pruebas JavaScript
se ejecutan por separado según el visor.

El 29 de octubre de 2026 local se completaron tres pruebas reales de `12.pdf`
en A100. Los identificadores siguientes usan UTC:

| Modo | Intento | Evidencia |
| --- | --- | --- |
| Parser | `20261030T032958Z-ba150cdc` | [13 páginas, 39 tareas completas, cero fallidas](results/parse_results/20261030T032958Z-ba150cdc/status.json) |
| Integrador | `20261030T035016Z-f35fc63e` | [Integración completa del intento anterior](results/reconciliation_results/20261030T035016Z-f35fc63e/summary.json) |
| Ambos | `20261030T040105Z-4215756a` | [Parsing completo: 13 páginas/39 tareas](results/parse_results/20261030T040105Z-4215756a/status.json) e [integración completa](results/reconciliation_results/20261030T040105Z-4215756a/summary.json) |

[Registro de los tres modos](runtime/three-mode-validation-20261030.json):
transportes, manifests y hashes verificados; sesiones cerradas al finalizar las
pruebas. Los recibos reales muestran MinerU/Detectron2 sin Docling/PyMuPDF en
`parser`, y Docling/PyMuPDF sin MinerU/Detectron2 en `integrator`.

Las pruebas detectaron una colisión entre el bundle de entrada y la nueva
exportación, y un índice inconsistente de un repositorio NVIDIA que no era
necesario para restaurar el entorno. Se corrigieron las rutas de bundles, la
confirmación de éxito remoto y el alcance de APT. Se conservaron los fallos y
continuaciones revisadas en las mismas sesiones; no se repitió inferencia.
Los scripts de continuación conservados son evidencia de esos intentos, no una
entrada de reanudación automática para futuras sesiones.

La corrida offline Windows registrada examinó 151 pruebas, con un error y una
omitida; no fue una suite completamente aprobada. La prueba afectada pasó en
WSL. Los fixtures y las pruebas reales tienen alcances distintos; consultar los
recibos concretos y no reemplazarlos por una afirmación genérica de éxito.

## Pendientes

**Diferido por decisión del usuario:** investigar el `PermissionError: [WinError 5]`
al mover la carpeta temporal descargada al destino final en
`test_full_controller_then_reuse_without_real_colab`, una prueba simulada Windows.
La causa concreta no está determinada: no atribuirla a antivirus, permisos
específicos o archivos abiertos sin evidencia. La misma prueba pasó en WSL y
los tres casos reales terminaron; eso no demuestra que el error de Windows esté
corregido. No se modificaron permisos del sistema para resolverlo.

El controlador actual requiere Ubuntu/WSL y Colab CLI. Aunque el cálculo ocurra
en Colab, todavía existen transferencias y almacenamiento locales, susceptibles
de errores. Si falla una entrega, conservar el estado y revisar el respaldo
antes de iniciar otro intento; no repetir parsing/integración automáticamente.
No existe garantía de que futuras sesiones no fallen por conexión, recursos o
repositorios externos.

La exactitud semántica, revisión humana, V&V independiente y QA visual real
siguen pendientes. Estos casos no prueban generalización a los 15 papers ni
capacidad en una GPU de 6 GB. El artefacto histórico de colección permanece intacto.
