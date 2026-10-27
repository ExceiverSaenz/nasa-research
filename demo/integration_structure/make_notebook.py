"""Generate a clean notebook pinned to the verified local upload package."""
import ast
import json
from pathlib import Path
import textwrap

DEMO = Path(__file__).resolve().parent


def build_notebook():
    expected = (DEMO / 'upload.sha256').read_text(encoding='ascii').strip()
    cells = []
    def cell(kind, source):
        cells.append(dict(cell_type=kind, metadata={}, source=textwrap.dedent(source).strip() + '\n',
                          **(dict(execution_count=None, outputs=[]) if kind == 'code' else {})))
    cell('markdown', '''
    # SiC · integración completa · Jupyter / A100

    Ejecuta las celdas **en orden, una sola vez, en una sesión Linux x86_64 con A100**.
    En Colab selecciona A100 en el tipo de entorno. Son 15 papers / 397 páginas.
    La integración actual usa CPU: la A100 identifica el entorno solicitado.

    Se ejecutan conciliación, clasificación v2, Docling geométrico, evidencia nativa,
    estructura, conexión operativa y exportación. Los tres parsers ya se ejecutaron;
    aquí se consumen sus resultados conservados. Se preservan cajas, texto, scores,
    procedencia, contradicciones y abstenciones. Los 374 hijos sin bbox siguen diferidos.

    `upload.zip` y `upload.sha256` de **demo/integration_structure** contienen código,
    los 15 PDFs y las salidas nativas. No uses el ZIP de la demo de parsing.
    La instalación necesita Internet para descargar el intérprete y los paquetes
    fijados; el procesamiento posterior usa solo los archivos incluidos.

    Reserva al menos 16 GiB de RAM y 20 GiB libres en disco; son márgenes recomendados,
    no medidas de un ensayo A100. Usa Drive para conservar el resultado en Colab.
    No hay reintentos ni recuperación automática. Ante fallo puedes respaldar el
    intento sin declarar que la integración se completó.

    El run histórico reutilizó cachés aprobados de 12.pdf; esta demo recalcula Docling
    y evidencia nativa para todos. No se promete igualdad binaria con ese run.
    Integridad técnica no equivale a exactitud semántica ni a QA visual.
    ''')
    cell('markdown', '''
    ## Flujo de integración

    ```mermaid
    flowchart TD
        P["Parsing y fuentes existentes"] --> C["Conciliación: unidades comunes"]
        C --> F["Clasificación funcional v2"]
        P --> O["Orden geométrico Docling"]
        P --> N["Evidencia nativa del PDF"]
        F --> S["Estructura propuesta"]
        N --> S
        F --> I["Conexión operativa"]
        O --> I
        N --> I
        S --> I
        I --> R["Relaciones y recorrido"]
        R --> E["Ensamblar y validar"]
        S --> E
        E --> J["JSON por paper"]
        E --> V["Vistas e índice"]
        E --> H["Revisión humana after_full_mvp"]
        A["Ambigüedad o contradicción"] -.-> E
        A -.-> H
    ```

    El paso auxiliar de inventario/cápsulas usa el contrato reading-v1 existente.
    Después Docling establece el baseline de orden que consume la integración
    operativa. Se conservan las salidas intermedias para inspección.
    ''')
    cell('markdown', '''
    ## 1 · Configuración y comprobación A100

    Si guardaste los archivos en Drive, cambia `INPUT_ZIP` y `INPUT_SHA` a sus rutas
    bajo `/content/drive/MyDrive/…`; Drive se monta en la siguiente celda.
    En Jupyter normal déjalos junto al notebook. El directorio del intento será nuevo.
    ''')
    cell('code', '''
    from pathlib import Path
    import os, sys, json, hashlib, shutil, subprocess, platform, uuid, traceback
    from datetime import datetime, timezone
    from IPython.display import display, FileLink, HTML

    if 'ATTEMPT' in globals():
        raise RuntimeError('Este kernel ya tiene un intento. Conserva sus salidas; no reinicies esta celda.')
    try:
        from google.colab import drive, files
        IS_COLAB = True
    except ImportError:
        IS_COLAB = False

    INPUT_ZIP = Path('upload.zip').resolve()
    INPUT_SHA = INPUT_ZIP.with_suffix('.sha256')
    USE_DRIVE = IS_COLAB
    WORK_ROOT = Path('/content') if IS_COLAB else Path.cwd() / 'integration-runs'
    assert platform.system() == 'Linux' and platform.machine() == 'x86_64', 'Se requiere Linux x86_64.'
    GPU = subprocess.check_output([
        'nvidia-smi', '--query-gpu=name,memory.total,driver_version',
        '--format=csv,noheader,nounits'], text=True).strip().splitlines()
    assert len(GPU) == 1 and 'A100' in GPU[0], 'Selecciona una sola A100.'
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    assert shutil.disk_usage(WORK_ROOT).free >= 20 * 1024**3, 'Se recomiendan al menos 20 GiB libres.'
    ATTEMPT = WORK_ROOT / ('sic-integration-a100-' + uuid.uuid4().hex)
    ATTEMPT.mkdir(exist_ok=False)
    PAYLOAD, STATE = ATTEMPT / 'payload', ATTEMPT / 'run'
    PROCESS = None
    print('GPU / MiB / driver:', GPU[0])
    print('Intento:', ATTEMPT)
    print('Cálculo de integración: CPU; sin inferencia de modelos.')
    ''')
    cell('markdown', '''
    ## 2 · Drive y archivos de entrada

    En Colab se autoriza Drive para respaldo persistente. Si los archivos ya están
    en el panel o en la ruta configurada no se vuelven a subir.
    ''')
    cell('code', '''
    DRIVE_RUN = None
    if USE_DRIVE:
        assert IS_COLAB, 'El montaje automático de Drive corresponde a Colab.'
        drive.mount('/content/drive')
        DRIVE_RUN = Path('/content/drive/MyDrive/nasa-sic-integration') / ATTEMPT.name
        DRIVE_RUN.mkdir(parents=True, exist_ok=False)
        print('Destino persistente:', DRIVE_RUN)
    if not INPUT_ZIP.is_file() or not INPUT_SHA.is_file():
        if IS_COLAB:
            print('Selecciona upload.zip y upload.sha256 de demo/integration_structure.')
            files.upload()
        assert INPUT_ZIP.is_file() and INPUT_SHA.is_file(), 'Faltan los dos archivos en las rutas configuradas.'
    print('Entradas:', INPUT_ZIP, INPUT_SHA)
    ''')
    cell('markdown', '''
    ## 3 · Verificar todo el paquete antes de extraer o importar su código

    Se comprueba el SHA256 esperado, la lista de miembros y el hash individual de
    todos los archivos. La extracción rechaza rutas inseguras, duplicados y symlinks.
    ''')
    common = (DEMO / 'integration_demo/common.py').read_text(encoding='utf-8')
    tree = ast.parse(common)
    wanted = {'digest', 'read_json', 'write_json', 'safe_name', 'check_members', 'member_digest', 'extract_bundle'}
    bootstrap = '\n\n'.join(ast.get_source_segment(common, n) for n in tree.body
                            if isinstance(n, (ast.Import, ast.ImportFrom))
                            or isinstance(n, ast.FunctionDef) and n.name in wanted)
    cell('code', bootstrap + '\n\n' + f"EXPECTED_BUNDLE_SHA256 = {expected!r}\n" + '''
assert INPUT_SHA.read_text(encoding='ascii').strip() == EXPECTED_BUNDLE_SHA256, 'Sidecar de otro paquete.'
PACKAGE = extract_bundle(INPUT_ZIP, PAYLOAD, EXPECTED_BUNDLE_SHA256)
sys.path.insert(0, str(PAYLOAD / 'code'))  # Solo después de verificar todos los miembros.
from integration_demo.runner import initialize, execute_stage, replace_json
from integration_demo.common import make_archive, verify_archive, durable_copy
initialize(PAYLOAD, STATE, GPU)
print('Paquete íntegro:', len(PACKAGE['files']), 'archivos y manifest.')
print('15 PDFs + resultados nativos incluidos; fuentes copiadas a un intento nuevo.')
''')
    cell('markdown', '''
    ## 4 · Entorno aislado y probe real del ordenador geométrico

    Se instala Python **3.13.5** y las dependencias exactas dentro del intento,
    sin cambiar el kernel. Los comandos y errores quedan en `run/logs/`.
    El hash del postprocesador Docling debe coincidir con el baseline conservado.
    Un fallo deja el intento registrado; pasa a la celda de respaldo para conservarlo.
    ''')
    cell('code', '''
    def run_logged(command, label, env=None):
        global PROCESS
        log_path = STATE / 'logs' / (label + '.log')
        log_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(STATE / 'commands' / (label + '.json'), {'argv': [str(x) for x in command]})
        with log_path.open('x', encoding='utf-8') as log:
            try:
                PROCESS = subprocess.Popen([str(x) for x in command], env=env, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', bufsize=1)
                for line in PROCESS.stdout:
                    print(line, end='', flush=True)
                    log.write(line)
                    log.flush()
                returncode = PROCESS.wait()
            except BaseException:
                if PROCESS is not None and PROCESS.poll() is None:
                    PROCESS.terminate()
                    try:
                        PROCESS.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        PROCESS.kill()
                        PROCESS.wait()
                raise
        if returncode != 0:
            raise RuntimeError(f'Comando fallido ({returncode}); consultar {log_path}. No reintentar.')

    STAGE_ENV = dict(os.environ, PYTHONPATH=str(STATE / 'source-code'),
        PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUDA_VISIBLE_DEVICES='')
    PYTHON = ATTEMPT / 'runtime/venv/bin/python'

    def prepare_environment():
        from integration_demo.runtime import setup
        actual = setup(ATTEMPT / 'runtime', PAYLOAD, STATE / 'logs')
        assert actual == PYTHON
        run_logged([PYTHON, '-B', '-m', 'integration_demo.runtime', STATE,
                    STATE / 'runtime-probe.json'], 'runtime-probe', STAGE_ENV)
        return {'python': str(PYTHON), 'probe': 'passed'}

    execute_stage(STATE, 'setup', prepare_environment)

    def run_stage(name):
        if (STATE / 'stages' / (name + '.json')).exists():
            raise FileExistsError('Etapa ya iniciada; conservar intento: ' + name)
        try:
            run_logged([PYTHON, '-B', '-m', 'integration_demo.runner', name, STATE], name, STAGE_ENV)
        except BaseException:
            if read_json(STATE / 'status.json')['status'] not in ('failed', 'completed', 'partial'):
                replace_json(STATE / 'status.json', {'status': 'failed', 'failed_stage': name,
                    'error': traceback.format_exc(), 'automatic_retries': False})
            raise
    print('Entorno y probe completados; continuar con las etapas de integración.')
    ''')
    steps = [
        ('prepare', '5 · Preparar entradas portables',
         'Verifica el ZIP nativo conservado y regenera los punteros de procedencia en este entorno. No cambia cajas ni texto.'),
        ('reconcile', '6 · Conciliar los tres parsings',
         'Ejecuta el motor congelado por página. MinerU, LayoutLMv3 y Table Transformer aportan evidencia. Las geometrías inválidas conservan abstención.'),
        ('classify', '7 · Clasificación funcional v2',
         'Clasifica las unidades conciliadas; conserva categorías previas, contradicciones y referencias a la evidencia.'),
        ('capsules', '8 · Inventario y cápsulas intermedias',
         'Construye el contrato existente de inventario/cápsulas; mantiene caption primero en asociaciones utilizables y contenido compartido por referencia.'),
        ('integrate', '9 · Docling + nativo + estructura + conexión + exportación',
         'Ejecuta el pipeline canónico: baseline geométrico Docling, evidencia nativa del PDF, estructura propuesta, relaciones y recorrido. Escribe JSON, vistas, índice y colas de revisión.'),
        ('verify', '10 · Validar el nuevo intento',
         'Comprueba manifests, código, PDFs, fuentes, renders y conservación del alcance. No vuelve a ejecutar las etapas anteriores. La calidad semántica y el QA visual siguen pendientes.'),
    ]
    for stage, title, description in steps:
        cell('markdown', '## ' + title + '\n\n' + description)
        cell('code', f"run_stage({stage!r})")
    cell('markdown', '''
    ## 11 · Inspeccionar métricas y localizar los resultados

    El índice y las vistas viajarán con sus imágenes relativas en el respaldo.
    Los avisos son una cola de revisión, no un recuento de errores confirmados.
    ''')
    cell('code', '''
    terminal = read_json(STATE / 'status.json')
    print('Estado técnico:', terminal['status'])
    summary_path = STATE / 'operational/summary.json'
    if summary_path.is_file():
        summary = read_json(summary_path)
        print(json.dumps({k: summary[k] for k in (
            'papers', 'pages', 'inventory_units', 'content_appearances',
            'deferred_children', 'abstained_pages', 'sections', 'semantic_accuracy')},
            ensure_ascii=False, indent=2))
        print('Índice:', STATE / 'operational/index.html')
        print('Cola:', STATE / 'operational/review-queue.json')
        if not IS_COLAB:
            display(FileLink(os.path.relpath(STATE / 'operational/index.html', Path.cwd())))
    else:
        print('No hay salida operativa completa. Conserva el registro y respalda el intento.')
    ''')
    cell('markdown', '''
    ## Solo si interrumpiste manualmente una celda

    **Deja `CLOSE_INTERRUPTED_RUN = False` en la ejecución normal.**
    Cambiarlo a `True` cierra como parcial el intento interrumpido, después de
    confirmar que el subproceso controlado por este kernel ya terminó. No reanuda.
    No usar tras reiniciar el kernel o si hay procesos lanzados por otro medio.
    ''')
    cell('code', '''
    CLOSE_INTERRUPTED_RUN = False
    if CLOSE_INTERRUPTED_RUN:
        assert PROCESS is None or PROCESS.poll() is not None, 'Todavía hay un proceso activo.'
        status = read_json(STATE / 'status.json')
        assert status['status'] in ('running', 'prepared'), 'El intento ya tiene estado terminal.'
        replace_json(STATE / 'status.json', {'status': 'partial',
            'reason': 'User closed an interrupted attempt after controlled child termination',
            'automatic_retries': False, 'semantic_validation': 'pending_after_full_mvp'})
        print('Intento parcial cerrado; puede respaldarse.')
    else:
        print('Cierre de interrupción omitido (ejecución normal).')
    ''')
    cell('markdown', '''
    ## 12 · Respaldar, verificar y descargar

    Esta celda sirve para un intento completado, fallido o cerrado como parcial.
    Incluye etapas, fuentes consumidas, PDFs, código ejecutado, vistas y logs.
    No respalda un proceso activo. El estado fallido se conserva como tal.
    En Colab copia el ZIP, SHA256 y recibo a Drive antes de iniciar la descarga.
    Conserva `upload.zip` original como fuente de la procedencia completa del parsing.
    ''')
    cell('code', '''
    assert PROCESS is None or PROCESS.poll() is not None, 'Todavía hay un proceso activo.'
    RESULT = ATTEMPT / 'result.zip'
    receipt = make_archive(STATE, RESULT)
    assert verify_archive(RESULT, RESULT.with_suffix('.sha256')) == receipt
    receipt_path = ATTEMPT / 'backup-receipt.json'
    write_json(receipt_path, receipt)
    if USE_DRIVE:
        durable_copy(RESULT, DRIVE_RUN / RESULT.name)
        durable_copy(RESULT.with_suffix('.sha256'), DRIVE_RUN / 'result.sha256')
        durable_copy(receipt_path, DRIVE_RUN / receipt_path.name)
        assert verify_archive(DRIVE_RUN / 'result.zip', DRIVE_RUN / 'result.sha256') == receipt
        print('Respaldo Drive íntegro:', DRIVE_RUN)
    print('Estado conservado:', receipt['status'])
    print('SHA256:', receipt['sha256'])
    print('Entrega:', RESULT)
    if IS_COLAB:
        files.download(str(RESULT))
    else:
        display(FileLink(os.path.relpath(RESULT, Path.cwd())))
        display(FileLink(os.path.relpath(RESULT.with_suffix('.sha256'), Path.cwd())))
    print('Descarga y conserva el respaldo antes de cerrar el runtime.')
    ''')
    for i, c in enumerate(cells):
        c['id'] = f'integration-{i:02d}'
        c['source'] = c['source'].splitlines(keepends=True)
    notebook = dict(nbformat=4, nbformat_minor=5, metadata=dict(
        kernelspec=dict(display_name='Python 3', language='python', name='python3'),
        language_info=dict(name='python', version='3'),
        colab=dict(name='integration_structure_pipeline.ipynb', provenance=[]),
        accelerator='GPU', integration_demo=dict(target='A100', bundle_sha256=expected)), cells=cells)
    path = DEMO / 'integration_structure_pipeline.ipynb'
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Notebook:', len(cells), 'cells;', sum(c['cell_type'] == 'code' for c in cells), 'code cells')


if __name__ == '__main__':
    build_notebook()
