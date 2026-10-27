# Entorno aislado desde Colab CLI 0.7.4

## Estado y continuidad

Instalación, descarga directa de pesos e imports/configuración completados en
Tesla T4 el 18 de octubre de 2026. Respaldo verificado:
`code/results/layoutlmv3-import/20261018T201957Z/`. Sesión real `nasa-layout-env`,
detenida según el usuario. Nueve tests aprobados en Windows y WSL.

No ejecutar de nuevo esta guía para recuperar contexto. El siguiente hito es
probar el MVP ya implementado de inferencia sobre una página; ver
[inference/README.md](inference/README.md). Faltan empaquetado/recuperación y
ejecución real del adaptador en GPU. Consultar
`docs/continuidad/04-estado-de-la-prueba.md` y `docs/continuidad/05-continuacion-de-la-prueba.md`.
Los comandos siguientes son un procedimiento de reconstrucción para una VM nueva,
con autorización de consumo, no una lista pendiente de verificaciones manuales.

## Instalación adicional del detector (segunda etapa)

Con los archivos locales ya preparados, verificar sin GPU:

```bash
python3 -m unittest discover -s code/layoutlmv3 -p 'test_*.py' -v
bash -n code/layoutlmv3/test_detector.sh
```

Después de autorizar el consumo, crear una T4 solo si no existe una sesión adecuada:

```bash
colab sessions
colab new -s nasa-layout-env --gpu T4
bash code/layoutlmv3/test_detector.sh nasa-layout-env
```

test_detector.sh transfiere código y el manifiesto pequeño, sin subir el TAR de pesos.
El instalador descarga el modelo directamente en Colab desde la revisión fija de
Hugging Face y verifica tamaño y SHA-256 antes de publicar cada archivo. Si la
descarga falla o está corrupta, elimina el archivo parcial y no continúa con la
instalación. Requiere acceso a Internet desde Colab; el acceso comprobado desde WSL
no demuestra acceso desde la VM. Los errores de descarga omiten URLs temporales.
Después reconstruye el entorno base, instala dependencias, comprueba importaciones y configuración,
y descarga registros con SHA-256 a code/results/layoutlmv3-import/<fecha>/.
No crea ni detiene sesiones. Tras comprobar el respaldo, detener exclusivamente
la sesión creada para la prueba con `colab stop -s nasa-layout-env`.
Si la instalación falla, el verificador devuelve error pero conserva el ZIP descargado.
Si hay timeout, no asumir que el proceso se detuvo ni repetirlo simultáneamente.
El respaldo incluye el manifiesto y, si la descarga terminó correctamente,
`model-download-check.json`. No incluye los pesos descargados.

Esta etapa NO carga los pesos en un detector ni ejecuta inferencia. Las dependencias
adicionales se instalaron y sus imports/configuración se comprobaron en Colab;
los tests locales por sí solos no prueban esas importaciones. No se modifican ni transfieren PDFs en esta prueba.

La sección de entorno base más abajo instala y verifica Python 3.9.25,
PyTorch 1.10.0+cu111, torchvision 0.11.1+cu111 y Detectron2 0.6. Esa sección
base sola no instala LayoutLMv3; el flujo adicional anterior sí lo instala y
descarga sus pesos. Ninguno procesa PDFs. Mantiene el kernel de Colab intacto.
El instalador conserva setuptools 80.9.0 porque PyTorch antiguo necesita pkg_resources.

## Preparación sin GPU

Desde Ubuntu WSL:

```bash
cd "/mnt/c/Users/HP Victus/Desktop/nasa_research"
python3 -m unittest discover -s code/layoutlmv3 -p 'test_*.py' -v
colab usage
colab sessions
```

Los tests no instalan paquetes, no invocan Colab y no necesitan GPU.

## Ejecución, solo después de autorizar consumo

Ejecutar paso por paso. Revisar sesiones existentes antes de crear una.
Si nasa-layout-env ya existe, revisar con colab status y no crear otra ni detener
una que pertenezca a otro trabajo. La tarifa se consulta después de asignar recursos.
Para este entorno inicial, solicitar T4; no hace falta A100 para las operaciones mínimas.

```bash
colab new -s nasa-layout-env --gpu T4
colab status -s nasa-layout-env
colab usage
colab upload -s nasa-layout-env code/layoutlmv3/setup_env.py /content/nasa_setup_env.py
colab upload -s nasa-layout-env code/layoutlmv3/cli_job.py /content/nasa_cli_job.py
```

Lanzar el archivo transferido mediante runpy: conserva __file__ y evita depender
de que colab exec -f sincronice otros archivos o defina esa variable.

```bash
printf '%s\n' 'import runpy, sys; sys.argv=["/content/nasa_cli_job.py"]; runpy.run_path(sys.argv[0], run_name="__main__")' \
  | colab exec -s nasa-layout-env --timeout 1800
```

Las descargas iniciales pueden tardar. Un timeout no confirma que el proceso
remoto se haya detenido: consultar su estado antes de repetir o cerrar la sesión.
No lanzar dos instaladores simultáneamente.

## Recuperar resultados, también después de un fallo del instalador

Antes de ejecutar este bloque, esperar a que aparezca `Respaldo remoto:` en la
salida. El proceso empaqueta los diagnósticos al terminar, incluso si el instalador
devuelve error. Si la VM se desconecta o muere, esa recuperación no está garantizada.
Si upload falla, corregirlo antes de ejecutar.

```bash
RUN_DIR="code/results/layoutlmv3-env/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$RUN_DIR"
colab download -s nasa-layout-env /content/nasa-layoutlm-setup.zip "$RUN_DIR/setup.zip"
colab download -s nasa-layout-env /content/nasa-layoutlm-setup.sha256 "$RUN_DIR/setup.sha256"
python3 code/layoutlmv3/verify_download.py "$RUN_DIR/setup.zip"
```

El verificador comprueba SHA-256 y CRC del ZIP, y después el estado del instalador.
Si indica instalación fallida pero integridad verificada, los diagnósticos están
recuperados: revisar setup-console.log dentro del ZIP; no afirmar que el entorno funciona.
Si falla la integridad, volver a descargar antes de detener.

Tras recuperar y comprobar los resultados, detener únicamente la sesión creada
para este trabajo:

```bash
colab stop -s nasa-layout-env
colab sessions
colab usage
```

## Qué se conserva

El ZIP contiene configuración, lista de versiones y registros. No contiene el
virtualenv, intérprete Python, PDFs, modelos ni resultados almacenados fuera de
/content/nasa-layoutlm-state. El entorno se reconstruye en cada VM; esta primera
adaptación no promete restauración offline ni automática de todos los archivos.
El cierre de la VM elimina /content.

La caché completa de wheels es opcional: setup_env.py admite --cache-wheels.
El lanzador normal no la activa para evitar duplicar descargas de varios GB.
Si se activa manualmente, se incluye en el ZIP y debe descargarse antes de cerrar.
Una futura restauración requiere transferir snapshot.json y wheelhouse verificados
al directorio de estado antes de ejecutar el instalador. Las versiones transitivas
se registran tras resolverlas; sin snapshot, dos instalaciones pueden diferir.

## Alcance de verificación

Las pruebas locales verifican recuperación y validación de archivos. Las versiones base y la instalación adicional fueron verificadas en Colab
en la ejecución documentada. Una VM nueva debe reconstruir y comprobar el entorno. Disponibilidad de wheels, descargas, compatibilidad del driver y acceso a
Internet pueden impedir instalar. No compila Detectron2 contra CUDA 13; utiliza su
wheel histórico para PyTorch/CUDA 11.1 dentro de un entorno separado.

Fuentes utilizadas para la configuración original:
- https://detectron2.readthedocs.io/en/latest/tutorials/install.html
- https://github.com/microsoft/unilm/tree/master/layoutlmv3
- Ayuda instalada de google-colab-cli 0.7.4 compartida por el usuario.


Actualización del lanzador (18 de octubre de 2026): empaquetado y recuperación ya
implementados. `code/layoutlmv3/test_page.sh NOMBRE_SESION` ejecuta todo el ensayo
sobre una sesión existente autorizada, sin crearla ni cerrarla. Incluye reconstrucción
automática del entorno de la VM nueva y descarga/verificación del respaldo de página.
Paquete `code/packages/layoutlmv3-page.zip`, aproximadamente3.8MiB; 22 tests locales
aprobados y sintaxis Bash correcta. **Siguiente paso vigente: autorizar/asignar una
T4 y ejecutar ese lanzador**; la inferencia real continúa sin acreditarse. No pedir
otra vez los controles locales para recuperar contexto.

inference/
├── __init__.py
├── render.py
├── detector.py
├── outputs.py
└── run_page.py
test_inference.py
