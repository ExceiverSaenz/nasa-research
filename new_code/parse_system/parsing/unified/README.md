# Parsing híbrido para n papers

Backend `hybrid`: un entorno virtual, tres workers persistentes y colas de páginas
con capacidad limitada. Cada worker aplica un motor a todos los PDFs. Render CPU,
inferencia de los motores y persistencia de resultados se solapan. Cada página
se renderiza una sola vez a 200 DPI y los tres motores reciben el mismo PNG/hash.

## Estado de validación

La coordinación dispone de pruebas offline con procesos y fixtures. Además se
completó la carga e inferencia reales en A100 para `12.pdf`: 13 páginas, 39 tareas
y cero fallidas en cada uno de los intentos parser y both. El segundo continuó
hasta integración y respaldo verificado. [Registro de ejecución](../../../runtime/three-mode-validation-20261030.json)
y [guía general](../../../README.md#pruebas-y-evidencia).

Los controles de entorno, imports, pesos y CUDA deben cumplirse en cada host.
Estas pruebas no acreditan exactitud semántica, generalización, mejora de
velocidad ni capacidad concurrente en una RTX 3050 de 6 GB. No hay fallback
secuencial, a CPU, de precisión o de resolución.

## Preparación explícita en WSL/Linux

Desde la carpeta autónoma se necesita Python **3.11.16**, acceso a los pesos
verificados existentes, controlador NVIDIA compatible y, para compilar Detectron2,
compiladores C++ y toolkit CUDA **12.6** con `nvcc`. No instalar un driver Linux
de GPU dentro de WSL. El instalador crea un destino nuevo con **un solo `.venv`**;
no modifica los tres entornos baseline ni descarga pesos.

Ejemplo de preparación (el usuario proporciona el Python de versión exacta):

```bash
cd /ruta/a/new_code/parse_system
NASA_ENV_PROFILE=parser python3 -B run.py environment prepare \
  --destination "$HOME/.local/share/nasa-parsing/hybrid-v1" \
  --python /ruta/al/python-3.11.16
```

Este comando instala paquetes en el destino nuevo, resuelve requisitos con
hashes, descarga una revisión fijada de Detectron2, compila su wheel con el
PyTorch común, comprueba dependencias e imports y escribe `environment.json`.
Un destino existente se rechaza. Los fallos y el log quedan conservados.
`NASA_ENV_PROFILE=parser` elige solo la lista de este parser; sin esa selección,
si está presente `new_code/requirements.in`, el instalador puede preparar el
candidato conjunto. Para exportar/reutilizar un perfil parser-only mantener
esa selección explícita. El controlador Colab configura los perfiles mediante
`setup_environment.py --profile parser|integrator|both`; ver la [automatización](../../../automation/README.md).
Un build compatible ya verificado puede reutilizarse sin compilar de nuevo;
reutilizar no equivale a omitir los controles de host, ABI, hashes o candidato.
`requirements.in` es **entrada candidata**, no un lock resuelto; los locks
efectivos son `requirements.lock` y `requirements-complete.lock` del intento.
El manifiesto acredita imports/ABI, no carga de checkpoints ni calidad científica.

No usar los binarios Detectron2 del entorno antiguo con el nuevo PyTorch.
Opcionalmente se puede aportar `--detectron2-source /ruta/a/checkout-local`;
se verifica la revisión completa y se crea una copia de build nueva.

## Configuración de pesos y ejecución

Crear una plantilla desde la carpeta autónoma, sin llamar a los modelos:

```bash
python3 -B run.py template --output hybrid-runtime.json
```

Completar las rutas de la plantilla:

- `env_manifest`: `.../hybrid-v1/environment.json` del entorno recién preparado.
- `vendor_dir`: `vendor/unilm` dentro del paquete, el padre del árbol `layoutlmv3`.
- `model_dirs.layoutlmv3`: carpeta con config, checkpoint y download-manifest.
- `model_dirs.table_transformer`: carpeta verificada con config, preprocesador,
  safetensors y download-manifest originales.
- `model_dirs.mineru`: directorio original verificado `MinerU-4_models_torch`.
- `mineru_receipt`: recibo original de archivos/pesos MinerU con hashes.
- `mineru_config`: una copia nueva de configuración YAML, con `base_dir` apuntando
  al padre de `MinerU-4_models_torch`, por ejemplo:

```yaml
model:
  source: local
  small_backend: torch
  base_dir: /ruta/al/padre-de-MinerU-4_models_torch
llm_aided:
  features:
    title_leveling: false
    cross_page_table_cell_merge: false
```

Los pesos MinerU deben conservar sus marcadores de verificación existentes.
El backend comprueba hashes/marcadores y precarga su contexto/modelos locales;
no repara marcadores ni descarga modelos durante la ejecución.

Las rutas relativas se resuelven respecto al JSON. El vendor original se conserva:
la adaptación de LayoutLMv3 se hace sobre una copia de ejecución identificada.

Usar **el Python del nuevo entorno** para comprobar y ejecutar:

```bash
HYBRID_PYTHON="$HOME/.local/share/nasa-parsing/hybrid-v1/.venv/bin/python"
"$HYBRID_PYTHON" -B run.py check --runtime hybrid-runtime.json

"$HYBRID_PYTHON" -B run.py run \
  --runtime hybrid-runtime.json \
  --input-dir /ruta/a/mis-papers \
  --output mi-intento-nuevo \
  --max-inflight 2 --load-timeout 300 --task-timeout 600 --user-run
```

El lanzador autónomo delega directamente: `run ... --user-run` inicia el backend;
`environment prepare` instala en el destino explícito. No hay opciones `--backend`
ni `--execute` en esta entrada. `--help` y `template` no cargan modelos. El ejemplo
de arriba representa un lote completo; usar únicamente el alcance autorizado,
sin regenerar la colección ni repetir las pruebas reales por rutina.

`--output` es opcional: sin él se crea un nombre único `run-<fechaUTC>-<uuid>`
en la carpeta hermana `results/parse_results`. Si se indica, debe ser un nombre
simple o una ruta absoluta hija directa de `parse_results`; otros destinos se
rechazan para mantener un punto de entrada estable al reconciliador.

`--input-dir` descubre PDFs de esa carpeta, sin recorrer subcarpetas. Alternativa:
repetir `--paper /ruta/a.pdf --paper /ruta/b.pdf`. Se rechazan entradas vacías,
PDFs duplicados y cambios del archivo durante planificación/renderizado.
`--max-inflight` limita páginas globalmente; no multiplica copias de modelos.
Cada motor avanza independientemente entre papers dentro de esa capacidad.

Los timeouts deben ser positivos y finitos. `load-timeout` incluye arranque y
carga; `task-timeout` limita render, cada inferencia y cierre de worker. El tiempo
de espera en cola no consume el timeout de inferencia.

## Resultados y fallos

```text
new_code/results/parse_results/mi-intento-nuevo/
  inputs.json                         PDFs, identidad y páginas esperadas
  renders/<paper-id>/<página>/         solo identity.json; PNG temporal
  results/<paper-id>/<página>/<motor>/ salidas nativas/derivadas de cada motor
  status.json                         eventos, workers, métricas y contabilidad
  configuration.json                  configuración efectiva
  manifest.json                       inventario y SHA256 por archivo
```

Cada tupla paper/página/motor queda contabilizada como completada, fallida,
pendiente o cancelada. Un error detiene el intento sin reintentar ni sobrescribir.
Los workers se recogen antes del estado y respaldo terminal. Ctrl+C conserva
evidencia cuando el proceso coordinador puede manejar la interrupción; un apagado
forzado puede impedir el respaldo, por lo que se conserva el directorio parcial.

Un renderizador Python bloqueado no puede matarse como thread: tras timeout se
retiene y reporta su staging aislado, sin permitirle modificar el resultado ya
cerrado. Los tres workers de inferencia sí se terminan y recogen.

Las métricas distinguen tuplas de inferencia, páginas completas y papers completos,
y reportan throughput total incluyendo arranque. Intervalos solapados de llamadas
demuestran concurrencia de workers, no necesariamente simultaneidad de kernels
CUDA ni aceleración. La colección canónica y sus ZIP permanecen intactos.
El contrato nuevo es `parsing-hybrid-files/2`, con manifest por archivo y sin
ZIP ni PNG persistente obligatorio. `new_code/reconciliation_system` consume
intentos completos y verifica la evidencia; el modo integrator puede seleccionar
papers sin reescribir los JSON originales. [Contrato de entrada](../../../reconciliation_system/README.md).

## Pruebas offline del proyecto

Las pruebas no forman parte de la distribución mínima; se mantienen fuera de
`parse_system`, en `tests/parsing_hybrid/`. Desde la raíz del proyecto:

```bash
python3 -B tests/run.py workflow --list
python3 -B tests/run.py workflow
```

No instala paquetes, llama a servicios ni ejecuta inferencia de los papers.
Las pruebas de coordinación usan procesos `spawn` y fixtures declaradas.

La carpeta puede copiarse o renombrarse sin `code/`, `history/`, notebooks ni
`PYTHONPATH` del proyecto. `run.py` establece su propio import path y el preflight
lanza el script environment.py de este mismo paquete. Los pesos de MinerU/TATR
externos y los PDFs se proporcionan mediante configuración/rutas; no se descargan
ni se transfieren automáticamente al copiar el código.

Al copiar únicamente parse_system, `results/parse_results` se resuelve junto a
la carpeta copiada, no respecto al directorio de trabajo del usuario. El
reconciliador lee solo intentos completos mediante status.json y su manifest.
La reconciliación es un sistema separado; no forma parte del paquete del parser.

Los PNG compartidos se eliminan tras finalizar los tres motores de cada página.
No se generan overlays, recortes ni la exportación native duplicada de MinerU.
El manifest se publica al finalizar; no se genera ZIP. Un renderizador bloqueado
puede dejar staging temporal identificado en status.json hasta revisión manual.
