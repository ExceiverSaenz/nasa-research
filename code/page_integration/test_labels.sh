#!/usr/bin/env bash
# USER-ONLY launcher: never creates/stops sessions or retries OCR.
set -euo pipefail
cd "$(dirname "$0")/../.."
SESSION="${1:?Uso: bash code/page_integration/test_labels.sh SESION_T4_EXISTENTE}"
PACKAGE="code/packages/localized-labels-v1"
python3 - "$PACKAGE" <<'PY'
import hashlib,json,sys,zipfile
from pathlib import Path
p=Path(sys.argv[1]);bundle=p/'upload.zip'
assert hashlib.sha256(bundle.read_bytes()).hexdigest()==(p/'upload.sha256').read_text().strip(), 'Paquete modificado'
with zipfile.ZipFile(bundle) as z:
    manifest=json.loads(z.read('bundle-manifest.json'))
    for name,spec in manifest['files'].items():
        raw=z.read(name)
        assert len(raw)==spec['bytes'] and hashlib.sha256(raw).hexdigest()==spec['sha256'],name
        if name.startswith(('page_integration/','mineru_probe/')):
            assert raw==(Path('code')/name).read_bytes(),'Codigo diferente del paquete: '+name
print('Paquete verificado sin OCR.')
PY
colab status -s "$SESSION"
RUN_DIR="code/results/localized-labels-v1/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "code/results/localized-labels-v1"
mkdir "$RUN_DIR"
colab upload -s "$SESSION" "$PACKAGE/upload.zip" /content/nasa-localized-labels-v1-upload.zip
colab upload -s "$SESSION" "$PACKAGE/upload.sha256" /content/nasa-localized-labels-v1-upload.sha256
set +e
colab exec -s "$SESSION" --timeout 1800 2>&1 <<'PY' | tee "$RUN_DIR/cli-console.log"
import runpy
import sys

# Colab executes inside IPython, whose sys.argv contains kernel arguments.
# Give our entrypoint its own arguments, leaving the kernel's argv intact.
previous_argv = sys.argv[:]
previous_path = sys.path[:]
try:
    sys.argv = ['localized-labels-user-run']
    sys.path.insert(0, '/content/nasa-localized-labels-v1-upload.zip')
    runpy.run_module('page_integration.remote_labels', run_name='__main__')
    print('LOCALIZED_LABELS_COMPLETED', flush=True)
finally:
    sys.argv = previous_argv
    sys.path[:] = previous_path
PY
REMOTE_CODE=${PIPESTATUS[0]}
set -e
if [ "$REMOTE_CODE" -ne 0 ]; then
    echo "Error/timeout. No repetir: un timeout no demuestra que termino el proceso."
    echo "Conservar la sesion y revisar antes de descargar el respaldo remoto."
    echo "Registro local: $RUN_DIR/cli-console.log"
    exit "$REMOTE_CODE"
fi
if ! grep -qx 'LOCALIZED_LABELS_COMPLETED' "$RUN_DIR/cli-console.log"; then
    echo "El kernel no confirmo finalizacion. No descargar ni repetir automaticamente."
    echo "Revisar el error en $RUN_DIR/cli-console.log"
    exit 1
fi
colab download -s "$SESSION" /content/nasa-localized-labels-v1.zip "$RUN_DIR/result.zip"
colab download -s "$SESSION" /content/nasa-localized-labels-v1.sha256 "$RUN_DIR/result.sha256"
python3 - "$RUN_DIR" <<'PY'
import hashlib,json,sys,zipfile
from pathlib import Path
p=Path(sys.argv[1]);archive=p/'result.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==(p/'result.sha256').read_text().strip(), 'Hash del respaldo incorrecto'
with zipfile.ZipFile(archive) as z:
    status=json.loads(z.read('execution-status.json'))
    assert status['status']=='completed',status
print('Respaldo descargado y verificado:',p)
print('OCR finalizado; recuperacion y vinculos pendientes de evaluar. Sesion sin cerrar.')
PY
