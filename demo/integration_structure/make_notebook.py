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
    # SiC · full integration · Jupyter / A100

    Run the cells **in order, once only, in a Linux x86_64 session with an A100**.
    In Colab, select A100 as the runtime type. There are 15 papers / 397 pages.
    The current integration uses the CPU: the A100 identifies the requested environment.

    The stages run reconciliation, classification v2, geometric Docling, native evidence,
    structure, operational integration, and export. The three parsers have already run;
    this notebook consumes their preserved results. It preserves boxes, text, scores,
    provenance, contradictions, and abstentions. The 374 children without bounding boxes remain deferred.

    `upload.zip` and `upload.sha256` from **demo/integration_structure** contain code,
    the 15 PDFs, and native outputs. Do not use the parsing demo ZIP.
    Installation needs the Internet to download the interpreter and pinned
    packages; subsequent processing uses only the included files.

    Reserve at least 16 GiB of RAM and 20 GiB of free disk space; these are recommended margins,
    not measurements from an A100 trial. Use Drive to retain the result in Colab.
    There are no retries or automatic recovery. On failure, you can back up the
    attempt without claiming that integration completed.

    The historical run reused approved caches for 12.pdf; this demo recalculates Docling
    and native evidence for all papers. Binary equality with that run is not promised.
    Technical integrity does not establish semantic accuracy or visual QA.
    ''')
    cell('markdown', '''
    ## Integration workflow

    ```mermaid
    flowchart TD
        P["Existing parsing outputs and sources"] --> C["Reconciliation: common units"]
        C --> F["Functional classification v2"]
        P --> O["Docling geometric order"]
        P --> N["Native PDF evidence"]
        F --> S["Proposed structure"]
        N --> S
        F --> I["Operational integration"]
        O --> I
        N --> I
        S --> I
        I --> R["Relations and traversal"]
        R --> E["Assemble and validate"]
        S --> E
        E --> J["JSON per paper"]
        E --> V["Views and index"]
        E --> H["Human review after_full_mvp"]
        A["Ambiguity or contradiction"] -.-> E
        A -.-> H
    ```

    The inventory/capsule helper step uses the existing reading-v1 contract.
    Docling then establishes the ordering baseline consumed by operational
    integration. Intermediate outputs are retained for inspection.
    ''')
    cell('markdown', '''
    ## 1 · Configuration and A100 check

    If you saved the files in Drive, set `INPUT_ZIP` and `INPUT_SHA` to their paths
    under `/content/drive/MyDrive/…`; Drive is mounted in the next cell.
    In regular Jupyter, leave them next to the notebook. The attempt directory will be new.
    ''')
    cell('code', '''
    from pathlib import Path
    import os, sys, json, hashlib, shutil, subprocess, platform, uuid, traceback
    from datetime import datetime, timezone
    from IPython.display import display, FileLink, HTML

    if 'ATTEMPT' in globals():
        raise RuntimeError('This kernel already has an attempt. Retain its outputs; do not restart this cell.')
    try:
        from google.colab import drive, files
        IS_COLAB = True
    except ImportError:
        IS_COLAB = False

    INPUT_ZIP = Path('upload.zip').resolve()
    INPUT_SHA = INPUT_ZIP.with_suffix('.sha256')
    USE_DRIVE = IS_COLAB
    WORK_ROOT = Path('/content') if IS_COLAB else Path.cwd() / 'integration-runs'
    assert platform.system() == 'Linux' and platform.machine() == 'x86_64', 'Linux x86_64 is required.'
    GPU = subprocess.check_output([
        'nvidia-smi', '--query-gpu=name,memory.total,driver_version',
        '--format=csv,noheader,nounits'], text=True).strip().splitlines()
    assert len(GPU) == 1 and 'A100' in GPU[0], 'Select a single A100.'
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    assert shutil.disk_usage(WORK_ROOT).free >= 20 * 1024**3, 'At least 20 GiB of free disk space is recommended.'
    ATTEMPT = WORK_ROOT / ('sic-integration-a100-' + uuid.uuid4().hex)
    ATTEMPT.mkdir(exist_ok=False)
    PAYLOAD, STATE = ATTEMPT / 'payload', ATTEMPT / 'run'
    PROCESS = None
    print('GPU / MiB / driver:', GPU[0])
    print('Attempt:', ATTEMPT)
    print('Integration computation: CPU; no model inference.')
    ''')
    cell('markdown', '''
    ## 2 · Drive and input files

    In Colab, Drive is authorized for persistent backup. Files already present
    in the panel or configured path are not uploaded again.
    ''')
    cell('code', '''
    DRIVE_RUN = None
    if USE_DRIVE:
        assert IS_COLAB, 'Automatic Drive mounting is for Colab.'
        drive.mount('/content/drive')
        DRIVE_RUN = Path('/content/drive/MyDrive/nasa-sic-integration') / ATTEMPT.name
        DRIVE_RUN.mkdir(parents=True, exist_ok=False)
        print('Persistent destination:', DRIVE_RUN)
    if not INPUT_ZIP.is_file() or not INPUT_SHA.is_file():
        if IS_COLAB:
            print('Select upload.zip and upload.sha256 from demo/integration_structure.')
            files.upload()
        assert INPUT_ZIP.is_file() and INPUT_SHA.is_file(), 'Both files must be present at the configured paths.'
    print('Inputs:', INPUT_ZIP, INPUT_SHA)
    ''')
    cell('markdown', '''
    ## 3 · Verify the entire package before extracting or importing its code

    The expected SHA256, member list, and individual hash of every file
    are checked. Extraction rejects unsafe paths, duplicates, and symlinks.
    ''')
    common = (DEMO / 'integration_demo/common.py').read_text(encoding='utf-8')
    tree = ast.parse(common)
    wanted = {'digest', 'read_json', 'write_json', 'safe_name', 'check_members', 'member_digest', 'extract_bundle'}
    bootstrap = '\n\n'.join(ast.get_source_segment(common, n) for n in tree.body
                            if isinstance(n, (ast.Import, ast.ImportFrom))
                            or isinstance(n, ast.FunctionDef) and n.name in wanted)
    cell('code', bootstrap + '\n\n' + f"EXPECTED_BUNDLE_SHA256 = {expected!r}\n" + '''
assert INPUT_SHA.read_text(encoding='ascii').strip() == EXPECTED_BUNDLE_SHA256, 'Sidecar belongs to another package.'
PACKAGE = extract_bundle(INPUT_ZIP, PAYLOAD, EXPECTED_BUNDLE_SHA256)
sys.path.insert(0, str(PAYLOAD / 'code'))  # Only after verifying all members.
from integration_demo.runner import initialize, execute_stage, replace_json
from integration_demo.common import make_archive, verify_archive, durable_copy
initialize(PAYLOAD, STATE, GPU)
print('Package integrity verified:', len(PACKAGE['files']), 'files and manifest.')
print('15 PDFs + native results included; sources copied to a new attempt.')
''')
    cell('markdown', '''
    ## 4 · Isolated environment and real geometric ordering probe

    Python **3.13.5** and exact dependencies are installed within the attempt,
    without changing the kernel. Commands and errors are saved in `run/logs/`.
    The Docling postprocessor hash must match the preserved baseline.
    A failure leaves the attempt recorded; proceed to the backup cell to retain it.
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
            raise RuntimeError(f'Command failed ({returncode}); see {log_path}. Do not retry.')

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
            raise FileExistsError('Stage already started; retain attempt: ' + name)
        try:
            run_logged([PYTHON, '-B', '-m', 'integration_demo.runner', name, STATE], name, STAGE_ENV)
        except BaseException:
            if read_json(STATE / 'status.json')['status'] not in ('failed', 'completed', 'partial'):
                replace_json(STATE / 'status.json', {'status': 'failed', 'failed_stage': name,
                    'error': traceback.format_exc(), 'automatic_retries': False})
            raise
    print('Environment and probe completed; continue with the integration stages.')
    ''')
    steps = [
        ('prepare', '5 · Prepare portable inputs',
         'Verifies the preserved native ZIP and regenerates provenance pointers in this environment. Boxes and text remain unchanged.'),
        ('reconcile', '6 · Reconcile the three parsing outputs',
         'Runs the frozen engine per page. MinerU, LayoutLMv3, and Table Transformer provide evidence. Invalid geometries retain abstention.'),
        ('classify', '7 · Functional classification v2',
         'Classifies reconciled units; preserves previous categories, contradictions, and evidence references.'),
        ('capsules', '8 · Intermediate inventory and capsules',
         'Builds the existing inventory/capsule contract; keeps captions first in usable associations and shares content by reference.'),
        ('integrate', '9 · Docling + native + structure + integration + export',
         'Runs the canonical pipeline: Docling geometric baseline, native PDF evidence, proposed structure, relations, and traversal. Writes JSON, views, index, and review queues.'),
        ('verify', '10 · Validate the new attempt',
         'Checks manifests, code, PDFs, sources, renders, and scope preservation. Does not rerun previous stages. Semantic quality and visual QA remain pending.'),
    ]
    for stage, title, description in steps:
        cell('markdown', '## ' + title + '\n\n' + description)
        cell('code', f"run_stage({stage!r})")
    cell('markdown', '''
    ## 11 · Inspect metrics and locate results

    The index and views travel with their relative images in the backup.
    Warnings form a review queue, not a count of confirmed errors.
    ''')
    cell('code', '''
    terminal = read_json(STATE / 'status.json')
    print('Technical status:', terminal['status'])
    summary_path = STATE / 'operational/summary.json'
    if summary_path.is_file():
        summary = read_json(summary_path)
        print(json.dumps({k: summary[k] for k in (
            'papers', 'pages', 'inventory_units', 'content_appearances',
            'deferred_children', 'abstained_pages', 'sections', 'semantic_accuracy')},
            ensure_ascii=False, indent=2))
        print('Index:', STATE / 'operational/index.html')
        print('Queue:', STATE / 'operational/review-queue.json')
        if not IS_COLAB:
            display(FileLink(os.path.relpath(STATE / 'operational/index.html', Path.cwd())))
    else:
        print('There is no complete operational output. Retain the log and back up the attempt.')
    ''')
    cell('markdown', '''
    ## Only if you manually interrupted a cell

    **Leave `CLOSE_INTERRUPTED_RUN = False` during normal execution.**
    Setting it to `True` closes the interrupted attempt as partial, after
    confirming that the subprocess controlled by this kernel has terminated. It does not resume.
    Do not use after restarting the kernel or if processes were launched through another mechanism.
    ''')
    cell('code', '''
    CLOSE_INTERRUPTED_RUN = False
    if CLOSE_INTERRUPTED_RUN:
        assert PROCESS is None or PROCESS.poll() is not None, 'A process is still active.'
        status = read_json(STATE / 'status.json')
        assert status['status'] in ('running', 'prepared'), 'The attempt already has a terminal status.'
        replace_json(STATE / 'status.json', {'status': 'partial',
            'reason': 'User closed an interrupted attempt after controlled child termination',
            'automatic_retries': False, 'semantic_validation': 'pending_after_full_mvp'})
        print('Partial attempt closed; it can be backed up.')
    else:
        print('Interruption closure skipped (normal execution).')
    ''')
    cell('markdown', '''
    ## 12 · Back up, verify, and download

    This cell supports a completed, failed, or closed partial attempt.
    It includes stages, consumed sources, PDFs, executed code, views, and logs.
    It does not back up an active process. Failed status is preserved as such.
    In Colab, it copies the ZIP, SHA256, and receipt to Drive before starting the download.
    Retain the original `upload.zip` as the source of complete parsing provenance.
    ''')
    cell('code', '''
    assert PROCESS is None or PROCESS.poll() is not None, 'A process is still active.'
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
        print('Drive backup integrity verified:', DRIVE_RUN)
    print('Preserved status:', receipt['status'])
    print('SHA256:', receipt['sha256'])
    print('Delivery:', RESULT)
    if IS_COLAB:
        files.download(str(RESULT))
    else:
        display(FileLink(os.path.relpath(RESULT, Path.cwd())))
        display(FileLink(os.path.relpath(RESULT.with_suffix('.sha256'), Path.cwd())))
    print('Download and retain the backup before closing the runtime.')
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
